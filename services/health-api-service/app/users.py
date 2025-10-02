from typing import Optional
import logging
import structlog

from fastapi import Depends, Request, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin, exceptions
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_async_session
from app.config import settings
from app.schemas import UserCreate
from app.auth.blocklist import get_blocklist, RedisBlocklist

logger = structlog.get_logger()
class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        await self.validate_password(user_create.password, user_create)

        existing_user = await self.user_db.get_by_email(user_create.email)
        if existing_user is not None:
            raise exceptions.UserAlreadyExists()

        user_dict = (
            user_create.create_update_dict()
            if safe
            else user_create.create_update_dict_superuser()
        )
        password = user_dict.pop("password")
        user_dict["hashed_password"] = self.password_helper.hash(password)
        
        # Add first_name and last_name if they exist on the schema
        if hasattr(user_create, "first_name"):
            user_dict["first_name"] = user_create.first_name
        if hasattr(user_create, "last_name"):
            user_dict["last_name"] = user_create.last_name

        created_user = await self.user_db.create(user_dict)

        await self.on_after_register(created_user, request)

        return created_user

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logging.info(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logging.info(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logging.info(f"Verification requested for user {user.id}. Verification token: {token}")

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

class CustomJWTStrategy(JWTStrategy):
    def __init__(self, secret: str, lifetime_seconds: int, blocklist: RedisBlocklist):
        super().__init__(secret, lifetime_seconds)
        self.blocklist = blocklist

    async def read_token(self, token: str, context: Optional[dict] = None) -> Optional[dict]:
        await self.check_active_user(token=token)
        return await super().read_token(token, context)
    
    async def check_active_user(
        self,
        token: str,
    ):
        if await self.blocklist.contains(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

def get_jwt_strategy(blocklist: RedisBlocklist = Depends(get_blocklist)) -> JWTStrategy:
    return CustomJWTStrategy(secret=settings.SECRET_KEY, lifetime_seconds=3600, blocklist=blocklist)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)