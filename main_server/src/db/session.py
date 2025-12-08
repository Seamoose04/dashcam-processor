from __future__ import annotations

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.utils.settings import settings

_engine = create_engine(settings.database_url, future=True)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session():
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
