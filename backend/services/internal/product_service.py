from typing import Optional, List
from database.connection import MongoDBConnection

import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class ProductService:
    """This class provides methods to interact with Leafy Bank's product catalogue."""

    def __init__(self, connection: MongoDBConnection, db_name: str, collection_name: str):
        """Initialize the ProductService with the MongoDB connection and collection name.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            collection_name (str): The name of the products collection.

        Returns:
            None
        """
        self.products_collection = connection.get_collection(db_name, collection_name)

    def list_products(self, product_type: Optional[str] = None) -> List[dict]:
        """Retrieve all active products, optionally filtered by type.

        Args:
            product_type (Optional[str]): Filter by product type (Loan, Mortgage, CreditCard).

        Returns:
            List[dict]: A list of product documents.
        """
        query = {"ProductStatus": "Active"}

        if product_type:
            query["ProductType"] = product_type

        products = list(self.products_collection.find(query))
        logging.info(f"Retrieved {len(products)} products" + (f" of type {product_type}" if product_type else ""))
        return products

    def get_product(self, product_id: str) -> Optional[dict]:
        """Retrieve a product by its ProductId.

        Args:
            product_id (str): The product ID to look up (e.g., 'lb-loan-001').

        Returns:
            Optional[dict]: The product document if found, otherwise None.
        """
        product = self.products_collection.find_one({"ProductId": product_id})
        if product:
            logging.info(f"Product found: {product_id}")
        else:
            logging.info(f"Product not found: {product_id}")
        return product

    def match_products(
        self,
        product_type: str,
        current_rate: float,
        current_amount: Optional[float] = None
    ) -> List[dict]:
        """Find Leafy Bank products with better rates than the user's current product.

        This is the core product matching logic for loan/credit card portability.
        It finds active products of the same type with lower rates.

        Args:
            product_type (str): The type of product to match (Loan, Mortgage, CreditCard).
            current_rate (float): The user's current interest rate/APR.
            current_amount (Optional[float]): The amount to check against min/max limits.

        Returns:
            List[dict]: A list of matching products sorted by rate (ascending),
                       with a 'rate_improvement' field showing the savings.
        """
        # Build the query
        query = {
            "ProductStatus": "Active",
            "ProductType": product_type
        }

        # For Loan/Mortgage: use ProductInterestRate
        # For CreditCard: use CardAPR
        if product_type == "CreditCard":
            rate_field = "CardAPR"
            query["CardAPR"] = {"$lt": current_rate}
        else:
            rate_field = "ProductInterestRate"
            query["ProductInterestRate"] = {"$lt": current_rate}

        # If amount is provided, check min/max limits
        if current_amount is not None:
            query["MinAmount"] = {"$lte": current_amount}
            query["MaxAmount"] = {"$gte": current_amount}

        # Execute query and sort by rate ascending (best rates first)
        products = list(self.products_collection.find(query).sort(rate_field, 1))

        # Add rate_improvement field to each product
        for product in products:
            product_rate = product.get(rate_field, 0)
            product["rate_improvement"] = round(current_rate - product_rate, 2)
            product["rate_field"] = rate_field

        logging.info(
            f"Found {len(products)} {product_type} products with better rates than {current_rate}%"
        )

        return products

    def get_products_by_type(self, product_type: str) -> List[dict]:
        """Retrieve all active products of a specific type.

        Args:
            product_type (str): The product type (Loan, Mortgage, CreditCard).

        Returns:
            List[dict]: A list of products of the specified type.
        """
        return self.list_products(product_type=product_type)
