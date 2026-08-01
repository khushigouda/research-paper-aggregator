import sys
from pathlib import Path

# Tell Python to look at the project root directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, timedelta, timezone
from typing import Optional
from app.scrapers.arxiv import ArXivScraper
from app.scrapers.pubmed import PubMedScraper
from app.scrapers.ieee import IEEEScraper
from app.database.repository import Repository

class PipelineOrchestrator:
    def __init__(self):
        self.repo = Repository()
        self.arxiv = ArXivScraper()
        self.pubmed = PubMedScraper()
        self.ieee = IEEEScraper()

    def _calculate_start_date(self, time_range: str) -> datetime:
        """
        Translates human-readable UI dropdown values into an absolute calendar cutoff date.
        """
        now = datetime.now(timezone.utc)
        clean_range = time_range.lower().strip()

        if "month" in clean_range:
            # Assumes 1 month or specific count e.g., '3 months'
            months = int([s for s in clean_range.split() if s.isdigit()][0]) if any(s.isdigit() for s in clean_range) else 1
            return now - timedelta(days=30 * months)
        elif "year" in clean_range:
            years = int([s for s in clean_range.split() if s.isdigit()][0]) if any(s.isdigit() for s in clean_range) else 1
            return now - timedelta(days=365 * years)
        elif "week" in clean_range:
            weeks = int([s for s in clean_range.split() if s.isdigit()][0]) if any(s.isdigit() for s in clean_range) else 1
            return now - timedelta(weeks=weeks)
        
        # Default fallback to 1 month ago if input is unreadable
        return now - timedelta(days=30)

    def run_pipeline(self, query: str, time_range: str, per_source_limit: int = 5) -> dict:
        """
        Executes the entire intake engine end-to-end for a given user configuration.
        """
        since_date = self._calculate_start_date(time_range)
        date_bound_str = since_date.strftime("%Y-%m-%d")
        
        print(f"[Orchestrator] Initiating ingest for loop. Topic: '{query}' | Range: '{time_range}' (Since {date_bound_str})")
        
        summary_stats = {"arxiv": 0, "pubmed": 0, "ieee": 0}

        # 1. Gather & Save ArXiv
        try:
            arxiv_papers = self.arxiv.fetch_papers(query=query, limit=per_source_limit)
            # Filter out older results if the API returned broad items
            filtered_arxiv = [p for p in arxiv_papers if p.published_date >= since_date]
            self.repo.insert_papers(filtered_arxiv)
            summary_stats["arxiv"] = len(filtered_arxiv)
            print(f"[Ingest] Saved {len(filtered_arxiv)} fresh papers from arXiv.")
        except Exception as e:
            print(f"[Error] ArXiv ingestion branch failed: {e}")

        # 2. Gather & Save PubMed
        try:
            pubmed_papers = self.pubmed.fetch_papers(query=query, limit=per_source_limit, since_date=since_date)
            self.repo.insert_papers(pubmed_papers)
            summary_stats["pubmed"] = len(pubmed_papers)
            print(f"[Ingest] Saved {len(pubmed_papers)} fresh papers from PubMed.")
        except Exception as e:
            print(f"[Error] PubMed ingestion branch failed: {e}")

        # 3. Gather & Save IEEE
        try:
            ieee_papers = self.ieee.fetch_papers(query=query, limit=per_source_limit)
            filtered_ieee = [p for p in ieee_papers if p.published_date >= since_date]
            self.repo.insert_papers(filtered_ieee)
            summary_stats["ieee"] = len(filtered_ieee)
            print(f"[Ingest] Saved {len(filtered_ieee)} fresh papers from IEEE Xplore.")
        except Exception as e:
            print(f"[Error] IEEE ingestion branch failed: {e}")

        return summary_stats

if __name__ == "__main__":
    # Test execution simulating a user setting up a "1 year" target window on "Quantum Computing"
    engine = PipelineOrchestrator()
    results = engine.run_pipeline(query="Quantum Computing", time_range="1 year", per_source_limit=3)
    print(f"\nPipeline run completed successfully. Ingested profiles: {results}")