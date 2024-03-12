import asyncio
import json
from dataclasses import dataclass
from pprint import pprint

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from server_message_types import (
    CHAT_MESSAGE,
    CONNECTED_USERS,
    RECIPIENT_CHOSEN,
    ROOM_KILLED,
)


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


class Broker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.rooms: list[Room] = []
        self.connected_users: dict[str, ConnectedUser] = {}

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

    async def _delete_room(self, room: Room):
        for username in room.users:
            try:
                await self.add_websocket_message(
                    username,
                    ROOM_KILLED,
                    {"value": list(self.connected_users.keys())},
                )
            except Exception:
                pass

        self.rooms.remove(room)

    async def _send_connected_users(self):
        for connected_user in self.connected_users.values():
            await self.add_websocket_message(
                connected_user.username,
                CONNECTED_USERS,
                {"value": len(self.connected_users.keys())},
            )

    async def new_room_for_users(self, username_1: str, username_2: str):
        for room in self.rooms:
            if username_1 in room.users:
                await self._delete_room(room)

        for room in self.rooms:
            if username_2 in room.users:
                await self._delete_room(room)

        room = Room((username_1, username_2))
        self.rooms.append(room)

        await self.add_websocket_message(
            username_1,
            RECIPIENT_CHOSEN,
            {"value": username_2},
        )
        await self.add_websocket_message(
            username_2,
            RECIPIENT_CHOSEN,
            {"value": username_1},
        )

    async def new_user(self, username: str, ws: WebSocket):
        if username in self.connected_users.keys():
            raise ValueError("Username already exists")

        self.connected_users[username] = ConnectedUser(username, ws)

        await self._send_connected_users()

    async def user_leaves(self, username: str):
        if username not in self.connected_users.keys():
            return

        connected_user = self.connected_users[username]

        ws = connected_user.ws
        if ws.state != WebSocketState.DISCONNECTED:
            await ws.close()

        del self.connected_users[username]

        room = self._get_room_for_user(username)
        if room is not None:
            await self._delete_room(room)

        await self._send_connected_users()

    async def send_chat_message(self, chat_message: ChatMessage):
        recipient = self._get_recipient_for_user(chat_message.sender)
        if recipient is None:
            return

        msg = {
            "value": chat_message.text,
        }

        await self.add_websocket_message(recipient, CHAT_MESSAGE, msg)

    async def add_websocket_message(self, recipient: str, type: str, msg: dict):
        msg["type"] = type

        pprint("created task to add websocket message: " + json.dumps(msg))
        await self.queue.put({"recipient": recipient, "msg": msg})
        pprint("websocket message in the queue: " + json.dumps(msg))

    async def unpile_messages(self):
        while True:
            print("on attend dans send messages")
            to_send = await self.queue.get()
            print("chopé une task")
            connected_user = self.connected_users[to_send["recipient"]]

            if connected_user.ws.state != WebSocketState.DISCONNECTED:
                await connected_user.ws.send_json(to_send["msg"])
            print("fini la task")
