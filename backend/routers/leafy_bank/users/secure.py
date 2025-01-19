from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Dict
from bson import ObjectId
import logging
import json

from dependencies import get_auth, get_bearer_token, get_mongo_connection
from services.auth import Auth
from services.internal.users_service import UsersService
from encoder.json_encoder import MyJSONEncoder
from pydantic import BaseModel

import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()

# Initialize the MongoDB connection
connection = get_mongo_connection()

# Get the database name from the environment variable
LEAFYBANK_DB_NAME = os.getenv("LEAFYBANK_DB_NAME")

# Collection names
USERS_COLLECTION = "users"

# Initialize the UsersService
users_service = UsersService(connection, LEAFYBANK_DB_NAME, USERS_COLLECTION)

# Define a rate limiter
limiter = Limiter(key_func=get_remote_address)

# Define Pydantic Models


class FetchUsersResponse(BaseModel):
    users: List[Dict]


class FindUserRequest(BaseModel):
    user_identifier: str


class FindUserResponse(BaseModel):
    user: Dict


# Define the endpoints

# # Endpoint to fetch all users
# @router.get("/fetch-users", response_model=FetchUsersResponse)
# @limiter.limit("60/minute")
# async def fetch_users(
#     request: Request, 
#     bearer_token: str = Depends(get_bearer_token),
#     auth: Auth = Depends(get_auth)
# ):
#     """
#     Fetch all users.
#     """
#     try:
#         # Validate Bearer Token and authenticate
#         user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

#         logging.info(
#             f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")

#         users = users_service.get_users()
#         return Response(content=json.dumps({"users": users}, cls=MyJSONEncoder), media_type="application/json")
#     except HTTPException as he:
#         raise he  # Propagate pre-raised HTTPException
#     except Exception as e:
#         logging.error(f"Error fetching users: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")


# Endpoint to find a user by their identifier (username or ID)
@router.post("/find-user", response_model=FindUserResponse)
@limiter.limit("60/minute")
async def find_user(
    request: Request, 
    user_data: FindUserRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Find a user by their identifier (username or ID).
    """
    try:
        # Validate Bearer Token and authenticate
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        logging.info(
            f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")

        # Ensure the authenticated user is looking up only their own data
        user_identifier = user_data.user_identifier

        # Validate user identity: Match UserName or ObjectId
        if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
            logging.error(
                "Unauthorized access attempt with mismatched user identifier.")
            raise HTTPException(
                status_code=403,
                 detail="Unauthorized access: The Bearer Token does not belong to this user or lacks necessary privileges."
            )

        # Convert string-based ObjectId to a valid ObjectId, if applicable
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)

        user = users_service.get_user(user_identifier)
        if not user:
            logging.error(f"User with identifier {user_identifier} not found.")
            raise HTTPException(status_code=404, detail="User not found.")

        return Response(content=json.dumps({"user": user}, cls=MyJSONEncoder), media_type="application/json")
    except HTTPException as he:
        raise he  # Propagate pre-raised HTTPException
    except Exception as e:
        logging.error(f"Error finding user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
