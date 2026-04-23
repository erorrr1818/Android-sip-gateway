#!/bin/bash
# ============================================================
# Полный тест-сценарий GSM-SIP Gateway
# Запускает тестовый SIP сервер и прогоняет все тесты
# ============================================================

GREEN="\033[92m"
RED="\033[91m"
YELLOW="\033[93m"
CYAN="\033[96m"
BOLD="\033[1m"
RESET="\033[0m"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SIP_DIR="$SCRIPT_DIR/sip-server"

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     GSM-SIP Gateway Full Test Suite                     ║"
echo "║     MI 8 Dipper + LineageOS 22.2 + Asterisk              ║"  
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# Проверяем Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ Python3 не найден!${RESET}"
    exit 1
fi

# Убиваем старый сервер если есть
pkill -f "sip_test_server.py" 2>/dev/null
sleep 1

# Запускаем тестовый SIP сервер
echo -e "${YELLOW}▶ Запускаем тестовый SIP сервер...${RESET}"
python3 "$SIP_DIR/sip_test_server.py" &
SIP_PID=$!
sleep 2

# Проверяем что сервер запущен
if ! kill -0 $SIP_PID 2>/dev/null; then
    echo -e "${RED}❌ Не удалось запустить SIP сервер!${RESET}"
    exit 1
fi
echo -e "${GREEN}✅ SIP сервер запущен (PID: $SIP_PID, порт: 5060)${RESET}"

# Прогоняем тесты
echo -e "\n${BOLD}Запуск тест-сценария...${RESET}\n"
python3 "$SIP_DIR/sip_client_test.py" full
TEST_RESULT=$?

# Останавливаем сервер
kill $SIP_PID 2>/dev/null
wait $SIP_PID 2>/dev/null

# Показываем БД
echo -e "\n${BOLD}${CYAN}━━━ Данные из тестовой БД ━━━${RESET}"
DB="$SCRIPT_DIR/gateway_events_test.db"
if [ -f "$DB" ]; then
    sqlite3 "$DB" "SELECT id, timestamp, event_type, from_number, to_number FROM events ORDER BY id DESC LIMIT 10;" | \
    while IFS='|' read id ts et fn tn; do
        echo -e "  ${GREEN}[#$id]${RESET} $ts | ${CYAN}$et${RESET} | $fn → $tn"
    done
else
    echo -e "${YELLOW}  БД не найдена${RESET}"
fi

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${BOLD}${GREEN}✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!${RESET}"
    echo -e "${GREEN}   Система готова к развёртыванию на MI 8 Dipper${RESET}"
else
    echo -e "${BOLD}${RED}❌ ЕСТЬ ПРОБЛЕМЫ В ТЕСТАХ${RESET}"
fi

echo ""
echo -e "${YELLOW}Следующий шаг: см. MASTER_GUIDE_MI8_DIPPER.md${RESET}"
