from pydantic import BaseModel

class NewTokenRequest(BaseModel):
    username: str

class RecoveryTokenRequest(BaseModel):
    sk: str
    rk: str

class NewTokenResponse(BaseModel):
    sk: str
    rk: str