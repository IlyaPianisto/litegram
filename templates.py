from server import logout

STYLE = """
    
"""

COMPRESSION_PRESETS = [
    {
        'id': 'none',
        'label': 'Без сжатия',
        'desc': 'Фото и видео без сжатия'
    },
    {
        'id': 'low',
        'label': 'Слабое',
        'desc': 'Фото до 800 px, аудио до 64kbps. Для хорошего соединения'
    },
    {
        'id': 'medium',
        'label': 'Среднее',
        'desc': 'Фото до 400 px, аудио до 32kbps. Баланс качества и скорости'
    },
    {
        'id': 'high',
        'label': 'Высокое',
        'desc': 'Фото до 200 px, аудио до 16kbps. Для медленного соединения'
    },
    {
        'id': 'ultra',
        'label': 'Максимальное',
        'desc': 'Фото до 200 px, аудио до 16kbps. Для ОЧЕНЬ ОЧЕНЬ медленного соединения'
    }
]

def settings_page(current_presets: str = 'medium') -> str:
    presets_html = "<p><b>Сжатие медиа</b></p>"

    for p in COMPRESSION_PRESETS:
        is_active = p['id'] == current_presets
        if is_active:
            presets_html += (
                f'<div class = "row">'
                f'<b>{p["label"]}</b><br>'
                f'<span class = "dim">{p["desc"]}</span>'
                "</div>"
            )
        else:
            presets_html += (
                f'<div class = "row">'
                f'<a> href="settings/compression/{p["id"]}">{p["label"]}</a><br>'
                f'<span class = "dim">{p["desc"]}</span>'
                "</div>"
            )

    logout_html = (
        "<hr>"
        "<form method = 'post' action='/logout'>"
        "<input type = 'submit' value='Выйти из аккаунта'"
        "</form>"
    )

    body = presets_html + logout_html
    nav = '<a href = "/chats" accesskey="0">0:Чаты</a>'

    return page("Настройки", body, nav)

def page(title:str, body:str, nav: str = "") -> str:
    return (
        "<DOCTYPE html>"
        "<html><head>"
        "<meta charset='utf-8'>"
        "<meta name = 'viewport' content = 'width=device-width, initial-scale=1'>"
        f"<title>Litegram | {title}</title>"
        f"<style>{STYLE}</style>"
        "</head><body>"
        f"<h1>Litegram | {title}</h1>"
        + (f"<div class = 'nav'>{nav}</div>" if nav else "")
        + body
        + "</body></html>"
    )

def login_form(error: str = "") -> str:
    err = f"<p><b>{error}</b></p>" if error else ""
    body = (
        err
        +"<p> Введите номер телефона. </p>"
        "form method: 'post' action='auth/phone'"
        "<p>+X XXX...<br>"
        "<input name = 'phone' type = 'tel' maxlength='20'> </p>"
        "<p><input type = 'submit' value='Далее'> </p>"
        "</form>"
    )
    return page("Вход", body)

def code_form(phone: str, error: str) -> str:
    err = f"<p><b>{error}</b></p>" if error else ""
    body = (
        err
        + f"<p>Код отправлен на {phone}</p>"
        "form method: 'post' action='auth/code'"
        "<p>Код из Telegram:<br>"
        "<input type='text' name = 'code' maxlength ='8'> </p>"
        "<p><input type='submit' value='OK></p>"
        "</form>"
    )
    return page("Введите код", body)

def password_form(error:str) -> str:
    err = f"<p><b>{error}</b></p>" if error else ""
    body = (
            err
            +"<p>Введите пароль от Telegram:</p>"
            "form method: 'post' action='auth/password'"
            "<p> input name='password' type='password'</p>"
            "<p><input type = 'submit' value='OK'> </p>"
            "</form>"
    )
    return page("Введите пароль", body)

def pin_create_form(error: str) -> str:
    err = f"<p><b>{error}</b></p>" if error else ""
    body = (
        err
        +"<p>Придумайте Pin-код для доступа к Litegram<p>"
        "form method: 'post' action='auth/create_pin'>"
        "<p>PIN (4 цифры): <br>"
        "<input type = 'password' name = 'pin' maxlength='4' minlength='4'></p>"
        "<p>Повторите PIN:<br>"
        "<input type = 'password' name = 'pin2' maxlength='4' minlength='4'></p>"
        "<p><input type = 'submit' value='OK'> </p>"
        "</form>"
    )
    return page("Создать PIN", body)

def pin_enter_form(error: str) -> str:
    err = f"<p><b>{error}</b></p>" if error else ""
    body = (
        err
        +"<p>Введите Pin-код для входа </p>"
        "form method: 'post' action='auth/pin_enter'>"
        "<input type = 'password' name = 'pin' maxlength='4' minlength='4'></p>"
        "<p><input type = 'submit' value='OK'> </p>"
        "</form>"
    )
    return page("Введи PIN", body)

def chats_lists(dialogs: list, folders: list, active_folder: int = 0) -> str: #Вернуться ещё
    tabs_html = (
        '<div class="tabs">'
    )
    for i, folder in enumerate(folders):
        is_active = folder["id"] == active_folder
        label = f'[{folder["title"]}]' if is_active else folder["title"]
        tabs_html += (
            f'<a href="/chat/folder={folder["url"]}">{label}</a>'
        )
    tabs_html += '/div'

    rows = []

    for dialog in dialogs:
        cls = "row unread" if dialog["unread"] else "row"
        unread_mark = f'[{dialog["unread"]}]' if dialog["unread"] else ''
        rows.append(
            f'<div class="{cls}">'
            f'<a href="/chat/{dialog["id"]}">{dialog["name"]}{unread_mark}</a><br>'
            f'<span class="dim">{dialog["last_msg"][:20] if dialog["last_msg"] else ""}'
            f'{"  " + dialog["date"] if dialog["date"] else ""}</span>'
            f'</div>'
        )

    nav = "<a href=/settings> accesskey='0'>Настройки</a>"

    body = tabs_html + "\n".join(rows) if rows else "<p>Нет диалогов</p>"
    return page("Чаты", body, nav)

def chat_view(chat_id: int, title: str, messages: list, offset: int = 0) -> str:
    rows = []
    for m in messages:
        cls = "bubble me" if m["is_me"] else "bubble"
        media_html = ""

        if m["media_type"] == "photo":
            media_html = (
                f'<br><a href="{m["media_url"]}">'
                f'<img src="{m["thumb_url"]}" alt="фото" width="80"></a>'
            )

        elif m["media_type"] == "video":
            if m.get("thumb_url"):
                media_html = (
                    f'<br>img src="{m["thumb_url"]}" alt="видео" width="80">'
                )
            media_html += f'<a href="{m["media_url"]}">Скачать видео</a>'

        elif m["media_type"] == ["audio", "voice"]:
            media_html = f'<br><a href="{m["media_url"]}"> Скачать аудио</a>'

        elif m["media_type"] == "file":
            media_html = f'<br><a href="{m["media_url"]}"> Скачать файл</a>'

        rows.append(
            f'<div class="{cls}">'
            f'<span class="dim">{m["sender"]} {m["time"]}</span><br>'
            + (m["text"] or "")
            + media_html
            + "</div>"
        )

    load_more = ""
    if len(messages) >= 10:
        new_offset = offset + 10
        load_more = (
            f'<p><a href="/chat/{chat_id}?offset={new_offset}">'
            "Загрузить ещё</a></p>"
        )

    send_form = {
        "<form method='post' action='/send'"
        f"<input type = 'hidden' name='chat_id' value='{chat_id}'>"
        "<textarea name='text' rows='2' cols='22'></textarea><br>"
        "<input type = 'submit' value='->'> </form>"
    }

    nav = f"<a href='/chats'> Назад </a> {title}"
    body = "\n".join(rows) + load_more + send_form

    return page(title, body, nav)

def error_page(msg: str, back: str = "/", back_label: str = "Назад") -> str:
    body = f"<p>{msg}</p><a href='{back}'>{back_label}</a>"
    return page("Ошибка", body)

