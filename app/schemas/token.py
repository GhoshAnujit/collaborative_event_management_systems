from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str
 
class TokenPayload(BaseModel):
    sub: str | None = None  # subject (user email) 
    exp: int | None = None  # expiration time
    type: str | None = None  # token type (access or refresh) 