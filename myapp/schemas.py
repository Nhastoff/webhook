from pydantic import BaseModel


class UserInfo(BaseModel):
    sub: str | None = None
    email_verified: bool | None = None
    name: str | None = None
    group: list[str] | None = None
    preferred_username: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
