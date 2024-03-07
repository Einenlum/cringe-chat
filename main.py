from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from uuid import uuid4
import json

app = FastAPI()

connected_users = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websockets("/ws/{username}")
async def ws_endpoint(username: str, websocket: WebSocket):
    await websocket.accept()

    if username in connected_users.keys():
        await websocket.close(reason="Username taken")

    connected_users[username] = websocket
