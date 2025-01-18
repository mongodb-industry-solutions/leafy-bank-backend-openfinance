from fastapi import Header, HTTPException, Depends
from database.connection import MongoDBConnection
from pymongo.collection import Collection
from services.auth import Auth
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
OPENFINANCE_DB_NAME = os.getenv("OPENFINANCE_DB_NAME")


def get_mongo_connection() -> MongoDBConnection:
    return MongoDBConnection(uri=MONGODB_URI)


def get_tokens_collection(db_connection: MongoDBConnection = Depends(get_mongo_connection)) -> Collection:
    return db_connection.get_database(OPENFINANCE_DB_NAME)["tokens"]


def get_auth(mongo_connection: MongoDBConnection = Depends(get_mongo_connection)) -> Auth:
    return Auth(connection=mongo_connection, db_name=OPENFINANCE_DB_NAME)


def get_bearer_token(authorization: str = Header(...)):
    """ Dependency to extract and validate the Bearer token from the Authorization header. """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=403, detail="Bearer token is malformed or missing.")
    return authorization.replace("Bearer ", "")
