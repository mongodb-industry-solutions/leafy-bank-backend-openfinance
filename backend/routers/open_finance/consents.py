from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging
import json

from dependencies import get_auth, get_bearer_token, get_mongo_connection
from services.auth import Auth
from services.consents.consent_service import ConsentService
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
INSTITUTIONS_COLLECTION = "institutions"

# Initialize the ConsentService
consent_service = ConsentService(
    connection,
    OPENFINANCE_DB_NAME,
    CONSENTS_COLLECTION,
    INSTITUTIONS_COLLECTION
)

# Define a rate limiter
limiter = Limiter(key_func=get_remote_address)


# Define Pydantic Models
class CreateConsentRequest(BaseModel):
    consumer_id: str  # UserName or UserId - validated against bearer token
    permissions: List[str]
    purpose: str  # LOAN_PORTABILITY | CREDIT_CARD_PORTABILITY | FINANCIAL_ADVICE
    source_institution_name: str  # must match an existing institution's InstitutionName
    expiration_days: Optional[int] = 180


class UpdateStatusRequest(BaseModel):
    status: str  # the target status
    rejection_reason: Optional[Dict] = None  # required if status is REJECTED


class ConsentResponse(BaseModel):
    consent: Dict


class ConsentListResponse(BaseModel):
    consents: List[Dict]


class MessageResponse(BaseModel):
    message: str


# Define API Endpoints

@router.post("/", response_model=ConsentResponse, status_code=201)
@limiter.limit("30/minute")
async def create_consent(
    request: Request,
    consent_data: CreateConsentRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Create a new consent for data sharing.

    The consumer_id must match the authenticated user (UserName or UserId).
    The source_institution_name must be a valid institution in the system.
    Valid purposes: LOAN_PORTABILITY, CREDIT_CARD_PORTABILITY, FINANCIAL_ADVICE
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        # Validate that consumer_id matches authenticated user
        if user_auth['UserName'] != consent_data.consumer_id and str(user_auth['_id']) != consent_data.consumer_id:
            logging.error("Unauthorized: consumer_id does not match authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: consumer_id must match the authenticated user."
            )

        # Create the consent
        consent = consent_service.create_consent(
            consumer_user_name=user_auth['UserName'],
            consumer_user_id=str(user_auth['_id']),
            permissions=consent_data.permissions,
            purpose=consent_data.purpose,
            source_institution_name=consent_data.source_institution_name,
            expiration_days=consent_data.expiration_days
        )

        return Response(
            content=json.dumps({"consent": consent}, cls=MyJSONEncoder),
            media_type="application/json",
            status_code=201
        )

    except ValueError as ve:
        logging.error(f"Validation error creating consent: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error creating consent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/", response_model=ConsentListResponse)
@limiter.limit("60/minute")
async def list_consents(
    request: Request,
    consumer_id: str = Query(..., description="The consumer's UserName or UserId"),
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    List all consents for a specific user.

    The consumer_id query parameter must match the authenticated user.
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        # Validate that consumer_id matches authenticated user
        if user_auth['UserName'] != consumer_id and str(user_auth['_id']) != consumer_id:
            logging.error("Unauthorized: consumer_id does not match authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: consumer_id must match the authenticated user."
            )

        consents = consent_service.list_consents_for_user(user_auth['UserName'])

        return Response(
            content=json.dumps({"consents": consents}, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error listing consents: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{consent_id}", response_model=ConsentResponse)
@limiter.limit("60/minute")
async def get_consent(
    request: Request,
    consent_id: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Get a specific consent by its ConsentId.

    Only the consent owner can access their consent.
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        consent = consent_service.get_consent(consent_id)

        if not consent:
            raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found.")

        # Verify the consent belongs to the authenticated user
        if consent['Consumer']['UserName'] != user_auth['UserName']:
            logging.error("Unauthorized: consent does not belong to authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: You can only access your own consents."
            )

        return Response(
            content=json.dumps({"consent": consent}, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error getting consent {consent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.patch("/{consent_id}/status", response_model=ConsentResponse)
@limiter.limit("30/minute")
async def update_consent_status(
    request: Request,
    consent_id: str,
    status_data: UpdateStatusRequest,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Update the status of a consent.

    Valid transitions:
    - AWAITING_AUTHORISATION -> AUTHORISED, REJECTED
    - AUTHORISED -> CONSUMED, REVOKED

    If setting status to REJECTED, rejection_reason is required.
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        # Fetch consent to verify ownership
        consent = consent_service.get_consent(consent_id)
        if not consent:
            raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found.")

        # Verify the consent belongs to the authenticated user
        if consent['Consumer']['UserName'] != user_auth['UserName']:
            logging.error("Unauthorized: consent does not belong to authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: You can only modify your own consents."
            )

        # Update the status
        updated_consent = consent_service.update_status(
            consent_id=consent_id,
            new_status=status_data.status,
            rejection_reason=status_data.rejection_reason
        )

        if not updated_consent:
            raise HTTPException(status_code=500, detail="Failed to update consent status.")

        return Response(
            content=json.dumps({"consent": updated_consent}, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except ValueError as ve:
        logging.error(f"Validation error updating consent status: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error updating consent status {consent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/{consent_id}/approve", response_model=ConsentResponse)
@limiter.limit("30/minute")
async def approve_consent(
    request: Request,
    consent_id: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Demo shortcut: Simulate approval of a consent.

    In a real Open Finance implementation, this would be done by the source institution
    after user authentication. For demo purposes, this endpoint allows direct approval.

    Transitions consent from AWAITING_AUTHORISATION to AUTHORISED.
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        # Fetch consent to verify ownership
        consent = consent_service.get_consent(consent_id)
        if not consent:
            raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found.")

        # Verify the consent belongs to the authenticated user
        if consent['Consumer']['UserName'] != user_auth['UserName']:
            logging.error("Unauthorized: consent does not belong to authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: You can only approve your own consents."
            )

        # Simulate approval
        updated_consent = consent_service.simulate_approval(consent_id)

        if not updated_consent:
            raise HTTPException(status_code=500, detail="Failed to approve consent.")

        return Response(
            content=json.dumps({"consent": updated_consent}, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except ValueError as ve:
        logging.error(f"Validation error approving consent: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error approving consent {consent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/{consent_id}", response_model=ConsentResponse)
@limiter.limit("30/minute")
async def revoke_consent(
    request: Request,
    consent_id: str,
    bearer_token: str = Depends(get_bearer_token),
    auth: Auth = Depends(get_auth)
):
    """
    Revoke an authorized consent.

    Transitions consent from AUTHORISED to REVOKED.
    Only authorized consents can be revoked.
    """
    try:
        # Validate Bearer Token and get authenticated user
        user_auth = auth.bearer_token_validation(bearer_token=bearer_token)

        # Fetch consent to verify ownership
        consent = consent_service.get_consent(consent_id)
        if not consent:
            raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found.")

        # Verify the consent belongs to the authenticated user
        if consent['Consumer']['UserName'] != user_auth['UserName']:
            logging.error("Unauthorized: consent does not belong to authenticated user")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: You can only revoke your own consents."
            )

        # Revoke the consent
        updated_consent = consent_service.revoke_consent(consent_id)

        if not updated_consent:
            raise HTTPException(status_code=500, detail="Failed to revoke consent.")

        return Response(
            content=json.dumps({"consent": updated_consent}, cls=MyJSONEncoder),
            media_type="application/json"
        )

    except ValueError as ve:
        logging.error(f"Validation error revoking consent: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error revoking consent {consent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
