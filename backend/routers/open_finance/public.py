from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from secrets import token_hex
from pymongo.collection import Collection
from dependencies import get_tokens_collection
from slowapi import Limiter
from slowapi.util import get_remote_address
from bson import ObjectId

import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


class AuthorizationResponse(BaseModel):
    message: str
    UserName: str
    BearerToken: str


@router.get("/get-authorization", response_model=AuthorizationResponse)
@limiter.limit("30/minute")
async def get_authorization(
    request: Request,
    user_identifier: str,  # `user_identifier` could be either UserName or _id
    tokens_collection: Collection = Depends(get_tokens_collection)
):
    """
    Retrieve and display a token document based on a user identifier,
    which can be either a UserName or an _id.
    """
    # Try to find the document by UserName
    query = {"UserName": user_identifier}

    # Provide additional logging for better debugging
    logging.info(
        f"Trying to find user document by UserName: {user_identifier}")

    # If the user_identifier looks like an ObjectId, check both UserName and _id
    if ObjectId.is_valid(user_identifier):
        query = {"$or": [{"UserName": user_identifier},
                         {"_id": ObjectId(user_identifier)}]}
        logging.info(
            f"User identifier is a valid ObjectId, querying by _id as well.")

    try:
        user_document = tokens_collection.find_one(query)
        if not user_document:
            logging.warning(f"User identifier {user_identifier} not found.")
            raise HTTPException(status_code=404, detail="User not found.")

        # Prepare the response data
        response_data = {
            "message": "Authorization document retrieved successfully.",
            "UserName": user_document.get("UserName"),
            "BearerToken": user_document.get("BearerToken")
        }

        logging.info(
            f"User document for {user_identifier} retrieved successfully.")
        return response_data

    except Exception as e:
        logging.error(f"Error retrieving user document: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


class CreateUserResponse(BaseModel):
    message: str
    UserName: str
    BearerToken: str


@router.post("/create-user", response_model=CreateUserResponse, status_code=201)
@limiter.limit("5/minute")  # Limit to 5 requests per minute for this endpoint
async def create_user(
    request: Request,
    tokens_collection: Collection = Depends(get_tokens_collection),
    max_retries: int = 5
):
    """
    Create a new user document with a unique UserName and BearerToken.
    """
    for _ in range(max_retries):
        generated_user_name = f"api_user_{token_hex(4)}"
        existing_user = tokens_collection.find_one(
            {"UserName": generated_user_name})
        if not existing_user:
            new_bearer_token = token_hex(32)

            user_document = {
                "UserName": generated_user_name,
                "BearerToken": new_bearer_token,
                "TokenDates": {
                    "CreationDate": datetime.now(timezone.utc),
                    "LastUseDate": None,
                },
            }

            try:
                tokens_collection.insert_one(user_document)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

            return {
                "message": "User created successfully.",
                "UserName": generated_user_name,
                "BearerToken": new_bearer_token,
            }

    raise HTTPException(
        status_code=500,
        detail="Could not generate a unique UserName after multiple attempts."
    )
