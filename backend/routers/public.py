from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from secrets import token_hex
from pymongo.collection import Collection
from dependencies import get_keys_collection
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()


class CreateUserResponse(BaseModel):
    message: str
    UserName: str
    ApiKey: str


limiter = Limiter(key_func=get_remote_address)


@router.post("/create-user", response_model=CreateUserResponse, status_code=201)
@limiter.limit("2/minute")  # Limit to 2 requests per minute for this endpoint
async def create_user(
    request: Request,
    keys_collection: Collection = Depends(get_keys_collection),
    max_retries: int = 5
):
    """
    Create a new user with an autogenerated UserName and API key.

    The UserName is generated automatically with a unique 8-character hexadecimal string.
    An API key is also generated and stored alongside the UserName in the database.

    Args:
        keys_collection (Collection): The MongoDB collection where the keys are stored.
        max_retries (int): Maximum number of attempts to generate a unique UserName.

    Returns:
        CreateUserResponse: The response containing the new UserName and API key.

    Raises:
        HTTPException: If a unique UserName cannot be generated and inserted into the database.
    """
    for _ in range(max_retries):
        generated_user_name = f"api_user_{token_hex(4)}"
        existing_user = keys_collection.find_one(
            {"UserName": generated_user_name})
        if not existing_user:
            new_api_key = token_hex(32)

            user_document = {
                "UserName": generated_user_name,
                "ApiKey": new_api_key,
                "ApiKeyDates": {
                    "CreationDate": datetime.now(timezone.utc),
                    "LastUseDate": None,
                },
            }

            try:
                keys_collection.insert_one(user_document)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

            return {
                "message": "User created successfully.",
                "UserName": generated_user_name,
                "ApiKey": new_api_key,
            }

    raise HTTPException(
        status_code=500,
        detail="Could not generate a unique UserName after multiple attempts."
    )
