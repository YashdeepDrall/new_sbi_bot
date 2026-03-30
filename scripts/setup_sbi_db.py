import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import SBI_BANK_DIR, SBI_BANK_ID, SBI_BANK_NAME, SBI_SOP_FILE  # noqa: E402


def main():
    load_dotenv(ROOT_DIR / ".env")

    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "sbi_fraud_chatbot")
    users_collection_name = os.getenv("MONGO_USERS_COLLECTION", "users")
    documents_collection_name = os.getenv("MONGO_DOCUMENTS_COLLECTION", "documents")
    cases_collection_name = os.getenv("MONGO_CASES_COLLECTION", "historical_cases")
    chat_logs_collection_name = os.getenv("MONGO_CHAT_LOGS_COLLECTION", "chat_logs")
    default_user_id = os.getenv("SBI_DEFAULT_USER_ID", "sbi001")
    default_password = os.getenv("SBI_DEFAULT_PASSWORD", "ChangeMe123!")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")

    db = client[db_name]
    users_collection = db[users_collection_name]
    documents_collection = db[documents_collection_name]
    cases_collection = db[cases_collection_name]
    chat_logs_collection = db[chat_logs_collection_name]

    users_collection.create_index([("userId", ASCENDING)], unique=True)
    users_collection.create_index([("bankId", ASCENDING)])
    documents_collection.create_index([("bankId", ASCENDING), ("fileName", ASCENDING)])
    documents_collection.create_index([("bankId", ASCENDING), ("sourceFile", ASCENDING)])
    cases_collection.create_index([("bankId", ASCENDING), ("fileName", ASCENDING)])
    chat_logs_collection.create_index([("userId", ASCENDING), ("sessionId", ASCENDING), ("timestamp", ASCENDING)])

    users_collection.delete_many({"bankId": {"$ne": SBI_BANK_ID}})
    documents_collection.delete_many({"bankId": {"$ne": SBI_BANK_ID}})
    cases_collection.delete_many({"bankId": {"$ne": SBI_BANK_ID}})
    chat_logs_collection.delete_many({"bankId": {"$ne": SBI_BANK_ID}})

    now = datetime.now(timezone.utc)
    users_collection.update_one(
        {"userId": default_user_id},
        {
            "$set": {
                "userId": default_user_id,
                "password": default_password,
                "bankId": SBI_BANK_ID,
                "bankName": SBI_BANK_NAME,
                "role": "investigator",
                "updatedAt": now,
            },
            "$setOnInsert": {
                "createdAt": now,
            },
        },
        upsert=True,
    )

    sbi_sop_path = Path(SBI_BANK_DIR) / SBI_SOP_FILE

    if sbi_sop_path.exists():
        documents_collection.update_one(
            {
                "bankId": SBI_BANK_ID,
                "fileName": SBI_SOP_FILE,
                "isPDF": True,
            },
            {
                "$set": {
                    "bankId": SBI_BANK_ID,
                    "documentType": "SOP",
                    "fileName": SBI_SOP_FILE,
                    "filePath": str(sbi_sop_path),
                    "isPDF": True,
                    "updatedAt": now,
                },
                "$setOnInsert": {
                    "createdAt": now,
                },
            },
            upsert=True,
        )

    print(f"SBI database is ready: {db_name}")
    print(f"Mongo URL: {mongo_url}")
    print(f"Seeded user: {default_user_id}")
    print(f"SBI SOP found: {'yes' if sbi_sop_path.exists() else 'no'}")


if __name__ == "__main__":
    main()
