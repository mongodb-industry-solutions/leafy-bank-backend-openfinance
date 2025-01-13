import json
from datetime import datetime
from bson import ObjectId

# Inspired by https://sentry.io/answers/fastapi-and-mongodb-objectid-object-is-not-iterable-error/#solution-2-define-a-custom-jsonencoder-class

class MyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for encoding ObjectId and datetime objects.

    Args:
        json (_type_): The JSON encoder class to inherit from.
    """
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)  # Convert ObjectId to string
        if isinstance(o, datetime):
            return o.isoformat()  # Convert datetime to ISO 8601 string
        return super().default(o)