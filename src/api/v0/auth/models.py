import re
from pydantic import BaseModel, Field, field_validator


# Username validation pattern: alphanumeric, underscores, hyphens only
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class NewTokenRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not USERNAME_PATTERN.match(v):
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )
        # Prevent reserved names
        reserved = {"admin", "moderator", "system", "api", "cdn", "static", "b", "u", "post"}
        if v.lower() in reserved:
            raise ValueError("This username is reserved")
        return v


class RecoveryTokenRequest(BaseModel):
    sk: str = Field(..., min_length=16, max_length=256)
    rk: str = Field(..., min_length=16, max_length=256)


class NewTokenResponse(BaseModel):
    sk: str
    rk: str


class VerifyLoginRequest(BaseModel):
    sk: str = Field(..., min_length=16, max_length=256)


class VerifyLoginResponse(BaseModel):
    username: str
    valid: bool = True
