-- 1. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create Papers Table (Normalized data from all 3 scrapers)
CREATE TABLE IF NOT EXISTS papers (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT,
    authors TEXT[],
    published_date TIMESTAMP WITH TIME ZONE,
    pdf_url TEXT,
    transcript_markdown TEXT,
    ai_summary TEXT,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_source_system_id UNIQUE (source_system, source_id)
);

-- 3. Create User Subscriptions Table
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    topics TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Sent Emails Table
CREATE TABLE IF NOT EXISTS sent_emails (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    paper_source_system VARCHAR(50) NOT NULL,
    paper_source_id VARCHAR(255) NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_user_sent_paper UNIQUE (user_email, paper_source_system, paper_source_id)
);

-- 5. Create Digests Table (Stores AI generated summaries & paper publication dates)
CREATE TABLE IF NOT EXISTS digests (
    id SERIAL PRIMARY KEY,
    paper_id INT REFERENCES papers(id) ON DELETE CASCADE,
    article_type VARCHAR(50) NOT NULL,
    article_id VARCHAR(100) NOT NULL,
    url TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    article_published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_digest_article UNIQUE (article_type, article_id)
);