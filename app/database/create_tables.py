import sys
from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Ensure the root folder is accessible for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from app.models import Base

def create_all_tables():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        DATABASE_URL = db_url
    else:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    print("Connecting to database via SQLAlchemy...")
    engine = create_engine(DATABASE_URL)
    
    try:
        # Ensure the pgvector extension is enabled globally
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            
        # SQLAlchemy reads the metadata inside models.py and applies it
        Base.metadata.create_all(engine)

        # Ensure newly added columns exist on pre-existing tables
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE digests ADD COLUMN IF NOT EXISTS article_published_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("UPDATE digests SET article_published_at = papers.published_date FROM papers WHERE digests.paper_id = papers.id AND digests.article_published_at IS NULL;"))
            conn.commit()

        print("✅ [Success] All SQLAlchemy tables and columns initialized cleanly.")
    except Exception as e:
        print(f"[Error] Failed to build tables: {e}")

if __name__ == "__main__":
    create_all_tables()