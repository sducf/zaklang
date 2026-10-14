import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database.models import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Alembic compares the database against the SQLAlchemy models. -H
target_metadata = Base.metadata


# Railway provides the PostgreSQL connection through DATABASE_URL. -H
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured. Set DATABASE_URL before running Alembic."
    )

# Railway PostgreSQL URLs begin with postgresql://.
# SQLAlchemy uses the psycopg driver explicitly. -H
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

# Alembic treats % specially in configuration values,
# so escaped URL characters must be preserved safely. -H
config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL.replace("%", "%%"),
)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()