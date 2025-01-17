from database.connection import MongoDBConnection
from bson import ObjectId
from typing import List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


class AccountAggregations:
    """This class provides methods to perform account aggregations."""

    def __init__(self, connection: MongoDBConnection, db1_name: str, collection1_name: str,
                 db2_name: str, collection2_name: str):
        # Use provided connection to get collections
        self.accounts_collection = connection.get_collection(
            db1_name, collection1_name
        )
        self.external_accounts_collection = connection.get_collection(
            db2_name, collection2_name
        )

    def _aggregate_internal_account_balances(self, user_id: ObjectId) -> float:
        """Aggregate total balance for internal accounts for a specific user."""
        pipeline = [
            {'$match': {'AccountUser.UserId': user_id}},  # Match only by user_id
            {'$group': {'_id': None, 'TotalBalance': {'$sum': '$AccountBalance'}}}
        ]
        logging.info(f"Aggregating internal accounts for user: {user_id}")
        result_aggregate = list(self.accounts_collection.aggregate(pipeline))

        total_balance = result_aggregate[0]['TotalBalance'] if result_aggregate else 0
        logging.info(f"Total Internal Balance: {total_balance}")
        return total_balance  # Return the total internal balance

    def _aggregate_external_account_balances(self, user_id: ObjectId, connected_external_accounts: Optional[List[str]]) -> float:
        """Aggregate total balance for specified external accounts."""
        match_stage = {
            'AccountUser.UserId': user_id  # Always match by user_id
        }

        if connected_external_accounts:
            # When connected_external_accounts is provided, match only specified accounts
            match_stage['_id'] = {
                '$in': [ObjectId(account_id) for account_id in connected_external_accounts]
            }

        pipeline = [
            {'$match': match_stage},
            {'$group': {'_id': None, 'TotalBalance': {'$sum': '$AccountBalance'}}}
        ]
        logging.info(
            f"Aggregating external accounts for user: {user_id} with connected accounts: {connected_external_accounts}"
        )
        result_aggregate = list(
            self.external_accounts_collection.aggregate(pipeline))

        total_balance = result_aggregate[0]['TotalBalance'] if result_aggregate else 0
        logging.info(f"Total External Balance: {total_balance}")
        return total_balance  # Return the total external balance

    def get_user_account_balances(self, user_id: str, connected_external_accounts: Optional[List[str]] = None) -> dict:
        """Get aggregated total balance for internal and external accounts."""
        user_id_obj = ObjectId(user_id)

        # Step 1: Aggregate balances for internal accounts
        internal_total_balance = self._aggregate_internal_account_balances(
            user_id_obj)

        # Step 2: Aggregate balances for specified external accounts (if provided)
        external_total_balance = 0
        if connected_external_accounts:
            external_total_balance = self._aggregate_external_account_balances(
                user_id_obj, connected_external_accounts
            )

        # Step 3: Compute total balance (internal + external)
        total_balance = internal_total_balance + external_total_balance

        logging.info(f"Final Total Aggregated Balance: {total_balance}")

        return {
            "total_balance": total_balance,
        }
