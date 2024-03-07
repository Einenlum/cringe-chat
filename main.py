from utils import encode_query_params, redirect_with_error, redirect_with_query_params
from security import encrypt_message, decrypt_message
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from datetime import datetime
from uuid import uuid4
from faker import Faker
import json

app = FastAPI()

templates = Jinja2Templates(directory="templates")

connected_users: dict[str, WebSocket] = {}
rooms: list[tuple[str, str]] = []


async def _send_connected_users_message():
    msg = f"Users connected: {len(connected_users)}"

    for _, ws in connected_users.items():
        await ws.send_text(msg)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def home(request: Request):
    context = {}
    if request.query_params.get("error"):
        error = request.query_params["error"]

        context["error"] = error

    return templates.TemplateResponse(
        request=request, name="home.html", context=context
    )


@app.get("/chat")
async def chat(request: Request):
    encoded_username = request.query_params.get("encoded_username")
    if not encoded_username:
        return redirect_with_error("/", "Username not provided")

    username = decrypt_message(encoded_username)

    if username in connected_users.keys():
        error = f'Username "{username}" is already taken'

        return redirect_with_error("/", error)

    return templates.TemplateResponse(
        request=request, name="chat.html", context={"username": username}
    )


@app.post("/enter-chat")
async def enter_chat(request: Request):
    data = await request.form()
    username = str(data["username"])

    if username in connected_users.keys():
        error = f'Username "{username}" is already taken'

        return redirect_with_error("/", error)

    encoded_username = encrypt_message(username)

    return redirect_with_query_params("/chat", {"encoded_username": encoded_username})


@app.websocket("/ws/{username}")
async def ws_endpoint(username: str, websocket: WebSocket):
    global connected_users

    await websocket.accept()

    if username in connected_users.keys():
        await websocket.close(reason="Username taken")

    connected_users[username] = websocket

    await _send_connected_users_message()

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except:
        del connected_users[username]
        await _send_connected_users_message()
        await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
