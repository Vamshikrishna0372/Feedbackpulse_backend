import asyncio
from app.database import db
from app.auth.jwt import get_password_hash
from datetime import datetime

async def seed_main_admin():
    await db.connect()
    database = db.db
    
    # Target email
    email = "admin@feedbackpulse.com"
    password = "admin123"
    
    # 1. Remove any old main admins to ensure only one exists (as per system requirements)
    await database["users"].delete_many({"role": "main_admin"})
    
    # 2. Also remove any user with the new email to avoid duplication
    await database["users"].delete_one({"email": email})

    # Create main admin
    main_admin = {
        "fullName": "System Administrator",
        "email": email,
        "passwordHash": get_password_hash(password),
        "role": "main_admin",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "companyId": None # Platform level
    }
    
    result = await database["users"].insert_one(main_admin)
    if result.inserted_id:
        print(f"Successfully seeded main admin: {email}")
        print(f"Password: {password}")
    else:
        print("Failed to seed main admin.")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(seed_main_admin())
