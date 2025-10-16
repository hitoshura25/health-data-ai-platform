from fastapi import APIRouter, Depends, Response, status, Header
from app.db.models import User
from app.users import current_active_user as get_current_active_user
from app.auth.blocklist import RedisBlocklist, get_blocklist

from typing import Annotated
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.post("/auth/jwt/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: User = Depends(get_current_active_user),
    blocklist: RedisBlocklist = Depends(get_blocklist),
    authorization: Annotated[str | None, Header()] = None,
):
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            await blocklist.add(token, 3600) # expires in 1 hour
    return Response(status_code=status.HTTP_204_NO_CONTENT)
