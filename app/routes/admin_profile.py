from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, EmailStr
from typing import Optional
from bson import ObjectId
from app.database import get_database
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin Profile"])

class ProfileResponse(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    role: str
    companyId: Optional[str] = None

class ProfileUpdate(BaseModel):
    fullName: str
    email: EmailStr

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Fetch the logged-in user's profile details.
    """
    db = await get_database()
    user = await db["users"].find_one({"_id": ObjectId(current_user["userId"])})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ProfileResponse(
        id=str(user["_id"]),
        fullName=user["fullName"],
        email=user["email"],
        role=user["role"],
        companyId=str(user["companyId"]) if user.get("companyId") else None
    )

@router.get("/details", response_model=ProfileResponse) 
async def get_full_profile(current_user: dict = Depends(get_current_user)):
    # Re-implementing to fetch from DB to get fullName
    db = await get_database()
    user = await db["users"].find_one({"_id": ObjectId(current_user["userId"])})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return ProfileResponse(
        id=str(user["_id"]),
        fullName=user["fullName"],
        email=user["email"],
        role=user["role"],
        companyId=str(user["companyId"]) if user.get("companyId") else None
    )

@router.put("/", response_model=ProfileResponse)
async def update_profile(
    profile_update: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the logged-in user's profile (name and email).
    """
    db = await get_database()
    user_id = current_user["userId"]
    
    # Check if email is being changed and if it's already taken
    if profile_update.email != current_user["sub"]:
        existing = await db["users"].find_one({"email": profile_update.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    update_data = {
        "fullName": profile_update.fullName,
        "email": profile_update.email
    }
    
    updated_user = await db["users"].find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if not updated_user:
         raise HTTPException(status_code=404, detail="User not found")

    return ProfileResponse(
        id=str(updated_user["_id"]),
        fullName=updated_user["fullName"],
        email=updated_user["email"],
        role=updated_user["role"],
        companyId=str(updated_user["companyId"]) if updated_user.get("companyId") else None
    )
