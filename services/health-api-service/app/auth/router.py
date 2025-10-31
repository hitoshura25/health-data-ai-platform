from fastapi import APIRouter, Depends, Response, status, Header, HTTPException, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.models import User
from app.db.session import get_async_session
from app.users import (
    current_active_user as get_current_active_user,
    auth_backend,
    get_user_manager,
    get_jwt_strategy,
)
from app.auth.blocklist import RedisBlocklist, get_blocklist
from app.auth.webauthn_config import webauthn_config
from app.schemas import UserRead, UserCreate
from fastapi_users import models
from fastapi_users.manager import BaseUserManager
from fastapi_users.authentication import JWTStrategy
import jwt

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


class TokenExchangeRequest(BaseModel):
    """Request model for WebAuthn token exchange"""
    webauthn_token: str


class TokenExchangeResponse(BaseModel):
    """Response model for token exchange"""
    access_token: str
    token_type: str = "bearer"
    user: UserRead


@router.post("/auth/webauthn/exchange", response_model=TokenExchangeResponse)
async def exchange_webauthn_token(
    request: TokenExchangeRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    """
    Exchange WebAuthn JWT for Health API JWT.

    Flow:
    1. Verify WebAuthn JWT signature using public key
    2. Extract user identity (sub = username from WebAuthn)
    3. Get or auto-create Health API user
    4. Issue Health API JWT using fastapi-users

    This enables passkey-based authentication:
    - Client authenticates with WebAuthn service → receives WebAuthn JWT
    - Client exchanges WebAuthn JWT → receives Health API JWT
    - Client uses Health API JWT for all subsequent API requests
    """

    try:
        # Verify WebAuthn JWT using JWKS
        # PyJWKClient automatically fetches the signing key from JWKS endpoint
        signing_key = webauthn_config.get_signing_key_from_jwt(request.webauthn_token)

        payload = jwt.decode(
            request.webauthn_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=webauthn_config.issuer,
            audience="webauthn-clients",  # WebAuthn server sets this audience claim
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            }
        )

        webauthn_username = payload["sub"]  # Username from WebAuthn

        # Convert username to email format if not already an email
        # WebAuthn usernames may not be email addresses, so we normalize them
        # Using example.com which is reserved for documentation/testing per RFC 2606
        if "@" not in webauthn_username:
            user_email = f"{webauthn_username}@example.com"
        else:
            user_email = webauthn_username

        logger.info("WebAuthn token verified using JWKS",
                   webauthn_user=webauthn_username,
                   normalized_email=user_email)

    except jwt.ExpiredSignatureError:
        logger.warning("WebAuthn token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebAuthn token expired"
        )
    except jwt.InvalidSignatureError:
        logger.warning("Invalid WebAuthn token signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WebAuthn token signature"
        )
    except jwt.InvalidIssuerError:
        logger.warning("Invalid WebAuthn token issuer")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer"
        )
    except Exception as e:
        logger.error("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}"
        )

    # Get or create Health API user
    result = await db.execute(
        select(User).where(User.email == user_email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create user from WebAuthn identity
        logger.info("Creating new user from WebAuthn identity", email=user_email)

        user_create = UserCreate(
            email=user_email,
            password="webauthn-sso-user-no-password",  # Placeholder for WebAuthn users
            is_verified=True  # Pre-verified via WebAuthn
        )

        try:
            user = await user_manager.create(user_create, safe=False)
            logger.info("User created from WebAuthn", user_id=user.id, email=user.email)
        except Exception as e:
            logger.error("User creation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
    else:
        logger.info("Existing user found", user_id=user.id, email=user.email)

    # Generate Health API JWT
    token = await strategy.write_token(user)

    logger.info("Token exchange successful",
               health_user_id=user.id,
               webauthn_user=webauthn_username)

    return TokenExchangeResponse(
        access_token=token,
        user=UserRead.model_validate(user)
    )
