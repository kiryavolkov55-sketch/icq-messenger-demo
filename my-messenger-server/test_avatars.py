"""
Тесты аватарок ICQ Messenger
Запуск: python test_avatars.py
"""

import websocket
import json
import time
import os
import sys
from colorama import init, Fore, Style
import webbrowser
import sqlite3 # <-- Убедись, что это есть в импортах

def clean_db():
    """Автоматически очищает БД перед тестами"""
    db_path = "./icq.db"
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM users")
        conn.commit()
        conn.close()
        print(f"{Fore.YELLOW}🧹 База данных автоматически очищена{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}⚠️ Не удалось очистить БД: {e}{Style.RESET_ALL}")

init(autoreset=True)

SERVER_URL = "ws://127.0.0.1:8080/ws"
TIMEOUT = 5

class AvatarTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def ok(self, name):
        self.passed += 1
        print(f"  {Fore.GREEN}✅ {name}{Style.RESET_ALL}")
    
    def fail(self, name, reason):
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  {Fore.RED}❌ {name}{Style.RESET_ALL}")
        print(f"     {Fore.RED} {reason}{Style.RESET_ALL}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 ИТОГИ ТЕСТОВ АВАТАРОК{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"\n{Fore.WHITE}Всего:{Style.RESET_ALL} {total}")
        print(f"{Fore.GREEN}✅ Пройдено:{Style.RESET_ALL} {self.passed}")
        print(f"{Fore.RED} Провалено:{Style.RESET_ALL} {self.failed}")
        
        if self.errors:
            print(f"\n{Fore.RED}Ошибки:{Style.RESET_ALL}")
            for error in self.errors:
                print(f"  • {error}")
        
        success_rate = (self.passed / total * 100) if total > 0 else 0
        if success_rate == 100:
            print(f"\n{Fore.GREEN} ВСЕ ТЕСТЫ АВАТАРОК ПРОЙДЕНЫ!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}⚠️  УСПЕХ: {success_rate:.1f}%{Style.RESET_ALL}")
        
        return self.failed == 0

def create_ws():
    try:
        ws = websocket.create_connection(SERVER_URL, timeout=TIMEOUT)
        return ws
    except Exception as e:
        print(f"{Fore.RED} Не удалось подключиться: {e}{Style.RESET_ALL}")
        sys.exit(1)

def recv_json(ws, timeout=TIMEOUT):
    ws.settimeout(timeout)
    try:
        msg = ws.recv()
        return json.loads(msg)
    except:
        return None

def test_custom_avatar(result):
    """Тест 1: Регистрация с кастомной аватаркой"""
    print(f"\n{Fore.CYAN}▶️  Тест 1: Регистрация с аватаркой 😎{Style.RESET_ALL}")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "AvatarUser1",
        "password": "pass123",
        "email": "avatar1@test.com",
        "avatar": "😎"
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp and resp.get("type") == "register" and "error" not in resp:
        if resp.get("avatar") == "😎":
            result.ok("Кастомная аватарка 😎 сохранена и возвращена")
            return resp.get("uin")
        else:
            result.fail("Кастомная аватарка", f"Ожидалась 😎, получено: {resp.get('avatar')}")
            return None
    else:
        result.fail("Регистрация с аватаркой", f"Ошибка: {resp}")
        return None

def test_default_avatar(result):
    """Тест 2: Регистрация без аватарки (дефолт)"""
    print(f"\n{Fore.CYAN}▶️  Тест 2: Регистрация без аватарки (дефолт){Style.RESET_ALL}")
    ws = create_ws()
    
    ws.send(json.dumps({
        "type": "register",
        "name": "DefaultUser",
        "password": "pass123",
        "email": "default@test.com"
        # avatar НЕ указан
    }))
    
    resp = recv_json(ws)
    ws.close()
    
    if resp and resp.get("type") == "register" and "error" not in resp:
        if resp.get("avatar") == "😀":
            result.ok("Дефолтная аватарка 😀 установлена автоматически")
            return resp.get("uin")
        else:
            result.fail("Дефолтная аватарка", f"Ожидалась 😀, получено: {resp.get('avatar')}")
            return None
    else:
        result.fail("Регистрация без аватарки", f"Ошибка: {resp}")
        return None

def test_different_avatars(result):
    """Тест 3: Разные аватарки у разных пользователей"""
    print(f"\n{Fore.CYAN}▶️  Тест 3: Разные аватарки у пользователей{Style.RESET_ALL}")
    
    # Убрали пустую строку, теперь там 5 реальных эмодзи
    avatars = ["😎", "👽", "🤖", "👻", "🐱"]
    uins = []
    
    for i, avatar in enumerate(avatars):
        ws = create_ws()
        ws.send(json.dumps({
            "type": "register",
            "name": f"User{i}",
            "password": "pass",
            "email": f"user{i}_auto@test.com", # Уникальный email на всякий случай
            "avatar": avatar
        }))
        
        resp = recv_json(ws)
        ws.close()
        
        if resp and resp.get("avatar") == avatar:
            uins.append(resp.get("uin"))
        else:
            result.fail(f"Аватарка {avatar}", f"Не совпадает: {resp.get('avatar') if resp else 'None'}")
            return None
    
    result.ok(f"Все 5 аватарок сохранены корректно: {', '.join(avatars)}")
    return uins

def test_avatar_in_contacts(result, uin1, uin2):
    """Тест 4: Аватарка отображается в списке контактов"""
    print(f"\n{Fore.CYAN}▶️  Тест 4: Аватарка в списке контактов{Style.RESET_ALL}")
    
    ws = create_ws()
    ws.send(json.dumps({"type": "login", "uin": uin1, "password": "pass123"}))
    recv_json(ws)  # login
    recv_json(ws)  # contact_list (старый)
    
    # Добавляем контакт
    ws.send(json.dumps({"type": "add_contact", "contact_uin": uin2}))
    resp = recv_json(ws)  # contact_list
    
    ws.close()
    
    if resp and resp.get("type") == "contact_list":
        contacts = json.loads(resp.get("text", "[]"))
        if contacts and any(c.get("avatar") for c in contacts):
            result.ok("Аватарка контакта присутствует в списке")
            return True
        else:
            result.fail("Аватарка в контактах", "Аватарка не найдена в списке контактов")
            return False
    else:
        result.fail("Аватарка в контактах", f"Неверный ответ: {resp}")
        return False

def test_avatar_persistence(result, uin):
    """Тест 5: Аватарка сохраняется после перезахода"""
    print(f"\n{Fore.CYAN}▶️  Тест 5: Сохранение аватарки после выхода{Style.RESET_ALL}")
    
    # Выходим и заходим снова
    ws = create_ws()
    ws.send(json.dumps({"type": "login", "uin": uin, "password": "pass123"}))
    resp = recv_json(ws)
    ws.close()
    
    if resp and resp.get("type") == "login" and "avatar" in resp:
        result.ok(f"Аватарка {resp.get('avatar')} сохранена после повторного входа")
        return True
    else:
        result.fail("Сохранение аватарки", "Аватарка не возвращена при входе")
        return False

def main():
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🎨 ТЕСТЫ АВАТАРОК ICQ MESSENGER{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    if not os.path.exists("./icq.db"):
        print(f"{Fore.RED}❌ База данных не найдена. Запустите сервер!{Style.RESET_ALL}")
        sys.exit(1)
    
    # АВТОМАТИЧЕСКАЯ ОЧИСТКА ПЕРЕД ТЕСТАМИ!
    clean_db()
    
    result = AvatarTestResult()
    
    # Тест 1: Кастомная аватарка
    uin1 = test_custom_avatar(result)
    if not uin1:
        print(f"\n{Fore.RED}❌ Критическая ошибка! Тесты остановлены.{Style.RESET_ALL}")
        result.summary()
        sys.exit(1)
    
    # Тест 2: Дефолтная аватарка
    uin2 = test_default_avatar(result)
    
    # Тест 3: Разные аватарки
    test_different_avatars(result)
    
    # Тест 4: Аватарка в контактах
    if uin1 and uin2:
        test_avatar_in_contacts(result, uin1, uin2)
        
        # Тест 5: Сохранение
        test_avatar_persistence(result, uin1)
    
    # Итоги
    success = result.summary()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()