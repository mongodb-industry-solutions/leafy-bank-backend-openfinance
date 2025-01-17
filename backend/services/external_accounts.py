from bson import ObjectId
from typing import Union
from database.connection import MongoDBConnection
from datetime import datetime, timedelta, timezone
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class ExternalAccounts:
    """This class provides methods to simulate retrieval of external accounts from external banks."""

    def __init__(self, connection: MongoDBConnection, db_name: str, external_accounts_collection_name: str):
        """Initialize the ExternalAccountsService with the MongoDB connection and collection names.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            external_accounts_collection_name (str): The name of the external accounts collection.

        Returns:
            None
        """
        self.external_accounts_collection = connection.get_collection(
            db_name, external_accounts_collection_name)

    def retrieve_external_account_for_user(self, account_bank: str, user_name: str, user_id: str) -> ObjectId:
        """Simulate retrieving an existing external account.

        Args:
            account_bank (str): The name of the external bank.
            user_name (str): The username of the user.
            user_id (str): The ObjectId of the user.

        Returns:
            ObjectId: The ID of the newly created external account document.
        """
        # Directly use user_id for referencing; assume it's already a valid ObjectId in string form
        user_id_obj = ObjectId(user_id)

        account_number = self._generate_account_number()
        account_balance = self._generate_random_balance(2000, 10000)
        account_type = self._choose_random_type()
        opening_date = self._generate_random_opening_date()

        # Construct the account data matching the existing structure
        account_data = {
            "_id": ObjectId(),  # Generate a new unique ObjectId
            "AccountNumber": account_number,
            "AccountBank": account_bank,
            "AccountStatus": "Active",
            "AccountIdentificationType": "AccountNumber",
            "AccountDate": {
                "OpeningDate": opening_date
            },
            "AccountType": account_type,
            "AccountBalance": account_balance,
            "AccountCurrency": "USD",  # Always USD
            "AccountUser": {
                "UserName": user_name,
                "UserId": user_id_obj  # Keep as reference but not enforced in main user collection
            }
        }

        # Introduce schema differentiation based on account_bank
        if account_bank == "Green Bank":
            # Using a different field name for account description to highlight MongoDB's flexibility
            account_data.update({
                "GreenAccountNarrative": f"{account_type} account focusing on sustainable banking at {account_bank}"
            })
        elif account_bank == "MongoDB Bank":
            # Using a different field name for MongoDB Bank
            account_data.update({
                "MDBAccountNarrative": f"{account_type} account powered by MongoDB at {account_bank}"
            })
        else:
            # Default case
            account_data.update({
                "AccountDescription": f"{account_type} account for {user_name} at {account_bank}"
            })

        # Insert the account data into the external accounts collection
        result = self.external_accounts_collection.insert_one(account_data)
        account_id = result.inserted_id

        logging.info(
            f"Retrieved external account {account_number} for user {user_name} at {account_bank}.")
        return account_id

    def _generate_account_number(self) -> str:
        """Generate a random account number following the frontend logic."""
        return str(random.randint(100000000, 999999999))

    def _generate_random_balance(self, min_balance: float, max_balance: float) -> float:
        """Generate a random balance within a specified range."""
        return round(random.uniform(min_balance, max_balance), 0)

    def _choose_random_type(self) -> str:
        """Choose a random account type."""
        return random.choice(["Checking", "Savings"])

    def _generate_random_opening_date(self) -> datetime:
        """Generate a random past opening date within the last 5 years."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=5*365)
        return start_date + (end_date - start_date) * random.random()

    def get_external_accounts_for_user(self, user_identifier: Union[str, ObjectId], bank_name: str) -> list[dict]:
        """Retrieve external accounts for a specific user from a specific bank.
        Args:
            user_identifier (Union[str, ObjectId]): The user identifier (username or ObjectId of the user).
            bank_name (str): The name of the bank associated with the external accounts.
        Returns:
            List[dict]: A list of external accounts associated with the user.
        """
        # Determine if the identifier is an ObjectId or a username
        if isinstance(user_identifier, ObjectId):
            query = {"AccountUser.UserId": user_identifier,
                     "AccountBank": bank_name}
        else:
            query = {"AccountUser.UserName": user_identifier,
                     "AccountBank": bank_name}

        external_accounts = list(self.external_accounts_collection.find(query))
        return external_accounts

# Note:
# This design showcases MongoDB's schema flexibility—allowing the system to store open finance data
# in diverse formats within the same collection. By leveraging MongoDB's dynamic schema, we accommodate
# variations in how account descriptions are structured per bank, demonstrating its capability to support
# heterogeneous data models seamlessly.
