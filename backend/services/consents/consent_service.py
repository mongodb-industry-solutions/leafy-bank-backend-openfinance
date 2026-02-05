from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from secrets import token_hex
from database.connection import MongoDBConnection
from services.consents.consent_state_machine import (
    validate_transition,
    validate_purpose,
    is_terminal,
    VALID_STATUSES
)

import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class ConsentService:
    """This class provides methods to manage consent lifecycle in the database."""

    def __init__(self, connection: MongoDBConnection, db_name: str,
                 consents_collection_name: str, institutions_collection_name: str):
        """Initialize the ConsentService with MongoDB connection and collection names.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            consents_collection_name (str): The name of the consents collection.
            institutions_collection_name (str): The name of the institutions collection.

        Returns:
            None
        """
        self.consents_collection = connection.get_collection(db_name, consents_collection_name)
        self.institutions_collection = connection.get_collection(db_name, institutions_collection_name)

        # Ensure indexes exist
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes for the consents collection."""
        try:
            # Unique index on ConsentId
            self.consents_collection.create_index("ConsentId", unique=True)
            # Index for querying by user
            self.consents_collection.create_index("Consumer.UserName")
            # TTL index for auto-expiry (documents expire at ExpirationDateTime)
            self.consents_collection.create_index(
                "ExpirationDateTime",
                expireAfterSeconds=0
            )
            logging.info("Consent collection indexes ensured")
        except Exception as e:
            logging.warning(f"Index creation warning (may already exist): {e}")

    def _generate_consent_id(self, institution_name: str) -> str:
        """Generate a unique consent ID in URN format.

        Args:
            institution_name (str): The institution name to include in the URN.

        Returns:
            str: A URN-formatted consent ID (e.g., urn:greenbank:C1a2b3c4d5e6f7)
        """
        # Create a slug from institution name (lowercase, no spaces)
        slug = institution_name.lower().replace(" ", "")
        # Generate random hex token
        random_token = token_hex(7)
        return f"urn:{slug}:C{random_token}"

    def create_consent(
        self,
        consumer_user_name: str,
        consumer_user_id: str,
        permissions: List[str],
        purpose: str,
        source_institution_name: str,
        expiration_days: int = 180
    ) -> dict:
        """Create a new consent record.

        Args:
            consumer_user_name (str): The username of the consumer.
            consumer_user_id (str): The user ID of the consumer.
            permissions (List[str]): List of permissions being requested.
            purpose (str): The purpose of the consent (LOAN_PORTABILITY, etc.).
            source_institution_name (str): The name of the source institution.
            expiration_days (int): Number of days until consent expires. Defaults to 180.

        Returns:
            dict: The created consent document.

        Raises:
            ValueError: If purpose is invalid or institution doesn't exist.
        """
        # Validate purpose
        validate_purpose(purpose)

        # Validate institution exists
        institution = self.institutions_collection.find_one(
            {"InstitutionName": source_institution_name}
        )
        if not institution:
            raise ValueError(f"Institution '{source_institution_name}' not found.")

        # Generate consent ID
        consent_id = self._generate_consent_id(source_institution_name)

        # Calculate timestamps
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(days=expiration_days)

        # Build the consent document
        consent_document = {
            "ConsentId": consent_id,
            "Status": "AWAITING_AUTHORISATION",
            "Consumer": {
                "UserName": consumer_user_name,
                "UserId": consumer_user_id
            },
            "Permissions": permissions,
            "Purpose": purpose,
            "SourceInstitution": {
                "InstitutionName": source_institution_name,
                "InstitutionId": str(institution.get("_id"))
            },
            "CreationDateTime": now,
            "ExpirationDateTime": expiration,
            "StatusUpdateDateTime": now,
            "StatusHistory": [
                {
                    "Status": "AWAITING_AUTHORISATION",
                    "DateTime": now,
                    "Reason": "Consent created"
                }
            ]
        }

        # Insert the document
        self.consents_collection.insert_one(consent_document)
        logging.info(f"Consent created: {consent_id} for user {consumer_user_name}")

        return consent_document

    def get_consent(self, consent_id: str) -> Optional[dict]:
        """Retrieve a consent by its ConsentId.

        Args:
            consent_id (str): The consent ID to look up.

        Returns:
            Optional[dict]: The consent document if found, otherwise None.
        """
        consent = self.consents_collection.find_one({"ConsentId": consent_id})
        if consent:
            logging.info(f"Consent found: {consent_id}")
        else:
            logging.info(f"Consent not found: {consent_id}")
        return consent

    def list_consents_for_user(self, user_name: str) -> List[dict]:
        """Retrieve all consents for a specific user.

        Args:
            user_name (str): The username to query consents for.

        Returns:
            List[dict]: A list of consent documents for the user.
        """
        consents = list(self.consents_collection.find({"Consumer.UserName": user_name}))
        logging.info(f"Found {len(consents)} consents for user {user_name}")
        return consents

    def update_status(
        self,
        consent_id: str,
        new_status: str,
        rejection_reason: Optional[Dict] = None
    ) -> Optional[dict]:
        """Update the status of a consent.

        Args:
            consent_id (str): The consent ID to update.
            new_status (str): The new status to transition to.
            rejection_reason (Optional[Dict]): Rejection details if status is REJECTED.

        Returns:
            Optional[dict]: The updated consent document, or None if not found.

        Raises:
            ValueError: If the transition is invalid.
        """
        # Fetch the consent
        consent = self.get_consent(consent_id)
        if not consent:
            return None

        current_status = consent.get("Status")

        # Validate the transition (raises ValueError if invalid)
        validate_transition(current_status, new_status)

        now = datetime.now(timezone.utc)

        # Build the update
        update_fields = {
            "Status": new_status,
            "StatusUpdateDateTime": now
        }

        # Add rejection details if status is REJECTED
        if new_status == "REJECTED" and rejection_reason:
            update_fields["Rejection"] = rejection_reason

        # Build status history entry
        history_entry = {
            "Status": new_status,
            "DateTime": now,
            "Reason": rejection_reason.get("Reason") if rejection_reason else f"Status changed to {new_status}"
        }

        # Perform the update
        result = self.consents_collection.update_one(
            {"ConsentId": consent_id},
            {
                "$set": update_fields,
                "$push": {"StatusHistory": history_entry}
            }
        )

        if result.modified_count > 0:
            logging.info(f"Consent {consent_id} status updated: {current_status} -> {new_status}")
            return self.get_consent(consent_id)

        return None

    def simulate_approval(self, consent_id: str) -> Optional[dict]:
        """Simulate approval of a consent (demo shortcut).

        Args:
            consent_id (str): The consent ID to approve.

        Returns:
            Optional[dict]: The updated consent document, or None if not found.
        """
        return self.update_status(consent_id, "AUTHORISED")

    def revoke_consent(self, consent_id: str) -> Optional[dict]:
        """Revoke an authorized consent.

        Args:
            consent_id (str): The consent ID to revoke.

        Returns:
            Optional[dict]: The updated consent document, or None if not found.
        """
        rejection_reason = {
            "Code": "CUSTOMER_MANUALLY_REVOKED",
            "Reason": "Consent revoked by user"
        }
        return self.update_status(consent_id, "REVOKED", rejection_reason)

    def reject_consent(self, consent_id: str, rejection_code: str, reason: str) -> Optional[dict]:
        """Reject a pending consent.

        Args:
            consent_id (str): The consent ID to reject.
            rejection_code (str): The rejection code.
            reason (str): The rejection reason.

        Returns:
            Optional[dict]: The updated consent document, or None if not found.
        """
        rejection_reason = {
            "Code": rejection_code,
            "Reason": reason
        }
        return self.update_status(consent_id, "REJECTED", rejection_reason)

    def consume_consent(self, consent_id: str) -> Optional[dict]:
        """Mark a consent as consumed after data retrieval.

        Args:
            consent_id (str): The consent ID to consume.

        Returns:
            Optional[dict]: The updated consent document, or None if not found.
        """
        return self.update_status(consent_id, "CONSUMED")
