import logging
from datetime import datetime, timezone
from fastapi import HTTPException
from database.connection import MongoDBConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Auth:
    """
    This class provides methods for handling API authentication.
    """

    def __init__(self, connection: MongoDBConnection, db_name: str):
        self.db = connection.get_database(db_name)
        self.keys_collection = self.db["keys"]

    def api_key_validation(self, api_key: str) -> dict:
        if not api_key:
            logging.error("API Key is missing.")
            raise HTTPException(status_code=400, detail="API Key is missing.")

        user = self.keys_collection.find_one({"ApiKey": api_key})

        if not user:
            logging.error("Invalid API Key.")
            raise HTTPException(status_code=403, detail="Invalid API Key.")

        self.keys_collection.update_one(
            {"ApiKey": api_key},
            {"$set": {"ApiKeyDates.LastUseDate": datetime.now(timezone.utc)}}
        )

        logging.info(f"API Key validated for user: {user['UserName']} | API Key: {api_key}")
        return user
