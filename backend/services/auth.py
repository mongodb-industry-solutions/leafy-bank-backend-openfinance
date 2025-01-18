import logging
from datetime import datetime, timezone
from fastapi import HTTPException
from database.connection import MongoDBConnection

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


class Auth:
    """ Handles Bearer token authentication. 

    Args:
        connection (MongoDBConnection): MongoDB connection object.
        db_name (str): Name of the database
    """

    def __init__(self, connection: MongoDBConnection, db_name: str):
        self.db = connection.get_database(db_name)
        self.tokens_collection = self.db["tokens"]

    def bearer_token_validation(self, bearer_token: str) -> dict:
        if not bearer_token:
            logging.error("Bearer token is missing.")
            raise HTTPException(
                status_code=400, detail="Bearer token is missing.")
        # Search for the token in the database
        user = self.tokens_collection.find_one({"BearerToken": bearer_token})
        if not user:
            logging.error("Invalid bearer token.")
            raise HTTPException(
                status_code=403, detail="Invalid bearer token.")
        # Update the LastUseDate for the token
        self.tokens_collection.update_one(
            {"BearerToken": bearer_token},
            {"$set": {"TokenDates.LastUseDate": datetime.now(timezone.utc)}}
        )
        logging.info(
            f"Bearer token validated for user: {user['UserName']} | Bearer token: {bearer_token}")
        return user
