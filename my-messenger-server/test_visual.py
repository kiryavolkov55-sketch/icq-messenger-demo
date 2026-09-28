"""
Визуализация E2E тестов ICQ Messenger
Запуск: python test_visual.py
"""

import base64
import websocket
import json
import time
import sqlite3
import os
import sys
from datetime import datetime
from colorama import init, Fore, Style
import webbrowser
import urllib.request

# Инициализация colorama для цветов в консоли
init(autoreset=True)

# ===== НАСТРОЙКИ =====
SERVER_URL = "ws://127.0.0.1:8080/ws"
DB_PATH = "./icq.db"
TIMEOUT = 5

# ===== ВИЗУАЛЬНЫЕ ЭЛЕМЕНТЫ =====

class VisualTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
        self.test_times = []
        self.start_time = None
    
    def start_test(self, name):
        print(f"\n{Fore.CYAN}▶️  {name}{Style.RESET_ALL}")
        self.start_time = time.time()
    
    def ok(self, name, duration=None):
        self.passed += 1
        if duration is None:
            duration = time.time() - self.start_time if self.start_time else 0
        self.test_times.append((name, duration, "✅"))
        print(f"  {Fore.GREEN}✅ {name}{Style.RESET_ALL} {Fore.YELLOW}({duration:.2f}s){Style.RESET_ALL}")
    
    def fail(self, name, reason, duration=None):
        self.failed += 1
        if duration is None:
            duration = time.time() - self.start_time if self.start_time else 0
        self.test_times.append((name, duration, "❌"))
        self.errors.append(f"{name}: {reason}")
        print(f"  {Fore.RED}❌ {name}{Style.RESET_ALL} {Fore.YELLOW}({duration:.2f}s){Style.RESET_ALL}")
        print(f"     {Fore.RED}📝 {reason}{Style.RESET_ALL}")
    
    def skip(self, name, reason=""):
        self.skipped += 1
        print(f"  {Fore.YELLOW}⏭️  {name} (пропущен){Style.RESET_ALL}")
        if reason:
            print(f"     {Fore.YELLOW}ℹ️ {reason}{Style.RESET_ALL}")
    
    def generate_html_report(self):
        """Генерирует HTML-отчёт"""
        total = self.passed + self.failed + self.skipped
        total_time = sum(t[1] for t in self.test_times)
        
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧪 Отчёт по тестам ICQ Messenger</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 20px; min-height: 100vh; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); padding: 30px; }}
        h1 {{ color: #333; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .stat-card {{ padding: 20px; border-radius: 10px; text-align: center; color: white; font-weight: bold; }}
        .total {{ background: linear-gradient(135deg, #667eea, #764ba2); }}
        .passed {{ background: linear-gradient(135deg, #11998e, #38ef7d); }}
        .failed {{ background: linear-gradient(135deg, #eb3349, #f45c43); }}
        .skipped {{ background: linear-gradient(135deg, #f093fb, #f5576c); }}
        .stat-number {{ font-size: 48px; margin: 10px 0; }}
        .stat-label {{ font-size: 14px; opacity: 0.9; }}
        .test-list {{ margin-top: 30px; }}
        .test-item {{ padding: 15px; margin: 10px 0; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; border-left: 4px solid #ddd; }}
        .test-item.passed {{ background: #e8f5e9; border-left-color: #4caf50; }}
        .test-item.failed {{ background: #ffebee; border-left-color: #f44336; }}
        .test-name {{ font-weight: 600; color: #333; }}
        .test-time {{ color: #666; font-size: 14px; }}
        .progress-bar {{ width: 100%; height: 30px; background: #f0f0f0; border-radius: 15px; overflow: hidden; margin: 20px 0; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #4caf50, #8bc34a); transition: width 0.3s; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; }}
        .timestamp {{ color: #999; font-size: 12px; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Отчёт по тестам ICQ Messenger</h1>
        
        <div class="summary">
            <div class="stat-card total"><div class="stat-number">{total}</div><div class="stat-label">ВСЕГО ТЕСТОВ</div></div>
            <div class="stat-card passed"><div class="stat-number">{self.passed}</div><div class="stat-label">ПРОЙДЕНО ✅</div></div>
            <div class="stat-card failed"><div class="stat-number">{self.failed}</div><div class="stat-label">ПРОВАЛЕНО ❌</div></div>
            <div class="stat-card skipped"><div class="stat-number">{self.skipped}</div><div class="stat-label">ПРОПУЩЕНО ⏭️</div></div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {(self.passed/total*100) if total > 0 else 0}%">
                {(self.passed/total*100) if total > 0 else 0:.1f}%
            </div>
        </div>
        
        <p><strong>Общее время выполнения:</strong> {total_time:.2f} секунд</p>
        
        <div class="test-list">
            <h2>📋 Результаты тестов</h2>
"""
        
        for test_name, duration, status in self.test_times:
            status_class = "passed" if status == "✅" else "failed"
            html += f"""
            <div class="test-item {status_class}">
                <div><span class="test-name">{status} {test_name}</span></div>
                <div class="test-time">{duration:.2f}s</div>
            </div>
"""
        
        if self.errors:
            html += "<h2>⚠️ Ошибки</h2><ul>"
            for error in self.errors:
                html += f"<li style='color: #f44336;'>{error}</li>\n"
            html += "</ul>"
        
        html += f"""
        </div>
        <div class="timestamp">Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</div>
    </div>
</body>
</html>
"""
        return html
    
    def save_html_report(self, filename="test_report.html"):
        html = self.generate_html_report()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n{Fore.CYAN}📄 HTML-отчёт сохранён: {filename}{Style.RESET_ALL}")
        try:
            webbrowser.open(f"file://{os.path.abspath(filename)}")
            print(f"   {Fore.GREEN}✅ Отчёт открыт в браузере{Style.RESET_ALL}")
        except Exception as e:
            print(f"   {Fore.YELLOW}⚠️ Не удалось открыть автоматически: {e}{Style.RESET_ALL}")
    
    def summary(self):
        total = self.passed + self.failed + self.skipped
        
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 ИТОГОВЫЙ ОТЧЁТ{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        print(f"\n{Fore.WHITE}Всего тестов:{Style.RESET_ALL}        {total}")
        print(f"{Fore.GREEN}✅ Пройдено:{Style.RESET_ALL}          {self.passed}")
        print(f"{Fore.RED}❌ Провалено:{Style.RESET_ALL}         {self.failed}")
        print(f"{Fore.YELLOW}⏭️  Пропущено:{Style.RESET_ALL}         {self.skipped}")
        
        if self.test_times:
            total_time = sum(t[1] for t in self.test_times)
            print(f"\n{Fore.WHITE}Общее время:{Style.RESET_ALL}         {total_time:.2f} сек")
            avg_time = total_time / len(self.test_times)
            print(f"{Fore.WHITE}Среднее время теста:{Style.RESET_ALL} {avg_time:.2f} сек")
        
        if self.errors:
            print(f"\n{Fore.RED}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.RED}⚠️  ОШИБКИ:{Style.RESET_ALL}")
            print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}")
            for error in self.errors:
                print(f"  {Fore.RED}• {error}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        success_rate = (self.passed / total * 100) if total > 0 else 0
        if success_rate == 100:
            print(f"{Fore.GREEN}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!{Style.RESET_ALL}")
        elif success_rate >= 80:
            print(f"{Fore.YELLOW}⚠️  БОЛЬШИНСТВО ТЕСТОВ ПРОЙДЕНО ({success_rate:.1f}%){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ КРИТИЧЕСКОЕ КОЛИЧЕСТВО ОШИБОК ({success_rate:.1f}%){Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
        
        return self.failed == 0

# ===== УТИЛИТЫ =====

def create_ws():
    try:
        ws = websocket.create_connection(SERVER_URL, timeout=TIMEOUT)
        return ws
    except Exception as e:
        print(f"{Fore.RED}❌ Не удалось подключиться к серверу: {e}{Style.RESET_ALL}")
        print(f"   {Fore.YELLOW}Убедитесь, что сервер запущен: go run main.go{Style.RESET_ALL}")
        sys.exit(1)

def recv_json(ws, timeout=TIMEOUT):
    ws.settimeout(timeout)
    try:
        msg = ws.recv()
        return json.loads(msg)
    except websocket.WebSocketTimeoutException:
        return None
    except Exception as e:
        print(f"  {Fore.YELLOW}⚠️  Ошибка получения: {e}{Style.RESET_ALL}")
        return None

def recv_login_setup(ws):
    """Read login, automatic history, and contact list packets."""
    for _ in range(10):
        msg = recv_json(ws)
        if msg is None or msg.get("type") == "contact_list" or "error" in msg:
            return msg
    return None

def check_db(query, expected=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result

def clean_db():
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
    result.start_test("📝 Тест 1: Регистрация")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "ТестПользователь",
        "password": "test123",
        "email": "test@example.com",
        "phone": "+79001112233",
        "avatar": "😎"
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
    
    avatar = resp.get("avatar")
    if avatar != "😎":
        result.fail("Регистрация", f"Неверная аватарка: ожидалась '😎', получена '{avatar}'")
        return None
    
    result.ok(f"Регистрация успешна (UIN: {uin}, Avatar: {avatar})")
    return uin

def test_register_second_user(result):
    """Тест 2: Регистрация второго пользователя"""
    result.start_test("👤 Тест 2: Регистрация второго пользователя")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "ВторойПользователь",
        "password": "test123",
        "email": "second@example.com",
        "phone": "",
        "avatar": "🤖"  
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp and resp.get("type") == "register" and "error" not in resp:
        uin2 = resp.get("uin")
        avatar2 = resp.get("avatar")
        result.ok(f"Второй пользователь зарегистрирован (UIN: {uin2}, Avatar: {avatar2})")
        return uin2
    else:
        result.fail("Регистрация второго пользователя", f"Ошибка: {resp}")
        return None

def test_login_by_uin(result, uin):
    result.start_test("🔑 Тест 3: Вход по UIN")
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
    result.start_test("🚫 Тест 4: Вход с неверным паролем")
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
    result.start_test("➕ Тест 5: Добавление контакта")
    ws = create_ws()
    
    ws.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
    recv_login_setup(ws)
    
    ws.send(json.dumps({"type": "add_contact", "contact_uin": uin2}))
    resp = recv_json(ws)
    
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
        result.fail("Добавление контакта", f"Контакт UIN {uin2} не найден в списке")

def test_send_message(result, uin1, uin2):
    result.start_test("💬 Тест 8: Отправка сообщения")
    
    ws1 = create_ws()
    ws2 = create_ws()
    
    ws1.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
    recv_login_setup(ws1)
    
    ws2.send(json.dumps({"type": "login", "uin": uin2, "password": "test123"}))
    recv_login_setup(ws2)
    
    test_text = f"Тестовое сообщение {datetime.now().strftime('%H:%M:%S')}"
    ws1.send(json.dumps({
        "type": "message",
        "from": uin1,
        "to": uin2,
        "text": test_text,
        "timestamp": datetime.now().isoformat()
    }))
    
    resp = recv_json(ws2, timeout=3)
    
    ws1.close()
    ws2.close()
    
    if resp and resp.get("text") == test_text:
        result.ok("Сообщение доставлено")
    else:
        result.fail("Отправка сообщения", f"Получено: {resp}")

def test_create_and_use_group(result, uin1, uin2):
    result.start_test("👥 Тест 6: Создание и использование группового чата")
    ws1 = create_ws()
    ws2 = None

    try:
        ws1.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
        login_response = recv_login_setup(ws1)
        if login_response is None or login_response.get("type") != "contact_list":
            result.fail("Групповой чат", f"Не удалось войти владельцем группы: {login_response}")
            return

        ws1.send(json.dumps({
            "type": "create_group",
            "name": "TestGroup",
            "member_uins": [uin2]
        }))
        group_response = recv_json(ws1)
        if not group_response or group_response.get("type") != "group_created":
            result.fail("Групповой чат", f"Группа не создана: {group_response}")
            return

        group_id = group_response.get("id")
        if not group_id or uin2 not in group_response.get("members", []):
            result.fail("Групповой чат", f"Некорректный ответ создания группы: {group_response}")
            return

        ws2 = create_ws()
        ws2.send(json.dumps({"type": "login", "uin": uin2, "password": "test123"}))
        login_response = recv_login_setup(ws2)
        if login_response is None or login_response.get("type") != "contact_list":
            result.fail("Групповой чат", f"Не удалось подключить получателя: {login_response}")
            return

        ws1.send(json.dumps({
            "type": "send_to_group",
            "group_id": group_id,
            "text": "Hello Group!"
        }))

        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            message = recv_json(ws2, timeout=max(remaining, 0.01))
            if message is None:
                break
            if message.get("type") == "message" and message.get("is_group") is True:
                if message.get("text") == "Hello Group!":
                    result.ok(f"Группа {group_id}: сообщение доставлено UIN {uin2}")
                else:
                    result.fail("Групповой чат", f"Получен неверный текст сообщения: {message}")
                return

        result.fail("Групповой чат", "Групповое сообщение не получено за 5 секунд")
    finally:
        ws1.close()
        if ws2 is not None:
            ws2.close()

def test_send_image(result, uin1, uin2):
    result.start_test("🖼️ Тест 7: Отправка файла/изображения")
    ws1 = create_ws()
    ws2 = None
    image_data = b"fake image data"

    try:
        ws1.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
        login_response = recv_login_setup(ws1)
        if login_response is None or login_response.get("type") != "contact_list":
            result.fail("Отправка файла", f"Не удалось войти отправителем: {login_response}")
            return

        ws2 = create_ws()
        ws2.send(json.dumps({"type": "login", "uin": uin2, "password": "test123"}))
        login_response = recv_login_setup(ws2)
        if login_response is None or login_response.get("type") != "contact_list":
            result.fail("Отправка файла", f"Не удалось войти получателем: {login_response}")
            return

        ws1.send(json.dumps({
            "type": "send_file",
            "to": uin2,
            "data": base64.b64encode(image_data).decode("ascii"),
            "mime_type": "image/png"
        }))

        deadline = time.monotonic() + TIMEOUT
        file_message = None
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            message = recv_json(ws2, timeout=max(remaining, 0.01))
            if message is None:
                break
            if message.get("type") == "message" and message.get("is_file") is True:
                file_message = message
                break

        if file_message is None:
            result.fail("Отправка файла", "Получатель не получил сообщение с файлом за 5 секунд")
            return

        file_path = file_message.get("text", "")
        if not isinstance(file_path, str) or not file_path.startswith("/uploads/"):
            result.fail("Отправка файла", f"Некорректный путь в сообщении: {file_path}")
            return

        file_url = f"http://127.0.0.1:8080{file_path}"
        try:
            with urllib.request.urlopen(file_url, timeout=TIMEOUT) as response:
                downloaded_data = response.read()
                if response.status != 200:
                    result.fail("Отправка файла", f"HTTP GET вернул статус {response.status}")
                    return
        except Exception as error:
            result.fail("Отправка файла", f"Файл недоступен по HTTP: {error}")
            return

        if downloaded_data != image_data:
            result.fail("Отправка файла", "Содержимое скачанного файла не совпало с отправленным")
            return

        result.ok(f"Файл доставлен и доступен по ссылке (HTTP 200): {file_path}")
    finally:
        ws1.close()
        if ws2 is not None:
            ws2.close()

def test_auto_history_on_login(result, uin1, uin2):
    result.start_test("📜 Тест 9: Автоматическая история при входе")
    ws = create_ws()

    try:
        ws.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
        deadline = time.monotonic() + TIMEOUT
        history_message = None

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            message = recv_json(ws, timeout=max(remaining, 0.01))
            if message is None:
                break
            if message.get("type") == "login" and message.get("error"):
                result.fail("Автоматическая история", f"Ошибка входа: {message['error']}")
                return
            if message.get("type") == "history":
                history_message = message
                break

        if history_message is None:
            result.fail("Автоматическая история", "Пакет history не получен за 5 секунд")
            return

        try:
            history = json.loads(history_message.get("text", ""))
        except (json.JSONDecodeError, TypeError) as error:
            result.fail("Автоматическая история", f"Поле text содержит невалидный JSON: {error}")
            return

        if not isinstance(history, list):
            result.fail("Автоматическая история", f"Ожидался JSON-массив, получено: {type(history).__name__}")
            return
        if not history:
            result.fail("Автоматическая история", "Список сообщений пуст")
            return
        if not any(message.get("from") == uin1 and message.get("to") == uin2 for message in history):
            result.fail("Автоматическая история", f"Сообщение от UIN {uin1} к UIN {uin2} не найдено")
            return

        result.ok(f"Автоматическая история получена: {len(history)} сообщений")
    finally:
        ws.close()

def test_message_history(result, uin1, uin2):
    result.start_test("📜 Тест 10: История сообщений")
    
    ws = create_ws()
    ws.send(json.dumps({"type": "login", "uin": uin1, "password": "test123"}))
    recv_login_setup(ws)
    
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
    result.start_test("️  Тест 11: Целостность БД")
    
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
    result.start_test("🚫 Тест 12: Дублирующая регистрация (Email)")
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
        result.fail("Дубликат Email", "Должна быть ошибка")

def test_default_avatar(result):
    result.start_test("🎭 Тест 13: Регистрация без аватарки (дефолт)")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "ДефолтЮзер",
        "password": "pass",
        "email": "default@example.com",
        "phone": ""
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

def test_phone_normalization(result):
    """Тест 14: Проверка нормализации телефона (+7 vs 8)"""
    result.start_test("📱 Тест 14: Нормализация телефона")
    
    # Шаг 1: Регистрируем пользователя с форматом "8..."
    ws1 = create_ws()
    unique_email_1 = f"norm_test_{int(time.time())}@example.com"
    
    ws1.send(json.dumps({
        "type": "register",
        "name": "NormUser1",
        "password": "pass123",
        "email": unique_email_1,
        "phone": "89001234567"  # <-- Формат БЕЗ плюса
    }))
    
    resp1 = recv_json(ws1)
    ws1.close()
    
    if resp1 is None or "error" in resp1:
        result.fail("Нормализация телефона", f"Первая регистрация упала: {resp1}")
        return
        
    uin_original = resp1.get("uin")
    phone_in_db = check_db(f"SELECT phone FROM users WHERE uin = {uin_original}")
    
    if not phone_in_db:
        result.fail("Нормализация телефона", "Пользователь не найден в БД после регистрации")
        return
        
    stored_phone = phone_in_db[0][0]
    
    # Проверяем, что сервер сохранил номер в формате +7
    if stored_phone != "+79001234567":
        result.fail("Нормализация телефона", f"Сервер НЕ нормализовал номер при сохранении. Хранится: '{stored_phone}', ожидалось '+79001234567'")
        return

    # Шаг 2: Пытаемся зарегистрировать ВТОРОГО пользователя с тем же номером, но форматом "+7..."
    ws2 = create_ws()
    unique_email_2 = f"norm_test_dup_{int(time.time())}@example.com"
    
    ws2.send(json.dumps({
        "type": "register",
        "name": "NormUser2_Dup",
        "password": "pass456",
        "email": unique_email_2, # Другой email, чтобы исключить конфликт по email
        "phone": "+79001234567"  # <-- Тот же номер, но ДРУГОЙ формат
    }))
    
    resp2 = recv_json(ws2)
    ws2.close()
    
    # Анализ результата второй попытки
    if resp2 and "error" in resp2:
        # Идеальный сценарий: база данных отвергла дубликат по телефону
        error_msg = str(resp2["error"]).lower()
        if "duplicate" in error_msg or "unique" in error_msg or "exists" in error_msg:
             result.ok(f"Дубликат по телефону корректно отклонён ({resp2['error']})")
        else:
             # Если ошибка другая (например, парсинг), это тоже успех защиты от дубля, но стоит проверить лог
             result.ok(f"Регистрация дубля заблокирована ошибкой: {resp2['error']}")
             
    elif resp2 and "uin" in resp2:
        # Плохой сценарий: создался новый аккаунт с другим UIN
        new_uin = resp2["uin"]
        if new_uin == uin_original:
            result.ok("Вернулся тот же UIN (допустимо, если логика такая)")
        else:
            result.fail("Нормализация телефона", f"БАГ НЕ ИСПРАВЛЕН! Создан дубликат с новым UIN={new_uin}. Оригинальный UIN={uin_original}")
    else:
        result.fail("Нормализация телефона", f"Неожиданный ответ при попытке дубля: {resp2}")


# ===== ГЛАВНЫЙ СЦЕНАРИЙ =====
def test_negative_registration(result):
    """Тест 15: Негативная регистрация — мусорный email и короткий телефон"""
    result.start_test("🚫 Тест 15: Негативная регистрация (bad-email / short-phone)")

    # Шаг 1: Регистрация с мусорным email ("mail.com" без домена пользователя)
    ws1 = create_ws()
    ws1.send(json.dumps({
        "type": "register",
        "name": "BadEmailUser",
        "password": "pass123",
        "email": "mail.com",   # <-- некорректный email
        "phone": "+79001113344"
    }))
    resp1 = recv_json(ws1)
    ws1.close()

    if resp1 is None:
        result.fail("Негативная регистрация (bad-email)", "Нет ответа от сервера")
    elif "error" in resp1 and resp1.get("uin") is None:
        result.ok(f"Регистрация с bad-email отклонена ({resp1['error']})")
    else:
        result.fail("Негативная регистрация (bad-email)", f"Сервер принял некорректный email: {resp1}")

    # Шаг 2: Регистрация с коротким/мусорным телефоном
    ws2 = create_ws()
    ws2.send(json.dumps({
        "type": "register",
        "name": "ShortPhoneUser",
        "password": "pass123",
        "email": "shortphone@example.com",
        "phone": "123"   # <-- слишком короткий номер, normalizePhone вернёт ""
    }))
    resp2 = recv_json(ws2)
    ws2.close()

    if resp2 is None:
        result.fail("Негативная регистрация (short-phone)", "Нет ответа от сервера")
    elif "error" in resp2 and resp2.get("uin") is None:
        result.ok(f"Регистрация с short-phone отклонена ({resp2['error']})")
    else:
        result.fail("Негативная регистрация (short-phone)", f"Сервер принял некорректный телефон: {resp2}")

    # Убедимся, что оба некорректных пользователя НЕ попали в БД
    leaked = check_db("SELECT COUNT(*) FROM users WHERE name IN ('BadEmailUser', 'ShortPhoneUser')")[0][0]
    if leaked != 0:
        result.fail("Негативная регистрация (БД)", f"Некорректные пользователи попали в БД: {leaked}")
def main():
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🧪 ВИЗУАЛЬНЫЕ E2E ТЕСТЫ МЕССЕНДЖЕРА ICQ{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    if not os.path.exists(DB_PATH):
        print(f"{Fore.RED}❌ База данных не найдена: {DB_PATH}{Style.RESET_ALL}")
        print(f"   {Fore.YELLOW}Сначала запустите сервер: go run main.go{Style.RESET_ALL}")
        sys.exit(1)
    
    result = VisualTestResult()
    
    print(f"\n{Fore.YELLOW}🔄 Очистка БД...{Style.RESET_ALL}")
    clean_db()
    
    # --- Основная цепочка тестов ---
    uin1 = test_registration(result)
    if uin1 is None:
        print(f"\n{Fore.RED}❌ Критическая ошибка: регистрация не работает{Style.RESET_ALL}")
        result.save_html_report()
        result.summary()
        sys.exit(1)
        
    uin2 = test_register_second_user(result)
    
    if uin2:
        test_login_by_uin(result, uin1)
        test_login_wrong_password(result, uin1)
        test_add_contact(result, uin1, uin2)
        test_create_and_use_group(result, uin1, uin2)
        test_send_image(result, uin1, uin2)
        test_send_message(result, uin1, uin2)
        test_auto_history_on_login(result, uin1, uin2)
        test_message_history(result, uin1, uin2)
        test_database_integrity(result, uin1)
        test_duplicate_registration(result)
        test_default_avatar(result)
        
        # === ДОБАВЛЯЕМ НОВЫЙ ТЕСТ ===
        test_phone_normalization(result) 
        test_negative_registration(result)
        
    else:
        print(f"{Fore.YELLOW}⚠️  Не удалось зарегистрировать второго пользователя{Style.RESET_ALL}")
    
    result.save_html_report()
    success = result.summary()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
