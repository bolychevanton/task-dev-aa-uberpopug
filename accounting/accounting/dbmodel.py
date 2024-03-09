from sqlmodel import SQLModel, Field
from datetime import datetime, date
from typing import Optional


class Account(SQLModel, table=True):
    __tablename__ = "accounting_accounts"
    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    fullname: str
    email: str
    role: str
    billing_cycle: int = Field(default=None, foreign_key="accounting_billing_cycles.id")
    balance: float


class BillingCycle(SQLModel, table=True):
    __tablename__ = "accounting_billing_cycles"
    id: int = Field(default=None, primary_key=True)
    start_date: datetime = Field(default_factory=datetime.now)
    end_date: datetime
    status: str


class Payment(SQLModel, table=True):
    __tablename__ = "accounting_payments"
    id: int = Field(default=None, primary_key=True)
    status: str
    billing_cycle: int = Field(default=None, foreign_key="accounting_billing_cycles.id")


class Task(SQLModel, table=True):
    __tablename__ = "accounting_tasks"
    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    title: str
    description: str
    assigned_to: str = Field(index=True, foreign_key="accounting_accounts.public_id")
    assign_task_cost: float = Field()
    complete_task_cost: float


class Transaction(SQLModel, table=True):
    __tablename__ = "accounting_transactions"
    id: int = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True)
    billing_cycle: int = Field(index=True, foreign_key="accounting_accounts.id")
    account_id: str = Field(index=True, foreign_key="accounting_accounts.public_id")
    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)
    time: datetime = Field(default_factory=datetime.now)
    type: str
    task_public_id: Optional[str] = Field(default=None)
    description: str
