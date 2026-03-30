import os
import gridfs
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sbi_fraud_chatbot")
MONGO_USERS_COLLECTION = os.getenv("MONGO_USERS_COLLECTION", "users")
MONGO_DOCUMENTS_COLLECTION = os.getenv("MONGO_DOCUMENTS_COLLECTION", "documents")
MONGO_CASES_COLLECTION = os.getenv("MONGO_CASES_COLLECTION", "historical_cases")
MONGO_CHAT_LOGS_COLLECTION = os.getenv("MONGO_CHAT_LOGS_COLLECTION", "chat_logs")

client = MongoClient(MONGO_URL)

db = client[MONGO_DB_NAME]

users_collection = db[MONGO_USERS_COLLECTION]
documents_collection = db[MONGO_DOCUMENTS_COLLECTION]
cases_collection = db[MONGO_CASES_COLLECTION]
chat_logs_collection = db[MONGO_CHAT_LOGS_COLLECTION]

fs = gridfs.GridFS(db)
