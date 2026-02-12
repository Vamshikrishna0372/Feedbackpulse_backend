from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
from app.models.common import PyObjectId

class Company(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(..., description="Company name, e.g. Amazon India")
    slug: str = Field(..., description="URL slug, e.g. amazon-india")
    logo: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"
    isVerified: bool = False
    searchKeywords: List[str] = []
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {PyObjectId: str}
