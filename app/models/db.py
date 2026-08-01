from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY, Boolean, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_system = Column(String(50), nullable=False)
    source_id = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    authors = Column(ARRAY(String))
    published_date = Column(DateTime(timezone=True))
    pdf_url = Column(Text)
    transcript_markdown = Column(Text)
    ai_summary = Column(Text)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('source_system', 'source_id', name='uix_source_system_id'),
    )


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    topics = Column(ARRAY(String), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SentEmail(Base):
    __tablename__ = "sent_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String(255), nullable=False)
    paper_source_system = Column(String(50), nullable=False)
    paper_source_id = Column(String(255), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_email', 'paper_source_system', 'paper_source_id', name='uix_user_sent_paper'),
    )


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=True)
    article_type = Column(String(50), nullable=False)
    article_id = Column(String(100), nullable=False)
    url = Column(Text)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    article_published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('article_type', 'article_id', name='uix_digest_article'),
    )
