from fastapi import APIRouter, Depends, Request, HTTPException, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from dependencies import get_auth, get_api_key
from pydantic import BaseModel
from typing import List, Dict, Optional
from bson import ObjectId

from dependencies import get_mongo_connection, DB_NAME
from services.auth import Auth
from services.external_accounts import ExternalAccounts

from encoder.json_encoder import MyJSONEncoder

import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()

# Initialize the MongoDB connection
db_name = DB_NAME
external_accounts_collection_name = "external_accounts"
connection = get_mongo_connection()

# Initialize the ExternalAccounts service
external_accounts_service = ExternalAccounts(
    connection, db_name, external_accounts_collection_name)

limiter = Limiter(key_func=get_remote_address)


@router.post("/validate-key")
@limiter.limit("5/minute")
async def validate_key(
    request: Request,
    api_key: str = Depends(get_api_key),
    auth: Auth = Depends(get_auth)
):
    """Endpoint for simple API key health check."""
    user = auth.api_key_validation(api_key=api_key)
    return {"message": f"API Key is valid for user: {user['UserName']}"}


@router.post("/hello-user")
@limiter.limit("5/minute")
async def hello_user(
    request: Request,
    api_key: str = Depends(get_api_key),
    auth: Auth = Depends(get_auth)
):
    """Protected endpoint returning a greeting."""
    user = auth.api_key_validation(api_key=api_key)
    return {"message": f"Hello, {user['UserName']}"}


class ExternalAccountRequest(BaseModel):
    account_bank: str
    user_name: str
    user_id: str


@router.post("/retrieve-external-account-for-user")
@limiter.limit("5/minute")
async def retrieve_external_account_for_user(
    request: Request,
    account_data: ExternalAccountRequest,
    api_key: str = Depends(get_api_key),
    auth: Auth = Depends(get_auth)
):
    """Endpoint to simulate the retrieval of an external account."""
    user_auth = auth.api_key_validation(api_key=api_key)

    logging.info(f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")

    # Validation: Both conditions must match
    if user_auth['UserName'] != account_data.user_name or str(user_auth['_id']) != account_data.user_id:
        logging.error(
            "Unauthorized access attempt with mismatched user.")
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: The API key does not belong to the provided user_name or user_id."
        )

    try:
        account_id = external_accounts_service.retrieve_external_account_for_user(
            account_bank=account_data.account_bank,
            user_name=account_data.user_name,
            user_id=account_data.user_id
        )
        return {"message": f"External account retrieved for {account_data.user_name}.", "account_id": str(account_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Response Models
class FetchExternalAccountsResponse(BaseModel):
    accounts: List[Dict]


@router.get("/fetch-external-accounts/", response_model=FetchExternalAccountsResponse)
@limiter.limit("20/minute")
async def fetch_external_accounts_for_user(
    request: Request,
    user_identifier: str,  # `user_identifier` as a query parameter
    bank_name: str,  # `bank_name` as a required query parameter
    api_key: str = Depends(get_api_key),
    auth: Auth = Depends(get_auth)
):
    """Get external accounts for a specific user and bank."""
    user_auth = auth.api_key_validation(api_key=api_key)
    logging.info(f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")
    # Validation: Check if user_auth matches user_identifier
    if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
        logging.error(
            "Unauthorized access attempt with mismatched user identifier.")
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: The API key does not belong to the user_identifier."
        )
    try:
        if not user_identifier:
            raise HTTPException(
                status_code=400, detail="User identifier is required")
        # Convert `user_identifier` to ObjectId if valid
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)
        accounts = external_accounts_service.get_external_accounts_for_user(user_identifier, bank_name)
        logging.info(
            f"Found {len(accounts)} external accounts for user {user_identifier} at bank {bank_name}")
        return Response(content=json.dumps({"accounts": accounts}, cls=MyJSONEncoder), media_type="application/json")
    except Exception as e:
        logging.error(f"Error retrieving external accounts for user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
