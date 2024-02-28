from fastapi import FastAPI, Depends, HTTPException
from common.jwt_decoder import JWTDecoder
from auth.schema import AuthDetails
from auth.jwt_encoder import JWTEncoder
from auth.password import get_password_hash, verify_password
from config import public_key, private_key, expire, algorithm

jwt_encoder = JWTEncoder(key=private_key, algorithm=algorithm, expire=expire)
jwt_decoder = JWTDecoder(key=public_key, algorithm=algorithm)


app = FastAPI()
users = []


@app.post("/register", status_code=201)
def register(auth_details: AuthDetails):
    if any(x["username"] == auth_details.username for x in users):
        raise HTTPException(status_code=400, detail="Username is taken")
    hashed_password = get_password_hash(auth_details.password)
    users.append({"username": auth_details.username, "password": hashed_password})
    return


@app.post("/login")
def login(auth_details: AuthDetails):
    user = None
    for x in users:
        if x["username"] == auth_details.username:
            user = x
            break

    if (user is None) or (not verify_password(auth_details.password, user["password"])):
        raise HTTPException(status_code=401, detail="Invalid username and/or password")
    token = jwt_encoder.encode_token(user["username"])
    return {"token": token}


@app.get("/unprotected")
def unprotected():
    return {"hello": "world"}


@app.get("/protected")
def protected(username=Depends(jwt_decoder)):
    return {"name": username}
