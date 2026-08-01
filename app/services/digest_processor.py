import sys
from pathlib import Path

# Ensure root folder is accessible for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.digest_agent import DigestAgent
from app.database.repository import Repository


class DigestProcessor:
    """
    Runner service that processes raw scraped papers in PostgreSQL
    and generates structured digest records in the 'digests' database table.
    """
    def __init__(self):
        self.repo = Repository()
        self.agent = DigestAgent()

    def process_all_papers(self, limit: int = None) -> dict:
        """
        Loops through papers in PostgreSQL lacking a digest entry,
        invokes DigestAgent, and persists records in the digests table.
        """
        unprocessed_papers = self.repo.get_unprocessed_papers(limit=limit)
        total_count = len(unprocessed_papers)
        print(f"\n[DigestProcessor] Found {total_count} unprocessed research papers requiring digest generation.")

        stats = {"processed": 0, "skipped": 0, "failed": 0}

        for idx, paper in enumerate(unprocessed_papers, start=1):
            try:
                print(f"\n[DigestProcessor] [{idx}/{total_count}] Processing Paper (ID: {paper.id} | Source: {paper.source_system.upper()} | Ref: {paper.source_id})")
                print(f"   Original Title: '{paper.title[:80]}...'")
                
                digest_out = self.agent.generate_digest(
                    title=paper.title,
                    abstract=paper.abstract or "",
                    full_markdown=paper.transcript_markdown
                )

                self.repo.insert_digest(
                    paper_id=paper.id,
                    article_type=paper.source_system,
                    article_id=paper.source_id,
                    url=paper.pdf_url,
                    title=digest_out.title,
                    summary=digest_out.summary,
                    article_published_at=paper.published_date
                )

                stats["processed"] += 1
                print(f"   ✅ Saved Digest Title: '{digest_out.title}'")

            except Exception as e:
                stats["failed"] += 1
                print(f"   ❌ [DigestProcessor Error] Failed processing paper ID {paper.id}: {e}")

        print(f"\n[DigestProcessor] Batch run finished. Summary stats: {stats}")
        return stats


if __name__ == "__main__":
    processor = DigestProcessor()
    processor.process_all_papers()
