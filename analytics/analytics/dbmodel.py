from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class Account(SQLModel, table=True):
    __tablename__ = "analytics_accounts"
    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    fullname: str
    email: str
    role: str


class Task(SQLModel, table=True):
    __tablename__ = "analytics_tasks"
    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    title: str
    description: str
    assign_task_cost: Optional[float] = Field(default=None)
    complete_task_cost: Optional[float] = Field(default=None)


class Transaction(SQLModel, table=True):
    __tablename__ = "analytics_transactions"
    id: int = Field(default=None, primary_key=True)
    account_public_id: str = Field(index=True)
    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)
    time: datetime = Field(default_factory=datetime.now)
    type: str
    description: str
