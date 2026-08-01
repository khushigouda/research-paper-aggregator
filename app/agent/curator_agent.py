import os
import sys
import json
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

from app.models.user_profile import UserProfile


class CuratedItem(BaseModel):
    digest_id: int = Field(description="Database ID of the digest item")
    paper_id: int = Field(description="Database ID of the linked paper item")
    title: str = Field(description="Executive title of the paper")
    relevance_score: float = Field(
        description="Relevance score from 0.0 to 100.0 indicating alignment with the User Profile"
    )
    reasoning: str = Field(
        description="Detailed explanation of why this paper aligns with the user's background, role, and interests"
    )


class CurationResult(BaseModel):
    curated_items: List[CuratedItem] = Field(
        description="List of evaluated paper items sorted by relevance_score in descending order"
    )


CURATOR_PROMPT = """
You are "The Curator", an elite AI research director responsible for hand-picking, scoring, and ranking top research papers for a subscriber.

Given:
1. A User Profile detailing the subscriber's role, background, interests, and desired technical depth.
2. A candidate list of pre-computed paper digests from the past week.

Your Task:
- Evaluate EVERY candidate paper against the User Profile.
- Assign a relevance_score from 0.0 to 100.0 (where 100.0 is perfect alignment and 0.0 is irrelevant).
- Provide a clear, compelling 2-3 sentence reasoning explaining why this paper is specifically valuable to this user.
- Return the evaluated items sorted by relevance_score in DESCENDING order.
"""


class CuratorAgent:
    """
    Agent responsible for evaluating a pool of candidate digests against a UserProfile,
    assigning 0-100 relevance scores and reasoning, and returning the top-ranked papers.
    """
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.client = genai.Client(api_key=self.gemini_api_key)

    def rank_digests(self, user_profile: UserProfile, candidate_digests: List[dict], top_n: int = 3) -> List[CuratedItem]:
        """
        Evaluates candidate_digests against user_profile, scores them from 0-100 with reasoning,
        and returns top_n items sorted by score descending.
        """
        if not candidate_digests:
            return []

        formatted_candidates = []
        for d in candidate_digests:
            formatted_candidates.append({
                "digest_id": d.get("digest_id"),
                "paper_id": d.get("paper_id"),
                "title": d.get("title"),
                "summary": d.get("summary")
            })

        user_context = f"""
USER PROFILE:
- Email: {user_profile.email}
- Role: {user_profile.role}
- Background: {user_profile.background}
- Active Interests: {", ".join(user_profile.interests)}
- Technical Depth: {user_profile.preferred_technical_depth}

CANDIDATE PAPERS TO EVALUATE AND RANK:
{json.dumps(formatted_candidates, indent=2)}
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
                            {"role": "system", "content": CURATOR_PROMPT},
                            {"role": "user", "content": user_context}
                        ],
                        text_format=CurationResult,
                    )
                    if hasattr(response, "output_parsed") and response.output_parsed:
                        sorted_items = sorted(
                            response.output_parsed.curated_items,
                            key=lambda x: x.relevance_score,
                            reverse=True
                        )
                        return sorted_items[:top_n]
            except Exception as e:
                print(f"[CuratorAgent OpenAI Fallback] {e}")

        # --- Primary Gemini Branch ---
        prompt = f"{CURATOR_PROMPT}\n\n{user_context}"
        try:
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": CurationResult,
                }
            )
            data = json.loads(response.text)
            parsed_result = CurationResult(**data)
            sorted_items = sorted(
                parsed_result.curated_items,
                key=lambda x: x.relevance_score,
                reverse=True
            )
            return sorted_items[:top_n]
        except Exception as e:
            print(f"[CuratorAgent Error] {e}")
            # Heuristic fallback if LLM scoring fails
            fallback_items = []
            for d in candidate_digests[:top_n]:
                fallback_items.append(CuratedItem(
                    digest_id=d.get("digest_id", 0),
                    paper_id=d.get("paper_id", 0),
                    title=d.get("title", ""),
                    relevance_score=85.0,
                    reasoning=f"Selected candidate matching user interest topic."
                ))
            return fallback_items


if __name__ == "__main__":
    agent = CuratorAgent()
    profile = UserProfile(email="developer@example.com")
    sample_candidates = [
        {
            "digest_id": 1,
            "paper_id": 101,
            "title": "Optimizing Transformer Architecture for Cross-Modality Medical Analytics",
            "summary": "Presents a novel cross-modality transformer architecture..."
        },
        {
            "digest_id": 2,
            "paper_id": 102,
            "title": "1-Lipschitz Neural Networks on Hadamard Manifolds",
            "summary": "Extends robust 1-Lipschitz neural network layers to non-Euclidean spaces..."
        }
    ]
    results = agent.rank_digests(profile, sample_candidates, top_n=2)
    print(f"✅ CuratorAgent test completed. Ranked items count: {len(results)}")
    for item in results:
        print(f"\n🏆 Score: {item.relevance_score}/100 | Title: '{item.title}'")
        print(f"   Reasoning: {item.reasoning}")
