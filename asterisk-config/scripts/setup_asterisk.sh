#!/bin/bash
# ═══════════════════════════════════════════════════
# dber88-sip | Скрипт автоматической установки Asterisk
# Запускай на Ubuntu 24.04 VPS от root
# ═══════════════════════════════════════════════════

set -e

echo "════════════════════════════════════════"
echo "  dber88-sip | Установка Asterisk"
echo "════════════════════════════════════════"

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запусти скрипт от root: sudo bash setup_asterisk.sh"
    exit 1
fi

# Получаем параметры
read -p "Введи IP этого VPS (или оставь пустым для автоопределения): " VPS_IP
if [ -z "$VPS_IP" ]; then
    VPS_IP=$(curl -s ifconfig.me)
    echo "Автоопределён IP: $VPS_IP"
fi

read -s -p "Придумай пароль для MicroSIP (extension 101): " PASS_MICROSIP
echo
read -s -p "Придумай пароль для Mi 8 (gateway): " PASS_GATEWAY
echo

echo ""
echo "📦 Устанавливаем пакеты..."
apt update -q
apt install -y asterisk python3 python3-pip sqlite3 ufw curl

echo "🔥 Настраиваем файрвол..."
ufw --force enable
ufw allow 22/tcp
ufw allow 5060/udp
ufw allow 5060/tcp
ufw allow 5061/tcp
ufw allow 10000:10100/udp

echo "⚙️ Создаём конфигурацию Asterisk..."

# Backup старых конфигов
cp /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.conf.bak 2>/dev/null || true
cp /etc/asterisk/extensions.conf /etc/asterisk/extensions.conf.bak 2>/dev/null || true

# pjsip.conf
cat > /etc/asterisk/pjsip.conf << PJSIP_EOF
[global]
type=global
endpoint_identifier_order=username,ip,anonymous

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[101]
type=endpoint
context=internal
disallow=all
allow=opus
allow=ulaw
allow=alaw
allow=g722
auth=101
aors=101
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
trust_id_inbound=yes
send_rpid=yes

[101]
type=auth
auth_type=userpass
username=101
password=${PASS_MICROSIP}

[101]
type=aor
qualify_frequency=30
max_contacts=3
remove_existing=yes

[gateway1]
type=endpoint
context=from-gateways
disallow=all
allow=opus
allow=ulaw
allow=alaw
auth=gateway1
aors=gateway1
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
trust_id_inbound=yes
send_rpid=yes

[gateway1]
type=auth
auth_type=userpass
username=gateway1
password=${PASS_GATEWAY}

[gateway1]
type=aor
qualify_frequency=30
max_contacts=2
remove_existing=no
PJSIP_EOF

# extensions.conf
cat > /etc/asterisk/extensions.conf << EXT_EOF
[general]
static=yes
writeprotect=no

[internal]
exten => 101,1,NoOp(Call to MicroSIP 101)
 same => n,Dial(PJSIP/101,60)
 same => n,Hangup()

exten => _+7XXXXXXXXXX,1,NoOp(Outgoing via GSM)
 same => n,Dial(PJSIP/\${EXTEN}@gateway1,60)
 same => n,Hangup()

exten => _7XXXXXXXXXX,1,NoOp(Outgoing via GSM)
 same => n,Dial(PJSIP/\${EXTEN}@gateway1,60)
 same => n,Hangup()

exten => _8XXXXXXXXXX,1,NoOp(Outgoing via GSM)
 same => n,Dial(PJSIP/\${EXTEN}@gateway1,60)
 same => n,Hangup()

exten => _+XXXXXXXXXXX,1,NoOp(Outgoing international via GSM)
 same => n,Dial(PJSIP/\${EXTEN}@gateway1,60)
 same => n,Hangup()

[from-gateways]
exten => _X.,1,NoOp(Incoming GSM call)
 same => n,Set(GSM_CALLER=\${PJSIP_HEADER(read,X-GSM-CallerID)})
 same => n,GotoIf(\$["\${GSM_CALLER}" != ""]?set_caller:skip_caller)
 same => n(set_caller),Set(CALLERID(num)=\${GSM_CALLER})
 same => n,Set(CALLERID(name)=\${GSM_CALLER})
 same => n(skip_caller),Dial(PJSIP/101,60)
 same => n,Hangup()
EXT_EOF

# rtp.conf
cat > /etc/asterisk/rtp.conf << RTP_EOF
[general]
rtpstart=10000
rtpend=10100
RTP_EOF

echo "🔄 Перезапускаем Asterisk..."
systemctl restart asterisk
systemctl enable asterisk

sleep 3

echo ""
echo "✅ Установка завершена!"
echo ""
echo "════════════════════════════════════════"
echo "  Параметры для настройки:"
echo "════════════════════════════════════════"
echo "  VPS IP:           $VPS_IP"
echo "  SIP Port:         5060"
echo ""
echo "  Mi 8 (dber88-sip app):"
echo "    Username:       gateway1"
echo "    Password:       $PASS_GATEWAY"
echo "    SIM1 → ext:     101"
echo ""
echo "  MicroSIP:"
echo "    Username:       101"
echo "    Password:       $PASS_MICROSIP"
echo "    Server:         $VPS_IP"
echo "════════════════════════════════════════"
echo ""
echo "Проверь статус: asterisk -rx 'pjsip show endpoints'"
