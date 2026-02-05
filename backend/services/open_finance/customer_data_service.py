from typing import Dict, List, Optional
from database.connection import MongoDBConnection
from services.consents.consent_state_machine import can_retrieve_data

import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class CustomerDataService:
    """This class provides consent-gated data retrieval from external institutions."""

    def __init__(
        self,
        connection: MongoDBConnection,
        db_name: str,
        consents_collection_name: str,
        external_accounts_collection_name: str,
        external_products_collection_name: str,
        external_transactions_collection_name: str
    ):
        """Initialize the CustomerDataService with MongoDB connection and collection names.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            consents_collection_name (str): The name of the consents collection.
            external_accounts_collection_name (str): The name of the external accounts collection.
            external_products_collection_name (str): The name of the external products collection.
            external_transactions_collection_name (str): The name of the external transactions collection.

        Returns:
            None
        """
        self.consents_collection = connection.get_collection(db_name, consents_collection_name)
        self.external_accounts_collection = connection.get_collection(db_name, external_accounts_collection_name)
        self.external_products_collection = connection.get_collection(db_name, external_products_collection_name)
        self.external_transactions_collection = connection.get_collection(db_name, external_transactions_collection_name)

    def retrieve_data_with_consent(self, consent_id: str, user_name: str) -> Dict:
        """Retrieve external data based on an authorized consent.

        This method:
        1. Validates consent exists and is AUTHORISED
        2. Verifies consent belongs to the requesting user
        3. Retrieves data based on the consent's purpose
        4. Transitions consent to CONSUMED
        5. Returns the retrieved data

        Args:
            consent_id (str): The ConsentId to use for data retrieval.
            user_name (str): The username of the requesting user.

        Returns:
            Dict: Retrieved data with keys: accounts, products, transactions (based on purpose).

        Raises:
            ValueError: If consent is invalid, not authorized, or doesn't belong to user.
        """
        # Step 1: Load consent
        consent = self.consents_collection.find_one({"ConsentId": consent_id})
        if not consent:
            raise ValueError(f"Consent '{consent_id}' not found.")

        # Step 2: Verify consent status is AUTHORISED
        status = consent.get("Status")
        if not can_retrieve_data(status):
            if status == "CONSUMED":
                raise ValueError(f"Consent '{consent_id}' has already been used (CONSUMED).")
            elif status == "AWAITING_AUTHORISATION":
                raise ValueError(f"Consent '{consent_id}' is not yet authorized. Please approve it first.")
            elif status in ("REJECTED", "REVOKED", "EXPIRED"):
                raise ValueError(f"Consent '{consent_id}' is no longer valid (status: {status}).")
            else:
                raise ValueError(f"Consent '{consent_id}' cannot be used for data retrieval (status: {status}).")

        # Step 3: Verify consent belongs to requesting user
        consent_user = consent.get("Consumer", {}).get("UserName")
        if consent_user != user_name:
            raise ValueError("Unauthorized: This consent does not belong to you.")

        # Step 4: Extract source institution and purpose
        source_institution = consent.get("SourceInstitution", {}).get("InstitutionName")
        purpose = consent.get("Purpose")

        if not source_institution:
            raise ValueError("Consent is missing source institution information.")
        if not purpose:
            raise ValueError("Consent is missing purpose information.")

        logging.info(f"Retrieving data for user {user_name} from {source_institution} for purpose {purpose}")

        # Step 5: Query data based on purpose
        result = self._query_data_by_purpose(user_name, source_institution, purpose)

        # Step 6: Transition consent to CONSUMED
        self._consume_consent(consent_id)

        # Step 7: Add consent status to result
        result["consent_id"] = consent_id
        result["consent_status"] = "CONSUMED"
        result["source_institution"] = source_institution
        result["purpose"] = purpose

        return result

    def _query_data_by_purpose(self, user_name: str, institution_name: str, purpose: str) -> Dict:
        """Query appropriate collections based on consent purpose.

        Args:
            user_name (str): The username to query data for.
            institution_name (str): The institution to query data from.
            purpose (str): The consent purpose determining what data to retrieve.

        Returns:
            Dict: Retrieved data with appropriate keys based on purpose.
        """
        result = {
            "accounts": None,
            "products": None,
            "transactions": None
        }

        if purpose == "LOAN_PORTABILITY":
            # Retrieve loans, mortgages, and accounts
            products = list(self.external_products_collection.find({
                "ProductCustomer.UserName": user_name,
                "ProductBank": institution_name,
                "ProductType": {"$in": ["Loan", "Mortgage"]}
            }))
            accounts = list(self.external_accounts_collection.find({
                "AccountUser.UserName": user_name,
                "AccountBank": institution_name
            }))
            result["products"] = products
            result["accounts"] = accounts
            logging.info(f"LOAN_PORTABILITY: Retrieved {len(products)} products, {len(accounts)} accounts")

        elif purpose == "CREDIT_CARD_PORTABILITY":
            # Retrieve credit card products only
            products = list(self.external_products_collection.find({
                "ProductCustomer.UserName": user_name,
                "ProductBank": institution_name,
                "ProductType": "CreditCard"
            }))
            result["products"] = products
            logging.info(f"CREDIT_CARD_PORTABILITY: Retrieved {len(products)} credit card products")

        elif purpose == "FINANCIAL_ADVICE":
            # Retrieve transactions and accounts for financial analysis
            transactions = list(self.external_transactions_collection.find({
                "TransactionUser.UserName": user_name,
                "TransactionBank": institution_name
            }))
            accounts = list(self.external_accounts_collection.find({
                "AccountUser.UserName": user_name,
                "AccountBank": institution_name
            }))
            result["transactions"] = transactions
            result["accounts"] = accounts
            logging.info(f"FINANCIAL_ADVICE: Retrieved {len(transactions)} transactions, {len(accounts)} accounts")

        else:
            logging.warning(f"Unknown purpose: {purpose}")

        return result

    def _consume_consent(self, consent_id: str) -> None:
        """Mark a consent as consumed after data retrieval.

        Args:
            consent_id (str): The ConsentId to consume.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        self.consents_collection.update_one(
            {"ConsentId": consent_id},
            {
                "$set": {
                    "Status": "CONSUMED",
                    "StatusUpdateDateTime": now
                },
                "$push": {
                    "StatusHistory": {
                        "Status": "CONSUMED",
                        "DateTime": now,
                        "Reason": "Data retrieved successfully"
                    }
                }
            }
        )
        logging.info(f"Consent {consent_id} marked as CONSUMED")
