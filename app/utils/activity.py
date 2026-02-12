from datetime import datetime, timezone
from bson import ObjectId
from app.database import get_database

async def log_activity(
    user_id: str,
    company_id: str,
    action: str,
    reference_id: str = None,
    metadata: dict = {}
):
    """
    Log an activity to the database asynchronously.
    """
    try:
        db = await get_database()
        
        log_entry = {
            "userId": ObjectId(user_id),
            "companyId": ObjectId(company_id),
            "action": action,
            "referenceId": ObjectId(reference_id) if reference_id else None,
            "metadata": metadata,
            "createdAt": datetime.now(timezone.utc)
        }
        
        await db["activityLogs"].insert_one(log_entry)
    except Exception as e:
        # Logging failure should not break the main application flow
        print(f"Failed to log activity: {e}")
