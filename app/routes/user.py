from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any
from bson import ObjectId
from datetime import datetime, timezone
import json
import csv
import io
from fastapi.responses import StreamingResponse

from app.database import get_database
from app.auth.dependencies import get_current_user
from app.auth.jwt import get_password_hash, verify_password
from app.utils.activity import log_activity

router = APIRouter(prefix="/user", tags=["User Settings"])

# --- Models ---
class ProfileUpdate(BaseModel):
    displayName: str

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    emailNotifications: Optional[bool] = None
    pushNotifications: Optional[bool] = None
    weeklyDigest: Optional[bool] = None
    marketingEmails: Optional[bool] = None

class PasswordChange(BaseModel):
    currentPassword: str
    newPassword: str

class TwoFactorUpdate(BaseModel):
    enabled: bool

# --- Endpoints ---

@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    user = await db["users"].find_one({"_id": ObjectId(current_user["userId"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": str(user["_id"]),
        "fullName": user["fullName"],
        "email": user["email"],
        "role": user["role"],
        "companyId": str(user.get("companyId")) if user.get("companyId") else None,
        "twoFactorEnabled": user.get("twoFactorEnabled", False)
    }

@router.patch("/profile")
async def update_profile(
    profile_in: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = await get_database()
    user_id = ObjectId(current_user["userId"])
    
    await db["users"].update_one(
        {"_id": user_id},
        {"$set": {
            "fullName": profile_in.displayName,
            "updatedAt": datetime.now(timezone.utc)
        }}
    )
    
    return await get_profile(current_user)

@router.get("/settings")
async def get_user_settings(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    user_id = current_user["userId"]
    
    settings_doc = await db["settings"].find_one({"userId": user_id})
    if not settings_doc:
        return {
            "theme": "light",
            "emailNotifications": True,
            "pushNotifications": False,
            "weeklyDigest": False,
            "marketingEmails": False
        }
    
    return {
        "theme": settings_doc.get("theme", "light"),
        "emailNotifications": settings_doc.get("emailNotifications", True),
        "pushNotifications": settings_doc.get("pushNotifications", False),
        "weeklyDigest": settings_doc.get("weeklyDigest", False),
        "marketingEmails": settings_doc.get("marketingEmails", False)
    }

@router.patch("/settings")
async def update_user_settings(
    settings_in: SettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = await get_database()
    user_id = current_user["userId"]
    
    update_data = settings_in.model_dump(exclude_unset=True)
    update_data["updatedAt"] = datetime.now(timezone.utc)
    
    company_id = current_user.get("companyId")
    update_query = {"$set": update_data}
    if company_id and company_id != "None":
        update_query["$setOnInsert"] = {"companyId": ObjectId(company_id)}
    
    await db["settings"].update_one(
        {"userId": user_id},
        update_query,
        upsert=True
    )
    
    return await get_user_settings(current_user)

@router.patch("/change-password")
async def change_password(
    pwd_in: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    # Enforce Role-Based Restrictions: Manager/Analyst cannot access security settings 
    # (Assuming role hierarchy: main_admin > sub_admin > analyst/manager)
    # The prompt says Manager/Analyst cannot access, let's check role.
    if current_user.get("role") not in ["main_admin", "sub_admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Insufficient permissions for security settings")

    db = await get_database()
    user_id = ObjectId(current_user["userId"])
    
    user = await db["users"].find_one({"_id": user_id})
    if not user or not verify_password(pwd_in.currentPassword, user["passwordHash"]):
        raise HTTPException(status_code=400, detail="Invalid current password")
    
    await db["users"].update_one(
        {"_id": user_id},
        {"$set": {
            "passwordHash": get_password_hash(pwd_in.newPassword),
            "updatedAt": datetime.now(timezone.utc)
        }}
    )
    
    await log_activity(
        user_id=str(user_id),
        company_id=current_user["companyId"],
        action="CHANGED_PASSWORD",
        reference_id=str(user_id)
    )
    
    return {"message": "Password updated successfully"}

@router.post("/logout-all")
async def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    user_id = ObjectId(current_user["userId"])
    
    await db["users"].update_one(
        {"_id": user_id},
        {"$inc": {"tokenVersion": 1}, "$set": {"updatedAt": datetime.now(timezone.utc)}}
    )
    
    return {"message": "All sessions invalidated"}

@router.patch("/2fa")
async def update_2fa(
    update: TwoFactorUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = await get_database()
    user_id = ObjectId(current_user["userId"])
    
    await db["users"].update_one(
        {"_id": user_id},
        {"$set": {"twoFactorEnabled": update.enabled, "updatedAt": datetime.now(timezone.utc)}}
    )
    
    return {"enabled": update.enabled}

@router.get("/export")
async def export_user_data(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    user_id = ObjectId(current_user["userId"])
    
    user = await db["users"].find_one({"_id": user_id}, {"passwordHash": 0})
    settings_doc = await db["settings"].find_one({"userId": str(user_id)})
    logs_cursor = db["activityLogs"].find({"userId": user_id})
    logs = await logs_cursor.to_list(1000)
    
    export_data = {
        "profile": {
            "fullName": user["fullName"],
            "email": user["email"],
            "role": user["role"],
            "createdAt": user["createdAt"].isoformat() if isinstance(user["createdAt"], datetime) else user["createdAt"]
        },
        "settings": {k: str(v) if isinstance(v, ObjectId) else v for k, v in settings_doc.items()} if settings_doc else {},
        "activityLogs": [
            {
                "action": l["action"],
                "createdAt": l["createdAt"].isoformat() if isinstance(l["createdAt"], datetime) else l["createdAt"],
                "metadata": l.get("metadata")
            } for l in logs
        ]
    }
    
    content = json.dumps(export_data, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=user_export.json"}
    )

@router.get("/reports")
async def download_company_reports(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    company_id = ObjectId(current_user["companyId"])
    
    feedbacks_cursor = db["feedback"].find({"companyId": company_id})
    feedbacks = await feedbacks_cursor.to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Rating", "Category", "Message", "Sentiment", "Status", "Date"])
    
    for f in feedbacks:
        writer.writerow([
            str(f["_id"]),
            f.get("name", "Anonymous"),
            f.get("email", "N/A"),
            f.get("rating"),
            f.get("category"),
            f.get("content", f.get("message")),
            f.get("sentiment"),
            f.get("status"),
            f["createdAt"].isoformat() if isinstance(f["createdAt"], datetime) else f["createdAt"]
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=company_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@router.patch("/delete-account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    user_id = ObjectId(current_user["userId"])
    company_id = ObjectId(current_user["companyId"])
    
    # Super admin cannot be deleted
    if current_user["role"] == "main_admin":
        raise HTTPException(status_code=400, detail="Main admin cannot be deactivated")
        
    # Company admin check: If only admin in company
    if current_user["role"] == "sub_admin":
        other_admins = await db["users"].count_documents({
            "companyId": company_id,
            "role": "sub_admin",
            "_id": {"$ne": user_id},
            "isActive": True
        })
        if other_admins == 0:
            raise HTTPException(status_code=400, detail="Cannot deactivate the only sub-admin of a company")

    await db["users"].update_one(
        {"_id": user_id},
        {"$set": {"isActive": False, "updatedAt": datetime.now(timezone.utc)}}
    )
    
    await log_activity(
        user_id=str(user_id),
        company_id=str(company_id),
        action="DEACTIVATED_ACCOUNT",
        reference_id=str(user_id)
    )
    
    return {"message": "Account deactivated"}
