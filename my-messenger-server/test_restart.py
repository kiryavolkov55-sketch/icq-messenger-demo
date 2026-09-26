"""
Тест на сохранение данных при перезапуске сервера (Persistence Test)
Запуск: py test_restart.py
"""

import subprocess
import time
import websocket
import json
import os
import sys

SERVER_URL = "ws://localhost:8080/ws"
TIMEOUT = 5
SERVER_EXE = "test_server.exe"

def create_ws():
    try:
        ws = websocket.create_connection(SERVER_URL, timeout=TIMEOUT)
        return ws
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        sys.exit(1)

def recv_json(ws, timeout=TIMEOUT):
    ws.settimeout(timeout)
    try:
        msg = ws.recv()
        return json.loads(msg)
    except websocket.WebSocketTimeoutException:
        return None
    except Exception:
        return None

def main():
    print("="*60)
    print("🔄 ТЕСТ НА ПЕРЕЗАПУСК СЕРВЕРА (PERSISTENCE TEST)")
    print("="*60)
    
    server_process = None
    
    try:
        # ==========================================
        # ШАГ 0: Компиляция сервера (чтобы запуск был мгновенным)
        # ==========================================
        print("\n🔨 Компиляция тестового сервера...")
        build_result = subprocess.run(
            ["go", "build", "-o", SERVER_EXE],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True
        )
        if build_result.returncode != 0:
            print(f"❌ Ошибка компиляции:\n{build_result.stderr}")
            sys.exit(1)
        print("  ✅ Сервер скомпилирован")

        # ==========================================
        # ФАЗА 1: Запуск сервера и создание данных
        # ==========================================
        print("\n🚀 Фаза 1: Запуск сервера...")
        server_process = subprocess.Popen(
            [SERVER_EXE],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)  # 1 секунды достаточно для запуска готового .exe
        
        print("📝 Создаём тестовые данные...")
        
        # 1. Регистрируем основного пользователя
        ws1 = create_ws()
        ws1.send(json.dumps({
            "type": "register", "name": "PersistUser", "password": "secure123", 
            "email": "persist@test.com", "phone": ""
        }))
        resp1 = recv_json(ws1)
        uin = resp1.get("uin")
        ws1.close()
        print(f"  ✅ Зарегистрирован пользователь: UIN {uin}")
        
        # 2. Регистрируем друга
        ws2 = create_ws()
        ws2.send(json.dumps({
            "type": "register", "name": "Friend", "password": "secure123", 
            "email": "friend@test.com", "phone": ""
        }))
        resp2 = recv_json(ws2)
        friend_uin = resp2.get("uin")
        ws2.close()
        print(f"  ✅ Зарегистрирован друг: UIN {friend_uin}")
        
        # 3. Отправляем сообщение
        ws3 = create_ws()
        ws3.send(json.dumps({"type": "login", "uin": uin, "password": "secure123"}))
        recv_json(ws3)  # login
        recv_json(ws3)  # contact_list
        
        test_message = "🔥 Это сообщение должно пережить перезапуск сервера! 🔥"
        ws3.send(json.dumps({
            "type": "message",
            "from": uin,
            "to": friend_uin,
            "text": test_message,
            "timestamp": "2026-09-14T12:00:00Z"
        }))
        ws3.close()
        print("  ✅ Сообщение отправлено и сохранено в БД")
        
        # ==========================================
        # ФАЗА 2: Жёсткий перезапуск сервера
        # ==========================================
        print("\n💥 ИМИТАЦИЯ СБОЯ / ПЕРЕЗАПУСК СЕРВЕРА...")
        server_process.terminate()
        server_process.wait()
        time.sleep(1)
        
        print("🚀 Фаза 2: Повторный запуск сервера...")
        server_process = subprocess.Popen(
            [SERVER_EXE],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        
        # ==========================================
        # ФАЗА 3: Проверка сохранности данных
        # ==========================================
        print("\n🔍 Проверяем, выжили ли данные...")
        
        ws4 = create_ws()
        ws4.send(json.dumps({"type": "login", "uin": uin, "password": "secure123"}))
        resp_login = recv_json(ws4)
        
        if resp_login and resp_login.get("type") == "login" and resp_login.get("uin") == uin:
            print("  ✅ Вход после перезапуска успешен")
        else:
            print("  ❌ Не удалось войти после перезапуска!")
            return
            
        recv_json(ws4)  # contact_list
        
        ws4.send(json.dumps({"type": "history", "uin": friend_uin}))
        resp_history = recv_json(ws4)
        ws4.close()
        
        if resp_history and resp_history.get("type") == "history":
            history_text = resp_history.get("text", "[]")
            history = json.loads(history_text) if history_text != "null" else []
            
            found = any(msg.get("text") == test_message for msg in history)
            
            if found:
                print(f"  ✅ ИСТОРИЯ СОХРАНЕНА! Найдено сообщение: '{test_message}'")
                print("\n" + "="*60)
                print("🎉 ТЕСТ ПРОЙДЕН! Сервер корректно сохраняет данные в БД.")
                print("="*60)
            else:
                print("  ❌ История пуста или сообщение потеряно при перезапуске!")
                print(f"     Полученная история: {history}")
        else:
            print(f"  ❌ Ошибка получения истории: {resp_history}")
            
    except Exception as e:
        print(f"\n❌ Критическая ошибка во время теста: {e}")
        
    finally:
        # Гарантированная очистка
        if server_process and server_process.poll() is None:
            server_process.terminate()
            server_process.wait()
        
        # Удаляем временный exe-файл
        if os.path.exists(SERVER_EXE):
            os.remove(SERVER_EXE)
            print("\n🛑 Тестовый сервер остановлен и очищен.")

if __name__ == "__main__":
    main()