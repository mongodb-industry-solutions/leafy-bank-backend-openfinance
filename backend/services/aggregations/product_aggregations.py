from database.connection import MongoDBConnection
from bson import ObjectId
from typing import List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


class ProductAggregations:
    """This class provides methods to perform product aggregations."""

    def __init__(self, connection: MongoDBConnection, db_name: str, collection_name: str):
        """Initialize the ProductAggregations service with the MongoDB collections."""
        self.external_products_collection = connection.get_collection(
            db_name, collection_name
        )

    def _aggregate_external_products_debt(self, user_id: ObjectId, connected_external_products: Optional[List[str]]) -> float:
        """Aggregate total debt for specified external products of type 'Loan' and 'Mortgage' for a specific user."""

        # If no connected external products are specified, return 0
        if not connected_external_products:
            logging.info(
                f"No connected products specified for user: {user_id}. Returning 0 debt.")
            return 0

        match_stage = {
            '_id': {'$in': [ObjectId(product_id) for product_id in connected_external_products]},
            'ProductCustomer.UserId': user_id,
            # Only include Loans and Mortgages
            'ProductType': {'$in': ['Loan', 'Mortgage']}
        }

        pipeline = [
            {'$match': match_stage},
            {'$group': {'_id': None, 'TotalDebt': {'$sum': '$ProductAmount'}}}
        ]

        logging.info(
            f"Aggregating total debt for user: {user_id} with connected products: {connected_external_products}")
        result_aggregate = list(
            self.external_products_collection.aggregate(pipeline))

        total_debt = result_aggregate[0]['TotalDebt'] if result_aggregate else 0
        logging.info(f"Total External Product Debt: {total_debt}")
        return total_debt  # Return the total debt

    def get_user_total_debt(self, user_id: str, connected_external_products: Optional[List[str]] = None) -> dict:
        """Get aggregated total debt for external products."""
        user_id_obj = ObjectId(user_id)

        # Aggregate debt for specified external products (only if they're listed)
        total_debt = self._aggregate_external_products_debt(
            user_id_obj, connected_external_products)

        logging.info(f"Final Total Debt for user {user_id}: {total_debt}")

        return {
            "total_debt": total_debt,
        }
