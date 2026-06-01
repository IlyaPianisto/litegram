import os
import asyncio
from aiohttp import web
from aiohttp_session import get_session, setup as session_setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from dotenv import load_dotenv
from datetime import datetime, timezone
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (MessageMediaPhoto, MessageMediaDocument, DocumentAttributeAudio, DocumentAttributeVideo)
from telethon.sessions import StringSession
import templates as t
from authorisation import decrypt_session, encrypt_session
from media import compress_image

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
COOKIE_SECRET = os.getenv("COOKIE_SECRET")

PRESET_PARAMS = {
    "low": {'max_px': 800, 'quality': 75, 'audio_kbps': 64},
    "medium": {'max_px': 400, 'quality': 55, 'audio_kbps': 32},
    "high": {'max_px': 200, 'quality': 35, 'audio_kbps': 16},
    "ultra": {'max_px': 120, 'quality': 25, 'audio_kbps': 8},
}

DEFAULT_PRESET = "medium"

os.makedirs("sessions", exist_ok=True)

clients: dict[str, TelegramClient] = {}
routes = web.RouteTableDef()

async def get_tg_client(request: web.Request) -> tuple[str, TelegramClient | None]:
    sess = await get_session(request)
    tg_id = sess.get("tg_id")
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
    saved_chat_id = sess.get("saved_tg_id")
    if not saved_chat_id:
        return web.HTTPFound("/auth/pin_enter")
    return web.Response(text=templates.login_form(), content_type="text/html", charset="utf-8")

@routes.get("/auth/phone")
async def auth_phone(request: web.Request):
    data = await request.post()
    phone = data.get("phone", "").strip()
    if not phone:
        return web.Response(text=templates.login_form("Введите номер"), content_type="text/html", charset="utf-8")

    sess = await get_session(request)
    saved_tg_id = sess.get("saved_tg_id")
    if os.path.exists(f"sessions/{saved_tg_id}.enc"):
        raise web.HTTPFound("/auth/pin_enter")

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
    except Exception as e:
        await client.disconnect()
        return web.HTTPFound(text=t.login_form(str(e)), content_type="text/html", charset="utf-8")

    clients[f"reg_{phone}"] = client####
    sess["reg_tg_id"] = phone
    raise web.HTTPFound("/auth/code")

@routes.get("/auth/pin_enter")
async def pin_enter_page(request: web.Request):
    return web.Response(text=templates.pin_enter_form(), content_type="text/html", charset="utf-8")

@routes.post("/auth/pin_enter")
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

    with open(enc_file, "r") as f:
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
    client = clients.get(f"reg_{phone}")

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

    me = await client.get_me()
    tg_id = str(me.id)

    clients[f"reg_{tg_id}"] = client
    del clients[f"reg_{phone}"]

    sess[f"reg_tg_id"] = tg_id
    sess.pop("saved_tg_id", None)
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
        return web.Response(text=t.pin_create_form("PIN не совпадают"), content_type="text/html", charset="utf-8")

    if len(pin) != 4:
        return web.Response(text=t.pin_create_form("PIN должен быть 4 цифры!!!"), content_type="text/html", charset="utf-8")

    session_str = client.session.save()
    encrypted = encrypt_session(session_str, pin)
    with open ("sessions/"+tg_id+".enc", "a") as f:
        f.write(encrypted)

    clients[tg_id] = client
    del clients[f"reg_{tg_id}"]

    sess["tg_id"] = tg_id
    sess["saved_tg_id"] = tg_id
    sess.pop("reg_tg_id", None)
    raise web.HTTPFound("/chats")

@routes.get("/logout")
async def logout(request: web.Request):
    sess = await get_session(request)
    tg_id = sess.get("tg_id")
    if tg_id and tg_id in clients:
        await clients[tg_id].diconnect()
        del clients[tg_id]
    sess.clear()
    raise web.HTTPFound("/")

async def get_folders(client: TelegramClient) -> list[dict]:
    folders = [{'id': 0, 'title': 'Все'} ]
    result = await client(GetDialogFiltersRequest())
    try:
        for i in result:
            if isinstance(i, DialogFilter):
                folders.append({'id': i.id, 'title': i.title})

    except Exception as e:
        pass

    return folders

@routes.get("/chats")
async def chats_page(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client or not tg_id:
        raise web.HTTPFound("/")

    folder_id = int(request.rel_url.query("folder", 0))
    folders = await get_folders(client)


    dialogs_raw = await client.get_dialogs(limit=80, folder=folder_id)
    dialogs = []
    for d in dialogs_raw:
        last = ""
        if d.message:
            last = d.message.text or ("Медиа" if d.message.media else "")

        dialogs.append({
            'id': d.id,
            'name': d.name or "Без названия",
            'last_message': last[:50],
            'unread_count': d.unread_count or 0,
            'date': fmt_time(d.date),
            #'type': d.type or "",
        })

    return web.Response(text=t.chats_lists(dialogs, tab), folders=folders, active_folder=folder_id, content_type="text/html", charset="utf-8")

@routes.get("/chat/{chat_id}")
async def chat_page(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client:
        raise web.HTTPFound("/")

    chat_id = int(request.match_info["chat_id"])
    offset = int(request.rel_url.query.get["offset"])

    try:
        entity = await client.get_entity(chat_id)
        msgs_row = await client.get_messages(chat_id, limit=15, offset=offset)

    except Exception as e:
        raise web.Response(text=t.error_page(str(e), "/chats"), content_type="text/html", charset="utf-8")

    me = await client.get_me()
    messages = []
    for m in reversed(msgs_row):
        sender = "Я" if m.sender_id == me.id else(
            entity_name(m.sender) if m.sender else '?'
        )
        kind = media_kind(m)
        messages.append({
            'sender': sender,
            'text': m.text or "",
            'time': fmt_time(m.date),
            'is_me': m.sender_id == me.id,
            'media_type': kind,
            'media_url': f"/media/{chat_id}/{m.id}" if kind else None,
            "thumb_url": f"/thumb/{chat_id}/{m.id}" if kind in ('photo', 'video') else None,
        })

    title = entity_name(entity)
    return web.Response(text=t.chat_view(chat_id, title, messages, offset), content_type="text/html", charset="utf-8")

def entity_name(entity):
    if isinstance(entity, user):
        return f"{entity.first_name or ""} {entity.last_name or ""}".strip() or "?"
    return getattr(entity, "tittle", None) or "Без названия"

@routes.post('/send')
async def send_message(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client:
        raise web.HTTPFound("/")
    data = await request.post()
    chat_id = int(data.get("chat_id"))
    text = data.get("text", "").strip()

    if text and chat_id:
        entity = await client.get_entity(chat_id)
        await client.send_message(entity, text)

    raise web.HTTPFound(f"chat/{chat_id}")

@routes.get("/thumb/{chat_id}/{msg_id}")
async def thumb(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client:
        raise web.HTTPFound("/")
    chat_id = int(request.match_info["chat_id"])
    msg_id = int(request.match_info["msg_id"])

    try:
        entity = await client.get_entity(chat_id)
        message = await client.get_message(entity, ids=msg_id)
        raw = await client.download_media(messagem, bytes)
        if raw:
            compressed = compress_image(raw, quality=40, max_px=120)
            return web.Response(body=compressed, content_type="image/jpeg")
    except Exception as e:
        pass

    return web.Response(text="no image", status=404)

@routes.get("/media/{chat_id}/{msg_id}")
async def media(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client:
        raise web.HTTPFound("/")
    chat_id = int(request.match_info["chat_id"])
    msg_id = int(request.match_info["msg_id"])
    try:
        entity = await client.get_entity(chat_id)
        message = await client.get_message(entity, ids=msg_id)
        raw = await client.download_media(message, bytes)
        if raw:
            ct = "application/octet-stream"
            if isinstance(message.media, message.media.photo):
                ct = "image/jpeg"
                raw = compress_image(raw, quality=40, max_px=120)
            return web.Response(body=ct, content_type=ct)

    except Exception as e:
        return web.Response(text=str(e), status=500)

    return web.Response(text="not found", status=404)

def get_presets(sess) -> dict:
    preset_id = sess.get("compression", DEFAULT_PRESET)
    return PRESET_PARAMS.get(preset_id, PRESET_PARAMS[DEFAULT_PRESET])

@routes.get("/settings")
async def settings_page(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client:
        raise web.HTTPFound("/")
    sess = await get_session(request)
    current = sess.get("compression", DEFAULT_PRESET)
    return web.Response(text=t.settings_page(current), content_type="text/html", charset="utf-8")

@routes.get("/settings/compression/{preset_id}")
async def set_compression(request: web.Request):
    tg_id, client = await get_tg_client(request)
    if not client:
        raise web.HTTPFound("/")

    preset_id = request.match_info["preset_id"]

    if preset_id not in PRESET_PARAMS:
        raise web.HTTPFound("/settings")

    sess = await get_session(request)
    sess["compression"] = preset_id
    raise web.HTTPFound("/settings/")

async def main():
    app = web.Application()
    session_setup(app, EncryptedCookieStorage(COOKIE_SECRET))
    app.add_routes(routes)
    return app

if __name__ == "__main__":
    web.run_app(main(), host="localhost", port=8080)