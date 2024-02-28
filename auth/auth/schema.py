from pydantic import BaseModel, EmailStr


class AuthDetails(BaseModel):
    fullname: str
    email: EmailStr
    password: str
    role: str
