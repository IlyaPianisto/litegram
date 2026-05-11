STYLE = """
    
"""

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
