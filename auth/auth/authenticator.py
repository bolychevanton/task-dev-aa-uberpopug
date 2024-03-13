import jwt

from datetime import datetime, timedelta, timezone


class Authentificator:
    def __init__(self, key: str, algorithm: str, expire: timedelta) -> None:
        self.key = key
        self.algorithm = algorithm
        self.expire = expire

    def encode_token(self, user_public_id: str, role: str):
        payload = {
            "exp": datetime.now(tz=timezone.utc) + self.expire,
            "iat": datetime.now(tz=timezone.utc),
            "public_id": user_public_id,
            "role": role,
        }
        return jwt.encode(payload, self.key, algorithm=self.algorithm)
