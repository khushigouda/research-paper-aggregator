import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is in python path
root_dir = str(Path(__file__).parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

from app.services.orchestrator import PipelineOrchestrator
from app.services.digest_processor import DigestProcessor
from app.services.curator_service import CuratorService
from app.services.email_service import send_email, digest_to_html
from app.agent.email_agent import EmailAgent
from app.database.repository import Repository
from app.models import UserProfile, EmailArticleItem, EmailDigestPayload


class WeeklyPipelineRunner:
    """
    Unified Weekly Pipeline Runner connecting all stages of the research paper aggregator:
    1. Ingestion: Fetch fresh papers from ArXiv, PubMed, and IEEE Xplore -> save to PostgreSQL.
    2. Processing: Generate 5-part student-friendly structured digests via DigestAgent.
    3. Curation: Score (0-100) and rank Top N candidate papers matching UserProfile & Topic.
    4. Email Dispatch: Format payload with EmailAgent, render minimal HTML, and send via SMTP.
    """
    def __init__(self):
        self.repo = Repository()
        self.orchestrator = PipelineOrchestrator()
        self.processor = DigestProcessor()
        self.curator_service = CuratorService()
        self.email_agent = EmailAgent()

    def run(self, user_email: str = None, topic: str = "Machine Learning", user_name: str = "Khushi", top_n: int = 3, time_range: str = "1 week", fetch_limit: int = 5) -> dict:
        if not user_email:
            user_email = os.getenv("MY_EMAIL")
            if not user_email:
                raise ValueError("MY_EMAIL is not set in environment or .env file.")

        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info(f"Starting Weekly AI Research Paper Digest Pipeline")
        logger.info(f"Subscriber: {user_name} ({user_email}) | Topic: '{topic}'")
        logger.info("=" * 60)

        results = {
            "start_time": start_time.isoformat(),
            "scraping": {},
            "processing": {},
            "curation": {},
            "email": {},
            "success": False
        }

        try:
            # ----------------------------------------------------
            # STEP 1: SCRAPE & INGEST ARTICLES FROM SOURCES
            # ----------------------------------------------------
            logger.info("\n[1/4] Scraping fresh research papers from sources...")
            fetch_stats = self.orchestrator.run_pipeline(
                query=topic,
                time_range=time_range,
                per_source_limit=fetch_limit
            )
            results["scraping"] = fetch_stats
            logger.info(f"✓ Ingested papers: ArXiv ({fetch_stats.get('arxiv', 0)}), "
                        f"PubMed ({fetch_stats.get('pubmed', 0)}), "
                        f"IEEE ({fetch_stats.get('ieee', 0)})")

            # ----------------------------------------------------
            # STEP 2: GENERATE STRUCTURED DIGEST SUMMARIES
            # ----------------------------------------------------
            logger.info("\n[2/4] Generating structured student-friendly paper digests...")
            digest_stats = self.processor.process_all_papers()
            results["processing"] = digest_stats
            logger.info(f"✓ Processed {digest_stats.get('processed', 0)} paper digests "
                        f"({digest_stats.get('failed', 0)} failed)")

            # ----------------------------------------------------
            # STEP 3: CURATE & RANK TOP N PAPERS FOR SUBSCRIBER
            # ----------------------------------------------------
            logger.info(f"\n[3/4] Scoring and ranking Top {top_n} papers for {user_name}...")
            profile = UserProfile(email=user_email, full_name=user_name)
            top_articles: list[EmailArticleItem] = self.curator_service.get_curated_top_digests(
                user_profile=profile,
                topic=topic,
                top_n=top_n
            )
            results["curation"] = {
                "curated_count": len(top_articles),
                "top_n": top_n
            }
            logger.info(f"✓ Selected Top {len(top_articles)} curated papers for {user_email}")

            if not top_articles:
                logger.warning(f"⚠️ No candidate papers available for topic '{topic}'. Pipeline finished.")
                results["email"] = {"sent": False, "reason": "No articles curated"}
                return results

            # ----------------------------------------------------
            # STEP 4: GENERATE & SEND EMAIL DIGEST
            # ----------------------------------------------------
            logger.info("\n[4/4] Generating and sending personalized email digest...")
            payload: EmailDigestPayload = self.email_agent.generate_email(
                user_profile=profile,
                topic=topic,
                articles=top_articles
            )

            # Render minimal HTML template
            html_body = digest_to_html(payload)
            payload.html_body = html_body

            # Dispatch via SMTP
            send_email(
                subject=payload.subject,
                body_text=payload.body_markdown or payload.intro_summary,
                body_html=html_body,
                recipients=[user_email]
            )
            results["email"] = {
                "sent": True,
                "recipient": user_email,
                "subject": payload.subject,
                "articles_count": len(top_articles)
            }
            logger.info(f"✓ Email digest sent successfully to {user_email}")
            logger.info(f"  Subject: '{payload.subject}'")

            # Mark papers as sent in database to guarantee zero duplicate dispatches
            for article in top_articles:
                self.repo.mark_paper_as_sent(
                    email=user_email,
                    source_system=article.source_system.lower(),
                    source_id=article.source_id
                )
            results["success"] = True

        except Exception as e:
            logger.error(f"✗ Pipeline failed with error: {e}", exc_info=True)
            results["error"] = str(e)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = duration

        logger.info("\n" + "=" * 60)
        logger.info("Weekly Pipeline Summary")
        logger.info("=" * 60)
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info(f"Scraped: {results['scraping']}")
        logger.info(f"Processed: {results['processing']}")
        logger.info(f"Curated: {results['curation']}")
        logger.info(f"Email: {'Sent successfully' if results['success'] else 'Failed'}")
        logger.info("=" * 60)

        return results


def run_weekly_pipeline(topic: str = "Machine Learning", user_name: str = "Khushi", user_email: str = None, top_n: int = 3) -> dict:
    runner = WeeklyPipelineRunner()
    return runner.run(user_email=user_email, topic=topic, user_name=user_name, top_n=top_n)


if __name__ == "__main__":
    runner = WeeklyPipelineRunner()
    target_email = os.getenv("MY_EMAIL")
    res = runner.run(
        user_email=target_email,
        topic="Machine Learning",
        user_name="Khushi",
        top_n=3
    )
    sys.exit(0 if res.get("success") else 1)
