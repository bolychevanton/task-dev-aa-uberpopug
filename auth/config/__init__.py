from pathlib import Path
from datetime import timedelta

repo_root = Path(__file__).parent.parent.parent
public_key = Path(repo_root / "certs" / "jwt-public.pem").read_bytes()
private_key = Path(repo_root / "certs" / "jwt-private.pem").read_bytes()
algorithm = "RS256"
expire = timedelta(seconds=500)
