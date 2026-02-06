from pydantic import BaseModel, Field

class NewTokenRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=256)

class RecoveryTokenRequest(BaseModel):
    sk: str
    rk: str

class NewTokenResponse(BaseModel):
    sk: str
    rk: str