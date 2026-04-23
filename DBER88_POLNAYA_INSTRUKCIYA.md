# 📱 dber88-sip — Полная инструкция для чайников
## Звонки без роуминга через Xiaomi Mi 8 + Asterisk + MicroSIP

---

> **Что получится в итоге:**  
> Ты оставляешь Mi 8 дома (или у кого-то), он подключен к Wi-Fi/интернету.  
> Едешь в любую страну, открываешь ноутбук, звонишь MicroSIP — и клиент  
> видит твой обычный номер телефона. Без роуминга, без дополнительных затрат.

---

## 📋 Что тебе нужно

| Что | Для чего |
|-----|----------|
| Xiaomi Mi 8 (dipper) | GSM-шлюз, стоит дома с SIM-картой |
| LineageOS 22.2 + Magisk root | Уже установлено у тебя ✅ |
| VPS-сервер (1GB RAM, Ubuntu 24.04) | Asterisk — "мозг" системы, ~$3-5/мес |
| MicroSIP на ноутбуке | Программа для звонков на Windows |
| Интернет на Mi 8 | Wi-Fi дома, где стоит телефон |

---

## 🗺️ Схема работы

```
[Клиент звонит тебе]
        ↓
[SIM-карта в Mi 8]  ←→  [dber88-sip APK]  ←→  [Интернет]
                                                      ↓
                                          [Asterisk на VPS]
                                                      ↓
                                          [MicroSIP на ноутбуке]
                                          (ты отвечаешь)

[Ты звонишь клиенту]
MicroSIP → Asterisk → Mi 8 → SIM → Клиент
```

---

# ═══════════════════════════════════════════
# ЧАСТЬ 1: НАСТРОЙКА VPS-СЕРВЕРА С ASTERISK
# ═══════════════════════════════════════════

## Шаг 1.1 — Выбери и купи VPS

**Рекомендуемые провайдеры:**
- [Hetzner](https://hetzner.com) — CX11, €3.29/мес, Германия/Финляндия (быстро, надёжно)
- [DigitalOcean](https://digitalocean.com) — $4/мес
- [Contabo](https://contabo.com) — дешевле, подходит

**Минимальные требования:**
- Ubuntu 24.04 LTS
- 1 CPU, 1 GB RAM, 20 GB диск
- Статический IP-адрес (он у тебя будет автоматически)

> Запомни IP своего VPS — он понадобится везде. Назовём его `ВАШ_IP`.

---

## Шаг 1.2 — Подключись к VPS

На Windows скачай [PuTTY](https://putty.org) или используй Windows Terminal:

```
ssh root@ВАШ_IP
```

Введи пароль, который дал тебе провайдер.

---

## Шаг 1.3 — Установи Asterisk

Выполняй команды **по одной**, копируй и вставляй в терминал:

```bash
# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем Asterisk и нужные пакеты
apt install -y asterisk python3 python3-pip sqlite3 ufw

# Проверяем что Asterisk установился
asterisk --version
```

Должно показать что-то вроде: `Asterisk 20.x.x`

---

## Шаг 1.4 — Настрой файрвол

```bash
# Открываем нужные порты
ufw allow 22/tcp        # SSH (чтобы не потерять доступ!)
ufw allow 5060/udp      # SIP без шифрования
ufw allow 5061/tcp      # SIP с шифрованием TLS
ufw allow 10000:10100/udp  # RTP (голос)

# Включаем файрвол
ufw enable

# Проверяем
ufw status
```

---

## Шаг 1.5 — Настрой конфиги Asterisk

### Создай файл `/etc/asterisk/pjsip.conf`

```bash
nano /etc/asterisk/pjsip.conf
```

Вставь следующее содержимое (замени `ВАШ_IP` на реальный IP):

```ini
[global]
type=global
endpoint_identifier_order=username,ip,anonymous

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

; ─── MicroSIP на ноутбуке (extension 101) ───
[101]
type=endpoint
context=internal
disallow=all
allow=opus
allow=ulaw
allow=alaw
auth=101
aors=101
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes

[101]
type=auth
auth_type=userpass
username=101
password=ПАРОЛЬ_ДЛЯ_MICROSIP

[101]
type=aor
qualify_frequency=30
max_contacts=3
remove_existing=yes

; ─── Mi 8 Gateway (SIM1) ───
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
password=ПАРОЛЬ_ДЛЯ_GATEWAY

[gateway1]
type=aor
qualify_frequency=30
max_contacts=2
remove_existing=no
```

Сохрани: `Ctrl+X` → `Y` → `Enter`

---

### Создай файл `/etc/asterisk/extensions.conf`

```bash
nano /etc/asterisk/extensions.conf
```

Вставь:

```ini
[general]
static=yes
writeprotect=no

; Звонки между клиентами и шлюзом
[internal]
; Входящий звонок от Mi 8 идёт на MicroSIP (101)
exten => 101,1,NoOp(Incoming from gateway)
 same => n,Dial(PJSIP/101,60)
 same => n,Hangup()

; Исходящий через Mi 8 — любой номер
exten => _+XXXXXXXXXXX,1,NoOp(Outgoing call to ${EXTEN})
 same => n,Dial(PJSIP/${EXTEN}@gateway1,60)
 same => n,Hangup()

exten => _XXXXXXXXXXX,1,NoOp(Outgoing call to ${EXTEN})
 same => n,Dial(PJSIP/${EXTEN}@gateway1,60)
 same => n,Hangup()

; Входящие от Mi 8
[from-gateways]
exten => _X.,1,NoOp(Incoming GSM call to ${EXTEN})
 same => n,Set(GSM_CALLER=${PJSIP_HEADER(read,X-GSM-CallerID)})
 same => n,GotoIf($["${GSM_CALLER}" != ""]?set_caller:skip)
 same => n(set_caller),Set(CALLERID(num)=${GSM_CALLER})
 same => n,Set(CALLERID(name)=${GSM_CALLER})
 same => n(skip),Dial(PJSIP/101,60)
 same => n,Hangup()
```

Сохрани: `Ctrl+X` → `Y` → `Enter`

---

### Создай файл `/etc/asterisk/rtp.conf`

```bash
nano /etc/asterisk/rtp.conf
```

Вставь:

```ini
[general]
rtpstart=10000
rtpend=10100
```

Сохрани: `Ctrl+X` → `Y` → `Enter`

---

## Шаг 1.6 — Запусти Asterisk

```bash
# Перезапускаем Asterisk
systemctl restart asterisk

# Включаем автозапуск при старте сервера
systemctl enable asterisk

# Проверяем статус
systemctl status asterisk
```

Должно показать `Active: active (running)`.

---

## Шаг 1.7 — Проверка конфигурации

```bash
# Входим в консоль Asterisk
asterisk -rvvv

# В консоли Asterisk проверяем endpoints:
pjsip show endpoints

# Должно показать 101 и gateway1
# Выходим:
exit
```

---

# ═══════════════════════════════════════════
# ЧАСТЬ 2: ПОДГОТОВКА XIAOMI MI 8
# ═══════════════════════════════════════════

## Шаг 2.1 — Проверь прошивку

У тебя уже стоит: `lineage-22.2-20260418-nightly-dipper-signed.zip` ✅

Прошивка правильная, продолжаем.

---

## Шаг 2.2 — Настрой Magisk (если ещё не сделано)

1. В LineageOS открой **Настройки → Об устройстве**
2. Нажми 7 раз на **Номер сборки** — включится режим разработчика
3. Зайди в **Настройки → Для разработчиков**:
   - Включи **Отладка по USB**
   - Включи **Rooted debugging**

---

## Шаг 2.3 — Установи ADB на ноутбук (Windows)

1. Скачай [Platform Tools](https://developer.android.com/tools/releases/platform-tools) (скачать для Windows)
2. Распакуй в папку `C:\adb\`
3. Подключи Mi 8 к ноутбуку по USB
4. На телефоне: **Разрешить отладку по USB** → нажми OK

Открой командную строку (`Win+R` → `cmd`):
```cmd
cd C:\adb
adb devices
```

Должно показать твой телефон.

---

## Шаг 2.4 — Установи APK dber88-sip

Скопируй файл `dber88-sip.apk` в папку `C:\adb\`.

```cmd
cd C:\adb
adb install -r dber88-sip.apk
```

---

## Шаг 2.5 — Переведи SELinux в Permissive

```cmd
adb shell "su -c 'setenforce 0'"
adb shell "su -c 'getenforce'"
```

Должно вернуть: `Permissive`

> ⚠️ **Важно:** После каждой перезагрузки телефона нужно повторять эту команду.  
> Чтобы сделать это автоматически, в Magisk установи модуль "SELinux Permissive" или добавь команду в Magisk скрипт.

### Сделать SELinux Permissive постоянным (через Magisk):

```cmd
adb shell "su -c 'echo setenforce 0 > /data/local/tmp/permissive.sh'"
adb shell "su -c 'chmod 755 /data/local/tmp/permissive.sh'"
```

Или в приложении **Magisk** → **Модули** → найди и установи **MagiskHide Props Config** или аналогичный модуль для постоянного permissive.

---

## Шаг 2.6 — Настрой приложение dber88-sip

1. Открой приложение **dber88-sip** на телефоне
2. Если появится запрос разрешений — **разреши все**
3. Если попросит Root — **разрешить всегда**
4. Установи приложение как **Phone App**:
   - Настройки телефона → Приложения → Телефон → Выбрать dber88-sip по умолчанию

---

### Заполни настройки SIP:

| Поле | Значение |
|------|---------|
| SIP Server | `ВАШ_IP` (IP твоего VPS) |
| SIP Port | `5060` |
| Username | `gateway1` |
| Password | `ПАРОЛЬ_ДЛЯ_GATEWAY` (тот что в pjsip.conf) |
| Use TLS | выключено (для начала) |
| Realm | `ВАШ_IP` |

### Маршрутизация SIM:

| Поле | Значение |
|------|---------|
| SIM1 Destination | `101` |
| SIM2 Destination | (оставь пустым если один SIM) |

### Пресет устройства:

В разделе **Audio** выбери: **Xiaomi Mi 8 (SD845)**

### Нажми **SAVE** → затем **CONNECT**

---

## Шаг 2.7 — Проверка подключения

В верхней части приложения должен появиться статус:
```
● REGISTERED
```

Если `○ OFFLINE` — проверь:
- IP правильный?
- Пароль совпадает с pjsip.conf?
- Файрвол открыт (порт 5060)?

На VPS проверь:
```bash
asterisk -rvvv
pjsip show contacts
```

Должно показать `gateway1` с Contact.

---

# ═══════════════════════════════════════════
# ЧАСТЬ 3: НАСТРОЙКА MICROSIP НА НОУТБУКЕ
# ═══════════════════════════════════════════

## Шаг 3.1 — Скачай и установи MicroSIP

Скачай: [https://www.microsip.org/downloads](https://www.microsip.org/downloads)

Установи как обычную программу.

---

## Шаг 3.2 — Добавь SIP аккаунт

Открой MicroSIP → **Меню (≡)** → **Add Account**

| Поле | Значение |
|------|---------|
| Account name | `dber88-sip` |
| SIP Server | `ВАШ_IP` |
| Domain | `ВАШ_IP` |
| Username | `101` |
| Password | `ПАРОЛЬ_ДЛЯ_MICROSIP` (из pjsip.conf) |
| Auth.Username | `101` |

Нажми **Save**.

---

## Шаг 3.3 — Проверка подключения

В MicroSIP внизу должно отображаться:
```
✅ 101@ВАШ_IP
```

Если красный значок — проверь пароль и доступность VPS.

---

# ═══════════════════════════════════════════
# ЧАСТЬ 4: ТЕСТ — ПЕРВЫЙ ЗВОНОК
# ═══════════════════════════════════════════

## Входящий звонок (кто-то звонит на твою SIM):

1. Попроси кого-то позвонить на номер SIM в Mi 8
2. На MicroSIP должен появиться входящий звонок
3. Нажми **Ответить**
4. Говори — через Mi 8 и Asterisk

## Исходящий звонок (ты звонишь клиенту):

1. В MicroSIP введи номер (например: `+79991234567`)
2. Нажми **Позвонить**
3. Asterisk передаст звонок → Mi 8 → SIM → клиент
4. Клиент увидит твой реальный номер!

---

# ═══════════════════════════════════════════
# ЧАСТЬ 5: ПРОБЛЕМЫ И РЕШЕНИЯ
# ═══════════════════════════════════════════

## ❌ Нет звука во время звонка

### Найди правильные ALSA контролы для Mi 8:

Выполни на телефоне через ADB:
```cmd
adb shell "su -c 'tinymix -D 0 | grep -i -E \"voc|incall|ear|speaker|mic\"'"
```

Или открой в приложении **Web Interface** → `http://IP_ТЕЛЕФОНА:8080`
(IP телефона смотри в настройках Wi-Fi)

## ❌ SELinux всегда сбрасывается в Enforcing

В Magisk → **Модули** → **+** → найди **"SELinux Permissive"** мод или скачай с Magisk репозитория.

Альтернатива — добавить в Magisk скрипт (требует root):
```bash
# Файл /data/adb/post-fs-data.d/selinux.sh
#!/system/bin/sh
setenforce 0
```

## ❌ Gateway не регистрируется

1. Проверь IP на VPS: `curl ifconfig.me`
2. Проверь порт: `nc -vzu ВАШ_IP 5060`
3. В Asterisk: `asterisk -rvvv` → `pjsip set logger on` → смотри логи при попытке регистрации

## ❌ Приложение вылетает

```cmd
adb logcat | grep -i "dber88\|gateway\|crash"
```

---

# ═══════════════════════════════════════════
# ЧАСТЬ 6: АВТОЗАПУСК И ПОСТОЯННАЯ РАБОТА
# ═══════════════════════════════════════════

## Настройка автозапуска на Mi 8:

1. В настройках телефона → **Батарея** → **Автозапуск приложений** → включи `dber88-sip`
2. В настройках → **Батарея** → найди `dber88-sip` → выбери **No restrictions**
3. В самом приложении включи **Web Interface** (он помогает определить IP)

## Защита от "засыпания" Wi-Fi:

Настройки → Wi-Fi → Дополнительно → **Keep Wi-Fi on during sleep** → **Always**

## Зарядка аккумулятора:

В приложении dber88-sip есть ограничитель заряда батареи.
Рекомендуется: 60% — это продлит жизнь аккумулятора при постоянной зарядке.

---

# ═══════════════════════════════════════════
# ЧАСТЬ 7: БЕЗОПАСНОСТЬ
# ═══════════════════════════════════════════

## Смени пароли на сложные!

Открой `/etc/asterisk/pjsip.conf` и замени:
- `ПАРОЛЬ_ДЛЯ_MICROSIP` → например `xK9#mP2$vQ7`
- `ПАРОЛЬ_ДЛЯ_GATEWAY` → например `nR4@jL8%wE1`

После изменения перезагрузи Asterisk:
```bash
asterisk -rx "pjsip reload"
```

## Установи Fail2Ban (защита от взлома):

```bash
apt install -y fail2ban

cat > /etc/fail2ban/jail.d/asterisk.conf << 'EOF'
[asterisk]
enabled = true
port = 5060
filter = asterisk
logpath = /var/log/asterisk/messages
maxretry = 5
bantime = 3600
EOF

systemctl restart fail2ban
```

---

# ═══════════════════════════════════════════
# ИТОГОВЫЙ ЧЕКЛИСТ
# ═══════════════════════════════════════════

- [ ] VPS куплен, Ubuntu 24.04 установлена
- [ ] Asterisk установлен и запущен
- [ ] pjsip.conf настроен (IP, пароли)
- [ ] extensions.conf настроен
- [ ] Порты открыты (22, 5060, 10000-10100)
- [ ] dber88-sip.apk установлен на Mi 8
- [ ] SELinux = Permissive
- [ ] Приложение настроено (SIP, gateway1)
- [ ] Статус "REGISTERED" в приложении
- [ ] MicroSIP настроен (extension 101)
- [ ] Тест звонок прошёл успешно
- [ ] Автозапуск настроен

---

# 📞 Быстрые данные для настройки

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 dber88-sip | Параметры подключения
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VPS IP:        ВАШ_IP
SIP Port:      5060

Mi 8 (Gateway):
  Username:    gateway1
  Password:    ПАРОЛЬ_ДЛЯ_GATEWAY
  SIM1 → ext:  101

MicroSIP (ноутбук):
  Username:    101
  Password:    ПАРОЛЬ_ДЛЯ_MICROSIP
  Server:      ВАШ_IP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🎉 Готово!

Теперь ты можешь звонить и принимать звонки со своего номера из любой страны мира без роуминга.

**Схема в двух словах:**
```
Клиент → SIM в Mi 8 → dber88-sip → Интернет → Asterisk VPS → MicroSIP → Ты
```

*dber88-sip v1.2 | Xiaomi Mi 8 (SD845) | LineageOS 22.2*
