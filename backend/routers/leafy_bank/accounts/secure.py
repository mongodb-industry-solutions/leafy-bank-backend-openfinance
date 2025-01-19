from fastapi import APIRouter, Depends, HTTPException, Response, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Dict
from pydantic import BaseModel
from bson import ObjectId
import logging
import json

from dependencies import get_auth, get_bearer_token, get_mongo_connection
from services.auth import Auth
from services.internal.accounts_service import AccountsService
from encoder.json_encoder import MyJSONEncoder

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

# Collection names
ACCOUNTS_COLLECTION = "accounts"
USERS_COLLECTION = "users"

# Initialize the AccountsService
accounts_service = AccountsService(
    connection, LEAFYBANK_DB_NAME, ACCOUNTS_COLLECTION, USERS_COLLECTION
)

# Define a rate limiter
limiter = Limiter(key_func=get_remote_address)

# Define Pydantic Models


class FetchAccountsForUserRequest(BaseModel):
    user_identifier: str


class FetchAccountsResponse(BaseModel):
    accounts: List[Dict]


class FindAccountByNumberRequest(BaseModel):
    account_number: str


class FindAccountByNumberResponse(BaseModel):
    account: Dict


# Define API Endpoints

# # Endpoint to fetch all accounts
# @router.get("/fetch-accounts", response_model=FetchAccountsResponse)
# @limiter.limit("60/minute")
# async def fetch_accounts(request: Request, bearer_token: str = Depends(get_bearer_token), auth: Auth = Depends(get_auth)):
#     """
#     Fetch all accounts from the database.
#     """
#     try:
#         auth.bearer_token_validation(bearer_token=bearer_token)
#         accounts = accounts_service.get_accounts()
#         return Response(content=json.dumps({"accounts": accounts}, cls=MyJSONEncoder), media_type="application/json")
#     except Exception as e:
#         logging.error(f"Error fetching accounts: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")


# # Endpoint to fetch active accounts
# @router.get("/fetch-active-accounts", response_model=FetchAccountsResponse)
# @limiter.limit("60/minute")
# async def fetch_active_accounts(request: Request, bearer_token: str = Depends(get_bearer_token), auth: Auth = Depends(get_auth)):
#     """
#     Fetch all active accounts from the database.
#     """
#     try:
#         auth.bearer_token_validation(bearer_token=bearer_token)
#         active_accounts = accounts_service.get_active_accounts()
#         return Response(content=json.dumps({"accounts": active_accounts}, cls=MyJSONEncoder), media_type="application/json")
#     except Exception as e:
#         logging.error(f"Error fetching active accounts: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")


# Endpoint to fetch accounts for a specific user
@router.post("/fetch-accounts-for-user", response_model=FetchAccountsResponse)
@limiter.limit("60/minute")
async def fetch_accounts_for_user(
    request: Request, 
    user_data: FetchAccountsForUserRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Fetch all accounts for a specific user.
    """
    try:
        # Validate Bearer Token and authenticate the user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
        user_identifier = user_data.user_identifier

        logging.info(
            f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")

        # Validation: Ensure the authenticated user's identity matches the requested user identifier
        if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
            logging.error("Unauthorized access attempt with mismatched user.")
            raise HTTPException(
                status_code=403, detail="Unauthorized access: The Bearer Token does not belong to the provided user identifier.")

        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)

        accounts = accounts_service.get_accounts_for_user(user_identifier)
        return Response(content=json.dumps({"accounts": accounts}, cls=MyJSONEncoder), media_type="application/json")

    except HTTPException as he:
        raise he  # Propagate pre-raised HTTPException
    except Exception as e:
        logging.error(f"Error fetching accounts for user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# # Endpoint to fetch active accounts for a specific user
# @router.post("/fetch-active-accounts-for-user", response_model=FetchAccountsResponse)
# @limiter.limit("60/minute")
# async def fetch_active_accounts_for_user(
#     request: Request, 
#     user_data: FetchAccountsForUserRequest,
#     bearer_token: str = Depends(get_bearer_token),
#     auth: Auth = Depends(get_auth)
# ):
#     """
#     Fetch all active accounts for a specific user.
#     """
#     try:
#         # Validate Bearer Token and authenticate the user
#         user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
#         user_identifier = user_data.user_identifier

#         logging.info(
#             f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")

#         # Validation: Ensure the authenticated user's identity matches the requested user identifier
#         if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
#             logging.error("Unauthorized access attempt with mismatched user.")
#             raise HTTPException(
#                 status_code=403, detail="Unauthorized access: The Bearer Token does not belong to the provided user identifier.")

#         if ObjectId.is_valid(user_identifier):
#             user_identifier = ObjectId(user_identifier)

#         active_accounts = accounts_service.get_active_accounts_for_user(
#             user_identifier)
#         return Response(content=json.dumps({"accounts": active_accounts}, cls=MyJSONEncoder), media_type="application/json")

#     except HTTPException as he:
#         raise he  # Propagate pre-raised HTTPException
#     except Exception as e:
#         logging.error(f"Error fetching active accounts for user: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")


# # Endpoint to find an account by its number
# @router.post("/find-account-by-number", response_model=FindAccountByNumberResponse)
# @limiter.limit("60/minute")
# async def find_account_by_number(
#     request: Request, 
#     account_data: FindAccountByNumberRequest,
#     bearer_token: str = Depends(get_bearer_token),
#     auth: Auth = Depends(get_auth)
# ):
#     """
#     Find an account by its number.
#     """
#     try:
#         auth.bearer_token_validation(bearer_token=bearer_token)
#         account = accounts_service.get_account_by_number(
#             account_data.account_number)
#         if not account:
#             logging.error(
#                 f"Account with number {account_data.account_number} not found.")
#             raise HTTPException(status_code=404, detail="Account not found.")
#         return Response(content=json.dumps({"account": account}, cls=MyJSONEncoder), media_type="application/json")
#     except Exception as e:
#         logging.error(f"Error finding account by number: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")


# # Endpoint to find an active account by its number
# @router.post("/find-active-account-by-number", response_model=FindAccountByNumberResponse)
# @limiter.limit("60/minute")
# async def find_active_account_by_number(
#     request: Request, 
#     account_data: FindAccountByNumberRequest,
#     bearer_token: str = Depends(get_bearer_token),
#     auth: Auth = Depends(get_auth)
# ):
#     """
#     Find an active account by its number.
#     """
#     try:
#         auth.bearer_token_validation(bearer_token=bearer_token)
#         account = accounts_service.get_active_account_by_number(
#             account_data.account_number)
#         if not account:
#             logging.error(
#                 f"Active account with number {account_data.account_number} not found.")
#             raise HTTPException(
#                 status_code=404, detail="Active account not found.")
#         return Response(content=json.dumps({"account": account}, cls=MyJSONEncoder), media_type="application/json")
#     except Exception as e:
#         logging.error(f"Error finding active account by number: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal Server Error")
