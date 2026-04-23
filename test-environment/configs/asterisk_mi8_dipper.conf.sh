#!/bin/bash
# ============================================================
# Скрипт генерации конфигурации Asterisk
# Адаптирован для MI 8 Dipper + LineageOS 22.2
# ============================================================

SERVER_DOMAIN="${1:-your.server.com}"
GATEWAY_PASS="${2:-$(openssl rand -base64 16 | tr -d '/+=')}"
CLIENT_PASS="${3:-$(openssl rand -base64 16 | tr -d '/+=')}"

echo "Генерируем конфиги для домена: $SERVER_DOMAIN"

# pjsip.conf
cat > /etc/asterisk/pjsip.conf << EOF
[global]
type=global
endpoint_identifier_order=username,ip,anonymous

; ── TLS транспорт (безопасно через интернет) ──
[transport-tls]
type=transport
protocol=tls
bind=0.0.0.0:5061
cert_file=/etc/asterisk/keys/${SERVER_DOMAIN}.crt
priv_key_file=/etc/asterisk/keys/${SERVER_DOMAIN}.key
method=tlsv1_2
external_media_address=${SERVER_DOMAIN}
external_signaling_address=${SERVER_DOMAIN}

; ── UDP транспорт (для локальной сети) ──
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

; ══════════════════════════════════════════
; MI 8 DIPPER - Основной шлюз (gateway1)
; Подключается через интернет к этому серверу
; SIM1 → экстеншн 101
; ══════════════════════════════════════════
[gateway1]
type=endpoint
context=from-gateways
disallow=all
allow=opus
allow=ulaw
allow=alaw
auth=gateway1-auth
aors=gateway1-aor
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
message_context=messages
media_encryption=no
trust_id_inbound=yes
; Без SRTP для простоты настройки (включить после проверки)

[gateway1-auth]
type=auth
auth_type=userpass
username=gateway1
password=${GATEWAY_PASS}

[gateway1-aor]
type=aor
qualify_frequency=30
max_contacts=1
remove_existing=yes

; ══════════════════════════════════════════
; Клиент 101 (ВЫ в другой стране)
; Linphone/Baresip на телефоне/компьютере
; ══════════════════════════════════════════
[101]
type=endpoint
context=internal
disallow=all
allow=opus
allow=ulaw
allow=alaw
auth=101-auth
aors=101-aor
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
ice_support=yes
message_context=messages
media_encryption=no

[101-auth]
type=auth
auth_type=userpass
username=101
password=${CLIENT_PASS}

[101-aor]
type=aor
qualify_frequency=30
max_contacts=5
remove_existing=no
; max_contacts=5 - можно подключить с компа, планшета и т.д.

; ══════════════════════════════════════════
; Клиент 102 (резервный / SIM2)
; ══════════════════════════════════════════
[102]
type=endpoint
context=internal
disallow=all
allow=opus
allow=ulaw
allow=alaw
auth=102-auth
aors=102-aor
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
message_context=messages
media_encryption=no

[102-auth]
type=auth
auth_type=userpass
username=102
password=${CLIENT_PASS}

[102-aor]
type=aor
qualify_frequency=30
max_contacts=3
remove_existing=no

[system]
type=system
disable_tcp_switch=yes
EOF

echo "✅ pjsip.conf создан"
echo "   gateway1 пароль: ${GATEWAY_PASS}"
echo "   клиент 101 пароль: ${CLIENT_PASS}"

# extensions.conf
cat > /etc/asterisk/extensions.conf << EOF
[general]
static=yes
writeprotect=no
clearglobalvars=no

; ══════════════════════════════
; ВНУТРЕННИЕ ЗВОНКИ (SIP ↔ SIP)
; ══════════════════════════════
[internal]
exten => _10[12],1,NoOp(Внутренний звонок: \${CALLERID(num)} → \${EXTEN})
 same => n,Dial(PJSIP/\${EXTEN},60)
 same => n,Hangup()

; ══════════════════════════════════════════════════════
; ИСХОДЯЩИЕ ЗВОНКИ: SIP клиент → GSM через MI 8 Dipper
; (вы в другой стране → звоните через телефон в Украине)
; ══════════════════════════════════════════════════════
[internal]
; Украинские номера +380XXXXXXXXX
exten => _+380XXXXXXXXX,1,NoOp(Исходящий: \${CALLERID(num)} → GSM \${EXTEN})
 same => n,Dial(PJSIP/\${EXTEN}@gateway1,60)
 same => n,Hangup()

; Без кода страны (0XXXXXXXXX)
exten => _0XXXXXXXXX,1,NoOp(Исходящий с 0: \${CALLERID(num)} → \${EXTEN})
 same => n,Set(EXTEN_FULL=+38\${EXTEN})
 same => n,Dial(PJSIP/\${EXTEN_FULL}@gateway1,60)
 same => n,Hangup()

; Международные (добавьте нужные форматы)
exten => _+XXXXXXXXXXX.,1,NoOp(Международный: \${EXTEN})
 same => n,Dial(PJSIP/\${EXTEN}@gateway1,60)
 same => n,Hangup()

; ══════════════════════════════════════════════════════
; ВХОДЯЩИЕ ЗВОНКИ: GSM → SIP клиент
; (кто-то звонит на симку в телефоне → вы слышите звонок)
; ══════════════════════════════════════════════════════
[from-gateways]
; SIM1 → клиент 101 (вы)
exten => 101,1,NoOp(Входящий GSM → SIP 101)
 same => n,Set(GSM_CALLER=\${PJSIP_HEADER(read,X-GSM-CallerID)})
 same => n,GotoIf(\$["\${GSM_CALLER}" != ""]?set_caller:skip)
 same => n(set_caller),Set(CALLERID(num)=\${GSM_CALLER})
 same => n,Set(CALLERID(name)=\${GSM_CALLER})
 same => n(skip),NoOp(Звонок от: \${CALLERID(num)})
 same => n,Dial(PJSIP/101,60)
 same => n,Hangup()

; SIM2 → клиент 102
exten => 102,1,NoOp(Входящий GSM → SIP 102)
 same => n,Set(GSM_CALLER=\${PJSIP_HEADER(read,X-GSM-CallerID)})
 same => n,GotoIf(\$["\${GSM_CALLER}" != ""]?set_caller:skip)
 same => n(set_caller),Set(CALLERID(num)=\${GSM_CALLER})
 same => n,Set(CALLERID(name)=\${GSM_CALLER})
 same => n(skip),Dial(PJSIP/102,60)
 same => n,Hangup()

; Любой другой (непредвиденный)
exten => _X.,1,NoOp(Неизвестный входящий: \${EXTEN})
 same => n,Dial(PJSIP/101,30)
 same => n,Hangup()

; ══════════════════════════════════════════════════════
; SMS (SIP MESSAGE)
; ══════════════════════════════════════════════════════
[messages]
exten => _10[12],1,NoOp(SMS → \${EXTEN})
 same => n,Set(GSM_SENDER=\${MESSAGE_DATA(X-GSM-CallerID)})
 same => n,GotoIf(\$["\${GSM_SENDER}" != ""]?gsm_sms:internal_msg)
 same => n(gsm_sms),Set(MESSAGE(from)=<sip:\${GSM_SENDER}@${SERVER_DOMAIN}>)
 same => n,MessageSend(pjsip:\${EXTEN},\${MESSAGE(from)})
 same => n,Hangup()
 same => n(internal_msg),MessageSend(pjsip:\${EXTEN},\${MESSAGE(from)})
 same => n,Hangup()

; Исходящий SMS на GSM
exten => _+380XXXXXXXXX,1,NoOp(SMS → GSM \${EXTEN})
 same => n,Set(MESSAGE(to)=sip:\${EXTEN}@${SERVER_DOMAIN})
 same => n,MessageSend(pjsip:gateway1,\${MESSAGE(from)})
 same => n,Hangup()

exten => _X.,1,NoOp(Неизвестный SMS: \${EXTEN})
 same => n,Hangup()
EOF

echo "✅ extensions.conf создан"

# rtp.conf
cat > /etc/asterisk/rtp.conf << EOF
[general]
rtpstart=10000
rtpend=10100
strictrtp=no
icesupport=yes
stunaddr=stun.l.google.com:19302
EOF

echo "✅ rtp.conf создан"
echo ""
echo "════════════════════════════════════"
echo "Данные для Android Gateway App (MI 8 Dipper):"
echo "  SIP Server: ${SERVER_DOMAIN}"
echo "  SIP Port:   5060 (UDP) / 5061 (TLS)"  
echo "  Username:   gateway1"
echo "  Password:   ${GATEWAY_PASS}"
echo "  SIM1 Dest:  101"
echo ""
echo "Данные для Linphone (ваш клиент в другой стране):"
echo "  SIP Server: ${SERVER_DOMAIN}"
echo "  Username:   101"
echo "  Password:   ${CLIENT_PASS}"
echo "════════════════════════════════════"
