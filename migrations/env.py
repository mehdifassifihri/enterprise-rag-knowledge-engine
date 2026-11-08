from alembic import context

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.db import models  # noqa: F401
from enterprise_knowledge_engine.db.base import Base
from enterprise_knowledge_engine.db.session import build_engine

settings = Settings()
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=str(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
