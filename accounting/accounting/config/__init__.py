from pathlib import Path
from datetime import time, timedelta

repo_root = Path(__file__).parent.parent.parent.parent
service_root = Path(__file__).parent.parent
db_url = "postgresql+asyncpg://postgres:password@localhost:5432/accounting"
nats_url = "nats://localhost:4222"
billing_cycle_start = time(hour=0, minute=0, second=0)
billing_cycle_period = timedelta(days=1)
