#!/usr/bin/env python3
"""
SIP Test Server - симулятор для тестирования GSM-SIP Gateway
Тестирует логику без реального Asterisk
Автор: Адаптировано для MI 8 Dipper + LineageOS 22.2
"""

import socket
import threading
import time
import re
import sqlite3
import os
import sys
import json
from datetime import datetime

DB_PATH = "/home/user/webapp/test-environment/gateway_events_test.db"
SIP_PORT = 5060
SIP_HOST = "0.0.0.0"

# Цвета для терминала
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(level, msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {"INFO": GREEN, "WARN": YELLOW, "ERROR": RED, "SIP": CYAN, "CALL": BLUE}
    c = colors.get(level, RESET)
    print(f"{c}[{ts}] [{level}] {msg}{RESET}")


def init_db():
    """Инициализация тестовой БД"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            gateway_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            from_number TEXT,
            to_number TEXT,
            message_text TEXT,
            sip_delivered BOOLEAN DEFAULT 0,
            tg_delivered BOOLEAN DEFAULT 0,
            retry_count INTEGER DEFAULT 0,
            last_retry DATETIME
        )
    """)
    conn.commit()
    conn.close()
    log("INFO", f"База данных инициализирована: {DB_PATH}")


def save_event(gateway_id, event_type, from_num, to_num, msg_text=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO events (gateway_id, event_type, from_number, to_number, message_text)
        VALUES (?, ?, ?, ?, ?)
    """, (gateway_id, event_type, from_num, to_num, msg_text))
    conn.commit()
    event_id = c.lastrowid
    conn.close()
    return event_id


def get_pending_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE sip_delivered=0 ORDER BY timestamp DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    return rows


# SIP зарегистрированные клиенты {username: (ip, port, contact)}
registered_clients = {}
registered_lock = threading.Lock()

# Активные звонки
active_calls = {}


class SIPServer:
    def __init__(self, host=SIP_HOST, port=SIP_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.running = False

    def parse_sip(self, data):
        """Базовый парсер SIP-сообщений"""
        try:
            text = data.decode("utf-8", errors="replace")
            lines = text.split("\r\n")
            if not lines:
                return None

            first_line = lines[0]
            headers = {}
            body = ""
            in_body = False

            for line in lines[1:]:
                if line == "":
                    in_body = True
                    continue
                if in_body:
                    body += line + "\r\n"
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    headers[key.strip().lower()] = val.strip()

            return {
                "first_line": first_line,
                "headers": headers,
                "body": body,
                "raw": text
            }
        except Exception as e:
            log("ERROR", f"Ошибка парсинга SIP: {e}")
            return None

    def get_from_user(self, msg):
        from_h = msg["headers"].get("from", "")
        m = re.search(r"sip:([^@>]+)@", from_h)
        return m.group(1) if m else "unknown"

    def get_to_user(self, msg):
        to_h = msg["headers"].get("to", "")
        m = re.search(r"sip:([^@>]+)@", to_h)
        return m.group(1) if m else "unknown"

    def get_call_id(self, msg):
        return msg["headers"].get("call-id", "")

    def make_response(self, msg, code, reason, extra_headers="", body=""):
        """Создание SIP-ответа"""
        via = msg["headers"].get("via", "")
        from_h = msg["headers"].get("from", "")
        to_h = msg["headers"].get("to", "")
        call_id = msg["headers"].get("call-id", "")
        cseq = msg["headers"].get("cseq", "")

        resp = f"SIP/2.0 {code} {reason}\r\n"
        resp += f"Via: {via}\r\n"
        resp += f"From: {from_h}\r\n"
        resp += f"To: {to_h}\r\n"
        resp += f"Call-ID: {call_id}\r\n"
        resp += f"CSeq: {cseq}\r\n"
        if extra_headers:
            resp += extra_headers
        resp += f"Content-Length: {len(body)}\r\n"
        resp += "\r\n"
        resp += body
        return resp.encode("utf-8")

    def handle_register(self, msg, addr):
        """Обработка REGISTER"""
        user = self.get_from_user(msg)
        contact = msg["headers"].get("contact", "")
        expires = int(msg["headers"].get("expires", "3600"))

        if expires == 0:
            # Отмена регистрации
            with registered_lock:
                if user in registered_clients:
                    del registered_clients[user]
            log("SIP", f"❌ Отменена регистрация: {user}")
        else:
            with registered_lock:
                registered_clients[user] = {
                    "ip": addr[0],
                    "port": addr[1],
                    "contact": contact,
                    "expires": expires,
                    "registered_at": time.time()
                }
            log("SIP", f"✅ Зарегистрирован: {user} с {addr[0]}:{addr[1]} (expires: {expires}s)")

        # 200 OK ответ
        extra = f"Contact: {contact}\r\nExpires: {expires}\r\n"
        resp = self.make_response(msg, 200, "OK", extra)
        self.sock.sendto(resp, addr)

    def handle_invite(self, msg, addr):
        """Обработка INVITE (входящий звонок)"""
        from_user = self.get_from_user(msg)
        to_user = self.get_to_user(msg)
        call_id = self.get_call_id(msg)

        # X-GSM-CallerID для входящих от шлюза
        gsm_caller = msg["headers"].get("x-gsm-callerid", "")

        if gsm_caller:
            log("CALL", f"📞 ВХОДЯЩИЙ ИЗ GSM: {gsm_caller} → экстеншн {to_user}")
            save_event("gateway1", "incoming_call", gsm_caller, to_user)
        else:
            log("CALL", f"📞 SIP ЗВОНОК: {from_user} → {to_user}")
            save_event("internal", "outgoing_call", from_user, to_user)

        # 100 Trying
        self.sock.sendto(self.make_response(msg, 100, "Trying"), addr)
        time.sleep(0.2)

        # Проверяем зарегистрирован ли получатель
        with registered_lock:
            target = registered_clients.get(to_user)

        if target:
            # 180 Ringing
            self.sock.sendto(self.make_response(msg, 180, "Ringing"), addr)
            log("CALL", f"🔔 Звоним на {to_user} @ {target['ip']}:{target['port']}")
            active_calls[call_id] = {"from": from_user, "to": to_user, "addr": addr}

            # Симуляция: через 2 секунды отправляем 200 OK
            def answer():
                time.sleep(2)
                sdp_body = (
                    "v=0\r\n"
                    f"o={to_user} 0 0 IN IP4 127.0.0.1\r\n"
                    "s=Test Call\r\n"
                    "c=IN IP4 127.0.0.1\r\n"
                    "t=0 0\r\n"
                    "m=audio 8000 RTP/AVP 0 8\r\n"
                    "a=rtpmap:0 PCMU/8000\r\n"
                    "a=rtpmap:8 PCMA/8000\r\n"
                )
                extra = f"Contact: <sip:{to_user}@127.0.0.1>\r\nContent-Type: application/sdp\r\n"
                resp_200 = self.make_response(msg, 200, "OK", extra, sdp_body)
                self.sock.sendto(resp_200, addr)
                log("CALL", f"✅ Звонок отвечен: {from_user} ↔ {to_user}")

            threading.Thread(target=answer, daemon=True).start()
        else:
            log("WARN", f"⚠️  Получатель {to_user} не зарегистрирован")
            self.sock.sendto(self.make_response(msg, 404, "Not Found"), addr)

    def handle_bye(self, msg, addr):
        call_id = self.get_call_id(msg)
        if call_id in active_calls:
            call = active_calls.pop(call_id)
            log("CALL", f"📴 Звонок завершён: {call['from']} ↔ {call['to']}")
        self.sock.sendto(self.make_response(msg, 200, "OK"), addr)

    def handle_message(self, msg, addr):
        """Обработка SMS через SIP MESSAGE"""
        from_user = self.get_from_user(msg)
        to_user = self.get_to_user(msg)
        body = msg.get("body", "").strip()
        gsm_sender = msg["headers"].get("x-gsm-callerid", "")

        if gsm_sender:
            log("SIP", f"💬 SMS ИЗ GSM: {gsm_sender} → {to_user}: {body[:50]}")
            event_id = save_event("gateway1", "incoming_sms", gsm_sender, to_user, body)
            log("INFO", f"📝 SMS сохранён в БД, event_id={event_id}")
        else:
            log("SIP", f"💬 SIP СООБЩЕНИЕ: {from_user} → {to_user}: {body[:50]}")
            save_event("internal", "internal_message", from_user, to_user, body)

        self.sock.sendto(self.make_response(msg, 200, "OK"), addr)

    def handle_options(self, msg, addr):
        """OPTIONS - проверка доступности (qualify)"""
        user = self.get_from_user(msg)
        extra = "Allow: INVITE,ACK,CANCEL,BYE,REGISTER,OPTIONS,MESSAGE\r\n"
        self.sock.sendto(self.make_response(msg, 200, "OK", extra), addr)

    def handle_cancel(self, msg, addr):
        call_id = self.get_call_id(msg)
        if call_id in active_calls:
            active_calls.pop(call_id)
        self.sock.sendto(self.make_response(msg, 200, "OK"), addr)

    def handle_ack(self, msg, addr):
        pass  # ACK не требует ответа

    def process_message(self, data, addr):
        msg = self.parse_sip(data)
        if not msg:
            return

        first_line = msg["first_line"]

        if first_line.startswith("REGISTER"):
            self.handle_register(msg, addr)
        elif first_line.startswith("INVITE"):
            threading.Thread(target=self.handle_invite, args=(msg, addr), daemon=True).start()
        elif first_line.startswith("BYE"):
            self.handle_bye(msg, addr)
        elif first_line.startswith("MESSAGE"):
            self.handle_message(msg, addr)
        elif first_line.startswith("OPTIONS"):
            self.handle_options(msg, addr)
        elif first_line.startswith("CANCEL"):
            self.handle_cancel(msg, addr)
        elif first_line.startswith("ACK"):
            self.handle_ack(msg, addr)
        elif first_line.startswith("SIP/2.0"):
            # Ответ на наш запрос
            code = first_line.split()[1] if len(first_line.split()) > 1 else "???"
            log("SIP", f"← Получен ответ: {code} от {addr[0]}:{addr[1]}")

    def run(self):
        self.running = True
        log("INFO", f"{BOLD}🚀 SIP Test Server запущен на {self.host}:{self.port}{RESET}")
        log("INFO", "Ожидаем подключения от Gateway приложения на MI 8 Dipper...")
        log("INFO", f"Протокол: UDP/SIP | Порт: {self.port}")

        while self.running:
            try:
                self.sock.settimeout(1.0)
                data, addr = self.sock.recvfrom(65535)
                log("SIP", f"← Пакет от {addr[0]}:{addr[1]} ({len(data)} bytes)")
                threading.Thread(
                    target=self.process_message,
                    args=(data, addr),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    log("ERROR", f"Ошибка сервера: {e}")

    def stop(self):
        self.running = False
        self.sock.close()


def status_monitor():
    """Периодический вывод статуса"""
    while True:
        time.sleep(30)
        with registered_lock:
            clients = list(registered_clients.items())

        log("INFO", f"━━━ Статус системы ━━━")
        log("INFO", f"Зарегистрированных клиентов: {len(clients)}")
        for user, info in clients:
            log("INFO", f"  • {user} @ {info['ip']}:{info['port']}")
        log("INFO", f"Активных звонков: {len(active_calls)}")

        # Проверка БД
        pending = get_pending_events()
        if pending:
            log("WARN", f"Ожидают доставки SMS: {len(pending)}")


def print_banner():
    print(f"""
{BOLD}{CYAN}
╔══════════════════════════════════════════════════════════════════╗
║         GSM-SIP Gateway - Тестовый Сервер                      ║
║         Адаптировано для: Xiaomi MI 8 Dipper                    ║
║         LineageOS 22.2 | Snapdragon 845 | arm64-v8a             ║
╠══════════════════════════════════════════════════════════════════╣
║  Порт SIP:     5060 (UDP)                                        ║
║  База данных:  {DB_PATH:<52}║
╚══════════════════════════════════════════════════════════════════╝
{RESET}""")
    print(f"{YELLOW}Для проверки регистрации: python3 sip_client_test.py register{RESET}")
    print(f"{YELLOW}Для симуляции входящего:  python3 sip_client_test.py incoming{RESET}")
    print(f"{YELLOW}Для исходящего звонка:    python3 sip_client_test.py outgoing{RESET}")
    print()


if __name__ == "__main__":
    print_banner()
    init_db()

    server = SIPServer()

    # Мониторинг статуса в фоне
    threading.Thread(target=status_monitor, daemon=True).start()

    try:
        server.run()
    except KeyboardInterrupt:
        log("INFO", "Остановка сервера...")
        server.stop()
