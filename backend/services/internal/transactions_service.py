from bson import ObjectId
from typing import Union
from pymongo.client_session import ClientSession
from datetime import datetime, timezone
import logging
from database.connection import MongoDBConnection

from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class TransactionsService:
    """This class provides methods to perform transactions in the database."""

    def __init__(self, connection: MongoDBConnection, db_name: str):
        """Initialize the TransactionsService with the MongoDB connection and database name.

        Args:
            connection (MongoDBConnection): The MongoDB connection instance.
            db_name (str): The name of the database.

        Returns:
            None
        """
        self.db = connection.get_database(db_name)
        self.accounts_collection = self.db['accounts']
        self.transactions_collection = self.db['transactions']
        self.users_collection = self.db['users']
        self.notifications_collection = self.db['notifications']

    def is_valid_user(self, user_identifier: Union[str, ObjectId]) -> bool:
        """Check if the user exists in the system.
        Args:
            user_identifier (Union[str, ObjectId]): The user identifier (username or ObjectId of the user).
        Returns:
            bool: True if the user exists, False otherwise.
        """
        if isinstance(user_identifier, ObjectId):
            user_query = {"_id": user_identifier}
        else:
            user_query = {"UserName": user_identifier}
        user = self.users_collection.find_one(user_query, {"_id": 1})
        return user is not None

    def get_recent_transactions_for_user(self, user_identifier: Union[str, ObjectId]) -> list[dict]:
        """Get the recent transactions for a specific user by UserName or ID.
        Args:
            user_identifier (Union[str, ObjectId]): The UserName or ID of the user.
        Returns:
            list[dict]: A list of recent transactions for the user.
        """
        # Determining if the identifier is an ObjectId or a username
        if isinstance(user_identifier, ObjectId):
            user_query = {"_id": user_identifier}
        else:
            user_query = {"UserName": user_identifier}
        # Fetching the user document
        user = self.users_collection.find_one(
            user_query, {"RecentTransactions": 1})
        if not user or "RecentTransactions" not in user:
            logging.info(
                f"No recent transactions found for user {user_identifier}")
            return []
        # Extracting the recent transaction IDs, sorted by date descending and limited to 20
        recent_transactions = sorted(
            user["RecentTransactions"], key=lambda x: x["Date"], reverse=True)[:20]
        transaction_ids = [txn["TransactionId"] for txn in recent_transactions]
        # Fetching the transaction details from the transactions collection
        transactions = list(self.transactions_collection.find(
            {"_id": {"$in": transaction_ids}}))
        # Sorting the transactions by the most recent date in the TransactionDates array
        transactions.sort(key=lambda x: max(
            date["TransactionDate"] for date in x["TransactionDates"]), reverse=True)
        return transactions

    def perform_transaction(self, account_id_receiver: str, account_id_sender: str,
                            transaction_amount: float, sender_user_id: str, sender_user_name: str,
                            sender_account_number: str, sender_account_type: str, receiver_user_id: str,
                            receiver_user_name: str, receiver_account_number: str, receiver_account_type: str,
                            transaction_type: str, transaction_description: Optional[str] = "N/A", payment_method: Optional[str] = "N/A") -> ObjectId:
        """Perform a transaction between two accounts.

        Args:
            account_id_receiver (str): The ID of the receiver's account.
            account_id_sender (str): The ID of the sender's account.
            transaction_amount (float): The amount to transfer.
            sender_user_id (str): The ID of the sender user.
            sender_user_name (str): The name of the sender user.
            sender_account_number (str): The account number of the sender.
            sender_account_type (str): The account type of the sender.
            receiver_user_id (str): The ID of the receiver user.
            receiver_user_name (str): The name of the receiver user.
            receiver_account_number (str): The account number of the receiver.
            receiver_account_type (str): The account type of the receiver.
            transaction_type (str): The type of transaction (e.g., AccountTransfer, DigitalPayment).
            transaction_description (str, Optional): The description of the transaction.
            payment_method (str, Optional): The payment method used if the transaction is a DigitalPayment.

        Returns:
            ObjectId: The ID of the transaction document if the transaction is successful, None otherwise
        """

        # In Python, type hints (like float in function signature) are not enforced at runtime.
        # This means that even if you specify transaction_amount: float, the actual value passed to the function can still be an integer if it's not explicitly converted to a float.
        # Ensure transaction_amount is a float
        # Validate that transaction_amount is a float
        try:
            transaction_amount = float(transaction_amount)
        except ValueError:
            logging.error("Transaction amount must be a float.")
            return None

        # Check if the transaction amount is valid
        if transaction_amount <= 0:
            logging.error("Transaction amount must be greater than 0.")
            return None

        transaction_limit = float(500)

        # Check if the transaction amount exceeds the limit
        if transaction_amount > transaction_limit:
            logging.error(
                f"Transaction amount exceeds the limit of {transaction_limit}.")
            return None

        # Retrieve and validate sender account details
        sender_account = self.accounts_collection.find_one(
            {"_id": ObjectId(account_id_sender)})
        if not sender_account:
            logging.error("Sender account not found.")
            return None
        if sender_account["AccountBalance"] < transaction_amount:
            logging.error("Insufficient funds in sender account.")
            return None
        if sender_account["AccountStatus"] == "Closed":
            logging.error("Sender account is closed.")
            return None
        if (sender_account["AccountNumber"] != sender_account_number or
                sender_account["AccountType"] != sender_account_type):
            logging.error("Sender account details do not match.")
            return None

        # Retrieve and validate sender user details
        sender_user = self.users_collection.find_one(
            {"_id": ObjectId(sender_user_id)})
        if not sender_user or sender_user["UserName"] != sender_user_name:
            logging.error("Sender user details do not match.")
            return None

        # Retrieve and validate receiver account details
        receiver_account = self.accounts_collection.find_one(
            {"_id": ObjectId(account_id_receiver)})
        if not receiver_account:
            logging.error("Receiver account not found.")
            return None
        if receiver_account["AccountStatus"] == "Closed":
            logging.error("Receiver account is closed.")
            return None
        if (receiver_account["AccountNumber"] != receiver_account_number or
                receiver_account["AccountType"] != receiver_account_type):
            logging.error("Receiver account details do not match.")
            return None

        # Retrieve and validate receiver user details
        receiver_user = self.users_collection.find_one(
            {"_id": ObjectId(receiver_user_id)})
        if not receiver_user or receiver_user["UserName"] != receiver_user_name:
            logging.error("Receiver user details do not match.")
            return None

        def callback(session: ClientSession):
            # Create the transaction document

            if sender_user_name == receiver_user_name and sender_account_number == receiver_account_number:
                logging.error("Cannot transfer to the same account!")
                return False

            transaction_internal = False

            if sender_user_name == receiver_user_name and sender_account_number != receiver_account_number:
                transaction_internal = True

            transaction = {
                "TransactionAmount": transaction_amount,
                "TransactionDescription": transaction_description,
                "TransactionDetails": {
                    "TransactionType": transaction_type,
                    "TransactionInternal": transaction_internal,
                },
                "TransactionReferenceData": {
                    "TransactionSender": {
                        "UserId": ObjectId(sender_user_id),
                        "UserName": sender_user_name,
                        "AccountId": ObjectId(account_id_sender),
                        "AccountNumber": sender_account_number,
                        "AccountType": sender_account_type,
                    },
                    "TransactionReceiver": {
                        "UserId": ObjectId(receiver_user_id),
                        "UserName": receiver_user_name,
                        "AccountId": ObjectId(account_id_receiver),
                        "AccountNumber": receiver_account_number,
                        "AccountType": receiver_account_type,
                    },
                },
                "TransactionDates": [
                    {
                        "TransactionDate": datetime.now(timezone.utc),
                        "TransactionDateType": "TransactionInitiatedDate",
                    }
                ],
                "TransactionStatus": "Initiated",
                "TransactionCompleted": False,
                "TransactionNotified": False,
            }

            # Add payment method if it's a DigitalPayment
            if transaction_type == "DigitalPayment" and payment_method:
                transaction["TransactionDetails"]["TransactionPaymentMethod"] = payment_method

            # Update sender account: subtract transaction amount from balance
            sender_result = self.accounts_collection.find_one_and_update(
                {"_id": ObjectId(account_id_sender)},
                {
                    "$inc": {"AccountBalance": -transaction_amount}
                },
                session=session,
                return_document=True
            )
            # Update receiver account: add transaction amount to balance
            receiver_result = self.accounts_collection.find_one_and_update(
                {"_id": ObjectId(account_id_receiver)},
                {
                    "$inc": {"AccountBalance": transaction_amount}
                },
                session=session,
                return_document=True
            )

            # Add new transaction to 'transactions' collection
            transaction_id = self.transactions_collection.insert_one(
                transaction, session=session).inserted_id

            # Update the transaction document with the completed date and status
            self.transactions_collection.update_one(
                {"_id": transaction_id},
                {
                    "$set": {
                        "TransactionStatus": "Completed",
                        "TransactionCompleted": True
                    },
                    "$push": {
                        "TransactionDates": {
                            "TransactionDate": datetime.now(timezone.utc),
                            "TransactionDateType": "TransactionCompletedDate"
                        }
                    }
                },
                session=session
            )

            # Update RecentTransactions
            if transaction_internal:
                # Internal transaction, update only once
                self.users_collection.update_one(
                    {"_id": ObjectId(sender_user_id)},
                    {
                        "$push": {
                            "RecentTransactions": {
                                "$each": [{"TransactionId": transaction_id, "Date": datetime.now(timezone.utc)}],
                                "$slice": -20
                            }
                        }
                    },
                    session=session
                )
            else:
                # Update RecentTransactions for sender
                self.users_collection.update_one(
                    {"_id": ObjectId(sender_user_id)},
                    {
                        "$push": {
                            "RecentTransactions": {
                                "$each": [{"TransactionId": transaction_id, "Date": datetime.now(timezone.utc)}],
                                "$slice": -20
                            }
                        }
                    },
                    session=session
                )
                # Update RecentTransactions for receiver
                self.users_collection.update_one(
                    {"_id": ObjectId(receiver_user_id)},
                    {
                        "$push": {
                            "RecentTransactions": {
                                "$each": [{"TransactionId": transaction_id, "Date": datetime.now(timezone.utc)}],
                                "$slice": -20
                            }
                        }
                    },
                    session=session
                )

            # Create notifications
            notification_date = datetime.now(timezone.utc)

            notification_accounts = {
                "AccountIdSender": ObjectId(account_id_sender),
                "AccountNumberSender": sender_account_number,
                "AccountTypeSender": sender_account_type,
                "AccountIdReceiver": ObjectId(account_id_receiver),
                "AccountNumberReceiver": receiver_account_number,
                "AccountTypeReceiver": receiver_account_type
            }
            if transaction_internal:
                # Internal transaction, create a single notification
                notification = {
                    "NotificationEvent": "InternalTransfer",
                    "NotificationMessage": f"You have transferred {sender_result['AccountCurrency']} {transaction_amount} internally!",
                    "NotificationDate": notification_date,
                    "NotificationUser": {
                        "UserName": sender_user_name,
                        "UserId": ObjectId(sender_user_id)
                    },
                    "NotificationTransaction": {
                        "TransactionId": transaction_id
                    },
                    "NotificationAccounts": notification_accounts
                }
                self.notifications_collection.insert_one(notification, session=session)
            else:
                # Create separate notifications for sender and receiver
                if transaction_type == "AccountTransfer":
                    sender_notification = {
                        "NotificationEvent": "TransferSent",
                        "NotificationMessage": f"You have transferred {sender_result['AccountCurrency']} {transaction_amount} to {receiver_user_name}. Your new balance is {sender_result['AccountCurrency']} {sender_result['AccountBalance']}.",
                        "NotificationDate": notification_date,
                        "NotificationUser": {
                            "UserName": sender_user_name,
                            "UserId": ObjectId(sender_user_id)
                        },
                        "NotificationTransaction": {
                            "TransactionId": transaction_id
                        },
                        "NotificationAccounts": notification_accounts
                    }
                    receiver_notification = {
                        "NotificationEvent": "TransferReceived",
                        "NotificationMessage": f"You have received a transfer of {receiver_result['AccountCurrency']} {transaction_amount} from {sender_user_name}. Your new balance is {receiver_result['AccountCurrency']} {receiver_result['AccountBalance']}.",
                        "NotificationDate": notification_date,
                        "NotificationUser": {
                            "UserName": receiver_user_name,
                            "UserId": ObjectId(receiver_user_id)
                        },
                        "NotificationTransaction": {
                            "TransactionId": transaction_id
                        },
                        "NotificationAccounts": notification_accounts
                    }
                else:  # Assuming the other type is DigitalPayment
                    sender_notification = {
                        "NotificationEvent": "PaymentMade",
                        "NotificationMessage": f"You have made a payment of {sender_result['AccountCurrency']} {transaction_amount} to {receiver_user_name} using {payment_method}. Your new balance is {sender_result['AccountCurrency']} {sender_result['AccountBalance']}.",
                        "NotificationDate": notification_date,
                        "NotificationUser": {
                            "UserName": sender_user_name,
                            "UserId": ObjectId(sender_user_id)
                        },
                        "NotificationTransaction": {
                            "TransactionId": transaction_id
                        },
                        "NotificationAccounts": notification_accounts
                    }
                    receiver_notification = {
                        "NotificationEvent": "PaymentReceived",
                        "NotificationMessage": f"You have received a payment of {receiver_result['AccountCurrency']} {transaction_amount} from {sender_user_name} via {payment_method}. Your new balance is {receiver_result['AccountCurrency']} {receiver_result['AccountBalance']}.",
                        "NotificationDate": notification_date,
                        "NotificationUser": {
                            "UserName": receiver_user_name,
                            "UserId": ObjectId(receiver_user_id)
                        },
                        "NotificationTransaction": {
                            "TransactionId": transaction_id
                        },
                        "NotificationAccounts": notification_accounts
                    }
                self.notifications_collection.insert_many([sender_notification, receiver_notification], session=session)

            # Update the transaction document with the notified date, status, and notification flag
            self.transactions_collection.update_one(
                {"_id": transaction_id},
                {
                    "$set": {
                        "TransactionStatus": "Notified",
                        "TransactionNotified": True
                    },
                    "$push": {
                        "TransactionDates": {
                            "TransactionDate": datetime.now(timezone.utc),
                            "TransactionDateType": "TransactionNotifiedDate"
                        }
                    }
                },
                session=session
            )

            logging.info("Transaction completed!")
            return transaction_id

        # Start a client session and execute the transaction
        with self.db.client.start_session() as session:
            # Ensure multi-document ACID transactions:
            # 1. Atomicity:
            #    - The `with_transaction` method is used to execute a series of operations as a single transaction.
            #    - If any operation within the transaction fails, all operations are rolled back, ensuring atomicity.
            #
            # 2. Consistency:
            #    - MongoDB ensures the database transitions from one consistent state to another during the transaction.
            #    - Operations like updating account balances and inserting transaction documents preserve data integrity.
            #
            # 3. Isolation:
            #    - The transaction operates in an isolated environment.
            #    - Changes are not visible to other operations until the transaction is successfully committed.
            #
            # 4. Durability:
            #    - Transaction changes are written to the oplog of the replica set.
            #    - Once committed, changes are durable and can endure server failures.
            #
            # - The code uses a callback function with `session.with_transaction(callback)` to execute the transaction.
            # - This includes multiple updates and inserts across different collections (accounts, transactions, users, notifications).
            # - Wrapping operations in a transaction ensures execution with ACID properties.
            #
            # For more details, see: https://www.mongodb.com/products/capabilities/transactions
            try:
                transaction_id = session.with_transaction(callback)
                return transaction_id
            except Exception as e:
                logging.error(f"Transaction failed: {e}")
                return None
