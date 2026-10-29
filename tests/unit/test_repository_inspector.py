import tarfile
import zipfile

import pytest

from app.services import repository_inspector
from app.services.repository_inspector import (
    RepositoryInspector,
    clone_repository,
    extract_archive,
)


def test_inspector_parses_supported_dependency_manifests_without_resolving_versions(tmp_path):
    repo_path = tmp_path / "manifest-repo"
    repo_path.mkdir()
    (repo_path / "requirements.txt").write_text("requests==2.31.0\n")
    (repo_path / "pyproject.toml").write_text(
        """
[project]
dependencies = ["httpx>=0.27.0"]

[project.optional-dependencies]
test = ["pytest~=8.0"]

[tool.poetry.dependencies]
python = "^3.11"
rich = { version = "^13.7.0" }
"""
    )

    inspection = RepositoryInspector(str(repo_path)).inspect()

    assert inspection["dependencies"]["requirements_txt"] == ["requests==2.31.0"]
    assert inspection["dependencies"]["pyproject_toml"]["dependencies"] == [
        "httpx>=0.27.0"
    ]


def test_inspector_discovers_nested_requirements_without_scanning_auxiliary_directories(tmp_path):
    repo_path = tmp_path / "nested-requirements-repo"
    backend_path = repo_path / "backend"
    backend_path.mkdir(parents=True)
    (backend_path / "requirements.txt").write_text(
        "fastapi>=0.109\n"
        "uvicorn[standard]>=0.27\n"
        "pydantic>=2.5\n"
        "razorpay\n"
        "python-dotenv>=1.0\n"
    )
    for excluded_directory in (
        "backend/.venv",
        "backend/vendor",
        "node_modules",
        "tests",
        "docs",
    ):
        excluded_path = repo_path / excluded_directory
        excluded_path.mkdir(parents=True)
        (excluded_path / "requirements.txt").write_text("not-a-project-dependency\n")

    inspection = RepositoryInspector(str(repo_path)).inspect()

    assert inspection["dependencies"]["requirements_txt"] == [
        "fastapi>=0.109",
        "uvicorn[standard]>=0.27",
        "pydantic>=2.5",
        "razorpay",
        "python-dotenv>=1.0",
    ]


def test_setup_py_parses_literal_required_and_optional_dependencies(tmp_path):
    repo_path = tmp_path / "setup-py-repo"
    repo_path.mkdir()
    (repo_path / "setup.py").write_text(
        """
from setuptools import setup

install_requires = ["urllib3<3,>=1.21.1", "certifi>=2017.4.17"]
extras = {"security": ["idna>=2.5"], "tests": ("pytest>=7",)}

setup(
    install_requires=install_requires,
    extras_require=extras,
)
"""
    )

    inspection = RepositoryInspector(str(repo_path)).inspect()
    dependencies = inspection["dependencies"]

    assert dependencies["setup_py"] == str(repo_path / "setup.py")
    assert dependencies["setup_py_dependencies"] == {
        "dependencies": ["urllib3<3,>=1.21.1", "certifi>=2017.4.17"],
        "optional_dependencies": {
            "security": ["idna>=2.5"],
            "tests": ["pytest>=7"],
        },
    }
    assert dependencies["setup_py_dependencies"]["dependencies"] == [
        "urllib3<3,>=1.21.1",
        "certifi>=2017.4.17",
    ]
    assert dependencies["setup_py_dependencies"]["optional_dependencies"]["security"] == [
        "idna>=2.5"
    ]


def test_setup_py_ignores_dynamic_dependency_expressions(tmp_path):
    repo_path = tmp_path / "dynamic-setup-py-repo"
    repo_path.mkdir()
    marker = repo_path / "executed.txt"
    (repo_path / "setup.py").write_text(
        f"""
from setuptools import setup

setup(
    install_requires=read_requirements(),
    extras_require={{"test": load_extras()}},
)
open({str(marker)!r}, "w").write("executed")
"""
    )

    inspection = RepositoryInspector(str(repo_path)).inspect()

    assert inspection["dependencies"]["setup_py_dependencies"] == {
        "dependencies": [],
        "optional_dependencies": {},
    }
    assert not marker.exists()


def test_zip_extraction_rejects_parent_traversal_and_cleans_partial_output(tmp_path):
    archive_path = tmp_path / "malicious.zip"
    output_root = tmp_path / "repositories"
    escaped_file = tmp_path / "outside.txt"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", "not extracted")

    with pytest.raises(ValueError, match="unsafe path"):
        extract_archive(str(archive_path), str(output_root))

    assert not escaped_file.exists()
    assert list(output_root.iterdir()) == []


def test_tar_extraction_rejects_links(tmp_path):
    archive_path = tmp_path / "malicious.tar"
    output_root = tmp_path / "repositories"
    with tarfile.open(archive_path, "w") as archive:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive.addfile(link)

    with pytest.raises(ValueError, match="unsupported entry"):
        extract_archive(str(archive_path), str(output_root))

    assert list(output_root.iterdir()) == []


def test_archive_extraction_does_not_overwrite_existing_files(tmp_path):
    archive_path = tmp_path / "project.zip"
    output_root = tmp_path / "repositories"
    output_root.mkdir()
    existing = output_root / "project"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("keep")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("module.py", "print('safe')")

    extracted = extract_archive(str(archive_path), str(output_root))

    assert (repository_inspector.Path(extracted) / "module.py").read_text() == "print('safe')"
    assert sentinel.read_text() == "keep"


def test_clone_uses_unique_destination_without_deleting_existing_data(tmp_path, monkeypatch):
    destination_root = tmp_path / "repositories"
    destination_root.mkdir()
    existing = destination_root / "repo"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("keep")

    def fake_clone(url, destination, branch):
        repository_inspector.Path(destination, "cloned.txt").write_text(f"{url}:{branch}")

    monkeypatch.setattr(repository_inspector.Repo, "clone_from", fake_clone)
    first = clone_repository("https://example.test/repo.git", str(destination_root), "main")
    second = clone_repository("https://example.test/repo.git", str(destination_root), "main")

    assert first != second
    assert sentinel.read_text() == "keep"
    assert (repository_inspector.Path(first) / "cloned.txt").exists()
