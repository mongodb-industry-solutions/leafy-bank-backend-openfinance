from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging
import json

from dependencies import get_auth, get_bearer_token, get_mongo_connection
from services.auth import Auth
from services.open_finance.customer_data_service import CustomerDataService
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
OPENFINANCE_DB_NAME = os.getenv("OPENFINANCE_DB_NAME")

# Collection names
CONSENTS_COLLECTION = "consents"
EXTERNAL_ACCOUNTS_COLLECTION = "external_accounts"
EXTERNAL_PRODUCTS_COLLECTION = "external_products"
EXTERNAL_TRANSACTIONS_COLLECTION = "external_transactions"

# Initialize the CustomerDataService
customer_data_service = CustomerDataService(
    connection,
    OPENFINANCE_DB_NAME,
    CONSENTS_COLLECTION,
    EXTERNAL_ACCOUNTS_COLLECTION,
    EXTERNAL_PRODUCTS_COLLECTION,
    EXTERNAL_TRANSACTIONS_COLLECTION
)

# Define a rate limiter
limiter = Limiter(key_func=get_remote_address)


# Define Pydantic Models
class ExternalDataResponse(BaseModel):
    accounts: Optional[List[Dict]] = None
    products: Optional[List[Dict]] = None
    transactions: Optional[List[Dict]] = None
    consent_id: str
    consent_status: str  # CONSUMED after successful retrieval
    source_institution: str
    purpose: str


# Define API Endpoints

@router.get("/{user_identifier}/external-data", response_model=ExternalDataResponse)
@limiter.limit("60/minute")
async def retrieve_external_data(
    request: Request,
    user_identifier: str,
    consent_id: str = Query(..., description="The ConsentId to use for data retrieval"),
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Retrieve external data using an authorized consent.

    This endpoint:
    1. Validates the consent exists and is AUTHORISED
    2. Verifies the consent belongs to the authenticated user
    3. Retrieves data from the source institution based on consent purpose:
       - LOAN_PORTABILITY: loans, mortgages, and accounts
       - CREDIT_CARD_PORTABILITY: credit card products
       - FINANCIAL_ADVICE: transactions and accounts
    4. Transitions the consent to CONSUMED (single-use)

    The user_identifier in the path must match the authenticated user.
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        # Validate that user_identifier matches authenticated user
        if user_auth['UserName'] != user_identifier and str(user_auth['_id']) != user_identifier:
            logging.error("Unauthorized: user_identifier does not match authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: user_identifier must match the authenticated user."
            )

        # Retrieve data using the consent
        result = customer_data_service.retrieve_data_with_consent(
            consent_id=consent_id,
            user_name=user_auth['UserName']
        )

        return Response(
            content=json.dumps(result, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except ValueError as ve:
        logging.error(f"Validation error retrieving external data: {str(ve)}")
        raise HTTPException(status_code=403, detail=str(ve))
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error retrieving external data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
