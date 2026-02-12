from fastapi import APIRouter, Depends
from pydantic import BaseModel
from bson import ObjectId
from app.database import get_database
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])

class DashboardSummary(BaseModel):
    totalFeedback: int
    averageRating: float
    lowRatings: int
    activeIssues: int

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(current_admin: dict = Depends(get_current_admin)):
    """
    Get real-time feedback statistics for the admin dashboard.
    Strictly scoped to the authenticated admin's company.
    """
    db = await get_database()
    company_id = current_admin.get("companyId")
    
    match_stage = {"isDeleted": {"$ne": True}}
    if company_id and company_id != "None":
        if ObjectId.is_valid(company_id):
            match_stage["companyId"] = ObjectId(company_id)
        else:
            # Invalid ID, essentially shouldn't happen with valid tokens
            pass
    elif current_admin.get("role") != "main_admin":
        # Non-main admin with no companyId should see nothing
        return DashboardSummary(totalFeedback=0, averageRating=0.0, lowRatings=0, activeIssues=0)

    # Aggregation Pipeline
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": None,
            "totalFeedback": {"$sum": 1},
            "averageRating": {"$avg": "$rating"},
            "lowRatings": {
                "$sum": {
                    "$cond": [{"$lte": ["$rating", 2]}, 1, 0]
                }
            },
            "activeIssues": {
                "$sum": {
                    "$cond": [{"$in": ["$status", ["New", "In Progress"]]}, 1, 0]
                }
            }
        }}
    ]

    cursor = db["feedback"].aggregate(pipeline)
    result = await cursor.to_list(length=1)

    if not result:
        # No feedback found, return zeros
        return DashboardSummary(
            totalFeedback=0,
            averageRating=0.0,
            lowRatings=0,
            activeIssues=0
        )

    data = result[0]
    
    # Round average rating to 1 decimal place
    avg_rating = round(data.get("averageRating", 0.0) or 0.0, 1)

    return DashboardSummary(
        totalFeedback=data.get("totalFeedback", 0),
        averageRating=avg_rating,
        lowRatings=data.get("lowRatings", 0),
        activeIssues=data.get("activeIssues", 0)
    )
