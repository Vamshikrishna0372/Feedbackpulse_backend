
import asyncio
import os
import random
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from bson import ObjectId

# Load environment variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "feedbackpulse")

async def seed_feedbacks():
    print("Connecting to database...")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # 1. Clear existing feedbacks, replies, notes
    print("Clearing existing feedback data...")
    await db["feedback"].delete_many({})
    await db["feedbackReplies"].delete_many({})
    await db["feedbackNotes"].delete_many({})
    print("Wiped all feedback data.")

    # 2. Get list of companies
    companies = await db["companies"].find({"status": "active"}).to_list(100)
    if not companies:
        print("Error: No companies found to link feedback to. Please run seed_companies.py first.")
        return

    print(f"Found {len(companies)} companies. Generating 15 new feedbacks...")
    
    categories = ["product", "delivery", "support", "payment", "technical", "store"]
    names = ["Rahul Sharma", "Ananya Iyer", "Vikram Singh", "Priya Das", "Amit Patel", 
             "Siddharth Rao", "Neha Gupta", "Arjun Malhotra", "Kavita Reddy", "Sanjay Verma",
             "Anonymous", "John Doe", "Jane Smith", "Alice Johnson", "Bob Wilson"]
    
    feedbacks = [
        "Great experience! The product quality is top-notch.",
        "The delivery was delayed by 3 days. Need better communication.",
        "Support team was very helpful with my inquiry.",
        "Payment gateway kept failing. Please fix this.",
        "I love the new UI update! Much cleaner.",
        "The store associate was rude and unhelpful.",
        "Technical glitch in the mobile app makes it crash on login.",
        "Reasonable pricing and fast shipping.",
        "The packaging was damaged when it arrived.",
        "Outstanding customer service! They resolved my issue in 5 minutes.",
        "The product doesn't match the description on the website.",
        "Easy to navigate website and checkout process.",
        "Need more color options for the latest collection.",
        "The subscription model is too expensive.",
        "Highly recommended for daily use!"
    ]

    count = 0
    now = datetime.now(timezone.utc)
    
    for i in range(15):
        company = random.choice(companies)
        rating = random.randint(1, 5)
        
        # Determine sentiment based on rating for demo consistency
        if rating <= 1:
            sentiment = "critical"
        elif rating == 2:
            sentiment = "negative"
        elif rating == 3:
            sentiment = "neutral"
        else:
            sentiment = "positive"

        # Random source
        source = random.choice(["Web", "Mobile App", "Social Media", "Direct"])
        
        doc = {
            "companyId": company["_id"],
            "name": random.choice(names),
            "email": f"user{i}@example.com" if i % 2 == 0 else None,
            "rating": rating,
            "category": random.choice(categories),
            "message": feedbacks[i],
            "sentiment": sentiment,
            "status": random.choice(["New", "In Progress", "Resolved", "Closed"]),
            "priority": "high" if rating <= 2 else "normal",
            "isPinned": False,
            "isPublic": True,
            "source": source,
            "createdAt": now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23)),
            "updatedAt": now
        }
        
        result = await db["feedback"].insert_one(doc)
        if result.inserted_id:
            count += 1
            
    print(f"Seeding complete. Added {count} new feedbacks.")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_feedbacks())
