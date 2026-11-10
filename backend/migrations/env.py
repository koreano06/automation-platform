from alembic import context

from app.core.config import settings
from app.database.base import Base
from app.database.session import build_engine
from app import models  # noqa: F401

config = context.config
target_metadata = Base.metadata


def run(connection):
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
    if sqlite:
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("A migração produziu referências inconsistentes.")


if context.is_offline_mode():
    context.configure(
        url=config.get_main_option("sqlalchemy.url") or settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        run(supplied)
    else:
        engine = build_engine(config.get_main_option("sqlalchemy.url") or settings.database_url)
        with engine.connect() as connection:
            run(connection)
        engine.dispose()
