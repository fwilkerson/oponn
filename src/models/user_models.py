from pydantic import BaseModel


class User(BaseModel):
    id: str
    email: str
    provider: str
    provider_id: str
