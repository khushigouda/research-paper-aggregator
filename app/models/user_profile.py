import sys
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class UserProfile(BaseModel):
    """
    Represents a user's technical profile, background, and specific topics of interest
    used by the CuratorAgent to evaluate and rank research papers.
    """
    email: str = Field(description="User's email address")
    full_name: str = Field(default="Khushi", description="User's full name or first name")
    role: str = Field(
        default="AI Research Engineer & Machine Learning Developer",
        description="User's professional role and focus"
    )
    background: str = Field(
        default="Applied AI, Large Language Models, Deep Learning Architectures, Computer Vision, Robotics",
        description="Detailed background of technical experience"
    )
    interests: List[str] = Field(
        default=["Machine Learning", "Autonomous Agents", "Optimization", "Neural Networks"],
        description="Key technical topics the user is actively monitoring"
    )
    preferred_technical_depth: str = Field(
        default="High (Algorithms, Mathematical Proofs, Benchmark Results, Code Repositories)",
        description="Desired level of technical detail"
    )


if __name__ == "__main__":
    profile = UserProfile(email="test_user@example.com")
    print(f"✅ Created UserProfile for: {profile.email}")
    print(f"   Role: {profile.role}")
    print(f"   Interests: {', '.join(profile.interests)}")
