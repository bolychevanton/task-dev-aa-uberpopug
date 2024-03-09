from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
service_root = Path(__file__).parent.parent
db_url = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
nats_url = "nats://localhost:4222"
