import uuid
import html
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy import create_engine, Column, Text, TIMESTAMP
from sqlalchemy.orm import sessionmaker, declarative_base

from datetime import datetime

PASSWORD = "Galaxy1776"
MAX_USERS = 50

DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL)

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
# DATABASE
# -------------------

class Message(Base):

    __tablename__ = "messages"

    id = Column(Text, primary_key=True)

    content = Column(Text)

    created_at = Column(TIMESTAMP)

Base.metadata.create_all(bind=engine)

# -------------------
# SESSION STORAGE
# -------------------

sessions = {}

# -------------------
# CLEANUP
# -------------------

def cleanup_sessions():

    now = time.time()

    dead = []

    for sid, last_seen in sessions.items():

        if now - last_seen > 30:
            dead.append(sid)

    for sid in dead:
        sessions.pop(sid, None)

# -------------------
# AUTH
# -------------------

class AuthRequest(BaseModel):
    password: str

@app.post("/enter")
def enter(req: AuthRequest):

    cleanup_sessions()

    if req.password != PASSWORD:
        raise HTTPException(status_code=403)

    if len(sessions) >= MAX_USERS:
        raise HTTPException(
            status_code=403,
            detail="Room full"
        )

    session_id = str(uuid.uuid4())

    sessions[session_id] = time.time()

    return {
        "session_id": session_id
    }

# -------------------
# HEARTBEAT
# -------------------

@app.post("/heartbeat/{session_id}")
def heartbeat(session_id: str):

    if session_id in sessions:

        sessions[session_id] = time.time()

        return {"ok": True}

    return {"ok": False}

# -------------------
# STATS
# -------------------

@app.get("/stats")
def stats():

    cleanup_sessions()

    return {
        "active_users": len(sessions),
        "max_users": MAX_USERS
    }

# -------------------
# MESSAGE
# -------------------

class Msg(BaseModel):
    content: str

@app.post("/message/{session_id}")
def post(session_id: str, msg: Msg):

    cleanup_sessions()

    if session_id not in sessions:
        raise HTTPException(status_code=403)

    clean = html.escape(msg.content.strip())

    if not clean:
        raise HTTPException(status_code=400)

    db = SessionLocal()

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
        .limit(100)
        .all()
    )

    db.close()

    return [
        {
            "content": m.content,
            "timestamp": str(m.created_at)
        }
        for m in data
    ]