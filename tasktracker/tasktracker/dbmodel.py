from sqlmodel import SQLModel, Field, Column, TEXT
from datetime import datetime
from pydantic import EmailStr


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    fullname: str
    email: EmailStr = Field(
        sa_column=Column(TEXT, unique=True, index=True)
    )  # used as login for simplicity    role: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    description: str
    assigned_to: str = Field(default=None, foreign_key="accounts.public_id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
