from pydantic import BaseModel


class UserInfo(BaseModel):
    sub: str
    email_verified: bool
    name: str
    groups: list[str]
    preferred_username: str
    given_name: str
    family_name: str
    email: str
