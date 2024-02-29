import jwt

from datetime import datetime, timedelta, timezone


class JWTEncoder:
    def __init__(self, key: str, algorithm: str, expire: timedelta) -> None:
        self.key = key
        self.algorithm = algorithm
        self.expire = expire

    def encode_token(self, user_public_id):
        payload = {
            "exp": datetime.now(tz=timezone.utc) + self.expire,
            "iat": datetime.now(tz=timezone.utc),
            "sub": user_public_id,
        }
        return jwt.encode(payload, self.key, algorithm=self.algorithm)
