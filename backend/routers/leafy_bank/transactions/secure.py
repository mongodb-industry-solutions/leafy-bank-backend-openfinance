from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Dict
from bson import ObjectId
import logging
import json

from dependencies import get_auth, get_bearer_token, get_mongo_connection
from services.auth import Auth
from services.internal.transactions_service import TransactionsService
from encoder.json_encoder import MyJSONEncoder
from pydantic import BaseModel

import os
from dotenv import load_dotenv

load_dotenv()

# Set up logging configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()

# Initialize the MongoDB connection
connection = get_mongo_connection()

# Get the database name from the environment variable
LEAFYBANK_DB_NAME = os.getenv("LEAFYBANK_DB_NAME")

# Initialize the TransactionsService
transactions_service = TransactionsService(connection, LEAFYBANK_DB_NAME)

# Define a rate limiter
limiter = Limiter(key_func=get_remote_address)

# Define Pydantic Models


class UserIdentifierRequest(BaseModel):
    user_identifier: str


class RecentTransactionsResponse(BaseModel):
    transactions: List[Dict]

# Endpoint to fetch recent transactions for a user


@router.post("/fetch-recent-transactions-for-user", response_model=RecentTransactionsResponse)
@limiter.limit("60/minute")
async def fetch_recent_transactions_for_user(
    request: Request, 
    user_data: UserIdentifierRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    try:
        # Validate Bearer Token and authenticate the user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        logging.info(
            f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}"
        )

        # Extract `user_identifier` from request and ensure it's not null
        user_identifier = user_data.user_identifier
        if not user_identifier:
            logging.error("Missing user identifier in request.")
            raise HTTPException(
                status_code=400, detail="User identifier is required.")

        # Validation: Make sure the authenticated user matches the requested user
        if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
            logging.error("Unauthorized access attempt with mismatched user.")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: The Bearer Token does not belong to the provided user identifier."
            )

        # If `user_identifier` is an ObjectId-like string, convert it to ObjectId
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)

        # Validate if the user exists
        if not transactions_service.is_valid_user(user_identifier):
            logging.error(f"User with identifier {user_identifier} not found.")
            raise HTTPException(status_code=404, detail="User not found.")

        # Retrieve recent transactions for the valid user
        transactions = transactions_service.get_recent_transactions_for_user(
            user_identifier)

        if transactions:
            logging.info(
                f"Found {len(transactions)} recent transactions for user {user_identifier}.")
        else:
            logging.info(
                f"No recent transactions found for user {user_identifier}.")

        return Response(
            content=json.dumps(
                {"transactions": transactions}, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except HTTPException as he:
        raise he  # Propagate pre-raised HTTPException
    except Exception as e:
        logging.error(
            f"Error retrieving recent transactions for user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
