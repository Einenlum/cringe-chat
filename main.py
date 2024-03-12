import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from security import decrypt_message, encrypt_message
from unpile_messages import Broker
from utils import (
    redirect_with_error,
)

broker = Broker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    unpile_messages_task = asyncio.create_task(broker.unpile_messages())

    yield

    unpile_messages_task.cancel()
    # Clean up the ML models and release the resources


app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")


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


@app.post("/choose-username")
async def choose_username(request: Request):
    data = await request.form()
    username = str(data["username"])

    if username in broker.connected_users.keys():
        error = f'Username "{username}" is already taken'

        return redirect_with_error(request, "/", error)

    encoded_username = encrypt_message(username)

    return templates.TemplateResponse(
        request=request,
        name="htmx/choose-recipient.html",
        context={
            "username": username,
            "encoded_username": encoded_username,
        },
    )


@app.get("/chat")
async def chat(request: Request):
    encoded_username = request.query_params.get("encoded_username")
    if not encoded_username:
        return redirect_with_error(request, "/", "Username not provided")

    username = decrypt_message(encoded_username)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "username": username,
            "encoded_username": encoded_username,
        },
    )


@app.post("/choose-recipient")
async def choose_recipient(request: Request):
    data = await request.form()
    recipient = str(data["recipient"])
    encoded_username = str(data["encoded_username"])
    username = decrypt_message(encoded_username)

    error = None
    if username not in broker.connected_users.keys():
        error = f'Username "{username}" is not connected'

    if recipient not in broker.connected_users.keys():
        error = f'Recipient "{recipient}" is not connected'

    if error:
        return templates.TemplateResponse(
            request=request,
            name="htmx/choose-recipient.html",
            context={
                "username": username,
                "encoded_username": encoded_username,
                "error": error,
            },
        )

    await broker.new_room_for_users(username, recipient)

    return templates.TemplateResponse(
        request=request,
        name="htmx/chat.html",
        context={
            "username": username,
            "encoded_username": encoded_username,
            "recipient": recipient,
            "error": error,
        },
    )


# @app.post("/send-message")
# async def send_message(request: Request):
#     data = await request.form()
#     encoded_username = str(data["encoded_username"])
#     username = decrypt_message(encoded_username)
#     message = str(data["message"])

#     if username not in connected_users.keys():
#         error = f'Username "{username}" is not connected'

#         return redirect_with_error("/", error)

#     if not message:
#         error = "Message cannot be empty"

#         return redirect_with_error("/chat", error)

#     if (room := _get_room_for_user(username)) is None:
#         error = "No recipient"

#         return redirect_with_error("/chat", error)

#     recipient = _get_recipient_for_user(room, username)
#     if recipient is None:
#         error = "No recipient"

#         return redirect_with_error("/chat", error)
#     recipient_user = connected_users[recipient]

#     return templates.TemplateResponse(
#         request=request,
#         name="htmx/own-message.html",
#         context={
#             "time": datetime.now().strftime("%H:%M:%S"),
#             "message": message,
#         },
#         status_code=201,
#     )


@app.websocket("/ws/{encoded_username}")
async def ws_endpoint(encoded_username: str, websocket: WebSocket):
    username = decrypt_message(encoded_username)

    await websocket.accept()

    try:
        await broker.new_user(username, websocket)

        while True:
            await websocket.receive_text()
    except Exception:
        await broker.user_leaves(username)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
