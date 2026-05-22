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
from authorisation import decrypt_session, encrypt_session

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
        raise web.HTTPFound("/auth/pin_enter")

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(tg_id)
    except Exception as e:
        await client.disconnect()
        return web.HTTPFound(text=t.login_form(str(e)), content_type="text/html", charset="utf-8")

    clients[f"reg {tg_id}"] = client####
    sess["reg_tg_id"] = tg_id
    raise web.HTTPFound("/auth/code")

@routes.get("/auth/pin_enter")
async def pin_enter_post(request: web.Request):
    data = await request.post()
    pin = data.get("pin", "").strip()
    sess = await get_session(request)
    tg_id = sess.get("saved_tg_id", "")

    if not tg_id:
        return web.HTTPFound("/")

    enc_file = f"sessions/{tg_id}.enc"
    if os.path.exists(enc_file):
        sess.clear()
        raise web.HTTPFound("/")

    with open(enc_file, "rb") as f:
        encrypted = f.read()

    session_str = decrypt_session(encrypted, pin)

    if not session_str:
        return web.Response(text=t.pin_enter_form("Неверный PIN!"), content_type="text/html", charset="utf-8")

    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        try:
            os.remove(enc_file)
        except OSError:
            pass

        sess.clear()

        return web.Response(text=t.error_page("Сессия была завершена. \nНеобходимо войти заного", back='/', back_label="Войти заного"), content_type="text/html", charset="utf-8")

    clients[tg_id] = client
    sess["tg_id"] = tg_id
    sess.pop("saved_tg_id", None)
    raise web.HTTPFound("/chats")

@routes.get("/auth/code")
async def auth_code_get(request: web.Request):
    sess = await get_session(request)
    phone = sess.get("reg_phone", "")
    return web.Response(text=t.code_form(phone), content_type="text/html", charset="utf-8")

@routes.post("/auth/code")
async def auth_code_post(request: web.Request):
    data = await request.post()
    sess = await get_session(request)
    code = data.get("code", "").strip()
    phone = sess.get("reg_phone", "")
    client = clients.get(phone)

    if not client or not phone:
        raise web.HTTPFound("/")

    try:
        await client.sign_in(phone, code)
    except errors.SessionPasswordNeededError:
        raise web.HTTPFound("/auth/password")
    except errors.PhoneCodeInvalidError:
        return web.Response(text=t.code_form(phone, "Неверный код"), content_type="text/html", charset="utf-8")
    except Exception as e:
        return web.Response(text=t.code_form(phone, str(e)), content_type="text/html", charset="utf-8")

    raise web.HTTPFound("/auth/pin_create")

@routes.get("/auth/password")
async def auth_password_get(request: web.Request):
    return web.Response(text=t.password_form(), content_type="text/html", charset="utf-8")

@routes.post("/auth/password")
async def auth_password_post(request: web.Request):
    data = await request.post()
    sess = await get_session(request)
    password = data.get("password", "").strip()
    phone = sess.get("reg_phone", "")
    client = clients.get(phone)

    if not client:
        raise web.HTTPFound("/")

    try:
        await client.sign_in(password=password)
    except errors.PasswordHashInvalidError:
        return web.Response(text=t.password_form("Неверный пароль!"), content_type="text/html", charset="utf-8")
    except Exception as e:
        return web.Response(text=t.password_form(str(e)), content_type="text/html", charset="utf-8")

    raise web.HTTPFound("/auth/pin_create")

@routes.get("/auth/pin_create")
async def auth_pin_create(request: web.Request):
    return web.Response(text=t.pin_create_form(), content_type="text/html", charset="utf-8")

@routes.post("/auth/pin_create")
async def auth_pin_post(request: web.Request):
    data = await request.post()
    pin = data.get("pin", "").strip()
    pin2 = data.get("pin2", "").strip()
    sess = await get_session(request)
    phone = sess.get("reg_phone", "")
    client = clients.get(phone)
    tg_id = sess.get("tg_id", "")

    if not client or not phone:
        raise web.HTTPFound("/")

    if pin != pin2:
        raise web.Response(text=t.pin_create_form("PIN не совпадают"), content_type="text/html", charset="utf-8")

    if len(pin) != 4:
        raise web.Response(text=t.pin_create_form("PIN должен быть 4 цифры!!!"), content_type="text/html", charset="utf-8")

    session_str = client.session.save()
    encrypted = encrypt_session(session_str, pin)
    with open ("sessions/"+tg_id+".enc", "a") as f:
        f.write(encrypted)

    clients[tg_id] = client
    del clients[tg_id]
    sess["tg_id"] = tg_id
    sess.pop("reg_tg_id", None)



