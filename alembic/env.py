import os
from logging.config import fileConfig

from dotenv import load_dotenv
load_dotenv()  # Loads .env from the current working directory

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models so their tables are registered on Base.metadata.
# Alembic autogenerate compares Base.metadata against the live DB —
# any model not imported here will be invisible to it.
from app.models import Base  # noqa: F401

config = context.config

# Use LOCAL_DATABASE_URL when running Alembic from the host machine (localhost:5433).
# Fall back to DATABASE_URL when running inside the Docker api container (db:5432).
database_url = os.environ.get("LOCAL_DATABASE_URL") or os.environ["DATABASE_URL"]
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
