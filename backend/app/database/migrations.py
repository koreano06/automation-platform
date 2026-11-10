from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.config import PROJECT_ROOT
from app.database.session import engine


def migration_config():
    return Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))


def check_schema(db_engine=engine):
    if "alembic_version" not in inspect(db_engine).get_table_names():
        raise RuntimeError("Banco sem migrações. Execute: python -m app.cli migrate")
    with db_engine.connect() as connection:
        if (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            != ScriptDirectory.from_config(migration_config()).get_current_head()
        ):
            raise RuntimeError("Schema incompatível. Faça backup e execute as migrações.")
