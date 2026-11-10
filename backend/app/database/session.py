from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import PROJECT_ROOT, settings


def build_engine(database_url: str):
    url = make_url(database_url)
    options = {}
    if url.get_backend_name() == "sqlite":
        if url.database and url.database != ":memory:":
            path = Path(url.database).expanduser()
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(path.resolve()))
        options["connect_args"] = {"check_same_thread": False, "timeout": 10}
        if not url.database or url.database == ":memory:":
            options["poolclass"] = StaticPool
    db_engine = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":

        @event.listens_for(db_engine, "connect")
        def sqlite_pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return db_engine


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
