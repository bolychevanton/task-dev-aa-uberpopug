from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from common.jwt_decoder import JWTDecoder
from auth.schema import AuthDetails
from auth.jwt_encoder import JWTEncoder
from auth.password import get_password_hash, verify_password
from config import public_key, private_key, expire, algorithm, engine, nats_url
from auth import dbmodel
from sqlmodel import Session
from datetime import datetime
import nats
from nats.js import JetStreamContext
import json
from contextlib import asynccontextmanager

jwt_encoder = JWTEncoder(key=private_key, algorithm=algorithm, expire=expire)
jwt_decoder = JWTDecoder(key=public_key, algorithm=algorithm)
jetstream: JetStreamContext = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    dbmodel.SQLModel.metadata.create_all(engine)
    nc = await nats.connect(nats_url)
    js = nc.jetstream()
    # await js.add_stream(name="auth", subjects=["auth.>"])
    global jetstream
    jetstream = js
    yield
    # Clean up the ML models and release the resources
    nc.close()


app = FastAPI(lifespan=lifespan)
users = []


@app.post("/register", status_code=201)
async def register(auth_details: AuthDetails):
    if any(x["email"] == auth_details.fullname for x in users):
        raise HTTPException(status_code=400, detail="Username is taken")
    hashed_password = get_password_hash(auth_details.password)
    with Session(engine) as session:
        new_account = dbmodel.Account(
            fullname=auth_details.fullname,
            email=auth_details.email,
            password_hash=hashed_password,
            role=auth_details.role,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        session.add(new_account)
        session.commit()
        event = dict(
            public_id=new_account.public_id,
            fullname=new_account.fullname,
            email=new_account.email,
            role=new_account.role,
        )

    await jetstream.publish("auth.registered", json.dumps(event).encode())
    return {"message": "Account created"}


@app.post("/login")
async def login(auth_details: AuthDetails):
    user = None
    for x in users:
        if x["username"] == auth_details.fullname:
            user = x
            break

    if (user is None) or (not verify_password(auth_details.password, user["password"])):
        raise HTTPException(status_code=401, detail="Invalid username and/or password")
    token = jwt_encoder.encode_token(user["username"])
    return {"token": token}


@app.get("/unprotected")
async def unprotected():
    return {"hello": "world"}


@app.get("/protected")
async def protected(username=Depends(jwt_decoder)):
    return {"name": username}


# with TestClient(app) as client:
#     client.get(headers={"Authorization": f"Bearer {jwt_encoder.encode_token('test')}"})
