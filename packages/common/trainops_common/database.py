from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from trainops_domain.models import Base

from trainops_common.settings import get_settings


def make_engine(url: str | None = None):
    settings = get_settings()
    database_url = url or settings.database_url
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    connect_args = {"check_same_thread": False, "timeout": 30} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_all_for_local_tests() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
