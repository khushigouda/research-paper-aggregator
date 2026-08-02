import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from google import genai

# Ensure root directory is accessible for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()


class PaperEmbedder:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)

    def get_embedding(self, text: str) -> Optional[list[float]]:
        """
        Generates a 1536-dimensional vector embedding for input text
        using Gemini's gemini-embedding-001 model with output_dimensionality set to 1536.
        """
        if not text or not text.strip():
            return None

        try:
            response = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config={"output_dimensionality": 1536}
            )
            if response and response.embeddings and len(response.embeddings) > 0:
                return response.embeddings[0].values
            return None
        except Exception as e:
            print(f"[Embedder Error] Failed to generate embedding: {e}")
            return None


if __name__ == "__main__":
    embedder = PaperEmbedder()
    vector = embedder.get_embedding("Machine Learning for Healthcare Applications")
    if vector:
        print(f" Success! Vector dimension: {len(vector)}")
    else:
        print(" Embedding generation failed.")
