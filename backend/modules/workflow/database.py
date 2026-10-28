"""M3 owns its SQLite DB; no other major-module models are registered here."""
import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base

DEFAULT_FILE = Path(__file__).resolve().parents[2] / 'data' / 'workflow.sqlite'


def make_session_factory(database_url: str | None = None):
    url = database_url or os.getenv('MODERATOR_WORKFLOW_DB_URL')
    if not url:
        DEFAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
        url = f'sqlite+pysqlite:///{DEFAULT_FILE}'
    engine = create_engine(
        url,
        connect_args={'check_same_thread': False} if url.startswith('sqlite') else {},
    )
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def enable_foreign_keys(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)