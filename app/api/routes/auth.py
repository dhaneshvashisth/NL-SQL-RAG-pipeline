import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel

from app.auth.jwt_handler import create_access_token
from app.auth.models import TokenData
from app.auth.rbac import get_current_user
from app.db.connection import get_pool
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str
    username:     str
    user_id:      int


def verify_password(plain_password: str, hashed_password: str) -> bool:

    return pwd_context.verify(plain_password, hashed_password)


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), pool: asyncpg.Pool = Depends(get_pool)):
    
    logger.info("Login attempt | username=%s", form_data.username)

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, username, hashed_password, role, parent_id, full_name, is_active
            FROM users
            WHERE username = $1
            """,
            form_data.username
        )

    if not user:
        logger.warning("Login failed — user not found | username=%s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    if not verify_password(form_data.password, user["hashed_password"]):
        logger.warning("Login failed — wrong password | username=%s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        parent_id=user["parent_id"]
    )

    logger.info(
        "Login successful | username=%s | role=%s | id=%d",
        user["username"], user["role"], user["id"]
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        username=user["username"],
        user_id=user["id"]
    )


@router.get("/me")
async def get_me(token_data: TokenData = Depends(get_current_user)):
    
    return {
        "user_id":  token_data.user_id,
        "username": token_data.username,
        "role":     token_data.role.value,
        "parent_id": token_data.parent_id
    }