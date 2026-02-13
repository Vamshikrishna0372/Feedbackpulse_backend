from fastapi import APIRouter, Depends, Body, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from bson import ObjectId

from app.database import get_database
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])

class SettingsResponse(BaseModel):
    userId: str
    companyId: str
    theme: str
    emailNotifications: bool
    pushNotifications: bool

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    emailNotifications: Optional[bool] = None
    pushNotifications: Optional[bool] = None

@router.get("/", response_model=SettingsResponse)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """
    Get the admin's account settings/preferences.
    """
    db = await get_database()
    user_id = current_user["userId"]
    
    settings = await db["settings"].find_one({"userId": user_id})
    if not settings:
        # Default settings if none found
        return SettingsResponse(
            userId=user_id, 
            companyId=current_user.get("companyId", ""),
            theme="light", 
            emailNotifications=True,
            pushNotifications=False
        )
        
    return SettingsResponse(
        userId=user_id,
        companyId=str(settings.get("companyId", "")),
        theme=settings.get("theme", "light"),
        emailNotifications=settings.get("emailNotifications", True),
        pushNotifications=settings.get("pushNotifications", False)
    )

@router.put("/", response_model=SettingsResponse)
async def update_settings(
    update_data: SettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the admin's account settings. Uses upsert logic.
    """
    db = await get_database()
    user_id = current_user["userId"]
    
    update_fields = update_data.model_dump(exclude_unset=True)
    if not update_fields:
         raise HTTPException(status_code=400, detail="No fields to update")

    # Prepare update fields
    company_id_str = current_user.get("companyId")
    company_id_obj = None
    if company_id_str and company_id_str != "None":
        try:
            company_id_obj = ObjectId(company_id_str)
        except:
            pass

    # Simple upsert
    update_ops = {"$set": update_fields}
    if company_id_obj:
        update_ops["$setOnInsert"] = {"companyId": company_id_obj}

    updated_settings = await db["settings"].find_one_and_update(
        {"userId": user_id},
        update_ops,
        upsert=True,
        return_document=True
    )

    
    if not updated_settings:
        raise HTTPException(status_code=500, detail="Failed to update settings")
        
    return SettingsResponse(
        userId=user_id,
        companyId=str(updated_settings["companyId"]),
        theme=updated_settings.get("theme", "light"),
        emailNotifications=updated_settings.get("emailNotifications", True),
        pushNotifications=updated_settings.get("pushNotifications", False)
    )
