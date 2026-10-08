import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Railway provides the PostgreSQL connection string through DATABASE_URL. -H
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")


# Railway PostgreSQL URLs normally begin with postgresql://.
# SQLAlchemy needs the psycopg driver specified explicitly. -H
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


# Create the shared SQLAlchemy database engine. -H
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# Creates database sessions used by FastAPI routes and services. -H
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# Provides a database session and closes it automatically
# after the request is finished. -H
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()