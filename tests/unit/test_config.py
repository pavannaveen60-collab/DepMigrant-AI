from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings as AppSettings


def test_database_url_defaults_to_existing_workspace_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)

    config = AppSettings(_env_file=None)

    assert make_url(config.database_url).database == str(
        Path.home() / "DepMigrant AI" / "depmigrant.db"
    )


def test_database_url_defaults_to_temporary_path_on_render(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RENDER", "true")

    config = AppSettings(_env_file=None)

    assert config.database_url == "sqlite:////tmp/depmigrant.db"


def test_database_url_environment_override_uses_temporary_database(monkeypatch, tmp_path):
    monkeypatch.setenv("RENDER", "true")
    test_database = tmp_path / "test.db"
    database_url = f"sqlite:///{test_database}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = AppSettings(_env_file=None)

    assert config.database_url == database_url
    engine = create_engine(config.database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE configuration_test (value TEXT)"))
            connection.execute(
                text("INSERT INTO configuration_test (value) VALUES ('temporary')")
            )
            result = connection.execute(
                text("SELECT value FROM configuration_test")
            ).scalar_one()
        assert result == "temporary"
        assert test_database.exists()
    finally:
        engine.dispose()


def test_sqlite_parent_directory_is_created_without_creating_database(tmp_path):
    from app.db.session import _ensure_sqlite_parent

    database_path = tmp_path / "nested" / "depmigrant.db"

    _ensure_sqlite_parent(f"sqlite:///{database_path}")

    assert database_path.parent.is_dir()
    assert not database_path.exists()


def test_init_db_loads_models_and_creates_tables_in_configured_engine(
    monkeypatch, tmp_path
):
    from sqlalchemy import inspect

    from app.db import session

    engine = create_engine(f"sqlite:///{tmp_path / 'startup.db'}")
    monkeypatch.setattr(session, "engine", engine)

    try:
        session.init_db()

        assert {
            "repositories",
            "migration_plans",
            "migration_jobs",
            "model_interactions",
        } <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
