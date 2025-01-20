from fastapi import APIRouter, Depends, Request, HTTPException, Response, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from dependencies import get_auth, get_bearer_token
from pydantic import BaseModel
from typing import List, Dict, Optional
from bson import ObjectId

from dependencies import get_mongo_connection
from services.auth import Auth
from services.external.external_accounts import ExternalAccounts
from services.external.external_products import ExternalFinancialProducts
from services.aggregations.account_aggregations import AccountAggregations
from services.aggregations.product_aggregations import ProductAggregations

from encoder.json_encoder import MyJSONEncoder

import json
import logging

import os
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
OPENFINANCE_DB_NAME = os.getenv("OPENFINANCE_DB_NAME")
LEAFYBANK_DB_NAME = os.getenv("LEAFYBANK_DB_NAME")

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()

# Define the database and collection names

# External
open_finance_db_name = OPENFINANCE_DB_NAME
external_accounts_collection_name = "external_accounts"
external_products_collection_name = "external_products"

# Internal
leafy_bank_db_name = LEAFYBANK_DB_NAME
accounts_collection_name = "accounts"

# Initialize the MongoDB connection
connection = get_mongo_connection()

# Initialize the ExternalAccounts service
external_accounts_service = ExternalAccounts(connection, db_name=open_finance_db_name,
                                             external_accounts_collection_name=external_accounts_collection_name)

# Initialize the ExternalProducts service
external_products_service = ExternalFinancialProducts(connection,  db_name=open_finance_db_name,
                                                      external_products_collection_name=external_products_collection_name
                                                      )

# Initialize the AccountAggregations service
account_aggr_service = AccountAggregations(connection, db1_name=leafy_bank_db_name, collection1_name=accounts_collection_name,
                                           db2_name=open_finance_db_name, collection2_name=external_accounts_collection_name)


# Initialize the ProductAggregations service
product_aggr_service = ProductAggregations(connection, db_name=open_finance_db_name,
                                           collection_name=external_products_collection_name)

limiter = Limiter(key_func=get_remote_address)


@router.post("/validate-token")
@limiter.limit("30/minute")
async def validate_token(
    request: Request,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Endpoint for simple Bearer Token health check."""
    user = auth.bearer_token_validation(bearer_token=bearer_token)
    return {"message": f"Bearer Token is valid for user: {user['UserName']}"}


class FetchExternalAccountsResponse(BaseModel):
    accounts: List[Dict]


class FetchExternalProductsResponse(BaseModel):
    products: List[Dict]
    

@router.get("/fetch-external-accounts-for-user-and-institution/", response_model=FetchExternalAccountsResponse)
@limiter.limit("60/minute")
async def fetch_external_accounts_for_user_and_institution(
    request: Request,
    user_identifier: str,
    institution_name: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Get external accounts for a specific user and institution."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")
    if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
        raise HTTPException(
            status_code=403, detail="Unauthorized: The Bearer Token does not belong to the user_identifier.")
    try:
        if not user_identifier:
            raise HTTPException(
                status_code=400, detail="User identifier is required")
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)
        accounts = external_accounts_service.get_external_accounts_for_user_and_institution(user_identifier, institution_name)
        logging.info(
            f"Found {len(accounts)} external accounts for user {user_identifier} at institution {institution_name}")
        return Response(content=json.dumps({"accounts": accounts}, cls=MyJSONEncoder), media_type="application/json")
    except Exception as e:
        logging.error(f"Error retrieving external accounts for user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fetch-external-products-for-user-and-institution/", response_model=FetchExternalProductsResponse)
@limiter.limit("60/minute")
async def fetch_external_products_for_user_and_institution(
    request: Request,
    user_identifier: str,
    institution_name: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Get external financial products for a specific user and institution."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")
    if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
        raise HTTPException(
            status_code=403, detail="Unauthorized: The Bearer Token does not belong to the user_identifier.")
    try:
        if not user_identifier:
            raise HTTPException(
                status_code=400, detail="User identifier is required")
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)
        products = external_products_service.get_external_products_for_user_and_institution(user_identifier, institution_name)
        logging.info(
            f"Found {len(products)} external products for user {user_identifier} at institution {institution_name}")
        return Response(content=json.dumps({"products": products}, cls=MyJSONEncoder), media_type="application/json")
    except Exception as e:
        logging.error(f"Error retrieving external products for user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fetch-external-accounts-for-user/", response_model=FetchExternalAccountsResponse)
@limiter.limit("60/minute")
async def fetch_all_external_accounts_for_user(
    request: Request,
    user_identifier: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Get all external accounts for a specific user."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")
    if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
        raise HTTPException(
            status_code=403, detail="Unauthorized: The Bearer Token does not belong to the user_identifier.")
    try:
        if not user_identifier:
            raise HTTPException(
                status_code=400, detail="User identifier is required")
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)
        accounts = external_accounts_service.get_all_external_accounts_for_user(user_identifier)
        logging.info(
            f"Found {len(accounts)} external accounts for user {user_identifier}")
        return Response(content=json.dumps({"accounts": accounts}, cls=MyJSONEncoder), media_type="application/json")
    except Exception as e:
        logging.error(
            f"Error retrieving all external accounts for user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fetch-external-products-for-user/", response_model=FetchExternalProductsResponse)
@limiter.limit("60/minute")
async def fetch_all_external_products_for_user(
    request: Request,
    user_identifier: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Get all external financial products for a specific user."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")
    if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
        raise HTTPException(
            status_code=403, detail="Unauthorized: The Bearer Token does not belong to the user_identifier.")
    try:
        if not user_identifier:
            raise HTTPException(
                status_code=400, detail="User identifier is required")
        if ObjectId.is_valid(user_identifier):
            user_identifier = ObjectId(user_identifier)
        products = external_products_service.get_all_external_products_for_user(user_identifier)
        logging.info(
            f"Found {len(products)} external products for user {user_identifier}")
        return Response(content=json.dumps({"products": products}, cls=MyJSONEncoder), media_type="application/json")
    except Exception as e:
        logging.error(
            f"Error retrieving all external products for user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class TotalBalanceRequest(BaseModel):
    user_id: str  # The user's ObjectId as a string
    # List of connected external account IDs (optional)
    connected_external_accounts: Optional[List[str]]


class TotalBalanceResponse(BaseModel):
    total_balance: float


@router.post("/calculate-total-balance-for-user/", response_model=TotalBalanceResponse)
@limiter.limit("60/minute")
async def calculate_total_balance_for_user(
    request: Request,
    # Using a Pydantic model to validate request data
    total_balance_request: TotalBalanceRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth),
):
    """Endpoint to retrieve the total balance for a specific user."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)
    # Ensure the authenticated user matches the user_id being queried
    if user_auth["_id"] != ObjectId(total_balance_request.user_id):
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: User ID does not match the authenticated user.",
        )
    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}, UserId: {user_auth['_id']}"
    )
    try:
        logging.info(
            f"Calculating total balance for user_id: {total_balance_request.user_id}"
        )
        # Call the `get_user_account_balances` method to get the total balance
        balance_data = account_aggr_service.get_user_account_balances(
            total_balance_request.user_id,
            total_balance_request.connected_external_accounts,
        )
        # Return the total balance in the response
        return Response(
            content=json.dumps(balance_data, cls=MyJSONEncoder),
            media_type="application/json",
        )
    except Exception as e:
        logging.error(f"Error calculating total balance for user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


class TotalDebtRequest(BaseModel):
    user_id: str  # The user's ObjectId as a string
    # List of connected external product IDs
    connected_external_products: Optional[List[str]]


class TotalDebtResponse(BaseModel):
    total_debt: float


@router.post("/calculate-total-debt-for-user/", response_model=TotalDebtResponse)
@limiter.limit("60/minute")
async def calculate_total_debt_for_user(
    request: Request,
    total_debt_request: TotalDebtRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Endpoint to retrieve the total debt for a specific user."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

    # Ensure the authenticated user matches the user_id being queried
    if user_auth["_id"] != ObjectId(total_debt_request.user_id):
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: User ID does not match the authenticated user."
        )
    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}, UserId: {user_auth['_id']}"
    )
    try:
        logging.info(
            f"Calculating total debt for user_id: {total_debt_request.user_id} with connected products: {total_debt_request.connected_external_products}"
        )
        # Call the `get_user_total_debt` method to get the total debt
        debt_data = product_aggr_service.get_user_total_debt(
            total_debt_request.user_id,
            total_debt_request.connected_external_products
        )
        # Return the total debt in the response
        return Response(
            content=json.dumps(debt_data, cls=MyJSONEncoder),
            media_type="application/json"
        )
    except Exception as e:
        logging.error(f"Error calculating total debt for user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


class ExternalAccountRequest(BaseModel):
    account_bank: str
    user_name: str
    user_id: str


@router.post("/retrieve-external-account-for-user")
@limiter.limit("30/minute")
async def retrieve_external_account_for_user(
    request: Request,
    account_data: ExternalAccountRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Endpoint to simulate the retrieval of an external account."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}")

    # Validation: Both conditions must match
    if user_auth['UserName'] != account_data.user_name or str(user_auth['_id']) != account_data.user_id:
        logging.error(
            "Unauthorized access attempt with mismatched user.")
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: The Bearer Token does not belong to the provided user_name or user_id."
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


class ExternalProductRequest(BaseModel):
    product_bank: str
    user_name: str
    user_id: str


@router.post("/retrieve-external-product-for-user")
@limiter.limit("30/minute")
async def retrieve_external_product_for_user(
    request: Request,
    product_data: ExternalProductRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """Endpoint to simulate the retrieval of an external financial product."""
    user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

    logging.info(
        f"Authenticated User: UserName: {user_auth['UserName']}; UserId: {user_auth['_id']}"
    )

    # Validation: Ensure the provided user matches the authenticated user
    if user_auth['UserName'] != product_data.user_name or str(user_auth['_id']) != product_data.user_id:
        logging.error(
            "Unauthorized access attempt with mismatched user."
        )
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: The Bearer Token does not belong to the provided user_name or user_id."
        )

    try:
        # Retrieve the external financial product for the user
        product_id = external_products_service.retrieve_external_product_for_user(
            product_bank=product_data.product_bank,
            user_name=product_data.user_name,
            user_id=product_data.user_id
        )
        return {
            "message": f"External financial product retrieved for {product_data.user_name}.",
            "product_id": str(product_id)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error retrieving external financial product: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
