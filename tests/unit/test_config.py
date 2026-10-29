from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings as AppSettings


def test_database_url_defaults_to_existing_workspace_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    config = AppSettings(_env_file=None)

    assert make_url(config.database_url).database == str(
        Path.home() / "DepMigrant AI" / "depmigrant.db"
    )


def test_database_url_environment_override_uses_temporary_database(monkeypatch, tmp_path):
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
