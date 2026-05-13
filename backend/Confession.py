import uuid
import html
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy import (
    create_engine,
    Column,
    Text,
    TIMESTAMP,
    Float
)

from sqlalchemy.orm import (
    sessionmaker,
    declarative_base
)

from datetime import datetime

# -------------------
# PASSWORDS
# -------------------

USER_PASSWORD = "Galaxy1776"

ADMIN_PASSWORD = "VoidDelete999"

MAX_USERS = 50

# -------------------
# DATABASE
# -------------------

DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

app = FastAPI()

# -------------------
# CORS
# -------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# MESSAGE TABLE
# -------------------

class Message(Base):

    __tablename__ = "messages"

    id = Column(Text, primary_key=True)

    content = Column(Text)

    created_at = Column(TIMESTAMP)

# -------------------
# SESSION TABLE
# -------------------

class Session(Base):

    __tablename__ = "sessions"

    id = Column(Text, primary_key=True)

    role = Column(Text)

    last_seen = Column(Float)

# -------------------
# CREATE TABLES
# -------------------

Base.metadata.create_all(bind=engine)

# -------------------
# CLEANUP
# -------------------

def cleanup_sessions():

    db = SessionLocal()

    now = time.time()

    # 24 HOURS
    SESSION_TIMEOUT = 600

    dead = (
        db.query(Session)
        .filter(now - Session.last_seen > SESSION_TIMEOUT)
        .all()
    )

    for s in dead:
        db.delete(s)

    db.commit()

    db.close()

# -------------------
# AUTH
# -------------------

class AuthRequest(BaseModel):
    password: str

@app.post("/enter")
def enter(req: AuthRequest):

    cleanup_sessions()

    role = None

    if req.password == USER_PASSWORD:
        role = "user"

    elif req.password == ADMIN_PASSWORD:
        role = "admin"

    else:
        raise HTTPException(status_code=403)

    db = SessionLocal()

    active_users = db.query(Session).count()

    if active_users >= MAX_USERS:

        db.close()

        raise HTTPException(
            status_code=403,
            detail="Room full"
        )

    session_id = str(uuid.uuid4())

    new_session = Session(
        id=session_id,
        role=role,
        last_seen=time.time()
    )

    db.add(new_session)

    db.commit()

    db.close()

    return {
        "session_id": session_id,
        "role": role
    }

# -------------------
# HEARTBEAT
# -------------------

@app.post("/heartbeat/{session_id}")
def heartbeat(session_id: str):

    db = SessionLocal()

    s = (
        db.query(Session)
        .filter(Session.id == session_id)
        .first()
    )

    if not s:

        db.close()

        return {"ok": False}

    s.last_seen = time.time()

    db.commit()

    db.close()

    return {"ok": True}

# -------------------
# STATS
# -------------------

@app.get("/stats")
def stats():

    cleanup_sessions()

    db = SessionLocal()

    active_users = db.query(Session).count()

    db.close()

    return {
        "active_users": active_users,
        "max_users": MAX_USERS
    }

# -------------------
# POST MESSAGE
# -------------------

class Msg(BaseModel):
    content: str

@app.post("/message/{session_id}")
def post(session_id: str, msg: Msg):

    cleanup_sessions()

    db = SessionLocal()

    s = (
        db.query(Session)
        .filter(Session.id == session_id)
        .first()
    )

    if not s:

        db.close()

        raise HTTPException(status_code=403)

    clean = html.escape(
        msg.content.strip()
    )

    if not clean:

        db.close()

        raise HTTPException(status_code=400)

    new = Message(
        id=str(uuid.uuid4()),
        content=clean,
        created_at=datetime.utcnow()
    )

    db.add(new)

    db.commit()

    db.close()

    return {"ok": True}

# -------------------
# GET MESSAGES
# -------------------

@app.get("/messages")
def get_msgs():

    db = SessionLocal()

    data = (
        db.query(Message)
        .order_by(Message.created_at.asc())
        .limit(30000)
        .all()
    )

    db.close()

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": str(m.created_at)
        }
        for m in data
    ]

# -------------------
# DELETE MESSAGE
# -------------------

@app.delete("/delete/{session_id}/{message_id}")
def delete_message(
    session_id: str,
    message_id: str
):

    cleanup_sessions()

    db = SessionLocal()

    s = (
        db.query(Session)
        .filter(Session.id == session_id)
        .first()
    )

    if not s:

        db.close()

        raise HTTPException(status_code=403)

    if s.role != "admin":

        db.close()

        raise HTTPException(status_code=403)

    msg = (
        db.query(Message)
        .filter(Message.id == message_id)
        .first()
    )

    if not msg:

        db.close()

        raise HTTPException(status_code=404)

    db.delete(msg)

    db.commit()

    db.close()

    return {
        "deleted": True
    }

# -------------------
# ROOT
# -------------------

@app.get("/")
def root():

    return {
        "status": "online"
    }