import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from .models import Base

DEFAULT_DB_FILE = Path(__file__).resolve().parents[2] / "data" / "knowledge.sqlite"


def make_session_factory(database_url: str | None = None):
    if database_url is None:
        database_url = os.getenv("MODERATOR_KNOWLEDGE_DB_URL")

    if not database_url :
        DEFAULT_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+pysqlite:///{DEFAULT_DB_FILE}"



    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread":False if database_url.startswith("sqlite") else {}
            
        }

    )
    
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


