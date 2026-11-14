"""Engine and session factory. `configure()` is called once by the app factory (and by tests)."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal: sessionmaker | None = None


def configure(url: str):
    global engine, SessionLocal
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores ON DELETE CASCADE unless asked
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    return engine


def get_session():
    with SessionLocal() as s:
        yield s
