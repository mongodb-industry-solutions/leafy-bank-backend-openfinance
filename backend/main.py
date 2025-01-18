from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from routers.open_finance import secure as of_secure
from routers.open_finance import public as of_public
from routers.leafy_bank.accounts import secure as lb_accounts_secure
from routers.leafy_bank.users import secure as lb_users_secure
from routers.leafy_bank.transactions import secure as lb_transactions_secure

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set up the Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# Initialize the FastAPI app
app = FastAPI()

# Add SlowAPI Middleware
app.state.limiter = limiter
app.add_middleware(
    SlowAPIMiddleware
)

# Include CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom handler for RateLimitExceeded exceptions
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# Root route
@app.get("/")
async def read_root(request: Request):
    return {"message": "Server is running"}

# Open Finance API routes

# Include the Open Finance public router
app.include_router(
    of_public.router,
    prefix="/api/v1/openfinance/public",
    tags=["Open Finance Public Endpoints"]
)

# Include the Open Finance secure router
app.include_router(
    of_secure.router,
    prefix="/api/v1/openfinance/secure",
    tags=["Open Finance Secure Endpoints"]
)

# Leafy Bank API routes

# Include the Leafy Bank accounts secure router
app.include_router(
    lb_accounts_secure.router,
    prefix="/api/v1/leafybank/accounts/secure",
    tags=["Leafy Bank Secure Accounts Endpoints"]
)

# Include the Leafy Bank accounts secure router
app.include_router(
    lb_users_secure.router,
    prefix="/api/v1/leafybank/users/secure",
    tags=["Leafy Bank Secure Users Endpoints"]
)

# Include the Leafy Bank transactions secure router
app.include_router(
    lb_transactions_secure.router,
    prefix="/api/v1/leafybank/transactions/secure",
    tags=["Leafy Bank Secure Transactions Endpoints"]
)
