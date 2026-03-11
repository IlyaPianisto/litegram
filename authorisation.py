import os
import asyncio
import base64
from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")


def get_key(pin, salt):
    # Превращаем короткий ПИН в надежный 32-байтный ключ
    return PBKDF2(pin, salt, dkLen=32, count=100000)

def encrypt_session(session_string, pin):
    salt = get_random_bytes(16)
    key = get_key(pin, salt)
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(session_string.encode('utf-8'))
    payload = salt + cipher.nonce + tag + ciphertext
    return base64.b64encode(payload).decode('utf-8')


def decrypt_session(encrypted_b64, pin):
    payload = base64.b64decode(encrypted_b64)
    salt = payload[:16]
    nonce = payload[16:32]
    tag = payload[32:48]
    ciphertext = payload[48:]

    key = get_key(pin, salt)
    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    try:
        return cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
    except ValueError:
        return None

async def main():
    if not os.path.exists('sessions'):
        os.makedirs('sessions')

    phone = input("Введите номер телефона (+7...): ").strip()
    # Убираем плюсик для имени файла
    safe_phone = phone.replace("+", "")
    session_file = f"sessions/{safe_phone}.enc"

    session_string = ""

    # Проверяем, есть ли уже зашифрованный файл для этого номера
    if os.path.exists(session_file):
        print("Найдена сохраненная сессия для этого номера.")
        pin = input("Введите ваш ПИН-код для входа: ")

        with open(session_file, "r") as f:
            encrypted_data = f.read()

        decrypted = decrypt_session(encrypted_data, pin)
        if decrypted:
            print("Успешно расшифровано!")
            session_string = decrypted
        else:
            print("Ошибка: Неверный ПИН-код! Доступ запрещен.")
            return

    # Запускаем клиент Телеграма. Если session_string пустая - попросит код
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    await client.connect()

    # Если мы еще не авторизованы (например, первый вход)
    if not await client.is_user_authorized():
        print("Сессия пуста. Начинаем первичную авторизацию...")
        await client.send_code_request(phone)
        code = input("Введите код подтверждения из Telegram: ")

        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = input("Обнаружен облачный пароль! Введите его: ")
            await client.sign_in(password=password)

        print("SUCCESS! Успешный вход.")

        # Получаем строковую сессию, просим юзера придумать ПИН и шифруем
        new_session_string = client.session.save()
        new_pin = input("Придумайте ПИН-код для защиты вашей сессии на сервере: ")
        encrypted_new = encrypt_session(new_session_string, new_pin)

        with open(session_file, "w") as f:
            f.write(encrypted_new)
        print("Сессия надежно зашифрована и сохранена!")
    else:
        print("SUCCESS! Сессия активна, повторный ввод кода не требуется.")

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())