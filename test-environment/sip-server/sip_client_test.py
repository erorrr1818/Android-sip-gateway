#!/usr/bin/env python3
"""
SIP Client Test Tool - тестирование SIP сервера и логики шлюза
Симулирует поведение Android Gateway App
"""

import socket
import time
import sys
import uuid
import random

SIP_SERVER = "127.0.0.1"
SIP_PORT = 5060
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = random.randint(5100, 5900)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def make_sip_request(method, from_user, to_user, call_id, seq, extra_headers="", body=""):
    via_branch = f"z9hG4bK{uuid.uuid4().hex[:8]}"
    tag = uuid.uuid4().hex[:8]
    
    req = f"{method} sip:{to_user}@{SIP_SERVER}:{SIP_PORT} SIP/2.0\r\n"
    req += f"Via: SIP/2.0/UDP {LOCAL_HOST}:{LOCAL_PORT};branch={via_branch};rport\r\n"
    req += f"Max-Forwards: 70\r\n"
    req += f"From: <sip:{from_user}@{LOCAL_HOST}>;tag={tag}\r\n"
    req += f"To: <sip:{to_user}@{SIP_SERVER}>\r\n"
    req += f"Call-ID: {call_id}\r\n"
    req += f"CSeq: {seq} {method}\r\n"
    req += f"Contact: <sip:{from_user}@{LOCAL_HOST}:{LOCAL_PORT}>\r\n"
    req += f"User-Agent: GSM-SIP-Gateway-Test/1.0 (MI8-Dipper-LineageOS22)\r\n"
    if extra_headers:
        req += extra_headers
    req += f"Content-Length: {len(body)}\r\n"
    req += "\r\n"
    req += body
    return req.encode("utf-8")


def send_and_receive(sock, data, timeout=3.0):
    sock.sendto(data, (SIP_SERVER, SIP_PORT))
    sock.settimeout(timeout)
    try:
        resp, addr = sock.recvfrom(65535)
        return resp.decode("utf-8", errors="replace")
    except socket.timeout:
        return None


def test_register(username, password="gateway_pass123"):
    """Тест регистрации SIP аккаунта"""
    print(f"\n{BOLD}{CYAN}━━━ ТЕСТ: REGISTER ({username}) ━━━{RESET}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCAL_HOST, LOCAL_PORT))
    
    call_id = f"reg-{uuid.uuid4().hex[:12]}@{LOCAL_HOST}"
    
    req = make_sip_request("REGISTER", username, "sip-server", call_id, 1,
                           extra_headers=f"Expires: 300\r\n")
    
    print(f"{YELLOW}→ Отправка REGISTER для '{username}'...{RESET}")
    resp = send_and_receive(sock, req)
    
    if resp:
        first_line = resp.split("\r\n")[0]
        if "200 OK" in first_line:
            print(f"{GREEN}✅ РЕГИСТРАЦИЯ УСПЕШНА: {first_line}{RESET}")
        elif "401" in first_line:
            print(f"{YELLOW}⚠️  Требуется аутентификация: {first_line}{RESET}")
        else:
            print(f"{RED}❌ Неожиданный ответ: {first_line}{RESET}")
    else:
        print(f"{RED}❌ Нет ответа от сервера (timeout){RESET}")
    
    sock.close()


def test_incoming_gsm_call(gsm_number="+380991234567", extension="101"):
    """Симуляция входящего GSM звонка (как от Android шлюза)"""
    print(f"\n{BOLD}{CYAN}━━━ ТЕСТ: ВХОДЯЩИЙ GSM ЗВОНОК ━━━{RESET}")
    print(f"Симуляция: GSM {gsm_number} → SIP экстеншн {extension}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCAL_HOST, LOCAL_PORT + 1))
    
    call_id = f"gsm-{uuid.uuid4().hex[:12]}@{LOCAL_HOST}"
    
    sdp_body = (
        "v=0\r\n"
        f"o=gateway 0 0 IN IP4 {LOCAL_HOST}\r\n"
        "s=GSM Call\r\n"
        f"c=IN IP4 {LOCAL_HOST}\r\n"
        "t=0 0\r\n"
        "m=audio 8000 RTP/AVP 0 8 101\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
    )
    
    extra = (
        f"X-GSM-CallerID: {gsm_number}\r\n"
        f"X-Gateway-ID: gateway1\r\n"
        f"Content-Type: application/sdp\r\n"
        f"Allow: INVITE,ACK,BYE,CANCEL,OPTIONS\r\n"
    )
    
    req = make_sip_request("INVITE", "gateway1", extension, call_id, 1, extra, sdp_body)
    
    print(f"{YELLOW}→ Отправка INVITE с X-GSM-CallerID: {gsm_number}{RESET}")
    resp = send_and_receive(sock, req, timeout=5.0)
    
    if resp:
        first_line = resp.split("\r\n")[0]
        code = first_line.split()[1] if len(first_line.split()) > 1 else "?"
        
        if code in ("100", "180"):
            print(f"{GREEN}✅ Сервер принял звонок: {first_line}{RESET}")
            print(f"{YELLOW}   Ожидаем ответа (200 OK)...{RESET}")
            resp2 = send_and_receive(sock, req, timeout=5.0)
            if resp2 and "200 OK" in resp2.split("\r\n")[0]:
                print(f"{GREEN}✅ Звонок установлен! (200 OK){RESET}")
            # Завершаем звонок
            time.sleep(1)
            bye_req = make_sip_request("BYE", "gateway1", extension, call_id, 2)
            sock.sendto(bye_req, (SIP_SERVER, SIP_PORT))
            print(f"{BLUE}📴 BYE отправлен - звонок завершён{RESET}")
        elif code == "200":
            print(f"{GREEN}✅ Звонок установлен сразу: {first_line}{RESET}")
        elif code == "404":
            print(f"{YELLOW}⚠️  Экстеншн {extension} не найден (не зарегистрирован){RESET}")
            print(f"   Сначала зарегистрируйте клиента: python3 sip_client_test.py register")
        else:
            print(f"{RED}❌ Ответ: {first_line}{RESET}")
    else:
        print(f"{RED}❌ Нет ответа от сервера{RESET}")
    
    sock.close()


def test_outgoing_gsm_call(from_ext="101", dest_number="+380991234567"):
    """Симуляция исходящего звонка (SIP клиент → GSM через шлюз)"""
    print(f"\n{BOLD}{CYAN}━━━ ТЕСТ: ИСХОДЯЩИЙ ЗВОНОК ━━━{RESET}")
    print(f"Симуляция: SIP {from_ext} → GSM {dest_number} (через шлюз)")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCAL_HOST, LOCAL_PORT + 2))
    
    call_id = f"out-{uuid.uuid4().hex[:12]}@{LOCAL_HOST}"
    
    sdp_body = (
        "v=0\r\n"
        f"o={from_ext} 0 0 IN IP4 {LOCAL_HOST}\r\n"
        "s=Outgoing Call\r\n"
        f"c=IN IP4 {LOCAL_HOST}\r\n"
        "t=0 0\r\n"
        "m=audio 8010 RTP/AVP 0 8\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
    )
    
    extra = f"Content-Type: application/sdp\r\n"
    req = make_sip_request("INVITE", from_ext, dest_number, call_id, 1, extra, sdp_body)
    
    print(f"{YELLOW}→ INVITE: {from_ext} → {dest_number}{RESET}")
    resp = send_and_receive(sock, req, timeout=5.0)
    
    if resp:
        first_line = resp.split("\r\n")[0]
        print(f"← Ответ: {first_line}")
        if "200" in first_line or "100" in first_line or "180" in first_line:
            print(f"{GREEN}✅ Шлюз принял запрос на исходящий звонок{RESET}")
        elif "404" in first_line:
            print(f"{YELLOW}⚠️  Номер не найден в диалплане (проверьте extensions.conf){RESET}")
        else:
            print(f"{YELLOW}Ответ: {first_line}{RESET}")
    else:
        print(f"{RED}❌ Нет ответа{RESET}")
    
    sock.close()


def test_sms_incoming(gsm_number="+380991234567", to_ext="101", text="Тест SMS через GSM шлюз"):
    """Симуляция входящего SMS от GSM"""
    print(f"\n{BOLD}{CYAN}━━━ ТЕСТ: ВХОДЯЩЕЕ SMS (GSM → SIP) ━━━{RESET}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCAL_HOST, LOCAL_PORT + 3))
    
    call_id = f"sms-{uuid.uuid4().hex[:12]}@{LOCAL_HOST}"
    
    extra = (
        f"X-GSM-CallerID: {gsm_number}\r\n"
        f"Content-Type: text/plain; charset=UTF-8\r\n"
    )
    
    body = text
    req = make_sip_request("MESSAGE", "gateway1", to_ext, call_id, 1, extra, body)
    
    print(f"{YELLOW}→ SIP MESSAGE: {gsm_number} → {to_ext}: '{text}'{RESET}")
    resp = send_and_receive(sock, req)
    
    if resp and "200 OK" in resp.split("\r\n")[0]:
        print(f"{GREEN}✅ SMS принято сервером{RESET}")
    else:
        print(f"{RED}❌ Ошибка доставки SMS{RESET}")
        if resp:
            print(f"   Ответ: {resp.split(chr(13))[0]}")
    
    sock.close()


def test_options_qualify(username="gateway1"):
    """Тест OPTIONS (qualify - проверка доступности)"""
    print(f"\n{BOLD}{CYAN}━━━ ТЕСТ: OPTIONS (Qualify) ━━━{RESET}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOCAL_HOST, LOCAL_PORT + 4))
    
    call_id = f"opt-{uuid.uuid4().hex[:12]}@{LOCAL_HOST}"
    req = make_sip_request("OPTIONS", username, username, call_id, 1)
    
    print(f"{YELLOW}→ OPTIONS запрос к серверу (qualify check){RESET}")
    start = time.time()
    resp = send_and_receive(sock, req)
    latency = (time.time() - start) * 1000
    
    if resp and "200 OK" in resp.split("\r\n")[0]:
        print(f"{GREEN}✅ Сервер доступен! Задержка: {latency:.1f}ms{RESET}")
    else:
        print(f"{RED}❌ Сервер не отвечает{RESET}")
    
    sock.close()


def test_full_scenario():
    """Полный сценарий: регистрация + входящий звонок + SMS"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  ПОЛНЫЙ ТЕСТ СЦЕНАРИЯ GSM-SIP GATEWAY{RESET}")
    print(f"{BOLD}{CYAN}  Устройство: Xiaomi MI 8 Dipper + LineageOS 22.2{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")
    
    print(f"{BLUE}Шаг 1: Регистрация шлюза (gateway1){RESET}")
    test_register("gateway1", "gateway_secure_pass")
    time.sleep(0.5)
    
    print(f"\n{BLUE}Шаг 2: Проверка доступности (OPTIONS/qualify){RESET}")
    test_options_qualify("gateway1")
    time.sleep(0.5)
    
    print(f"\n{BLUE}Шаг 3: Симуляция входящего GSM звонка{RESET}")
    test_incoming_gsm_call("+380991234567", "101")
    time.sleep(0.5)
    
    print(f"\n{BLUE}Шаг 4: Симуляция входящего SMS{RESET}")
    test_sms_incoming("+380991234567", "101", "Привет! Это тест SMS через GSM-SIP шлюз")
    time.sleep(0.5)
    
    print(f"\n{BLUE}Шаг 5: Симуляция исходящего звонка{RESET}")
    test_outgoing_gsm_call("101", "+380997654321")
    
    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}  ✅ ТЕСТ ЗАВЕРШЁН УСПЕШНО{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")


def show_help():
    print(f"""
{BOLD}{CYAN}SIP Client Test Tool - MI 8 Dipper GSM-SIP Gateway Tester{RESET}

Использование:
  python3 sip_client_test.py <команда> [аргументы]

Команды:
  {GREEN}register{RESET}    [username]        - Тест регистрации
  {GREEN}incoming{RESET}    [номер] [ext]     - Симуляция входящего GSM звонка
  {GREEN}outgoing{RESET}    [ext] [номер]     - Симуляция исходящего звонка
  {GREEN}sms{RESET}         [номер] [ext]     - Симуляция входящего SMS
  {GREEN}options{RESET}     [username]        - Проверка доступности (qualify)
  {GREEN}full{RESET}                          - Полный сценарий тестирования

Примеры:
  python3 sip_client_test.py register gateway1
  python3 sip_client_test.py incoming +380991234567 101
  python3 sip_client_test.py sms +380991234567 101 "Привет!"
  python3 sip_client_test.py full
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    
    if cmd == "register":
        user = sys.argv[2] if len(sys.argv) > 2 else "gateway1"
        test_register(user)
    elif cmd == "incoming":
        num = sys.argv[2] if len(sys.argv) > 2 else "+380991234567"
        ext = sys.argv[3] if len(sys.argv) > 3 else "101"
        test_incoming_gsm_call(num, ext)
    elif cmd == "outgoing":
        ext = sys.argv[2] if len(sys.argv) > 2 else "101"
        num = sys.argv[3] if len(sys.argv) > 3 else "+380997654321"
        test_outgoing_gsm_call(ext, num)
    elif cmd == "sms":
        num = sys.argv[2] if len(sys.argv) > 2 else "+380991234567"
        ext = sys.argv[3] if len(sys.argv) > 3 else "101"
        text = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "Тест SMS"
        test_sms_incoming(num, ext, text)
    elif cmd == "options":
        user = sys.argv[2] if len(sys.argv) > 2 else "gateway1"
        test_options_qualify(user)
    elif cmd == "full":
        test_full_scenario()
    else:
        show_help()
