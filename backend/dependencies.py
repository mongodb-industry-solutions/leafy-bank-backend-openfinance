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
    """ Dependency to provide a MongoDB connection. """
    return MongoDBConnection(uri=MONGODB_URI)


def get_keys_collection(db_connection: MongoDBConnection = Depends(get_mongo_connection)) -> Collection:
    """ Dependency to provide the keys collection. """
    return db_connection.get_database(OPENFINANCE_DB_NAME)["keys"]


def get_auth(mongo_connection: MongoDBConnection = Depends(get_mongo_connection)) -> Auth:
    """ Dependency to provide the Auth service. """
    return Auth(connection=mongo_connection, db_name=OPENFINANCE_DB_NAME)


def get_api_key(x_api_key: str = Header(...)):
    """ Dependency that pulls the API key from request headers. """
    if not x_api_key:
        raise HTTPException(status_code=403, detail="API Key is missing.")
    return x_api_key
