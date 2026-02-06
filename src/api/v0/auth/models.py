from pydantic import BaseModel

class NewTokenRequest(BaseModel):
    username: str

class RotateTokenRequest(BaseModel):
    sk: str
    rk: str

class NewTokenRespone(BaseModel):
    sk: str