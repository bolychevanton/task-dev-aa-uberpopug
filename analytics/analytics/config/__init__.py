from pathlib import Path

repo_root = Path(__file__).parent.parent.parent.parent
service_root = Path(__file__).parent.parent
db_url = "postgresql+asyncpg://postgres:password@localhost:5432/analytics"
nats_url = "nats://localhost:4222"
public_key = Path(repo_root / "certs" / "jwt-public.pem").read_bytes()
algorithm = "RS256"
