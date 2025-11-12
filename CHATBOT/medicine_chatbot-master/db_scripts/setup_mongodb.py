from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)

user_db = client["user_db"]
user_collection = user_db["users"]
drug_db = client["drugbank_db"]
drug_collection = drug_db["drugs"]

