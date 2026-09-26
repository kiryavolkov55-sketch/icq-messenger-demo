"""
E2E тесты мессенджера ICQ
Запуск: python test_e2e.py
Требования: pip install websocket-client
"""

import websocket
import json
import time
import sqlite3
import os
import sys
from datetime import datetime

# ===== НАСТРОЙКИ =====
SERVER_URL = "ws://127.0.0.1:8080/ws"
DB_PATH = "./icq.db"
TIMEOUT = 5  # секунд на ожидание ответа

# ===== УТИЛИТЫ =====

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def ok(self, name):
        self.passed += 1
        print(f"  ✅ {name}")
    
    def fail(self, name, reason):
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  ❌ {name} — {reason}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"ИТОГО: {total} тестов")
        print(f"✅ Пройдено: {self.passed}")
        print(f"❌ Провалено: {self.failed}")
        if self.errors:
            print(f"\nОшибки:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*50}")
        return self.failed == 0

def create_ws():
    """Создаёт WebSocket подключение"""
    try:
        ws = websocket.create_connection(SERVER_URL, timeout=TIMEOUT)
        return ws
    except Exception as e:
        print(f"❌ Не удалось подключиться к серверу: {e}")
        print("   Убедитесь, что сервер запущен: go run main.go")
        sys.exit(1)

def recv_json(ws, timeout=TIMEOUT):
    """Получает JSON от сервера с таймаутом"""
    ws.settimeout(timeout)
    try:
        msg = ws.recv()
        return json.loads(msg)
    except websocket.WebSocketTimeoutException:
        return None
    except Exception as e:
        print(f"  ⚠️ Ошибка получения: {e}")
        return None

def check_db(query, expected=None):
    """Проверяет запрос к БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result

def clean_db():
    """Очищает БД перед тестами"""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM contacts")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()

# ===== ТЕСТЫ =====

def test_registration(result):
    """Тест 1: Регистрация нового пользователя с аватаркой"""
    print("\n📝 Тест 1: Регистрация")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "ТестПользователь",
        "password": "test123",
        "email": "test@example.com",
        "phone": "+79001112233",
        "avatar": "😎"  # <-- ПРОВЕРКА КАСТОМНОЙ АВАТАРКИ
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp is None:
        result.fail("Регистрация", "Нет ответа от сервера")
        return None
    
    if resp.get("type") != "register":
        result.fail("Регистрация", f"Неверный тип: {resp.get('type')}")
        return None
    
    if "error" in resp:
        result.fail("Регистрация", f"Ошибка: {resp['error']}")
        return None
    
    uin = resp.get("uin")
    if not uin or uin < 1000000 or uin > 9999999:
        result.fail("Регистрация", f"Некорректный UIN: {uin}")
        return None
    
    # ПРОВЕРКА АВАТАРКИ В ОТВЕТЕ
    avatar = resp.get("avatar")
    if avatar != "😎":
        result.fail("Регистрация", f"Неверная аватарка: ожидалась '😎', получена '{avatar}'")
        return None
    
    result.ok(f"Регистрация успешна, UIN: {uin}, Аватар: {avatar}")
    return uin

def test_login_by_uin(result, uin):
    """Тест 2: Вход по UIN"""
    print("\n🔑 Тест 2: Вход по UIN")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "login",
        "uin": uin,
        "password": "test123"
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp is None:
        result.fail("Вход по UIN", "Нет ответа")
        return
    
    if "error" in resp:
        result.fail("Вход по UIN", resp["error"])
        return
    
    if resp.get("uin") == uin and resp.get("name") == "ТестПользователь":
        result.ok("Вход по UIN успешен")
    else:
        result.fail("Вход по UIN", f"Неверные данные: {resp}")

def test_login_wrong_password(result, uin):
    """Тест 3: Вход с неверным паролем"""
    print("\n🚫 Тест 3: Вход с неверным паролем")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "login",
        "uin": uin,
        "password": "wrongpassword"
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp and "error" in resp:
        result.ok("Неверный пароль корректно отклонён")
    else:
        result.fail("Неверный пароль", "Должна быть ошибка")

def test_add_contact(result, uin1, uin2):
    """Тест 4: Добавление контакта"""
    print("\n➕ Тест 4: Добавление контакта")
    ws = create_ws()
    
    # Логинимся
    ws.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
    recv_json(ws)  # login
    recv_json(ws)  # contact_list (игнорируем)
    
    # Добавляем контакт
    ws.send(json.dumps({"type": "add_contact", "contact_uin": uin2}))
    resp = recv_json(ws)  # contact_list
    
    ws.close()
    
    if resp is None:
        result.fail("Добавление контакта", "Нет ответа от сервера")
        return
    
    if resp.get("type") != "contact_list":
        result.fail("Добавление контакта", f"Ожидали contact_list, получили {resp.get('type')}")
        return
    
    text_field = resp.get("text")
    
    if text_field is None or text_field == "null" or text_field == "":
        result.fail("Добавление контакта", "Сервер вернул пустой список контактов")
        return
    
    try:
        contacts = json.loads(text_field)
    except (json.JSONDecodeError, TypeError) as e:
        result.fail("Добавление контакта", f"Ошибка парсинга: {e}")
        return
    
    if contacts is None:
        contacts = []
    
    if not isinstance(contacts, list):
        result.fail("Добавление контакта", f"Ожидали список, получили {type(contacts)}")
        return
    
    if any(c.get("uin") == uin2 for c in contacts):
        result.ok("Контакт добавлен успешно")
    else:
        result.fail("Добавление контакта", f"Контакт UIN {uin2} не найден в списке: {contacts}")

def test_send_message(result, uin1, uin2):
    """Тест 5: Отправка и получение сообщения"""
    print("\n💬 Тест 5: Отправка сообщения")
    
    ws1 = create_ws()
    ws2 = create_ws()
    
    # Логиним ws1 и читаем ВСЕ сообщения (login + contact_list)
    ws1.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
    recv_json(ws1)  # login
    recv_json(ws1)  # contact_list (игнорируем)
    
    # Логиним ws2 и читаем ВСЕ сообщения
    ws2.send(json.dumps({"type": "login", "uin": uin2, "password": "test123"}))
    recv_json(ws2)  # login
    recv_json(ws2)  # contact_list (игнорируем)
    
    # Отправляем сообщение
    test_text = f"Тестовое сообщение {datetime.now().strftime('%H:%M:%S')}"
    ws1.send(json.dumps({
        "type": "message",
        "from": uin1,
        "to": uin2,
        "text": test_text,
        "timestamp": datetime.now().isoformat()
    }))
    
    # Ждём получения
    resp = recv_json(ws2, timeout=3)
    
    ws1.close()
    ws2.close()
    
    if resp and resp.get("text") == test_text:
        result.ok("Сообщение доставлено")
    else:
        result.fail("Отправка сообщения", f"Получено: {resp}")

def test_message_history(result, uin1, uin2):
    """Тест 6: История сообщений"""
    print("\n📜 Тест 6: История сообщений")
    
    ws = create_ws()
    ws.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
    recv_json(ws)  # login
    recv_json(ws)  # contact_list (игнорируем)
    
    ws.send(json.dumps({"type": "history", "uin": uin2}))
    resp = recv_json(ws)
    ws.close()
    
    if resp and resp.get("type") == "history":
        history = json.loads(resp.get("text", "[]"))
        if len(history) > 0:
            result.ok(f"История получена: {len(history)} сообщений")
        else:
            result.fail("История", "Пустая история")
    else:
        result.fail("История", f"Неверный ответ: {resp}")

def test_database_integrity(result, uin):
    """Тест 7: Целостность БД"""
    print("\n🗄️  Тест 7: Целостность БД")
    
    users = check_db("SELECT COUNT(*) FROM users")
    if users and users[0][0] > 0:
        result.ok(f"В БД {users[0][0]} пользователей")
    else:
        result.fail("БД", "Таблица users пуста")
    
    user = check_db(f"SELECT name FROM users WHERE uin = {uin}")
    if user and user[0][0] == "ТестПользователь":
        result.ok("Данные пользователя корректны")
    else:
        result.fail("БД", "Пользователь не найден или имя неверное")

def test_duplicate_registration(result):
    """Тест 8: Дублирующая регистрация"""
    print("\n🚫 Тест 8: Дублирующая регистрация")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "Дубль",
        "password": "pass",
        "email": "dup@example.com",
        "phone": ""
    }))
    recv_json(ws)
    
    ws.send(json.dumps({
        "type": "register",
        "name": "Дубль2",
        "password": "pass",
        "email": "dup@example.com",
        "phone": ""
    }))
    resp = recv_json(ws)
    ws.close()
    
    if resp and "error" in resp:
        result.ok("Дубликат email корректно отклонён")
    else:
        result.fail("Дубликат", "Должна быть ошибка")

def test_default_avatar(result):
    """Тест 9: Регистрация без аватарки (проверка дефолтного значения)"""
    print("\n🎭 Тест 9: Регистрация без аватарки (дефолт)")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "ДефолтЮзер",
        "password": "pass",
        "email": "default@example.com",
        "phone": ""
        # Намеренно НЕ отправляем поле avatar
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp and resp.get("type") == "register" and "error" not in resp:
        if resp.get("avatar") == "😀":
            result.ok("Дефолтная аватарка '😀' установлена корректно")
        else:
            result.fail("Дефолтная аватарка", f"Ожидалась '😀', получено: {resp.get('avatar')}")
    else:
        result.fail("Дефолтная аватарка", f"Ошибка регистрации: {resp}")

# ===== ГЛАВНЫЙ СЦЕНАРИЙ =====

def main():
    print("="*50)
    print("🧪 E2E ТЕСТЫ МЕССЕНДЖЕРА ICQ")
    print("="*50)
    
    # Проверяем, что БД существует
    if not os.path.exists(DB_PATH):
        print(f"❌ База данных не найдена: {DB_PATH}")
        print("   Сначала запустите сервер: go run main.go")
        sys.exit(1)
    
    result = TestResult()
    
    # Очищаем БД для чистого теста
    print("\n🧹 Очистка БД...")
    clean_db()
    
    # Запускаем тесты по порядку
    uin1 = test_registration(result)
    if uin1 is None:
        print("\n❌ Критическая ошибка: регистрация не работает")
        print("   Дальнейшие тесты невозможны")
        result.summary()
        sys.exit(1)
    
    # Регистрируем второго пользователя для тестов общения
    ws = create_ws()
    ws.send(json.dumps({
        "type": "register",
        "name": "ВторойПользователь",
        "password": "test123",
        "email": "second@example.com",
        "phone": "",
        "avatar": "🤖"  # <-- ДОБАВЛЕНА АВАТАРКА ДЛЯ ВТОРОГО ПОЛЬЗОВАТЕЛЯ
    }))
    resp = recv_json(ws)
    ws.close()
    uin2 = resp.get("uin") if resp else None
    
    if uin2:
        test_login_by_uin(result, uin1)
        test_login_wrong_password(result, uin1)
        test_add_contact(result, uin1, uin2)
        test_send_message(result, uin1, uin2)
        test_message_history(result, uin1, uin2)
        test_database_integrity(result, uin1)
        test_duplicate_registration(result)
        test_default_avatar(result)  # <-- ДОБАВЛЕН НОВЫЙ ТЕСТ
    else:
        print("⚠️  Не удалось зарегистрировать второго пользователя")
    
    # Финальный отчёт
    success = result.summary()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()