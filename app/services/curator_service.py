import sys
from pathlib import Path
from typing import List, Dict

# Ensure root folder is accessible for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.curator_agent import CuratorAgent, CuratedItem
from app.database.repository import Repository
from app.models import UserProfile, EmailArticleItem
from app.services.digest_processor import DigestProcessor
from app.services.orchestrator import PipelineOrchestrator


class CuratorService:
    """
    Service that orchestrates paper digest curation:
    1. Fetches candidate digests matching user interests.
    2. Runs scrapers + DigestProcessor if candidate pool is empty.
    3. Invokes CuratorAgent to score (0-100) and rank papers against UserProfile.
    4. Returns Top N curated paper digests as Pydantic EmailArticleItem models.
    """
    def __init__(self):
        self.repo = Repository()
        self.curator_agent = CuratorAgent()
        self.orchestrator = PipelineOrchestrator()
        self.processor = DigestProcessor()

    def get_curated_top_digests(self, user_profile: UserProfile, topic: str, top_n: int = 3) -> List[EmailArticleItem]:
        """
        Retrieves candidate digests, runs CuratorAgent evaluation, and returns top_n items as EmailArticleItem models.
        """
        print(f"\n[CuratorService] Initiating paper curation for: {user_profile.email}")
        print(f"[CuratorService] Target Topic: '{topic}' | Requested Top N: {top_n}")

        # Step 1: Fetch candidate pool from PostgreSQL
        candidates = self.repo.get_weekly_candidate_digests(email=user_profile.email, topic=topic, limit=10)

        # Step 2: Scraping + Digest Generation Fallback if candidates are missing/insufficient
        if not candidates or len(candidates) < top_n:
            print(f"[CuratorService] Candidate pool has {len(candidates)} items. Ingesting fresh papers from scrapers...")
            self.orchestrator.run_pipeline(query=topic, time_range="1 week", per_source_limit=5)
            self.processor.process_all_papers()
            candidates = self.repo.get_weekly_candidate_digests(email=user_profile.email, topic=topic, limit=10)

        if not candidates:
            print(f"⚠️ [CuratorService] Exhausted all available candidate papers for topic '{topic}'.")
            return []

        # Step 3: Run CuratorAgent ranking & scoring
        print(f"[CuratorService] Submitting {len(candidates)} candidates to CuratorAgent for LLM scoring & ranking...")
        ranked_items: List[CuratedItem] = self.curator_agent.rank_digests(
            user_profile=user_profile,
            candidate_digests=candidates,
            top_n=top_n
        )

        # Step 4: Merge ranking scores and reasoning into EmailArticleItem Pydantic models
        candidates_by_id = {c["digest_id"]: c for c in candidates}
        final_top_list: List[EmailArticleItem] = []

        for item in ranked_items:
            orig = candidates_by_id.get(item.digest_id, {})
            pub_date = str(orig.get("published_date")) if orig.get("published_date") else None
            article_model = EmailArticleItem(
                digest_id=item.digest_id,
                paper_id=item.paper_id or orig.get("paper_id"),
                source_system=orig.get("article_type", "arxiv").upper(),
                source_id=orig.get("article_id", ""),
                url=orig.get("url", ""),
                title=item.title or orig.get("title", ""),
                summary=orig.get("summary", ""),
                relevance_score=item.relevance_score,
                reasoning=item.reasoning,
                published_date=pub_date
            )
            final_top_list.append(article_model)

        print(f"✅ [CuratorService] Successfully curated Top {len(final_top_list)} papers for {user_profile.email}.")
        return final_top_list


if __name__ == "__main__":
    service = CuratorService()
    profile = UserProfile(email="curator_test@example.com")
    top_papers = service.get_curated_top_digests(user_profile=profile, topic="Machine Learning", top_n=3)

    print("\n" + "=" * 60)
    print(f"🏆 TOP {len(top_papers)} CURATED PAPERS FOR: {profile.email}")
    print("=" * 60)
    for idx, paper in enumerate(top_papers, start=1):
        print(f"\n[{idx}] {paper['title']}")
        print(f"    Score: {paper['relevance_score']}/100")
        print(f"    Curator Reasoning: {paper['reasoning']}")
