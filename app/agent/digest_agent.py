import os
import sys
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai

# Ensure root folder is accessible for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()


PROMPT = r"""
You are an expert AI research mentor creating clear, student-friendly, and in-depth research paper breakdowns.
Your goal is to explain the research paper in clear, accessible, yet technically thorough language so that any student or researcher can completely understand the paper directly from the breakdown without needing to read the entire PDF.

CRITICAL RULE: DO NOT use any LaTeX math notation, mathematical formulas, equations, or LaTeX symbols (e.g., no `$`, `$$`, `\mathbb`, `\alpha`, `\frac`, etc.). Explain all mathematical concepts, loss functions, vectors, and algorithmic steps using plain, descriptive English words so it renders cleanly in all email clients without broken formatting.

Format the output strictly in Markdown with these exact sections for each paper:

### 📝 Short Abstract & Overview
(A clear, 2-3 sentence high-level summary of what the paper is about, the background context, and the fundamental problem it addresses)

### 💡 Novelty & Key Breakthroughs
(Explain clearly what makes this paper new, unique, and different from prior work)

### 🧠 Main Concepts & Technical Approach
(Break down the core ideas, model architecture, methodology, and key intuition in simple, easy-to-understand terms with bullet points)

### 🧪 Experimentation & Results
(Detail the datasets used, key benchmark metrics, accuracy/performance numbers, baseline comparisons, and experimental findings)

### 🎯 Conclusion & Key Takeaway
(Provide a concise summary of the final conclusions, practical implications, and why this research matters)
"""


class DigestOutput(BaseModel):
    title: str = Field(description="A concise, engaging, executive title for the research paper")
    summary: str = Field(description="Structured markdown summary including Big Picture, Key Tech, Innovations, and Results")


class DigestAgent:
    """
    AI Agent responsible for reading raw research paper content,
    generating structured executive titles and digest summaries,
    and handling text vector embeddings.
    """
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.client = genai.Client(api_key=self.gemini_api_key)

    def generate_digest(self, title: str, abstract: str, full_markdown: Optional[str] = None) -> DigestOutput:
        """
        Generates a structured DigestOutput containing a polished title and summary.
        Supports Gemini SDK response_schema (and OpenAI fallback if OPENAI_API_KEY is available).
        """
        if full_markdown and full_markdown.strip():
            content_to_analyze = f"Title: {title}\nFull Paper Markdown:\n{full_markdown}"
        else:
            content_to_analyze = f"Title: {title}\nAbstract: {abstract}"

        system_instruction = PROMPT

        # --- OpenAI Responses API Branch (if configured) ---
        if self.openai_api_key:
            try:
                from openai import OpenAI
                openai_client = OpenAI(api_key=self.openai_api_key)
                
                # Check for OpenAI Responses API syntax (client.responses.parse)
                if hasattr(openai_client, "responses") and hasattr(openai_client.responses, "parse"):
                    response = openai_client.responses.parse(
                        model="gpt-4o-mini",
                        input=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": content_to_analyze}
                        ],
                        text_format=DigestOutput,
                    )
                    if hasattr(response, "output_parsed") and response.output_parsed:
                        return response.output_parsed
                else:
                    response = openai_client.beta.chat.completions.parse(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": content_to_analyze}
                        ],
                        response_format=DigestOutput,
                    )
                    if response.choices and response.choices[0].message.parsed:
                        return response.choices[0].message.parsed
            except Exception as e:
                print(f"[DigestAgent OpenAI Fallback] {e}")

        # --- Primary Gemini Branch ---
        prompt = f"{system_instruction}\n\nPaper Content:\n{content_to_analyze}"
        try:
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": DigestOutput,
                }
            )
            data = json.loads(response.text)
            return DigestOutput(**data)
        except Exception as e:
            print(f"[DigestAgent Gemini Warning] Structured output parse retry: {e}")
            # Text fallback if structured JSON parsing fails
            try:
                text_response = self.client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt
                )
                return DigestOutput(
                    title=f"Digest: {title}",
                    summary=text_response.text or f"**Abstract:** {abstract}"
                )
            except Exception as ex:
                print(f"[DigestAgent Error] {ex}")
                return DigestOutput(
                    title=title,
                    summary=f"**Abstract:** {abstract}"
                )

    def generate_embedding(self, text: str) -> Optional[list[float]]:
        """
        Generates 1536-dim vector embedding using gemini-embedding-001.
        """
        if not text or not text.strip():
            return None
        try:
            res = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config={"output_dimensionality": 1536}
            )
            if res and res.embeddings and len(res.embeddings) > 0:
                return res.embeddings[0].values
            return None
        except Exception as e:
            print(f"[DigestAgent Embedding Error] {e}")
            return None


if __name__ == "__main__":
    agent = DigestAgent()
    sample = agent.generate_digest(
        title="1-Lipschitz Neural Networks on Hadamard Manifolds",
        abstract="This paper introduces robust neural network layers for non-Euclidean curved spaces."
    )
    print(f"✅ Generated Title: {sample.title}")
    print(f"✅ Summary Length: {len(sample.summary)} chars")
