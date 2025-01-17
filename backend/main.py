from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from routers import secure, public
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

# Include the secure router
app.include_router(
    secure.router,
    prefix="/api/v1/secure",
    tags=["secure"]
)

# Include the public router
app.include_router(
    public.router,
    prefix="/api/v1/public",
    tags=["public"]
)