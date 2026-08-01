import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, func, tuple_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

# Ensure root folder is accessible for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from app.models import Base, Paper, SentEmail, UserSubscription, Digest
from app.agent.digest_agent import DigestAgent


class Repository:
    def __init__(self):
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
        
        # Initialize the SQLAlchemy Engine and Session factory
        self.engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.agent = DigestAgent()

    def init_db(self) -> None:
        """
        Reads models.py and creates missing tables (papers, user_subscriptions, sent_emails, digests)
        in PostgreSQL without affecting existing tables or data.
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            print("✅ Database tables initialized successfully.")
        except Exception as e:
            print(f"[Database Error] Failed to initialize tables: {e}")

    def insert_papers(self, papers_list) -> None:
        """
        Inserts a list of Pydantic paper objects (ArXiv, PubMed, IEEE) into the database.
        Generates 1536-dim vector embeddings for paper title + abstract upon insertion.
        Uses PostgreSQL 'ON CONFLICT DO NOTHING' to prevent duplicate entries.
        """
        if not papers_list:
            return

        session = self.SessionLocal()
        try:
            for p in papers_list:
                # Generate embedding if missing
                embedding_vector = getattr(p, "embedding", None)
                if not embedding_vector:
                    embed_text = f"Title: {p.title} | Abstract: {p.abstract or ''}"
                    embedding_vector = self.agent.generate_embedding(embed_text)

                paper_dict = {
                    "source_system": p.source_system,
                    "source_id": p.source_id,
                    "title": p.title,
                    "abstract": p.abstract,
                    "authors": p.authors,
                    "published_date": p.published_date,
                    "pdf_url": p.pdf_url,
                    "transcript_markdown": getattr(p, "transcript_markdown", None),
                    "embedding": embedding_vector,
                }

                stmt = insert(Paper).values(**paper_dict)
                stmt = stmt.on_conflict_do_nothing(
                    constraint="uix_source_system_id"
                )
                session.execute(stmt)
            
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[Database Error] Failed during bulk paper insert operation: {e}")
            raise e
        finally:
            session.close()

    def get_unprocessed_papers(self, limit: Optional[int] = None) -> list[Paper]:
        """
        Returns a list of Paper records from the database that do NOT yet have
        a corresponding record in the 'digests' table.
        """
        session = self.SessionLocal()
        try:
            processed_subquery = session.query(
                Digest.article_type,
                Digest.article_id
            )
            query = session.query(Paper).filter(
                tuple_(Paper.source_system, Paper.source_id).notin_(processed_subquery)
            ).order_by(Paper.id.asc())

            if limit:
                query = query.limit(limit)

            return query.all()
        except Exception as e:
            print(f"[Database Error] Failed to fetch unprocessed papers: {e}")
            return []
        finally:
            session.close()

    def insert_digest(self, paper_id: Optional[int], article_type: str, article_id: str, url: Optional[str], title: str, summary: str, article_published_at: Optional[datetime] = None) -> None:
        """
        Inserts a structured digest record into the 'digests' database table,
        recording the original publication date of the paper.
        """
        session = self.SessionLocal()
        try:
            stmt = insert(Digest).values(
                paper_id=paper_id,
                article_type=article_type,
                article_id=article_id,
                url=url,
                title=title,
                summary=summary,
                article_published_at=article_published_at
            )
            stmt = stmt.on_conflict_do_nothing(constraint="uix_digest_article")
            session.execute(stmt)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[Database Error] Failed to insert digest: {e}")
        finally:
            session.close()

    def get_weekly_candidate_digests(self, email: str, topic: str, limit: int = 10) -> list[dict]:
        """
        Fetches a pool of unsent candidate paper digests matching the user's topic vector
        from the past 7 days based on the paper's original publication date (article_published_at),
        returning candidate dicts for CuratorAgent evaluation.
        """
        session = self.SessionLocal()
        try:
            sent_subquery = session.query(
                SentEmail.paper_source_system, 
                SentEmail.paper_source_id
            ).filter(SentEmail.user_email == email)

            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            topic_vector = self.agent.generate_embedding(topic)

            query = (
                session.query(Digest, Paper)
                .join(Paper, Digest.paper_id == Paper.id)
                .filter(tuple_(Digest.article_type, Digest.article_id).notin_(sent_subquery))
            )

            # Try 7-day vector search using original paper publication date
            if topic_vector:
                recent_candidates = (
                    query.filter(func.coalesce(Digest.article_published_at, Paper.published_date) >= seven_days_ago)
                    .filter(Paper.embedding.isnot(None))
                    .order_by(Paper.embedding.cosine_distance(topic_vector))
                    .limit(limit)
                    .all()
                )

                if recent_candidates:
                    print(f"[Repository] Fetched {len(recent_candidates)} vector-matched candidate digests from past 7 days.")
                    return [
                        {
                            "digest_id": d.id,
                            "paper_id": p.id,
                            "article_type": d.article_type,
                            "article_id": d.article_id,
                            "url": d.url or p.pdf_url,
                            "title": d.title,
                            "summary": d.summary,
                            "published_date": d.article_published_at or p.published_date
                        }
                        for d, p in recent_candidates
                    ]

            # All-time candidate fallback query ordered by original publication date
            all_candidates = (
                query.order_by(func.coalesce(Digest.article_published_at, Paper.published_date).desc())
                .limit(limit)
                .all()
            )

            print(f"[Repository] Fetched {len(all_candidates)} fallback candidate digests.")
            return [
                {
                    "digest_id": d.id,
                    "paper_id": p.id,
                    "article_type": d.article_type,
                    "article_id": d.article_id,
                    "url": d.url or p.pdf_url,
                    "title": d.title,
                    "summary": d.summary,
                    "published_date": d.article_published_at or p.published_date
                }
                for d, p in all_candidates
            ]

        except Exception as e:
            print(f"[Database Error] Failed to fetch candidate digests: {e}")
            return []
        finally:
            session.close()

    def get_weekly_digest_paper(self, email: str, topic: str) -> Optional[Paper]:
        """
        1. Generates topic vector embedding via Gemini API.
        2. Queries unsent candidate papers using pgvector cosine similarity ranking.
        3. Prioritizes fresh papers from past 7 days, falling back to all-time unsent candidates.
        4. Guarantees zero duplicate dispatches per user.
        """
        session = self.SessionLocal()
        try:
            sent_subquery = session.query(
                SentEmail.paper_source_system, 
                SentEmail.paper_source_id
            ).filter(SentEmail.user_email == email)

            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            topic_vector = self.agent.generate_embedding(topic)

            if topic_vector:
                # --- Vector Search Attempt: Past 7 Days ---
                paper = (
                    session.query(Paper)
                    .filter(Paper.embedding.isnot(None))
                    .filter(Paper.published_date >= seven_days_ago)
                    .filter(
                        tuple_(Paper.source_system, Paper.source_id).notin_(sent_subquery)
                    )
                    .order_by(Paper.embedding.cosine_distance(topic_vector))
                    .first()
                )

                if paper:
                    print(f"[Repository] Found vector-matched candidate (past 7 days): '{paper.title}'")
                    return paper

                # --- Vector Search Attempt: All-Time Unsent Candidate ---
                print("[Repository] No vector match in past 7 days. Searching all-time unsent papers via pgvector...")
                fallback_paper = (
                    session.query(Paper)
                    .filter(Paper.embedding.isnot(None))
                    .filter(
                        tuple_(Paper.source_system, Paper.source_id).notin_(sent_subquery)
                    )
                    .order_by(Paper.embedding.cosine_distance(topic_vector))
                    .first()
                )

                if fallback_paper:
                    print(f"[Repository] Found vector-matched fallback candidate: '{fallback_paper.title}'")
                    return fallback_paper

            # --- Text ILIKE Fallback if embedding query is unfulfilled ---
            print("[Repository] Vector search yielded no candidate. Running keyword ILIKE fallback search...")
            search_filter = f"%{topic.lower()}%"
            paper = (
                session.query(Paper)
                .filter(
                    (func.lower(Paper.title).like(search_filter)) | 
                    (func.lower(Paper.abstract).like(search_filter))
                )
                .filter(
                    tuple_(Paper.source_system, Paper.source_id).notin_(sent_subquery)
                )
                .order_by(Paper.published_date.desc())
                .first()
            )

            return paper

        except Exception as e:
            print(f"[Database Error] Failed to fetch weekly digest paper: {e}")
            return None
        finally:
            session.close()

    def mark_paper_as_sent(self, email: str, source_system: str, source_id: str) -> None:
        """
        Logs a paper dispatch in sent_emails to prevent sending it to this user again.
        """
        session = self.SessionLocal()
        try:
            stmt = insert(SentEmail).values(
                user_email=email,
                paper_source_system=source_system,
                paper_source_id=source_id
            )
            stmt = stmt.on_conflict_do_nothing(constraint="uix_user_sent_paper")
            session.execute(stmt)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[Database Error] Failed to mark paper as sent: {e}")
        finally:
            session.close()

    def update_paper_ai_summary(self, paper_id: int, ai_summary: str) -> None:
        """Saves the generated AI summary back to the paper record."""
        session = self.SessionLocal()
        try:
            paper = session.query(Paper).filter(Paper.id == paper_id).first()
            if paper:
                paper.ai_summary = ai_summary
                session.commit()
        except Exception as e:
            session.rollback()
            print(f"[Database Error] Failed to update AI summary: {e}")
        finally:
            session.close()


if __name__ == "__main__":
    # Running this file directly creates all missing tables in your DB
    repo = Repository()
    repo.init_db()