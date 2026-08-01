import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(override=True)

from app.models import Base

def reset_database():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    engine = create_engine(DATABASE_URL)

    confirm = input("⚠️ WARNING: This will drop all tables and delete all data! Type 'yes' to proceed: ")
    if confirm.lower() == 'yes':
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("✅ Database reset successfully.")
    else:
        print("Aborted.")

if __name__ == "__main__":
    reset_database()