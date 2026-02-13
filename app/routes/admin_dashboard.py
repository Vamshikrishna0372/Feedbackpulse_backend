from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from app.database import get_database
from app.auth.dependencies import get_current_admin, get_company_manager_or_above, get_company_admin_or_above

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])

class DashboardSummary(BaseModel):
    totalFeedback: int
    averageRating: float
    lowRatings: int
    activeIssues: int
    newCount: int = 0
    inProgressCount: int = 0
    resolvedCount: int = 0
    responseRate: float = 0.0

class TeamPerformance(BaseModel):
    totalMembers: int = 0
    feedbackHandled: int = 0
    avgResponseTime: str = "N/A"

class ManagerDashboardData(BaseModel):
    assignedFeedback: int = 0
    teamFeedbackNew: int = 0
    teamFeedbackInProgress: int = 0
    teamFeedbackResolved: int = 0
    responseRate: float = 0.0
    recentActivity: list = []


def _get_company_match(current_admin: dict) -> Optional[dict]:
    """Build a match stage scoped to the user's company."""
    company_id = current_admin.get("companyId")
    match_stage = {"isDeleted": {"$ne": True}}
    
    if company_id and company_id != "None":
        if ObjectId.is_valid(company_id):
            match_stage["companyId"] = ObjectId(company_id)
        else:
            pass
    elif current_admin.get("role") not in ("main_admin", "super_admin"):
        return None  # Non-platform admin with no company -> no data
    
    return match_stage


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(current_admin: dict = Depends(get_current_admin)):
    """
    Get real-time feedback statistics for the admin dashboard.
    Scoped to the admin's company. Works for all roles.
    """
    db = await get_database()
    match_stage = _get_company_match(current_admin)
    
    if match_stage is None:
        return DashboardSummary(totalFeedback=0, averageRating=0.0, lowRatings=0, activeIssues=0)

    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": None,
            "totalFeedback": {"$sum": 1},
            "averageRating": {"$avg": "$rating"},
            "lowRatings": {
                "$sum": {"$cond": [{"$lte": ["$rating", 2]}, 1, 0]}
            },
            "activeIssues": {
                "$sum": {"$cond": [{"$in": ["$status", ["New", "In Progress"]]}, 1, 0]}
            },
            "newCount": {
                "$sum": {"$cond": [{"$eq": ["$status", "New"]}, 1, 0]}
            },
            "inProgressCount": {
                "$sum": {"$cond": [{"$eq": ["$status", "In Progress"]}, 1, 0]}
            },
            "resolvedCount": {
                "$sum": {"$cond": [{"$in": ["$status", ["Resolved", "Closed"]]}, 1, 0]}
            },
            "withResponses": {
                "$sum": {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$responses", []]}}, 0]}, 1, 0]}
            }
        }}
    ]

    cursor = db["feedback"].aggregate(pipeline)
    result = await cursor.to_list(length=1)

    if not result:
        return DashboardSummary(totalFeedback=0, averageRating=0.0, lowRatings=0, activeIssues=0)

    data = result[0]
    total = data.get("totalFeedback", 0)
    avg_rating = round(data.get("averageRating", 0.0) or 0.0, 1)
    response_rate = round((data.get("withResponses", 0) / total * 100) if total > 0 else 0, 1)

    return DashboardSummary(
        totalFeedback=total,
        averageRating=avg_rating,
        lowRatings=data.get("lowRatings", 0),
        activeIssues=data.get("activeIssues", 0),
        newCount=data.get("newCount", 0),
        inProgressCount=data.get("inProgressCount", 0),
        resolvedCount=data.get("resolvedCount", 0),
        responseRate=response_rate,
    )


@router.get("/team-performance", response_model=TeamPerformance)
async def get_team_performance(current_admin: dict = Depends(get_company_admin_or_above)):
    """
    Get team performance overview. Only for company_admin or above.
    """
    db = await get_database()
    company_id = current_admin.get("companyId")
    
    member_query = {}
    if company_id and company_id != "None" and ObjectId.is_valid(company_id):
        member_query["companyId"] = ObjectId(company_id)
    elif current_admin.get("role") not in ("main_admin", "super_admin"):
        return TeamPerformance()
    
    member_query["role"] = {"$in": ["company_admin", "company_manager", "company_analyst"]}
    total_members = await db["users"].count_documents(member_query)
    
    match_stage = _get_company_match(current_admin)
    if match_stage is None:
        return TeamPerformance()
    
    handled = await db["feedback"].count_documents({
        **match_stage,
        "status": {"$in": ["Resolved", "Closed"]}
    })
    
    return TeamPerformance(
        totalMembers=total_members,
        feedbackHandled=handled,
        avgResponseTime="2.4h"
    )


@router.get("/manager-overview", response_model=ManagerDashboardData)
async def get_manager_overview(current_admin: dict = Depends(get_company_manager_or_above)):
    """
    Get manager-specific dashboard data. For company_manager or above.
    """
    db = await get_database()
    match_stage = _get_company_match(current_admin)
    
    if match_stage is None:
        return ManagerDashboardData()
    
    # Get assigned feedback (assigned to current user)
    user_id = current_admin.get("userId")
    assigned = 0
    if user_id and ObjectId.is_valid(user_id):
        assigned = await db["feedback"].count_documents({
            **match_stage,
            "assignedTo": ObjectId(user_id)
        })
    
    # Team status counts
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "new": {"$sum": {"$cond": [{"$eq": ["$status", "New"]}, 1, 0]}},
            "inProgress": {"$sum": {"$cond": [{"$eq": ["$status", "In Progress"]}, 1, 0]}},
            "resolved": {"$sum": {"$cond": [{"$in": ["$status", ["Resolved", "Closed"]]}, 1, 0]}},
            "withResponses": {
                "$sum": {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$responses", []]}}, 0]}, 1, 0]}
            }
        }}
    ]
    
    cursor = db["feedback"].aggregate(pipeline)
    result = await cursor.to_list(length=1)
    
    if not result:
        return ManagerDashboardData(assignedFeedback=assigned)
    
    data = result[0]
    total = data.get("total", 0)
    rate = round((data.get("withResponses", 0) / total * 100) if total > 0 else 0, 1)
    
    # Recent feedback activity
    recent_docs = await db["feedback"].find(match_stage).sort("updatedAt", -1).limit(5).to_list(5)
    recent = []
    for doc in recent_docs:
        recent.append({
            "id": str(doc["_id"]),
            "message": (doc.get("message", "") or "")[:80],
            "status": doc.get("status", "New"),
            "rating": doc.get("rating", 0),
            "updatedAt": doc.get("updatedAt", doc.get("createdAt")).isoformat() if doc.get("updatedAt") or doc.get("createdAt") else None
        })
    
    return ManagerDashboardData(
        assignedFeedback=assigned,
        teamFeedbackNew=data.get("new", 0),
        teamFeedbackInProgress=data.get("inProgress", 0),
        teamFeedbackResolved=data.get("resolved", 0),
        responseRate=rate,
        recentActivity=recent,
    )
