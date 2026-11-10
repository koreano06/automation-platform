import threading
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.version import BUILD_ID
from app.database.session import SessionLocal
from app.models import WorkerHeartbeat
from app.models.domain import utcnow


class WorkerPulse:
    def __init__(self, factory=SessionLocal):
        self.factory, self.id = factory, str(uuid4())
        self.job_id, self.job_kind = None, None
        self.stop_event = threading.Event()
        self.thread = None

    def beat(self):
        with self.factory() as db:
            row = db.get(WorkerHeartbeat, self.id)
            if not row:
                row = WorkerHeartbeat(id=self.id, version=settings.app_version, build_id=BUILD_ID)
                db.add(row)
            row.last_seen, row.job_id, row.job_kind = utcnow(), self.job_id, self.job_kind
            db.commit()

    def loop(self):
        while not self.stop_event.wait(2):
            try:
                self.beat()
            except SQLAlchemyError:
                pass

    def start(self):
        self.beat()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        with self.factory() as db:
            row = db.get(WorkerHeartbeat, self.id)
            if row:
                row.last_seen = utcnow() - timedelta(minutes=1)
                row.job_id, row.job_kind = None, None
                db.commit()


def live_worker_jobs(db):
    return set(
        db.scalars(
            select(WorkerHeartbeat.job_id).where(
                WorkerHeartbeat.last_seen >= utcnow() - timedelta(seconds=15),
                WorkerHeartbeat.job_id.is_not(None),
            )
        )
    )
