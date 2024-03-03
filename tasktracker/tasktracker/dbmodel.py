from sqlmodel import SQLModel, Field, Column, TEXT
from datetime import datetime
from pydantic import EmailStr


class Account(SQLModel, table=True):
    __tablename__ = "tt_accounts"

    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    fullname: str
    role: str
    email: EmailStr = Field(
        sa_column=Column(TEXT, unique=True, index=True)
    )  # used as login for simplicity    role: str


class Task(SQLModel, table=True):
    __tablename__ = "tt_tasks"

    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    status: str = Field(default="open")
    description: str
    assigned_to: str = Field(foreign_key="tt_accounts.public_id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
