import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.session import build_engine, get_db
from app.main import create_app
from app.models import User
from app.security import hash_password

PASSWORD = "Test-only-passphrase-123"


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def factory(tmp_path, password_hash, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "artifacts_dir", tmp_path / "artifacts")
    engine = build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        db.add_all(
            [
                User(id="admin-id", username="admin", password_hash=password_hash, role="admin"),
                User(
                    id="operator-id",
                    username="operator",
                    password_hash=password_hash,
                    role="operator",
                ),
                User(id="other-id", username="other", password_hash=password_hash, role="operator"),
            ]
        )
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def app(factory):
    app = create_app(verify_schema=False)

    def sessions():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = sessions
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def sign_in(client, username="admin"):
    response = client.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def admin(client):
    return sign_in(client)


@pytest.fixture
def operator(app):
    with TestClient(app) as client:
        yield sign_in(client, "operator")
