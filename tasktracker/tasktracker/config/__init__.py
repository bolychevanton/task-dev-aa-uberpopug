from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
public_key = Path(repo_root / "certs" / "jwt-public.pem").read_bytes()
algorithm = "RS256"
db_url = "postgresql+asyncpg://postgres:password@localhost:5432/postgres"
nats_url = "nats://localhost:4222"
