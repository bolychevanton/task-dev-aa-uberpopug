from sqlmodel import SQLModel, Field, Column, TEXT
from pydantic import EmailStr
from datetime import datetime


class Account(SQLModel, table=True):
    __tablename__ = "auth_accounts"

    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    fullname: str
    email: EmailStr = Field(
        sa_column=Column(TEXT, unique=True, index=True)
    )  # used as login for simplicity
    role: str
    password_hash: str
