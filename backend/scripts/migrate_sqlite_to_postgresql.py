import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401


def normalized_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def copy_database(source_url: str, target_url: str) -> None:
    if make_url(normalized_url(source_url)).get_backend_name() != "sqlite":
        raise ValueError("SOURCE_DATABASE_URL must point to SQLite")
    if make_url(normalized_url(target_url)).get_backend_name() != "postgresql":
        raise ValueError("TARGET_DATABASE_URL must point to PostgreSQL")

    source = create_engine(
        normalized_url(source_url),
        connect_args={"check_same_thread": False},
    )
    target = create_engine(normalized_url(target_url), pool_pre_ping=True)
    Base.metadata.create_all(target)

    source_inspector = inspect(source)
    table_names = source_inspector.get_table_names()
    if not table_names:
        raise RuntimeError("The SQLite database contains no tables")

    target_metadata = MetaData()
    target_metadata.reflect(bind=target)
    source_metadata = MetaData()
    source_metadata.reflect(bind=source)

    with Session(source) as source_session, Session(target) as target_session:
        priority_tables = ["retreats", "users"]
        tables_to_copy = [source_metadata.tables[name] for name in priority_tables if name in source_metadata.tables]
        tables_to_copy.extend(
            table for table in source_metadata.sorted_tables if table.name not in priority_tables
        )
        for table in tables_to_copy:
            if table.name not in target_metadata.tables or not table.primary_key.columns:
                continue
            rows = source_session.execute(table.select()).mappings().all()
            if not rows:
                continue
            rows = [dict(row) for row in rows]
            target_table = target_metadata.tables[table.name]
            statement = postgres_insert(target_table).values(rows)
            statement = statement.on_conflict_do_nothing(
                index_elements=list(target_table.primary_key.columns)
            )
            target_session.execute(statement)

        target_session.commit()

        for table_name, table in target_metadata.tables.items():
            primary_keys = list(table.primary_key.columns)
            if len(primary_keys) != 1:
                continue
            primary_key = primary_keys[0]
            sequence_name = target_session.scalar(
                text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                {"table_name": table_name, "column_name": primary_key.name},
            )
            if not sequence_name:
                continue
            maximum = target_session.scalar(text(f'SELECT COALESCE(MAX("{primary_key.name}"), 0) FROM "{table_name}"'))
            target_session.execute(
                text("SELECT setval(:sequence_name, :maximum, :has_rows)"),
                {
                    "sequence_name": sequence_name,
                    "maximum": max(maximum or 1, 1),
                    "has_rows": bool(maximum),
                },
            )
        target_session.commit()


if __name__ == "__main__":
    source_url = os.getenv("SOURCE_DATABASE_URL", "sqlite:///./retunori.db")
    target_url = os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    if not target_url:
        raise SystemExit("Set TARGET_DATABASE_URL or DATABASE_URL to the PostgreSQL URL")
    copy_database(source_url, target_url)
    print("SQLite data copied to PostgreSQL.")
