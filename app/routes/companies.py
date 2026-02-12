from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import re

from app.database import get_database
from app.auth.dependencies import get_current_user, get_current_admin

router = APIRouter(tags=["Companies"])

# --- Models ---
class CompanyCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None
    status: Optional[str] = None

# --- Helpers ---
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text

def map_company(c: dict) -> dict:
    return {
        "id": str(c["_id"]),
        "_id": str(c["_id"]),
        "name": c.get("name", ""),
        "slug": c.get("slug", ""),
        "industry": c.get("industry", ""),
        "website": c.get("website", ""),
        "description": c.get("description", ""),
        "logo": c.get("logo", ""),
        "status": c.get("status", "active"),
        "createdAt": c.get("createdAt").isoformat() if c.get("createdAt") else None,
    }

# --- Endpoints ---

@router.get("/")
async def list_companies(
    limit: int = Query(100, ge=1, le=500),
):
    """
    List all companies (public for feedback form, authenticated for admin).
    """
    db = await get_database()
    companies = await db["companies"].find().sort("name", 1).limit(limit).to_list(limit)
    return [map_company(c) for c in companies]


@router.get("/search")
async def search_companies(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search companies by name (used in feedback submission form).
    """
    db = await get_database()
    regex = {"$regex": query, "$options": "i"}
    companies = await db["companies"].find({"name": regex}).limit(limit).to_list(limit)
    return [map_company(c) for c in companies]


@router.get("/{company_id}")
async def get_company(company_id: str):
    """
    Get a single company by ID.
    """
    db = await get_database()
    company = await db["companies"].find_one({"_id": ObjectId(company_id)})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return map_company(company)


@router.post("/")
async def create_company(
    company_in: CompanyCreate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Create a new company.
    """
    db = await get_database()
    
    slug = slugify(company_in.name)
    
    # Check for duplicate slug
    existing = await db["companies"].find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=400, detail="A company with a similar name already exists")
    
    new_company = {
        "name": company_in.name,
        "slug": slug,
        "industry": company_in.industry or "",
        "website": company_in.website or "",
        "description": company_in.description or "",
        "logo": company_in.logo or "",
        "status": "active",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    
    result = await db["companies"].insert_one(new_company)
    new_company["_id"] = result.inserted_id
    
    return map_company(new_company)


@router.put("/{company_id}")
async def update_company(
    company_id: str,
    company_in: CompanyUpdate,
    current_user: dict = Depends(get_current_admin)
):
    """
    Update an existing company.
    """
    db = await get_database()
    
    update_data = company_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # If name changed, update slug too
    if "name" in update_data:
        update_data["slug"] = slugify(update_data["name"])
    
    update_data["updatedAt"] = datetime.now(timezone.utc)
    
    updated = await db["companies"].find_one_and_update(
        {"_id": ObjectId(company_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return map_company(updated)


@router.delete("/{company_id}")
async def delete_company(
    company_id: str,
    current_user: dict = Depends(get_current_admin)
):
    """
    Delete a company permanently.
    """
    db = await get_database()
    
    result = await db["companies"].delete_one({"_id": ObjectId(company_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {"message": "Company deleted successfully"}
