from typing import List, Optional
from pydantic import BaseModel, Field


class EmailArticleItem(BaseModel):
    """
    Represents an individual curated research paper article item formatted for email dispatches.
    """
    digest_id: Optional[int] = Field(default=None, description="Database ID of the digest record")
    paper_id: Optional[int] = Field(default=None, description="Database ID of the linked paper record")
    title: str = Field(description="Executive title of the paper")
    url: str = Field(description="Direct URL or PDF link to the full research paper")
    summary: str = Field(description="In-depth technical breakdown covering Gist, Core Architecture, Innovations, and Benchmarks")
    source_system: str = Field(default="ARXIV", description="Source repository (e.g., ARXIV, PUBMED, IEEE)")
    source_id: str = Field(default="", description="Unique source identifier (e.g., 2607.18236v1)")
    published_date: Optional[str] = Field(default=None, description="Publication date of the paper")
    relevance_score: Optional[float] = Field(default=None, description="Curator relevance score from 0 to 100")
    reasoning: Optional[str] = Field(default=None, description="Curator reasoning explanation")


class EmailDigestPayload(BaseModel):
    """
    Pydantic model representing the complete email payload generated for a subscriber's digest dispatch.
    """
    subject: str = Field(description="Personalized subject line for the email digest")
    greeting: str = Field(description="Personalized greeting incorporating the subscriber's name (e.g., 'Hey Dave,')")
    intro_summary: str = Field(description="2-3 sentence executive intro framing the overarching themes of today's papers")
    topic: str = Field(description="The research topic filter for this digest dispatch")
    total_curated_count: int = Field(default=3, description="Total number of curated papers included in this digest")
    articles: List[EmailArticleItem] = Field(description="List of Pydantic EmailArticleItem models included in the digest")
    body_markdown: str = Field(description="Complete formatted Markdown email digest using section headers (## Paper Title)")
    html_body: Optional[str] = Field(default=None, description="Formatted HTML email body ready for SMTP dispatch")
