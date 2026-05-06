import uuid
import html
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Model
class Message(Base):
    __tablename__ = "messages"

    id = Column(Text, primary_key=True)
    content = Column(Text)
    created_at = Column(TIMESTAMP)

Base.metadata.create_all(bind=engine)

# Session storage
active_sessions = set()
connections = {}

# AUTH
class AuthRequest(BaseModel):
    password: str

@app.post("/enter")
def enter(req: AuthRequest):
    if req.password != PASSWORD:
        raise HTTPException(status_code=403)

    if len(active_sessions) >= MAX_USERS:
        raise HTTPException(status_code=403, detail="Room full")

    session_id = str(uuid.uuid4())

    active_sessions.add(session_id)

    return {
        "session_id": session_id
    }

# STATS
@app.get("/stats")
def stats():
    return {
        "active_users": len(active_sessions),
        "max_users": MAX_USERS
    }

# MESSAGE
class Msg(BaseModel):
    content: str

@app.post("/message/{session_id}")
async def post(session_id: str, msg: Msg):

    if session_id not in active_sessions:
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

    # Broadcast
    dead = []

    for sid, ws in connections.items():
        try:
            await ws.send_text(clean)
        except:
            dead.append(sid)

    for sid in dead:
        connections.pop(sid, None)
        active_sessions.discard(sid)

    return {
        "ok": True
    }

# GET MESSAGES
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

# WEBSOCKET
@app.websocket("/ws/{session_id}")
async def ws(ws: WebSocket, session_id: str):

    if session_id not in active_sessions:
        await ws.close()
        return

    await ws.accept()

    connections[session_id] = ws

    try:
        while True:
            await ws.receive_text()

    except WebSocketDisconnect:
        connections.pop(session_id, None)
        active_sessions.discard(session_id)

# RESET
@app.post("/reset")
def reset():
    active_sessions.clear()
    connections.clear()

    return {
        "status": "reset"
    }