from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])

# --- Models ---
class TimelineItem(BaseModel):
    date: str
    count: int

# --- Helper ---
def get_match_stage(current_admin: dict):
    company_id = current_admin.get("companyId")
    if not company_id or company_id == "None":
        if current_admin.get("role") == "main_admin":
            return {}
        return None
    if not ObjectId.is_valid(company_id):
        return None
    return {"companyId": ObjectId(company_id)}

# --- Endpoints ---

@router.get("/ratings", response_model=Dict[str, int])
async def get_rating_distribution(current_admin: dict = Depends(get_current_admin)):
    """
    Get the count of feedback for each rating (1-5).
    """
    db = await get_database()
    match_stage = get_match_stage(current_admin)
    if match_stage is None:
        return {str(i): 0 for i in range(1, 6)}
    
    pipeline = [
        {"$match": match_stage},
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]

    
    cursor = db["feedback"].aggregate(pipeline)
    results = await cursor.to_list(length=None)
    
    # Initialize with zeros for all ratings 1-5
    distribution = {str(i): 0 for i in range(1, 6)}
    
    for item in results:
        rating = str(item["_id"])
        if rating in distribution:
            distribution[rating] = item["count"]
            
    return distribution


@router.get("/categories", response_model=Dict[str, int])
async def get_category_distribution(current_admin: dict = Depends(get_current_admin)):
    """
    Get the count of feedback per category.
    """
    db = await get_database()
    match_stage = get_match_stage(current_admin)
    if match_stage is None:
        return {}
    
    pipeline = [
        {"$match": match_stage},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    cursor = db["feedback"].aggregate(pipeline)
    results = await cursor.to_list(length=None)
    
    distribution = {}
    for item in results:
        category = item["_id"]
        # Handle cases where category might be null or empty
        if category:
            distribution[category] = item["count"]
            
    return distribution


@router.get("/timeline", response_model=List[TimelineItem])
async def get_feedback_timeline(current_admin: dict = Depends(get_current_admin)):
    """
    Get feedback count grouped by date for trend analysis.
    Sorted by date ascending.
    """
    db = await get_database()
    match_stage = get_match_stage(current_admin)
    if match_stage is None:
        return []
    
    pipeline = [
        {"$match": match_stage},

        {
            "$project": {
                # specific format %Y-%m-%d
                "dateStr": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}
                }
            }
        },
        {"$group": {"_id": "$dateStr", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}} # Sort by date ascending
    ]
    
    cursor = db["feedback"].aggregate(pipeline)
    results = await cursor.to_list(length=None)
    
    timeline = []
    for item in results:
        timeline.append(TimelineItem(date=item["_id"], count=item["count"]))
        
    return timeline
