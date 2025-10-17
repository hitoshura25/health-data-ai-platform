from fastapi import APIRouter, Depends, Response, status, Header, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from app.db.models import User
from app.users import (
    current_active_user as get_current_active_user,
    auth_backend,
    get_user_manager,
    get_jwt_strategy,
)
from app.auth.blocklist import RedisBlocklist, get_blocklist
from fastapi_users import models
from fastapi_users.manager import BaseUserManager
from fastapi_users.authentication import JWTStrategy

from typing import Annotated
import structlog

router = APIRouter(tags=["Authentication"])
logger = structlog.get_logger()

@router.post("/auth/jwt/login")
async def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    """
    Password-based JWT login endpoint.

    This endpoint authenticates users with email/password and returns a JWT access token.

    Future: Will be replaced or supplemented with WebAuthn token exchange endpoint
    for passkey-based authentication.
    """
    # Authenticate user with password
    user = await user_manager.authenticate(credentials)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Generate JWT token using the JWT strategy
    token = await strategy.write_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/auth/jwt/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: User = Depends(get_current_active_user),
    blocklist: RedisBlocklist = Depends(get_blocklist),
    authorization: Annotated[str | None, Header()] = None,
):
    """
    Logout endpoint that invalidates JWT tokens via Redis blocklist.

    After logout, the token is added to a blocklist and will be rejected
    on subsequent requests until it naturally expires.
    """
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            await blocklist.add(token, 3600)  # expires in 1 hour
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/webauthn/exchange", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def exchange_webauthn_token(
    webauthn_token: str,
):
    """
    [PLACEHOLDER] Exchange WebAuthn service JWT for Health API JWT.

    Future implementation will:
    1. Verify JWT from WebAuthn service (http://webauthn-server:8080)
    2. Extract user information from WebAuthn JWT
    3. Look up or create user in Health API database
    4. Issue Health API JWT with appropriate claims

    This endpoint will enable passkey-based authentication flow:
    - Android client authenticates with WebAuthn service
    - Android client receives WebAuthn JWT
    - Android client exchanges WebAuthn JWT for Health API JWT
    - Android client uses Health API JWT for all subsequent requests
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="WebAuthn integration not yet implemented. Use /auth/jwt/login for now.",
    )
