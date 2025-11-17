"""
Database Schemas for Charity Sponsorship App

Each Pydantic model below maps to a MongoDB collection. The collection name is the
lowercased class name by convention.
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class Sponsor(BaseModel):
    """
    Sponsors collection schema
    Collection: "sponsor"
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Unique email address")
    password_hash: str = Field(..., description="Hashed password")
    country: Optional[str] = Field(None, description="Country of residence")
    bio: Optional[str] = Field(None, description="Short bio")
    avatar_url: Optional[str] = Field(None, description="Profile image URL")
    api_key: Optional[str] = Field(None, description="Simple API key for session auth")
    is_active: bool = Field(True, description="Whether sponsor is active")

class Child(BaseModel):
    """
    Children collection schema
    Collection: "child"
    """
    name: str = Field(..., description="Child name")
    age: int = Field(..., ge=0, le=18, description="Age in years")
    country: str = Field(..., description="Country")
    bio: Optional[str] = Field(None, description="Short story/bio")
    photo_url: Optional[str] = Field(None, description="Photo URL")
    sponsored: bool = Field(False, description="Whether child is sponsored")
    sponsored_by: Optional[str] = Field(None, description="Sponsor id as string")

class Donation(BaseModel):
    """
    Donations collection schema
    Collection: "donation"
    """
    sponsor_id: str = Field(..., description="Sponsor id as string")
    child_id: str = Field(..., description="Child id as string")
    amount: float = Field(..., ge=0, description="Donation amount")
    currency: str = Field("USD", description="Currency code")
    month: Optional[str] = Field(None, description="YYYY-MM month this donation applies to")
    status: str = Field("completed", description="Donation status")

class Update(BaseModel):
    """
    Child updates collection schema
    Collection: "update"
    """
    child_id: str = Field(..., description="Child id as string")
    title: str = Field(..., description="Short title")
    content: Optional[str] = Field(None, description="Update content")
    photo_url: Optional[str] = Field(None, description="Optional photo URL")

# Example additional schemas could be added here if needed.
