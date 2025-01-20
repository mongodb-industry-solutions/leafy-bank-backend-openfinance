from bson import ObjectId
from typing import Union
from database.connection import MongoDBConnection
from datetime import datetime, timedelta, timezone
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class ExternalFinancialProducts:
    """This class provides methods to simulate retrieval of external financial products like loans and mortgages."""

    def __init__(self, connection: MongoDBConnection, db_name: str, external_products_collection_name: str):
        """Initialize the ExternalFinancialProductsService with the MongoDB connection and collection names.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            external_products_collection_name (str): The name of the external products collection.

        Returns:
            None
        """
        self.external_products_collection = connection.get_collection(
            db_name, external_products_collection_name)

    def retrieve_external_product_for_user(self, product_bank: str, user_name: str, user_id: str) -> ObjectId:
        """Simulate retrieving an existing external financial product.

        Args:
            product_bank (str): The name of the external bank.
            user_name (str): The username of the user.
            user_id (str): The ObjectId of the user.

        Returns:
            ObjectId: The ID of the newly created external product document.
        """
        user_id_obj = ObjectId(user_id)

        product_id = self._generate_product_id()
        product_type = self._choose_random_product_type()
        product_amount = self._generate_random_amount(10000, 50000)
        product_interest_rate = self._generate_random_interest_rate()
        product_opening_date = self._generate_random_opening_date()

        # Construct the product data
        product_data = {
            "_id": ObjectId(),
            "ProductId": product_id,
            "ProductBank": product_bank,
            "ProductStatus": "Active",
            "ProductType": product_type,
            "ProductAmount": product_amount,
            "ProductCurrency": "USD",
            "ProductInterestRate": product_interest_rate,
            "ProductDate": {
                "OpeningDate": product_opening_date
            },
            "ProductCustomer": {
                "UserName": user_name,
                "UserId": user_id_obj
            },
        }

        # Adding bank-specific schema differentiation
        if product_bank == "Green Bank":
            # Using a different field name for product description to show MongoDB's flexibility
            product_data.update({
                "GreenProductNarrative": f"{product_type} tailored for sustainability at {product_bank}"
            })
        elif product_bank == "MongoDB Bank":
            # MongoDB Bank has another distinct attribute name
            product_data.update({
                "MDBProductNarrative": f"{product_type} product offered by {product_bank} with MongoDB's excellence"
            })
        else:
            # Default case
            product_data.update({
                "ProductDescription": f"{product_type} for {user_name} at {product_bank}"
            })

        # Showcase MongoDB's schema flexibility by differentiating products
        if product_type == "Loan":
            product_data.update({
                "RepaymentPeriod": self._generate_repayment_period(),
                "LoanCollateral": "None"
            })
        elif product_type == "Mortgage":
            product_data.update({
                "AmortizationPeriod": self._generate_amortization_period(),
                "PropertyDetails": {
                    "Address": "123 Main St",
                    "PropertyValue": self._generate_random_amount(50000, 100000)
                }
            })

        # Insert the product data into the external products collection
        result = self.external_products_collection.insert_one(product_data)
        product_id = result.inserted_id

        logging.info(
            f"Retrieved external product {product_id} for user {user_name} at {product_bank}.")
        return product_id

    def _generate_product_id(self) -> str:
        """Generate a random product ID following similar logic as for accounts."""
        return str(random.randint(1000, 9999))

    def _generate_random_amount(self, min_amount: float, max_amount: float) -> float:
        """Generate a random loan or mortgage amount within a specified range."""
        return round(random.uniform(min_amount, max_amount), 0)

    def _generate_random_interest_rate(self) -> float:
        """Generate a random interest rate."""
        return round(random.uniform(2.5, 5.0), 2)

    def _choose_random_product_type(self) -> str:
        """Choose a random product type."""
        return random.choice(["Loan", "Mortgage"])

    def _generate_repayment_period(self) -> int:
        """Generate a random repayment period for loans."""
        return random.choice([12, 24, 36, 48, 60])

    def _generate_amortization_period(self) -> int:
        """Generate a random amortization period for mortgages."""
        return random.choice([15, 20, 25, 30])

    def _generate_random_opening_date(self) -> datetime:
        """Generate a random past opening date within the last 10 years."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=10*365)
        return start_date + (end_date - start_date) * random.random()

    def get_external_products_for_user_and_institution(self, user_identifier: Union[str, ObjectId], institution_name: str) -> list[dict]:
        """Retrieve external financial products for a specific user from a specific financial institution.

        Args:
            user_identifier (Union[str, ObjectId]): The user identifier (username or ObjectId of the user).
            institution_name (str): The name of the financial institution (bank).

        Returns:
            list[dict]: A list of external financial products associated with the user.
        """
        if isinstance(user_identifier, ObjectId):
            query = {"ProductCustomer.UserId": user_identifier,
                     "ProductBank": institution_name}
        else:
            query = {"ProductCustomer.UserName": user_identifier,
                     "ProductBank": institution_name}

        external_products = list(self.external_products_collection.find(query))
        return external_products
    
    def get_all_external_products_for_user(self, user_identifier: Union[str, ObjectId]) -> list[dict]:
        """Retrieve all external financial products for a specific user.

        Args:
            user_identifier (Union[str, ObjectId]): The user identifier (username or ObjectId of the user).

        Returns:
            list[dict]: A list of external financial products associated with the user.
        """
        if isinstance(user_identifier, ObjectId):
            query = {"ProductCustomer.UserId": user_identifier}
        else:
            query = {"ProductCustomer.UserName": user_identifier}

        external_products = list(self.external_products_collection.find(query))
        return external_products

# Note:
# MongoDB excels in its flexibility—being able to serve as a central data storage solution for retrieving data from
# external financial institutions while seamlessly supporting diverse formats and structures.
# This implementation demonstrates MongoDB's capability with structural differences between products and the capacity
# to adapt to different schema requirements per bank (or financial institution), enhancing its utility for Open Finance applications where
# accommodating diverse data formats is essential.
