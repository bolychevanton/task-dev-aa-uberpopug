"""Facilitates the creation of Avro schemas from Pydantic models, thus, simplifying the process of creating schemas"""

from dataclasses_avroschema.pydantic import AvroBaseModel
from enum import Enum
from datetime import datetime
from pathlib import Path
import json

schemas = Path(__file__).parent


def save_schema(schema: AvroBaseModel, path: Path) -> Path:
    p = path / schema.Name.name.value
    p.mkdir(parents=True, exist_ok=True)
    save_path = p / (schema.Version.version.value + ".json")
    save_path.write_text(json.dumps(schema.avro_schema_to_python(), indent=4))
    return save_path


class AccountCreatedV1(AvroBaseModel):
    class Name(Enum):
        name = "AccountCreated"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        account_public_id: str
        fullname: str
        email: str
        role: str

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "auth"
    data: Data


save_schema(AccountCreatedV1, schemas / "auth")


class AccountUpdatedV1(AvroBaseModel):
    class Name(Enum):
        name = "AccountUpdated"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        account_public_id: str
        role: str

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "auth"
    data: Data


save_schema(AccountUpdatedV1, schemas / "auth")


class TaskAssignedV1(AvroBaseModel):
    class Name(Enum):
        name = "TaskAssigned"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        assigned_to: str
        task_public_id: str

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "tasktracker"
    data: Data


save_schema(TaskAssignedV1, schemas / "tasktracker")


class TaskCompletedV1(AvroBaseModel):
    class Name(Enum):
        name = "TaskCompleted"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        task_public_id: str

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "tasktracker"
    data: Data


save_schema(TaskCompletedV1, schemas / "tasktracker")


class TaskAddedV1(AvroBaseModel):
    class Name(Enum):
        name = "TaskAdded"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        title: str
        description: str
        task_public_id: str
        assigned_to: str

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "tasktracker"
    data: Data


save_schema(TaskAddedV1, schemas / "tasktracker")


class TaskAddedV2(AvroBaseModel):
    class Name(Enum):
        name = "TaskAdded"

    class Version(Enum):
        version = "v2"

    class Data(AvroBaseModel):
        title: str
        jira_id: int
        description: str
        task_public_id: str
        assigned_to: str

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "tasktracker"
    data: Data


save_schema(TaskAddedV2, schemas / "tasktracker")


class FinTransactionAppliedV1(AvroBaseModel):
    class Name(Enum):
        name = "FinTransactionApplied"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        class TransactionType(Enum):
            enrollment = "enrollment"
            withdrawal = "withdrawal"
            payment = "payment"

        billing_cycle_id: int
        billing_cycle_start: datetime
        billing_cycle_end: datetime
        account_public_id: str
        type: TransactionType
        description: str
        amount: float

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "accounting"
    data: Data


save_schema(FinTransactionAppliedV1, schemas / "accounting")


class TaskCostsGeneratedV1(AvroBaseModel):
    class Name(Enum):
        name = "TaskCostsGenerated"

    class Version(Enum):
        version = "v1"

    class Data(AvroBaseModel):
        task_public_id: str
        assign_cost: float
        complete_cost: float

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "accounting"
    data: Data


save_schema(TaskCostsGeneratedV1, schemas / "accounting")


class EndOfDayHappenedV1(AvroBaseModel):
    class Name(Enum):
        name = "EndOfDayHappened"

    class Version(Enum):
        version = "v1"

    id: str
    time: datetime
    name: Name = Name.name
    version: Version = Version.version
    producer: str = "accounting"


save_schema(EndOfDayHappenedV1, schemas / "accounting")
