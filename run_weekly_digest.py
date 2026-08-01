import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is in python path
root_dir = str(Path(__file__).parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

load_dotenv(override=True)

from app.services.pipeline_runner import WeeklyPipelineRunner

def main():
    """
    Main entry point for running the weekly AI Research Paper Digest pipeline.
    Suitable for weekly cron jobs, Windows Task Scheduler, or manual execution.
    """
    my_email = os.getenv("MY_EMAIL")
    if not my_email:
        print("❌ Error: MY_EMAIL is not set in your .env file.")
        print("Please configure MY_EMAIL and APP_PASSWORD in .env before running.")
        sys.exit(1)

    runner = WeeklyPipelineRunner()
    results = runner.run(
        user_email=my_email,
        topic="Machine Learning",
        user_name="Khushi",
        top_n=3,
        time_range="1 week",
        fetch_limit=5
    )

    print(f"\nWeekly Pipeline Summary Results: {results}")

if __name__ == "__main__":
    main()
