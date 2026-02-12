import asyncio
import os
import random
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "feedbackpulse")

async def seed_data():
    print("Initializing database connection...")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # 1. Clear existing data
    print("Clearing existing feedback data...")
    await db["feedback"].delete_many({})
    await db["feedbackReplies"].delete_many({})
    await db["feedbackNotes"].delete_many({})
    await db["notifications"].delete_many({})
    await db["activityLogs"].delete_many({})
    # Don't strictly need to clear settings, but let's ensure we update/insert the admin settings
    # await db["settings"].delete_many({}) 
    
    # 2. Ensure Company exists with proper ObjectId
    print("Setting up company...")
    company_data = {
        "name": "Amazon India",
        "slug": "amazon-india",
        "industry": "E-commerce",
        "website": "https://amazon.in",
        "description": "Online marketplace",
        "status": "active",
        "isVerified": True,
        "searchKeywords": ["amazon", "amazon india", "shopping"],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    # Check if company exists by slug
    existing_company = await db["companies"].find_one({"slug": "amazon-india"})
    
    if existing_company:
        company_id = existing_company["_id"]
        print(f"Using existing company: {company_data['name']} (ID: {company_id})")
        # Ensure it has searchKeywords
        if "searchKeywords" not in existing_company:
             await db["companies"].update_one(
                 {"_id": company_id},
                 {"$set": {"searchKeywords": company_data["searchKeywords"]}}
             )
    else:
        result = await db["companies"].insert_one(company_data)
        company_id = result.inserted_id
        print(f"Created new company: {company_data['name']} (ID: {company_id})")

    # 3. Update Admin User with correct Company ID
    print("Updating admin user...")
    admin_email = "admin@gmail.com"
    user_result = await db["users"].update_one(
        {"email": admin_email},
        {"$set": {"companyId": company_id}}
    )
    
    # Get Admin ID for use in replies/notes
    admin_user = await db["users"].find_one({"email": admin_email})
    admin_id = admin_user["_id"] if admin_user else None

    if not admin_id:
        print("Warning: Admin user not found. Skipping creation of replis/notes/notifications/logs linked to admin.")
    else:
        print(f"Seeding settings for Admin ID: {admin_id}")
        # 3b. Seed/Reset Admin Settings
        settings_data = {
            "userId": admin_id,
            "companyId": company_id,
            "theme": "dark",
            "emailNotifications": True,
            "pushNotifications": True,
            "weeklyDigest": False,
            "marketingEmails": False,
            "createdAt": datetime.utcnow()
        }
        await db["settings"].update_one(
            {"userId": admin_id},
            {"$set": settings_data},
            upsert=True
        )
        print("Admin settings seeded.")

    # 4. Generate 20 Mock Feedbacks + Related Data
    print("Generating 20 mock feedbacks with related data...")
    
    categories = ["Product", "Delivery", "Support", "Technical", "Payment"]
    statuses = ["New", "In Progress", "Resolved", "Closed"]
    names = ["Aarav Patel", "Diya Sharma", "Vihaan Singh", "Ananya Gupta", "Rohan Kumar", "Ishita Reddy", "Kabir Joshi", "Mira Nair", "Arjun Das", "Sanya Malhotra"]
    
    feedback_list = []
    replies_list = []
    notes_list = []
    notifications_list = []
    logs_list = []
    
    for i in range(20):
        rating = random.randint(1, 5)
        category = random.choice(categories)
        status = random.choice(statuses)
        
        # Logic for priority based on rating
        if rating <= 2:
            priority = random.choice(["high", "critical"])
        elif rating == 3:
            priority = "medium"
        else:
            priority = "low"
            
        sentiment_map = {
            1: "critical", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"
        }
        
        created_at = datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        
        feedback_id = ObjectId()
        feedback = {
            "_id": feedback_id,
            "companyId": company_id,
            "rating": rating,
            "category": category,
            "message": f"This is a sample feedback message regarding {category.lower()}. The experience was {sentiment_map[rating]}.",
            "voiceTranscript": None,
            "status": status,
            "priority": priority,
            "isPinned": random.choice([True, False]) if i % 5 == 0 else False,
            "isDeleted": False,
            "isPublic": True,
            "createdAt": created_at,
            "updatedAt": created_at,
            "name": random.choice(names),
            "email": f"user{i}@example.com",
            "source": random.choice(["Web", "Mobile App", "Email"])
        }
        feedback_list.append(feedback)
        
        if admin_id:
            # Add random replies (to ~40% of feedbacks)
            if random.random() > 0.6:
                replies_list.append({
                    "feedbackId": feedback_id,
                    "companyId": company_id,
                    "adminId": admin_id,
                    "message": f"Thank you for your feedback, {feedback['name']}. We are looking into it.",
                    "createdAt": created_at + timedelta(hours=2)
                })
                
            # Add random notes (to ~30% of feedbacks)
            if random.random() > 0.7:
                notes_list.append({
                    "feedbackId": feedback_id,
                    "companyId": company_id,
                    "adminId": admin_id,
                    "note": f"Internal note: Customer raised this via {feedback['source']}. Priority verified.",
                    "createdAt": created_at + timedelta(hours=1)
                })
            
            # Add notifications for low ratings (1-2 stars)
            if rating <= 2:
                notifications_list.append({
                    "userId": admin_id,
                    "companyId": company_id,
                    "type": "feedback",
                    "title": f"New {rating}-Star Review",
                    "message": f"A {sentiment_map[rating]} rating was submitted by {feedback['name']}.",
                    "referenceId": feedback_id,
                    "isRead": random.choice([True, False]),
                    "createdAt": created_at
                })
                
            # Add activity logs for resolved/closed items
            if status in ["Resolved", "Closed"]:
                logs_list.append({
                    "userId": admin_id,
                    "companyId": company_id,
                    "action": "UPDATED_STATUS",
                    "referenceId": feedback_id,
                    "metadata": {"new_status": status},
                    "createdAt": created_at + timedelta(hours=4)
                })
        
    if feedback_list:
        await db["feedback"].insert_many(feedback_list)
        print(f"Inserted {len(feedback_list)} feedbacks.")
        
    if replies_list:
        await db["feedbackReplies"].insert_many(replies_list)
        print(f"Inserted {len(replies_list)} replies.")
        
    if notes_list:
        await db["feedbackNotes"].insert_many(notes_list)
        print(f"Inserted {len(notes_list)} notes.")
        
    if notifications_list:
        await db["notifications"].insert_many(notifications_list)
        print(f"Inserted {len(notifications_list)} notifications.")
        
    if logs_list:
        await db["activityLogs"].insert_many(logs_list)
        print(f"Inserted {len(logs_list)} activity logs.")

    client.close()
    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_data())
