import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai

# Ensure root directory is in python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from app.models import UserProfile, EmailArticleItem, EmailDigestPayload


EMAIL_AGENT_PROMPT = r"""
You are an expert AI Email Digest Agent crafting engaging, student-friendly research paper email digests.

Given:
1. Subscriber Profile (Name, Email, Role, Background, Interests).
2. Digest Topic and Current Date.
3. Top Curated Research Papers (Title, direct URL, Source System, Summary).

Your Task:
1. Generate an engaging, catchy subject line (e.g., "🚀 Here's your weekly Machine Learning Research Digest, Khushi!").
2. Create a warm, personalized greeting using the subscriber's name (e.g., "Hey Khushi,").
3. Start the intro with: "Here is your executive summary on recent [Topic] research." followed by a 1-2 sentence overview framing the core themes across today's papers.
4. Format a complete, beautifully structured Markdown body (`body_markdown`) where every paper is fully explained so a student can completely understand it without opening the link:
   - Header for each paper: `## [Paper Title]`
   - Source metadata & clickable link: `**Source:** [Source System] ([Source ID]) | **Direct Link:** [📄 Read Full Paper / PDF](url)`
   - Full student-friendly breakdown sections:
     - `### 📝 Short Abstract & Overview`
     - `### 💡 Novelty & Key Breakthroughs`
     - `### 🧠 Main Concepts & Technical Approach`
     - `### 🧪 Experimentation & Results`
     - `### 🎯 Conclusion & Key Takeaway`
5. Ensure the language is easy to understand, clear, and educational for students and developers alike.
6. CRITICAL FORMATTING RULE: Absolutely NO LaTeX math notation, equations, formulas, or LaTeX symbols (no `$`, `$$`, `\mathbb`, `\alpha`, `\frac`, etc.). Convert or strip all mathematical formulas into plain, descriptive English words so the email renders flawlessly across all email clients.
"""


class EmailAgent:
    """
    AI Agent responsible for creating structured email digests with personalized
    greetings, trend intros, section-header markdown formatting, and Pydantic EmailDigestPayload models.
    """
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.client = genai.Client(api_key=self.gemini_api_key)

    def generate_email(self, user_profile: UserProfile, topic: str, articles: List[EmailArticleItem]) -> EmailDigestPayload:
        """
        Generates a structured Pydantic EmailDigestPayload containing catchy subject line, greeting,
        intro summary, list of EmailArticleItems with URLs, Markdown body with section headers, and HTML body.
        """
        today_str = datetime.now().strftime("%B %d, %Y")
        user_name = getattr(user_profile, "full_name", "Khushi") or "Khushi"

        formatted_articles = []
        for a in articles:
            formatted_articles.append({
                "title": a.title,
                "url": a.url,
                "source": a.source_system,
                "ref_id": a.source_id,
                "published_date": a.published_date,
                "summary": a.summary
            })

        user_context = f"""
SUBSCRIBER INFO:
- Name: {user_name}
- Email: {user_profile.email}
- Role: {user_profile.role}
- Interests: {", ".join(user_profile.interests)}

DIGEST CONFIG:
- Topic: {topic}
- Date: {today_str}
- Total Articles: {len(articles)}

CURATED ARTICLES:
{json.dumps(formatted_articles, indent=2)}
"""

        # --- OpenAI Branch (if OPENAI_API_KEY is available) ---
        if self.openai_api_key:
            try:
                from openai import OpenAI
                openai_client = OpenAI(api_key=self.openai_api_key)

                if hasattr(openai_client, "responses") and hasattr(openai_client.responses, "parse"):
                    response = openai_client.responses.parse(
                        model="gpt-4o-mini",
                        input=[
                            {"role": "system", "content": EMAIL_AGENT_PROMPT},
                            {"role": "user", "content": user_context}
                        ],
                        text_format=EmailDigestPayload,
                    )
                    if hasattr(response, "output_parsed") and response.output_parsed:
                        parsed: EmailDigestPayload = response.output_parsed
                        parsed.articles = articles
                        parsed.topic = topic
                        parsed.total_curated_count = len(articles)
                        return parsed
            except Exception as e:
                print(f"[EmailAgent OpenAI Fallback] {e}")

        # --- Primary Gemini Branch ---
        prompt = f"{EMAIL_AGENT_PROMPT}\n\n{user_context}"
        try:
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": EmailDigestPayload,
                }
            )
            data = json.loads(response.text)
            payload = EmailDigestPayload(**data)
            payload.articles = articles
            payload.topic = topic
            payload.total_curated_count = len(articles)
            return payload
        except Exception as e:
            print(f"[EmailAgent Gemini Warning] Fallback email generation: {e}")
            greeting = f"Hey {user_name},"
            intro = f"Here is your executive summary on recent {topic} research."
            subject = f"🚀 Here's your weekly {topic} AI Research Digest, {user_name}!"
            
            markdown_parts = [
                f"{greeting}\n",
                f"{intro}\n",
                "---"
            ]
            for a in articles:
                markdown_parts.append(
                    f"\n## {a.title}\n"
                    f"**Source:** {a.source_system} ({a.source_id}) | **Direct Link:** [📄 Read Full Paper / PDF]({a.url})  \n\n"
                    f"{a.summary}\n"
                    f"---\n"
                )
            
            body_md = "\n".join(markdown_parts)
            return EmailDigestPayload(
                subject=subject,
                greeting=greeting,
                intro_summary=intro,
                topic=topic,
                total_curated_count=len(articles),
                articles=articles,
                body_markdown=body_md,
                html_body=None
            )


if __name__ == "__main__":
    agent = EmailAgent()
    profile = UserProfile(email="dave@example.com", full_name="Dave")
    sample_articles = [
        EmailArticleItem(
            title="Patch Policy: High-Performance Robot Control via Dense Visual Tokens",
            url="https://arxiv.org/pdf/2607.18236v1",
            source_system="ARXIV",
            source_id="2607.18236v1",
            summary="### 📌 Executive Gist & Problem Solved\nExisting robot control policies either discard fine-grained spatial details..."
        ),
        EmailArticleItem(
            title="Masked Visual Actions: Unifying Robotic World Modeling via Pixel-Space Trajectories",
            url="https://arxiv.org/pdf/2607.19343v1.pdf",
            source_system="ARXIV",
            source_id="2607.19343v1",
            summary="### 📌 Executive Gist & Problem Solved\nVideo generative models hold rich priors about physical dynamics..."
        )
    ]
    email_out = agent.generate_email(profile, "Machine Learning", sample_articles)
    print(f"✅ Subject Line: {email_out.subject}")
    print(f"✅ Greeting: {email_out.greeting}")
    print(f"✅ Articles Count: {len(email_out.articles)}")
    print(f"✅ Sample Article URL: {email_out.articles[0].url}")

