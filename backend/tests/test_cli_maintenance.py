import sqlite3
import sys

from alembic import command
from sqlalchemy import inspect, text

from app import cli
from app.database.migrations import migration_config
from app.database.session import build_engine


def old_database(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    config = migration_config()
    config.set_main_option(
        "sqlalchemy.url", f"sqlite:///{(tmp_path / 'old.db').as_posix()}".replace("%", "%%")
    )
    command.upgrade(config, "0003_concurrency")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO platforms (id,name,description,active,mode,config,created_at) VALUES ('pilot','Existing pilot','',1,'simulation','{}',CURRENT_TIMESTAMP)"
            )
        )
    return engine, config


def test_backup_accepts_schema_waiting_for_migration(tmp_path):
    engine, _ = old_database(tmp_path)
    backup = cli.backup_database(engine)
    with sqlite3.connect(backup) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0003_concurrency"
        )
        assert connection.execute("SELECT name FROM platforms").fetchone()[0] == "Existing pilot"
    assert "deleted_at" not in {
        column["name"] for column in inspect(engine).get_columns("platforms")
    }
    engine.dispose()


def test_cli_migrate_backs_up_before_upgrade_and_preserves_data(tmp_path, monkeypatch):
    engine, config = old_database(tmp_path)
    monkeypatch.setattr(cli, "engine", engine)
    monkeypatch.setattr(cli, "migration_config", lambda: config)
    monkeypatch.setattr(sys, "argv", ["cli", "migrate"])
    cli.main()
    backups = list((tmp_path / "backups").glob("*/automation_platform.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0003_concurrency"
        )
    assert "deleted_at" in {column["name"] for column in inspect(engine).get_columns("platforms")}
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT name FROM platforms WHERE id='pilot'"))
            == "Existing pilot"
        )
    cli.main()
    assert len(list((tmp_path / "backups").glob("*/automation_platform.db"))) == 1
    engine.dispose()
