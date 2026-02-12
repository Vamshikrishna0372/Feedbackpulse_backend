from fastapi import Depends, HTTPException, status
from bson import ObjectId
from fastapi.security import OAuth2PasswordBearer
from app.auth.jwt import decode_access_token
from app.auth.auth import authenticate_user  # Import logic
from app.database import get_database

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Validate access token and return the current user's payload.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    user_id: str = payload.get("userId")
    token_version: int = payload.get("tokenVersion")
    if user_id is None:
        raise credentials_exception
        
    db = await get_database()
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("isActive", True):
        raise HTTPException(status_code=401, detail="User is inactive or deleted")
        
    if token_version is not None and user.get("tokenVersion", 1) != token_version:
         raise HTTPException(status_code=401, detail="Session expired: All sessions logged out")

    return payload

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """
    Dependency that ensures the authenticated user has the 'admin' role.
    """
    role = current_user.get("role")
    if role not in ["main_admin", "sub_admin", "admin"]: # "admin" for backward compatibility if needed, but we should migrate
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access only"
        )
    return current_user

async def get_current_main_admin(current_user: dict = Depends(get_current_user)):
    """
    Dependency that ensures the authenticated user is the 'main_admin'.
    """
    if current_user.get("role") != "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Main Admin access only"
        )
    return current_user
