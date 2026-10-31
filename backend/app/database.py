from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_compatibility() -> None:
    """Small forward-compatible migration for new optional source-link audit fields."""
    tables = set(inspect(engine).get_table_names())
    if "source_records" not in tables:
        return
    columns = {column["name"] for column in inspect(engine).get_columns("source_records")}
    with engine.begin() as connection:
        if "link_status" not in columns:
            connection.execute(text("ALTER TABLE source_records ADD COLUMN link_status VARCHAR(40) NOT NULL DEFAULT 'unchecked'"))
        if "link_checked_at" not in columns:
            connection.execute(text("ALTER TABLE source_records ADD COLUMN link_checked_at DATETIME NULL"))
    experience_tables = set(inspect(engine).get_table_names())
    if "experiences" in experience_tables:
        experience_columns = {column["name"] for column in inspect(engine).get_columns("experiences")}
        with engine.begin() as connection:
            if "original_raw_text" not in experience_columns:
                connection.execute(text("ALTER TABLE experiences ADD COLUMN original_raw_text TEXT NOT NULL DEFAULT ''"))
            if "author_visibility" not in experience_columns:
                connection.execute(text("ALTER TABLE experiences ADD COLUMN author_visibility VARCHAR(40) NOT NULL DEFAULT 'anonymous'"))
