import os
import sys
from pathlib import Path

# Ensure root folder is in sys.path
root_dir = str(Path(__file__).parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.database.create_tables import create_all_tables

def initialize_database():
    """
    Safely initializes PostgreSQL database schema and enables pgvector extension.
    """
    print("🚀 Initializing database tables and verifying pgvector extension...")
    create_all_tables()
    print("✅ Database initialization complete.")

if __name__ == "__main__":
    initialize_database()
