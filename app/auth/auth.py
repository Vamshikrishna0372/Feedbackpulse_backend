from app.database import db
from app.auth.jwt import verify_password

async def authenticate_user(email: str, password: str):
    """
    Authenticate a user by email and password.
    Returns the user document if successful, False otherwise.
    """
    print(f"--- AUTH ATTEMPT: {email} ---")
    
    if not email or not password:
        print("Login Error: Missing email or password")
        return False
        
    from app.database import get_database
    database = await get_database()
    if database is None:
        print("Login Error: database is None")
        return False

    # Normalize email to check case-insensitively
    user = await database["users"].find_one({
        "email": {"$regex": f"^{email}$", "$options": "i"}
    })
    
    if not user:
        print(f"Login Error: User not found for {email}")
        return False
        
    print(f"Login Debug: Found user {user.get('email')} with role {user.get('role')}")
    
    stored_hash = user.get("passwordHash")
    is_valid = verify_password(password, stored_hash)
    print(f"Login Debug: Password valid: {is_valid}")
    
    if not is_valid:
        print(f"Login Error: Password mismatch for {email}")
        return False
        
    if not user.get("isActive", True):
        print(f"Login Error: Account deactivated for {email}")
        return False
        
    # Update last login time
    from datetime import datetime, timezone
    await database["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"lastLogin": datetime.now(timezone.utc)}}
    )
        
    return user
