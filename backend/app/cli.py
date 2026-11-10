import argparse
import getpass
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select

from app.database.migrations import check_schema, migration_config
from app.database.session import SessionLocal, engine
from app.models import AuthSession, Platform, User
from app.schemas import AutomationInput, FieldInput, PlatformConfig, PlatformInput, StepInput
from app.security import create_user, hash_password
from app.services.platforms import create_automation, save_platform, validate_automation


def backup_database(db_engine):
    """Back up the current SQLite schema, including versions awaiting migration."""
    if (
        db_engine.url.get_backend_name() != "sqlite"
        or not db_engine.url.database
        or db_engine.url.database == ":memory:"
    ):
        raise SystemExit("O backup deste comando está disponível apenas para SQLite em arquivo.")
    destination = (
        Path(db_engine.url.database).parent
        / "backups"
        / f"automation_{datetime.now():%Y%m%d_%H%M%S_%f}"
    )
    destination.mkdir(parents=True)
    path = destination / "automation_platform.db"
    with sqlite3.connect(db_engine.url.database) as source, sqlite3.connect(path) as target:
        source.backup(target)
        from app.core.config import settings

        has_references = target.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_images'"
        ).fetchone()
        references = (
            target.execute("SELECT id FROM reference_images").fetchall() if has_references else []
        )
        image_directory = destination / "reference-images"
        image_directory.mkdir()
        for (image_id,) in references:
            image_path = settings.assets_dir / f"{image_id}.png"
            if not image_path.is_file():
                raise SystemExit("Backup incompleto: uma imagem de referência não foi encontrada.")
            shutil.copy2(image_path, image_directory / f"{image_id}.png")
    return path


def seed_demo(db, admin):
    for name, fail in [("Portal de Treinamento", False), ("Diretório de Teste", True)]:
        if db.scalar(select(Platform).where(Platform.name == name, Platform.deleted_at.is_(None))):
            continue
        platform = save_platform(
            db,
            PlatformInput(
                name=name,
                description="Piloto fictício: nenhuma conta externa é criada.",
                config=PlatformConfig(simulate_failure=fail),
                fields=[
                    FieldInput(
                        key="profile",
                        label="Perfil",
                        field_type="select",
                        options=["Colaborador", "Gestor"],
                    )
                ],
            ),
            admin,
        )
        automation = create_automation(
            db,
            platform["id"],
            AutomationInput(
                name="Cadastro de colaborador",
                steps=[
                    StepInput(action="open_page", value="https://pilot.invalid/users/new"),
                    StepInput(action="fill", locator="#name", data_ref="employee.name"),
                    StepInput(action="fill", locator="#email", data_ref="employee.email"),
                    StepInput(action="fill", locator="#profile", data_ref="platform.profile"),
                    StepInput(action="click", locator="button[type=submit]"),
                    StepInput(
                        action="assert",
                        locator="[role=status]",
                        success_condition="Cadastro concluído",
                    ),
                ],
            ),
            admin,
        )
        validate_automation(db, automation["id"], admin)


def main():
    parser = argparse.ArgumentParser(description="Administração local da Automation Platform")
    parser.add_argument(
        "command", choices=["migrate", "create-admin", "reset-password", "seed-demo", "backup"]
    )
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    if args.command == "migrate":
        tables = set(inspect(engine).get_table_names())
        if tables and "alembic_version" not in tables:
            raise SystemExit(
                "Banco legado detectado. Faça backup e use um banco novo; não foi sobrescrito."
            )
        config = migration_config()
        with engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
        if tables and revision != ScriptDirectory.from_config(config).get_current_head():
            print(f"Backup antes da atualização: {backup_database(engine)}")
        command.upgrade(config, "head")
        print("Migrações aplicadas.")
        return
    if args.command == "backup":
        print(f"Backup criado em: {backup_database(engine)}")
        return
    check_schema()
    with SessionLocal() as db:
        if args.command in {"create-admin", "reset-password"}:
            username = args.username.strip().lower()
            existing = db.scalar(select(User).where(User.username == username))
            if args.command == "create-admin" and existing:
                raise SystemExit("Usuário já existe.")
            if args.command == "reset-password" and not existing:
                raise SystemExit("Usuário não encontrado.")
            password = getpass.getpass("Senha (mínimo 12 caracteres): ")
            confirmation = getpass.getpass("Confirme a senha: ")
            if password != confirmation or len(password) < 12:
                raise SystemExit("As senhas devem coincidir e ter pelo menos 12 caracteres.")
            if existing:
                existing.password_hash = hash_password(password)
                existing.login_attempts = 0
                existing.locked_until = None
                from sqlalchemy import delete

                db.execute(delete(AuthSession).where(AuthSession.user_id == existing.id))
            else:
                create_user(db, username, password, "admin")
            db.commit()
            print("Credencial salva. A senha não é exibida nem gravada em texto puro.")
        else:
            admin = db.scalar(select(User).where(User.role == "admin", User.active.is_(True)))
            if not admin:
                raise SystemExit("Crie um administrador primeiro.")
            seed_demo(db, admin)
            print("Plataformas fictícias preparadas.")


if __name__ == "__main__":
    main()
