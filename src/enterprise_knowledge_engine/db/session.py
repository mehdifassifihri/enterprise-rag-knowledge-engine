from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=5,
        pool_timeout=5,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
        hide_parameters=True,
    )


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_session)]
