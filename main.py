import asyncio
import pprint
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pool import Broker, ChatMessage
from security import decrypt_message, encrypt_message
from utils import (
    encode_query_params,
    redirect_with_error,
)
from vite_utils import get_main_js_manifest

# check if file exists
main_js_manifest = get_main_js_manifest()

templates = Jinja2Templates(directory="templates")
templates.env.globals["main_js_manifest"] = main_js_manifest

broker = Broker(templates)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    unpile_messages_task = asyncio.create_task(broker.unpile_messages())

    yield

    unpile_messages_task.cancel()
    # Clean up the ML models and release the resources


app = FastAPI(lifespan=lifespan)
app.mount("/dist", StaticFiles(directory="dist"), name="dist")

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
            "safe_encoded_username": encode_query_params(encoded_username),
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

    broker.choose_recipient(encoded_username, username, recipient)

    return Response(status_code=200)


@app.post("/send-message")
async def send_message(request: Request):
    # get json body
    body = await request.body()
    print(body)
    data = await request.json()

    encoded_username = str(data["encoded_username"])
    username = decrypt_message(encoded_username)
    message = str(data["message"])
    values = list(data["values"])

    pprint.pprint(data)
    now = datetime.now()

    chat_message = ChatMessage(username, message, values, now)

    broker.send_chat_message(chat_message)

    return Response(status_code=201)


@app.websocket("/ws/{encoded_username}")
async def ws_endpoint(encoded_username: str, websocket: WebSocket):
    username = decrypt_message(encoded_username)

    await websocket.accept()

    try:
        broker.new_user(username, websocket)

        while True:
            await websocket.receive_text()
    except Exception:
        await broker.user_leaves(username)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
