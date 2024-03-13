import asyncio
import datetime
from dataclasses import dataclass

from fastapi import WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocketState

from security import encrypt_message
from server_message_types import (
    ROOM_KILLED,
)
from utils import encode_query_params


@dataclass
class Room:
    users: tuple[str, str]


@dataclass
class ConnectedUser:
    username: str
    ws: WebSocket


@dataclass
class ChatMessage:
    sender: str
    text: str
    datetime: datetime.datetime


class Broker:
    def __init__(self, templating: Jinja2Templates):
        self.queue = asyncio.Queue()
        self.rooms: list[Room] = []
        self.connected_users: dict[str, ConnectedUser] = {}
        self.templating = templating

    def _get_room_for_user(self, username: str) -> Room | None:
        for room in self.rooms:
            if username in room.users:
                return room

        return None

    def _get_recipient_for_user(self, username: str) -> str | None:
        room = self._get_room_for_user(username)
        if room is None:
            return None

        recipient = list(filter(lambda user: user != username, room.users))[0]

        return recipient

    def _delete_room(self, room: Room):
        for username in room.users:
            try:
                self.add_html_message(
                    username,
                    "htmx/redirect-response.html",
                    {
                        "queryParams": encode_query_params(
                            {"error": "The other user left"}
                        )
                    },
                )
            except Exception:
                pass

        self.rooms.remove(room)

    def _send_connected_users(self):
        for connected_user in self.connected_users.values():
            self.add_html_message(
                connected_user.username,
                "htmx/connected-users.html",
                {"connected_users": len(self.connected_users.keys())},
            )

    def choose_recipient(self, encoded_username: str, username: str, recipient: str):
        error = None

        if username not in self.connected_users.keys():
            error = f'Username "{username}" is not connected'

        if recipient not in self.connected_users.keys():
            error = f'Recipient "{recipient}" is not connected'

        if error:
            return self.add_html_message(
                username,
                "htmx/choose-recipient-fragment.html",
                {
                    "encoded_username": encoded_username,
                    "username": username,
                    "error": error,
                },
            )

        self.new_room_for_users(encoded_username, username, recipient)

    def new_room_for_users(
        self, encoded_username: str, username_1: str, username_2: str
    ):
        for room in self.rooms:
            if username_1 in room.users:
                self._delete_room(room)

        for room in self.rooms:
            if username_2 in room.users:
                self._delete_room(room)

        room = Room((username_1, username_2))
        self.rooms.append(room)

        self.add_html_message(
            username_1,
            "htmx/chat.html",
            {"encoded_username": encoded_username, "recipient": username_2},
        )
        self.add_html_message(
            username_2,
            "htmx/chat.html",
            {"encoded_username": encrypt_message(username_2), "recipient": username_1},
        )

    def new_user(self, username: str, ws: WebSocket):
        if username in self.connected_users.keys():
            raise ValueError("Username already exists")

        self.connected_users[username] = ConnectedUser(username, ws)

        self._send_connected_users()

    async def user_leaves(self, username: str):
        if username not in self.connected_users.keys():
            return

        connected_user = self.connected_users[username]

        ws = connected_user.ws
        try:
            await ws.close()
        except RuntimeError:
            pass

        del self.connected_users[username]

        room = self._get_room_for_user(username)
        if room is not None:
            self._delete_room(room)

        self._send_connected_users()

    def send_chat_message(self, chat_message: ChatMessage):
        recipient = self._get_recipient_for_user(chat_message.sender)
        if recipient is None:
            return

        self.add_html_message(
            chat_message.sender,
            "htmx/own-message.html",
            {
                "time": chat_message.datetime,
                "message": chat_message.text,
            },
        )

        self.add_html_message(
            recipient,
            "htmx/recipient-message.html",
            {
                "time": chat_message.datetime,
                "message": chat_message.text,
            },
        )

    def add_html_message(self, recipient: str, template_name: str, params: dict):
        html = self.templating.get_template(template_name).render(params)

        self.queue.put_nowait({"recipient": recipient, "html": html})

    async def unpile_messages(self):
        while True:
            to_send = await self.queue.get()
            connected_user = self.connected_users[to_send["recipient"]]

            if connected_user.ws.state != WebSocketState.DISCONNECTED:
                await connected_user.ws.send_text(to_send["html"])
