from pydantic import BaseModel, EmailStr


class RegisterDetails(BaseModel):
    fullname: str
    email: EmailStr
    password: str


class LoginDetails(BaseModel):
    email: EmailStr
    password: str
