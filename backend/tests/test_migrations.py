import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.database.migrations import migration_config
from app.database.session import build_engine


def test_migrations_upgrade_downgrade_and_model_constraints(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}")
    config = migration_config()
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        tables = set(inspect(connection).get_table_names())
        assert {
            "platforms",
            "automation_steps",
            "executions",
            "execution_events",
            "audit_events",
            "reference_images",
        } <= tables
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO users (id, username, password_hash, role, active, created_at, login_attempts) VALUES ('bad','bad','hash','invalid',1,CURRENT_TIMESTAMP,0)"
                )
            )
        connection.rollback()
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
        command.upgrade(config, "head")
        assert "reference_images" in inspect(connection).get_table_names()
    engine.dispose()


def test_configured_sqlite_directory_and_foreign_keys(tmp_path):
    target = tmp_path / "custom" / "nested" / "db.sqlite"
    engine = build_engine(f"sqlite:///{target.as_posix()}")
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    assert target.parent.is_dir()
    engine.dispose()


def test_platform_deletion_migration_preserves_existing_history(tmp_path):
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from app.models import Execution, ExecutionEvent, Platform, User
    from app.schemas import AutomationInput, PlatformInput, RequestInput
    from app.services.platforms import create_automation, save_platform, validate_automation
    from app.services.provisioning import create_request
    from app.worker import run_once

    engine = build_engine(f"sqlite:///{(tmp_path / 'history.db').as_posix()}")
    config = migration_config()
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        user = User(username="migration-admin", password_hash="test-placeholder", role="admin")
        db.add(user)
        db.commit()
        target = save_platform(db, PlatformInput(name="Existing destination"), user)
        definition = create_automation(
            db,
            target["id"],
            AutomationInput(
                name="Existing flow",
                steps=[{"action": "assert", "locator": "#status", "success_condition": "OK"}],
            ),
            user,
        )
        validate_automation(db, definition["id"], user)
        request, _ = create_request(
            db,
            RequestInput(
                employee={
                    "name": "Test Person",
                    "email": "person@example.invalid",
                    "department": "QA",
                    "employee_id": "01",
                },
                targets=[{"platform_id": target["id"]}],
            ),
            "migration-test-request",
            user,
        )
    assert run_once(factory)
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0003_concurrency")
        command.upgrade(config, "head")
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    with factory() as db:
        assert db.get(Platform, target["id"]).name == "Existing destination"
        execution = db.scalar(select(Execution).where(Execution.request_id == request.id))
        assert execution.status == "succeeded"
        assert db.scalar(select(ExecutionEvent).where(ExecutionEvent.execution_id == execution.id))
    engine.dispose()
