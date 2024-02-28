from pathlib import Path
from datetime import timedelta
from sqlmodel import create_engine
from nats.aio.client import Client as NATS

repo_root = Path(__file__).parent.parent.parent
public_key = Path(repo_root / "certs" / "jwt-public.pem").read_bytes()
private_key = Path(repo_root / "certs" / "jwt-private.pem").read_bytes()
algorithm = "RS256"
expire = timedelta(seconds=500)
engine = create_engine(
    "postgresql://postgres:password@localhost:5432/postgres", echo=True
)
nats_url = "nats://localhost:4222"
