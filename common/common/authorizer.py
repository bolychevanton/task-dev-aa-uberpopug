import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class Authorizer:
    def __init__(self, key: str, algorithm: str):
        self.key = key
        self.algorithm = algorithm

    def decode_token(self, token):
        try:
            payload = jwt.decode(token, self.key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Signature has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail="Invalid token")

    def __call__(self, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        return self.decode_token(auth.credentials)["public_id"]

    def restrict_access(self, to: list[str]):
        def callback_with_restricted_roles(
            auth: HTTPAuthorizationCredentials = Security(HTTPBearer()),
        ):
            payload = self.decode_token(auth.credentials)
            if not payload["role"] in to:
                raise HTTPException(status_code=403, detail="Forbidden")

            return payload["public_id"]

        return callback_with_restricted_roles
