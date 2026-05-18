import os
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from datetime import datetime, timezone
#import logging
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

import templates
import templates as t

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

os.makedirs("sessions", exist_ok=True)

clients: dict[str, TelegramClient] = {}
routes = web.RouteTableDef()

async def get_tg_client(request: web.Request) -> tuple[str, TelegramClient | None]:
    sess = await get_session(request)
    tg_id = sess.get("chat_id")
    if not tg_id:
        return "", None
    client = clients.get(tg_id)
    return tg_id, client

def fmt_time(dt: datetime | None) -> str:
    if not dt:
        return ""

    now = datetime.now(tz=timezone.utc)
    local = dt.astimezone()

    if local.date() == now.astimezone().date():
        return local.strftime("%H:%M")
    return local.strftime("%d.%m.%Y")

def media_kind(msg) -> str | None:
    if isinstance(msg.media, MessageMediaPhoto):
        return "photo"

    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                return "video"
            if isinstance(attr, DocumentAttributeAudio):
                return "voice" if attr.voice else "audio"
        return "file"
    return None

@routes.get("/")
async def index(request: web.Request):
    tg_id, client = await get_tg_client(request)

    if client:
        raise web.HTTPFound("/chats")

    sess = await get_session(request)
    saved_chat_id = sess.get("saved_chat_id")
    if not saved_chat_id:
        return web.HTTPFound("/auth/pin_enter")
    return web.Response(text=templates.login_form(), content_type="text/html", charset="utf-8")

@routes.get("/auth/phone")
async def auth_phone(request: web.Request):
    data = await request.post()
    tg_id = data.get("tg_id", "").strip()
    if not tg_id:
        return web.Response(text=templates.login_form("Введите номер"), content_type="text/html", charset="utf-8")

    sess = await get_session(request)
    if os.path.exists(f"sessions/{tg_id}.enc"):
        sess["saved_chat_id"] = tg_id
