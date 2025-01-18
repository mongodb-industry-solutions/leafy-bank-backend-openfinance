from bson import ObjectId
from typing import Union
from database.connection import MongoDBConnection

import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class UsersService:
    """This class provides methods to interact with users in the database."""

    def __init__(self, connection: MongoDBConnection, db_name: str, users_collection_name: str):
        """Initialize the UserService with the MongoDB connection and collection name.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.
            users_collection_name (str): The name of the users collection.

        Returns:
            None
        """
        self.users_collection = connection.get_collection(
            db_name, users_collection_name)

    def get_users(self) -> list[dict]:
        """Retrieve all users from the users collection.

        Returns:
            list[dict]: A list of all users in the collection.
        """
        # Retrieve all users from the collection
        logging.info(f"Retrieving all users from the collection...")
        users = list(self.users_collection.find())
        return users

    def get_user(self, user_identifier: Union[str, ObjectId]) -> dict:
        """Retrieve a specific user by UserName or ObjectId.
        Args:
            user_identifier (Union[str, ObjectId]): The user identifier (username or ObjectId of the user).
        Returns:
            dict: The user document if found, otherwise None.
        """
        # Determine if the identifier is an ObjectId or a username
        if isinstance(user_identifier, ObjectId):
            query = {"_id": user_identifier}
        else:
            query = {"UserName": user_identifier}
        # Retrieve the user matching the query
        user = self.users_collection.find_one(query)
        if user:
            logging.info(f"Returning user with ObjectId {user['_id']}")
            return user
        else:
            logging.error("No user found with the given identifier.")
            return None
