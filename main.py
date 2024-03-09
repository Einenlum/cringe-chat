from pprint import pprint
import json
from utils import (
    redirect_with_error,
    redirect_with_query_params,
    encode_query_params,
    generate_uuid,
)
from security import encrypt_message, decrypt_message
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import server_message_types as server_types
import client_message_types as client_types

app = FastAPI()

templates = Jinja2Templates(directory="templates")

connected_users: dict[str, WebSocket] = {}


async def _send_connected_users_message():
    msg = {"type": "connected_users", "value": len(connected_users.keys())}

    for _, ws in connected_users.items():
        await ws.send_json(msg)


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

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "username": username,
            "encoded_username": encoded_username,
        },
    )


@app.post("/choose-username")
async def choose_username(request: Request):
    data = await request.form()
    username = str(data["username"])

    if username in connected_users.keys():
        error = f'Username "{username}" is already taken'

        return redirect_with_error("/", error)

    encoded_username = encrypt_message(username)

    return redirect_with_query_params("/chat", {"encoded_username": encoded_username})


@app.websocket("/ws/{encoded_username}")
async def ws_endpoint(encoded_username: str, websocket: WebSocket):
    global connected_users

    username = decrypt_message(encoded_username)

    if username in connected_users.keys():
        print("close socket because username taken")
        await websocket.close(reason="Username taken")

    chosen_recipient_username = None
    chosen_recipient = None

    async def new_recipient(recipient):
        nonlocal chosen_recipient_username, chosen_recipient

        chosen_recipient_username = recipient
        chosen_recipient = connected_users[recipient]

        msg = {
            "type": server_types.RECIPIENT_CHOSEN,
            "value": chosen_recipient_username,
        }
        await websocket.send_json(msg)

        msg = {"type": server_types.RECIPIENT_CHOSEN, "value": username}
        await chosen_recipient.send_json(msg)

    async def handle_received_message(data: dict[str, str]):
        nonlocal chosen_recipient

        if data["type"] == client_types.CHOOSE_RECIPIENT:
            recipient = data["value"]

            if recipient not in connected_users.keys():
                msg = {
                    "type": server_types.RECIPIENT_NOT_CONNECTED,
                    "value": "Recipient not found",
                }
                await websocket.send_json(msg)

                return

            await new_recipient(recipient)

            return

        if data["type"] == client_types.SEND_CHAT_MESSAGE:
            if not chosen_recipient:
                msg = {
                    "type": server_types.ERROR,
                    "value": "No recipient",
                }
                await websocket.send_json(msg)

                return

            text = data["value"]
            msg = {
                "type": server_types.CHAT_MESSAGE,
                "value": text,
            }

            await chosen_recipient.send_json(msg)

            return

    await websocket.accept()

    connected_users[username] = websocket

    await _send_connected_users_message()

    try:
        while True:
            data = await websocket.receive_json()

            await handle_received_message(data)
    except Exception as e:
        del connected_users[username]
        await _send_connected_users_message()
        pprint("close socket because exception")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
