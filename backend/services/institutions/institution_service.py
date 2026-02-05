from typing import Optional
from database.connection import MongoDBConnection

import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class InstitutionService:
    """This class provides methods to interact with institutions in the database."""

    def __init__(self, connection: MongoDBConnection, db_name: str, collection_name: str):
        """Initialize the InstitutionService with the MongoDB connection and collection name.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            collection_name (str): The name of the institutions collection.

        Returns:
            None
        """
        self.institutions_collection = connection.get_collection(db_name, collection_name)

    def list_institutions(self) -> list[dict]:
        """Retrieve all institutions.

        Returns:
            list[dict]: A list of all institutions.
        """
        institutions = list(self.institutions_collection.find({}))
        logging.info(f"Retrieved {len(institutions)} institutions")
        return institutions

    def get_institution_by_name(self, institution_name: str) -> Optional[dict]:
        """Retrieve an institution by its name.

        Args:
            institution_name (str): The institution name to search for (InstitutionName field).

        Returns:
            Optional[dict]: The institution document if found, otherwise None.
        """
        institution = self.institutions_collection.find_one(
            {"InstitutionName": institution_name}
        )
        if institution:
            logging.info(f"Institution found: {institution_name}")
        else:
            logging.info(f"No institution found with name: {institution_name}")
        return institution

    def get_active_institutions(self) -> list[dict]:
        """Retrieve all active institutions.

        Returns:
            list[dict]: A list of all active institutions.
        """
        query = {"InstitutionStatus": "Active"}
        institutions = list(self.institutions_collection.find(query))
        logging.info(f"Retrieved {len(institutions)} active institutions")
        return institutions

    def institution_exists(self, institution_name: str) -> bool:
        """Check if an institution exists by name.

        Args:
            institution_name (str): The institution name to check.

        Returns:
            bool: True if institution exists, False otherwise.
        """
        institution = self.institutions_collection.find_one(
            {"InstitutionName": institution_name}
        )
        return institution is not None
