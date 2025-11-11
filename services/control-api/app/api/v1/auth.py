"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
)
from app.models.schemas import LoginRequest, RefreshTokenRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


# Mock user database (replace with actual database)
MOCK_USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "role": "admin",
    },
    "operator": {
        "username": "operator",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
        "role": "operator",
    },
}


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """
    Login endpoint to obtain access and refresh tokens.

    **Credentials:**
    - username: admin / operator
    - password: secret
    """
    # Get user from mock database
    user = MOCK_USERS.get(request.username)

    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token = create_access_token(request.username, settings)
    refresh_token = create_refresh_token(request.username, settings)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    """
    Refresh access token using a valid refresh token.
    """
    # Decode and validate refresh token
    payload = decode_token(request.refresh_token, settings)

    # Validate token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Extract username
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Create new tokens
    access_token = create_access_token(username, settings)
    refresh_token = create_refresh_token(username, settings)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me")
async def get_current_user_info(
    current_user: str = Depends(get_current_user),
) -> dict[str, str]:
    """
    Get current authenticated user information.
    """
    user = MOCK_USERS.get(current_user)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return {
        "username": user["username"],
        "role": user["role"],
    }
