import os
from sqlalchemy import create_engine

database_url = os.getenv("OPENX_DB_URL") or "sqlite:///./.data/openx.db"
engine = create_engine(database_url, echo=True)