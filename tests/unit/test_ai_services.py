import asyncio
import json

import pytest

from app.services.failure_diagnoser import FailureDiagnoser
from app.services.migration_planner import (
    InvalidPlannerResponseError,
    MigrationPlanner,
)
from app.services.nebius_client import (
    NebiusClient,
    ProviderConfigurationError,
    ProviderResponseError,
)
from app.services.sandbox import CommandResult
from app.core.config import settings


def test_nebius_client_sends_configured_bearer_token_without_network(monkeypatch):
    client = NebiusClient()
    client.api_key = "unit-test-key"
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    async def fake_post(url, headers, json):
        captured["authorization"] = headers["Authorization"]
        return FakeResponse()

    monkeypatch.setattr(client.client, "post", fake_post)
    try:
        result = asyncio.run(client.chat_completion([{"role": "user", "content": "hello"}]))
    finally:
        asyncio.run(client.close())

    assert result["content"] == "ok"
    assert captured["authorization"] == "Bearer unit-test-key"


def test_nebius_client_uses_nebius_configuration_and_chat_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "nebius_api_key", "nebius-unit-test-key")
    monkeypatch.setattr(settings, "nebius_base_url", "https://nebius.example.test/v1/")
    monkeypatch.setattr(settings, "nebius_model", "test/nebius-model")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "nim-unit-test-key")

    client = NebiusClient()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    async def fake_post(url, headers, json):
        captured["url"] = url
        captured["authorization"] = headers["Authorization"]
        captured["model"] = json["model"]
        return FakeResponse()

    monkeypatch.setattr(client.client, "post", fake_post)
    try:
        asyncio.run(client.chat_completion([{"role": "user", "content": "hello"}]))
    finally:
        asyncio.run(client.close())

    assert client.provider == "nebius"
    assert captured["url"] == "https://nebius.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer nebius-unit-test-key"
    assert captured["model"] == "test/nebius-model"


def test_nebius_client_uses_extended_read_timeout():
    client = NebiusClient()
    try:
        assert client.client.timeout.connect == 10.0
        assert client.client.timeout.read == 180.0
        assert client.client.timeout.write == 30.0
        assert client.client.timeout.pool == 10.0
    finally:
        asyncio.run(client.close())


@pytest.mark.parametrize("configured_key", [None, ""])
def test_nebius_client_rejects_missing_or_empty_keys_without_request(
    monkeypatch, configured_key
):
    monkeypatch.setattr(settings, "nebius_api_key", configured_key)
    monkeypatch.setattr(settings, "nvidia_nim_api_key", None)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)

    client = NebiusClient()
    request_sent = False

    async def fail_if_called(*args, **kwargs):
        nonlocal request_sent
        request_sent = True
        raise AssertionError("request must not be sent without a configured key")

    monkeypatch.setattr(client.client, "post", fail_if_called)
    try:
        with pytest.raises(
            ProviderConfigurationError,
            match="Configure NEBIUS_API_KEY or NVIDIA_NIM_API_KEY",
        ):
            asyncio.run(client.chat_completion([{"role": "user", "content": "hello"}]))
    finally:
        asyncio.run(client.close())

    assert not request_sent


def test_nebius_client_rejects_malformed_provider_chat_response(monkeypatch):
    client = NebiusClient()
    client.api_key = "test-key"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    async def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(client.client, "post", fake_post)
    try:
        with pytest.raises(
            ProviderResponseError, match="invalid chat completion response"
        ):
            asyncio.run(
                client.chat_completion([{"role": "user", "content": "test"}])
            )
    finally:
        asyncio.run(client.close())


def test_nebius_client_supports_nvidia_nim_configuration(monkeypatch):
    monkeypatch.setattr(settings, "nebius_api_key", None)
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "nim-unit-test-key")
    monkeypatch.setattr(settings, "nvidia_nim_base_url", "https://nim.example.test/v1/")
    monkeypatch.setattr(settings, "nvidia_nim_model", "test/model")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    client = NebiusClient()
    try:
        assert client.provider == "nvidia_nim"
        assert client.api_key == "nim-unit-test-key"
        assert client.base_url == "https://nim.example.test/v1"
        assert client.model == "test/model"
    finally:
        asyncio.run(client.close())


def test_migration_planner_does_not_convert_model_failure_to_empty_plan(monkeypatch):
    planner = MigrationPlanner()

    async def failed_completion(messages):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(planner.client, "chat_completion", failed_completion)

    with pytest.raises(RuntimeError, match="model unavailable"):
        asyncio.run(planner._analyze_breaking_changes("test context"))


def test_migration_planner_reports_invalid_mocked_json_response(monkeypatch):
    planner = MigrationPlanner()

    async def invalid_completion(messages):
        return {"content": '[{"type": "behavior_change",}]'}

    monkeypatch.setattr(planner.client, "chat_completion", invalid_completion)

    with pytest.raises(
        InvalidPlannerResponseError,
        match="expected exactly one complete JSON array",
    ):
        asyncio.run(planner._analyze_breaking_changes("test context"))


def test_migration_planner_retries_malformed_breaking_changes_response(monkeypatch):
    planner = MigrationPlanner()
    responses = iter(
        [
            {"content": '[{"type": "behavior_change",}]'},
            {"content": json.dumps([_valid_planner_item("breaking changes")])},
        ]
    )
    captured_messages = []

    async def fake_completion(messages):
        captured_messages.append(messages)
        return next(responses)

    monkeypatch.setattr(planner.client, "chat_completion", fake_completion)

    result = asyncio.run(planner._analyze_breaking_changes("test context"))

    assert result == [_valid_planner_item("breaking changes")]
    assert len(captured_messages) == 2
    corrective_prompt = captured_messages[1][-1]["content"]
    assert "did not pass strict validation" in corrective_prompt
    assert '"severity": "low|medium|high|critical"' in corrective_prompt
    assert '"source": "changelog|documentation|inference"' in corrective_prompt


def test_migration_planner_fails_after_invalid_breaking_changes_retry(monkeypatch):
    planner = MigrationPlanner()
    call_count = 0

    async def invalid_completion(messages):
        nonlocal call_count
        call_count += 1
        return {"content": '[{"type": "behavior_change",}]'}

    monkeypatch.setattr(planner.client, "chat_completion", invalid_completion)

    with pytest.raises(
        InvalidPlannerResponseError,
        match="after one corrective retry.*JSON-only instructions",
    ):
        asyncio.run(planner._analyze_breaking_changes("test context"))
    assert call_count == 2


def _valid_planner_item(stage):
    return {
        "breaking changes": {
            "type": "behavior_change",
            "description": "A documented behavior may differ.",
            "severity": "medium",
            "source": "inference",
        },
        "affected files": {
            "path": "src/client.py",
            "reason": "Uses the affected API.",
            "estimated_changes": 1,
        },
        "planned edits": {
            "file_path": "src/client.py",
            "original_code": "old_call()",
            "new_code": "new_call()",
            "description": "Update the API call.",
        },
    }[stage]


async def _call_planner_stage(planner, stage):
    if stage == "breaking changes":
        return await planner._analyze_breaking_changes("context")
    if stage == "affected files":
        return await planner._identify_affected_files("context", [])
    return await planner._generate_edits(
        "context",
        [],
        [{"path": "src/client.py", "reason": "uses dependency", "estimated_changes": 1}],
    )


@pytest.mark.parametrize(
    ("stage", "wrapper"),
    [
        (stage, wrapper)
        for stage in ("breaking changes", "affected files", "planned edits")
        for wrapper in ("plain", "fenced", "surrounded")
    ],
)
def test_migration_planner_parses_supported_json_array_presentations(
    monkeypatch, stage, wrapper
):
    item = _valid_planner_item(stage)
    encoded = json.dumps([item])
    if wrapper == "fenced":
        content = f"```json\n{encoded}\n```"
    elif wrapper == "surrounded":
        content = f"Planning output follows:\n{encoded}\nEnd of response."
    else:
        content = encoded

    planner = MigrationPlanner()

    async def fake_completion(messages):
        return {"content": content}

    monkeypatch.setattr(planner.client, "chat_completion", fake_completion)

    assert asyncio.run(_call_planner_stage(planner, stage)) == [item]


@pytest.mark.parametrize(
    ("stage", "content", "message"),
    [
        (stage, content, message)
        for stage in ("breaking changes", "affected files", "planned edits")
        for content, message in (
            ("[{broken json]", "expected exactly one complete JSON array"),
            ('{"items": []}', "expected exactly one complete JSON array"),
            ("[{}]", "missing required fields"),
        )
    ],
)
def test_migration_planner_rejects_invalid_stage_responses(
    monkeypatch, stage, content, message
):
    planner = MigrationPlanner()

    async def fake_completion(messages):
        return {"content": content}

    monkeypatch.setattr(planner.client, "chat_completion", fake_completion)

    with pytest.raises(InvalidPlannerResponseError, match=message):
        asyncio.run(_call_planner_stage(planner, stage))


@pytest.mark.parametrize(
    ("stage", "item"),
    [
        ("breaking changes", {**_valid_planner_item("breaking changes"), "severity": 1}),
        ("breaking changes", {**_valid_planner_item("breaking changes"), "source": "made_up"}),
        ("affected files", {**_valid_planner_item("affected files"), "estimated_changes": True}),
        ("affected files", {**_valid_planner_item("affected files"), "path": "../outside.py"}),
        ("planned edits", {**_valid_planner_item("planned edits"), "file_path": "/outside.py"}),
        ("planned edits", {**_valid_planner_item("planned edits"), "extra": "not allowed"}),
    ],
)
def test_migration_planner_rejects_wrong_types_enums_and_unsafe_paths(
    monkeypatch, stage, item
):
    planner = MigrationPlanner()

    async def fake_completion(messages):
        return {"content": json.dumps([item])}

    monkeypatch.setattr(planner.client, "chat_completion", fake_completion)

    with pytest.raises(InvalidPlannerResponseError):
        asyncio.run(_call_planner_stage(planner, stage))


def test_migration_planner_rejects_oversized_response():
    with pytest.raises(InvalidPlannerResponseError, match="oversized"):
        MigrationPlanner._parse_json_array(
            " " * (MigrationPlanner.MAX_MODEL_RESPONSE_CHARS + 1),
            "breaking changes",
        )


def test_migration_planner_bounds_optional_dependency_prompt_context():
    planner = MigrationPlanner()
    inspection = {
        "name": "temporary-repo",
        "files": [f"module_{index}.py" for index in range(25)],
        "dependencies": {
            "pyproject_toml": {
                "dependencies": ["requests>=2.0"],
                "optional_dependencies": {
                    f"extra-{index}": ["package>=1.0"]
                    for index in range(15)
                },
            },
            "setup_py_dependencies": {
                "dependencies": ["urllib3>=2.0"],
                "optional_dependencies": {},
            },
        },
    }

    context = planner._build_context(
        inspection, "requests", "3.0", "2.0"
    )

    assert "[extra-0]" in context
    assert "[extra-9]" in context
    assert "[extra-10]" not in context
    assert "5 optional groups omitted" in context
    assert "setup.py: urllib3>=2.0" in context
    assert "module_19.py" in context
    assert "module_20.py" not in context


def test_failure_diagnoser_does_not_read_source_outside_repository(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("sensitive source")
    failure = CommandResult(
        command="pytest",
        exit_code=1,
        stdout=f"Failure in ../{outside_file.name}",
        stderr="",
        duration_ms=1,
        args=["pytest"],
    )

    context = FailureDiagnoser()._get_source_context(failure, {"path": str(repository)})

    assert context["file_contents"] == {}


def test_migration_planner_parses_response_with_think_tags_and_citations():
    planner = MigrationPlanner()
    item = _valid_planner_item("breaking changes")
    content = f"""<think>
Examining version upgrade for requests from 2.28.0 to 2.31.0.
Detected dependencies: ["requests", "click"]
Candidate changes: [1]
</think>
```json
{json.dumps([item], indent=2)}
```
References:
[1] https://github.com/psf/requests/releases/tag/v2.31.0
"""
    result = planner._parse_json_array(content, "breaking changes")
    assert result == [item]


def test_migration_planner_parses_plain_array_with_trailing_citations():
    planner = MigrationPlanner()
    item = _valid_planner_item("breaking changes")
    content = f"""Here are the breaking changes:
{json.dumps([item], indent=2)}

Notes:
[1] Recommended verification check.
"""
    result = planner._parse_json_array(content, "breaking changes")
    assert result == [item]


def test_migration_planner_retries_malformed_affected_files_response(monkeypatch):
    planner = MigrationPlanner()
    item = _valid_planner_item("affected files")
    responses = iter(
        [
            {"content": '[{"path": "src/client.py",}]'},
            {"content": json.dumps([item])},
        ]
    )
    captured = []

    async def fake_completion(messages):
        captured.append(messages)
        return next(responses)

    monkeypatch.setattr(planner.client, "chat_completion", fake_completion)

    result = asyncio.run(planner._identify_affected_files("test context", []))
    assert result == [item]
    assert len(captured) == 2
    assert "did not pass strict validation" in captured[1][-1]["content"]


def test_migration_planner_retries_malformed_planned_edits_response(monkeypatch):
    planner = MigrationPlanner()
    item = _valid_planner_item("planned edits")
    responses = iter(
        [
            {"content": '[{"file_path": "src/client.py",}]'},
            {"content": json.dumps([item])},
        ]
    )
    captured = []

    async def fake_completion(messages):
        captured.append(messages)
        return next(responses)

    monkeypatch.setattr(planner.client, "chat_completion", fake_completion)

    result = asyncio.run(
        planner._generate_edits(
            "test context",
            [],
            [{"path": "src/client.py", "reason": "uses api", "estimated_changes": 1}],
        )
    )
    assert result == [item]
    assert len(captured) == 2
    assert "did not pass strict validation" in captured[1][-1]["content"]

