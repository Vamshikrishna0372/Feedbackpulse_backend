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
    Dependency that ensures the authenticated user is either a Platform Admin 
    or a Company Staff member (Admin, Manager, Analyst).
    """
    role = current_user.get("role")
    allowed_roles = [
        "super_admin", "main_admin", "sub_admin", "admin",
        "company_admin", "company_manager", "company_analyst"
    ]
    if role not in allowed_roles:
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


# === Role-specific guards for company roles ===

async def get_company_admin_or_above(current_user: dict = Depends(get_current_user)):
    """
    Only company_admin or platform admins can access.
    Blocks company_manager and company_analyst.
    """
    role = current_user.get("role")
    allowed = ["super_admin", "main_admin", "sub_admin", "admin", "company_admin"]
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Company Admin or Platform Admin access required"
        )
    return current_user


async def get_company_manager_or_above(current_user: dict = Depends(get_current_user)):
    """
    company_manager, company_admin, or platform admins can access.
    Blocks company_analyst.
    """
    role = current_user.get("role")
    allowed = ["super_admin", "main_admin", "sub_admin", "admin", "company_admin", "company_manager"]
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Manager or above access required"
        )
    return current_user


async def get_company_analyst_or_above(current_user: dict = Depends(get_current_user)):
    """
    Any company role or platform admin can access (read-only analytics).
    """
    role = current_user.get("role")
    allowed = [
        "super_admin", "main_admin", "sub_admin", "admin",
        "company_admin", "company_manager", "company_analyst"
    ]
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Analyst or above access required"
        )
    return current_user
