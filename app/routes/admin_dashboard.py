import time
import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from app.database import get_database
from app.auth.dependencies import get_current_admin, get_company_manager_or_above, get_company_admin_or_above

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])

# --- Caching ---
CACHE: Dict[str, Any] = {}
CACHE_TTL = 60  # seconds

def get_cache_key(prefix: str, identifier: str) -> str:
    return f"{prefix}:{identifier}"

def get_from_cache(key: str) -> Optional[Any]:
    entry = CACHE.get(key)
    if entry and time.time() - entry["timestamp"] < CACHE_TTL:
        return entry["data"]
    return None

def set_cache(key: str, data: Any):
    CACHE[key] = {"data": data, "timestamp": time.time()}

# --- Models ---

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

class CombinedDashboardResponse(BaseModel):
    summary: DashboardSummary
    teamPerformance: Optional[TeamPerformance] = None
    managerOverview: Optional[ManagerDashboardData] = None


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
    Cached for 60 seconds.
    """
    user_id = str(current_admin["userId"])
    cache_key = get_cache_key("summary", user_id)
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    db = await get_database()
    match_stage = _get_company_match(current_admin)
    
    if match_stage is None:
        return DashboardSummary(totalFeedback=0, averageRating=0.0, lowRatings=0, activeIssues=0)

    # Optimized Pipeline with Lookup for precise response checking if needed
    # Assuming 'responses' might not be in feedback doc, we need to check if there are replies.
    # But for speed, if we trust the 'responses' field or if we want to add a lookup:
    # Adding a lookup just to count is expensive. 
    # Current aggregation logic assumes fields exist. We will keep it but ensure indexes are used.
    
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
            # Using $ifNull to handle missing array
            "withResponses": {
                 "$sum": {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$responses", []]}}, 0]}, 1, 0]}
            }
        }}
    ]

    cursor = db["feedback"].aggregate(pipeline)
    result = await cursor.to_list(length=1)

    if not result:
        res = DashboardSummary(totalFeedback=0, averageRating=0.0, lowRatings=0, activeIssues=0)
    else:
        data = result[0]
        total = data.get("totalFeedback", 0)
        avg_rating = round(data.get("averageRating", 0.0) or 0.0, 1)
        response_rate = round((data.get("withResponses", 0) / total * 100) if total > 0 else 0, 1)

        res = DashboardSummary(
            totalFeedback=total,
            averageRating=avg_rating,
            lowRatings=data.get("lowRatings", 0),
            activeIssues=data.get("activeIssues", 0),
            newCount=data.get("newCount", 0),
            inProgressCount=data.get("inProgressCount", 0),
            resolvedCount=data.get("resolvedCount", 0),
            responseRate=response_rate,
        )
    
    set_cache(cache_key, res)
    return res


@router.get("/team-performance", response_model=TeamPerformance)
async def get_team_performance(current_admin: dict = Depends(get_company_admin_or_above)):
    """
    Get team performance overview. Only for company_admin or above.
    Cached.
    """
    user_id = str(current_admin["userId"])
    cache_key = get_cache_key("team_perf", user_id)
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    db = await get_database()
    company_id = current_admin.get("companyId")
    
    match_stage = _get_company_match(current_admin)
    if match_stage is None:
        return TeamPerformance()

    # Parallelize queries
    member_query = {}
    if company_id and company_id != "None" and ObjectId.is_valid(company_id):
        member_query["companyId"] = ObjectId(company_id)
    elif current_admin.get("role") not in ("main_admin", "super_admin"):
        return TeamPerformance()
    
    member_query["role"] = {"$in": ["company_admin", "company_manager", "company_analyst"]}

    # Run queries concurrently
    task_members = db["users"].count_documents(member_query)
    task_handled = db["feedback"].count_documents({
        **match_stage,
        "status": {"$in": ["Resolved", "Closed"]}
    })
    
    total_members, handled = await asyncio.gather(task_members, task_handled)
    
    res = TeamPerformance(
        totalMembers=total_members,
        feedbackHandled=handled,
        avgResponseTime="2.4h"
    )
    set_cache(cache_key, res)
    return res


@router.get("/manager-overview", response_model=ManagerDashboardData)
async def get_manager_overview(current_admin: dict = Depends(get_company_manager_or_above)):
    """
    Get manager-specific dashboard data. For company_manager or above.
    Cached.
    """
    user_id = str(current_admin["userId"])
    cache_key = get_cache_key("manager_overview", user_id)
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    db = await get_database()
    match_stage = _get_company_match(current_admin)
    
    if match_stage is None:
        return ManagerDashboardData()
    
    # 1. Assigned Feedback Count
    user_oid = current_admin.get("userId")
    assigned_query = {**match_stage, "assignedTo": ObjectId(user_oid)} if user_oid and ObjectId.is_valid(user_oid) else None
    
    # 2. Team Stats (Aggregation)
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

    # 3. Recent Activity (Top 5)
    # Use projection to reduce payload
    recent_projection = {"message": 1, "status": 1, "rating": 1, "updatedAt": 1, "createdAt": 1}
    
    # Execute concurrently where possible (Aggregation + Count)
    # Note: assigned count can be part of aggregation but it has different filter (assignedTo).
    # Easier to just run await gather.
    
    task_assigned = db["feedback"].count_documents(assigned_query) if assigned_query else asyncio.Future()
    if not assigned_query: task_assigned.set_result(0)

    task_stats = db["feedback"].aggregate(pipeline).to_list(length=1)
    task_recent = db["feedback"].find(match_stage, recent_projection).sort("updatedAt", -1).limit(5).to_list(5)

    assigned, stats_result, recent_docs = await asyncio.gather(task_assigned, task_stats, task_recent)
    
    data = stats_result[0] if stats_result else {}
    total = data.get("total", 0)
    rate = round((data.get("withResponses", 0) / total * 100) if total > 0 else 0, 1)
    
    recent = []
    for doc in recent_docs:
        recent.append({
            "id": str(doc["_id"]),
            "message": (doc.get("message", "") or "")[:80],
            "status": doc.get("status", "New"),
            "rating": doc.get("rating", 0),
            "updatedAt": doc.get("updatedAt", doc.get("createdAt")).isoformat() if doc.get("updatedAt") or doc.get("createdAt") else None
        })
    
    res = ManagerDashboardData(
        assignedFeedback=assigned,
        teamFeedbackNew=data.get("new", 0),
        teamFeedbackInProgress=data.get("inProgress", 0),
        teamFeedbackResolved=data.get("resolved", 0),
        responseRate=rate,
        recentActivity=recent,
    )
    set_cache(cache_key, res)
    return res


@router.get("/full-summary", response_model=CombinedDashboardResponse)
async def get_full_dashboard(current_admin: dict = Depends(get_current_admin)):
    """
    Combined endpoint for critical dashboard metrics.
    Uses cached functions internally if available.
    """
    # Simply call the other functions. Since they cache, this is efficient.
    # However, we need to handle permissions.
    
    # Summary is for everyone
    task_summary = get_dashboard_summary(current_admin)
    
    # Team Performance for Admins
    task_team = None
    if current_admin.get("role") in ["main_admin", "company_admin"]:
        task_team = get_team_performance(current_admin)
        
    # Manager Overview for Managers/Admins
    task_manager = None
    if current_admin.get("role") in ["main_admin", "company_admin", "company_manager"]:
        task_manager = get_manager_overview(current_admin)
        
    # Execute
    results = await asyncio.gather(
        task_summary,
        task_team if task_team else asyncio.sleep(0),
        task_manager if task_manager else asyncio.sleep(0)
    )
    
    return CombinedDashboardResponse(
        summary=results[0],
        teamPerformance=results[1] if task_team else None,
        managerOverview=results[2] if task_manager else None
    )
