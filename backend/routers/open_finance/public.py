from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from secrets import token_hex
from pymongo.collection import Collection
from dependencies import get_tokens_collection
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()


class CreateUserResponse(BaseModel):
    message: str
    UserName: str
    BearerToken: str


limiter = Limiter(key_func=get_remote_address)


@router.post("/create-user", response_model=CreateUserResponse, status_code=201)
@limiter.limit("5/minute")  # Limit to 5 requests per minute for this endpoint
async def create_user(
    request: Request,
    tokens_collection: Collection = Depends(get_tokens_collection),
    max_retries: int = 5
):
    for _ in range(max_retries):
        generated_user_name = f"api_user_{token_hex(4)}"
        existing_user = tokens_collection.find_one(
            {"UserName": generated_user_name})
        if not existing_user:
            new_bearer_token = token_hex(32)

            user_document = {
                "UserName": generated_user_name,
                "BearerToken": new_bearer_token,
                "TokenDates": {
                    "CreationDate": datetime.now(timezone.utc),
                    "LastUseDate": None,
                },
            }

            try:
                tokens_collection.insert_one(user_document)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

            return {
                "message": "User created successfully.",
                "UserName": generated_user_name,
                "BearerToken": new_bearer_token,
            }

    raise HTTPException(
        status_code=500,
        detail="Could not generate a unique UserName after multiple attempts."
    )
