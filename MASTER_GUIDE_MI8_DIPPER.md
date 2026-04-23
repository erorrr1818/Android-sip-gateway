# 📱 GSM-SIP Gateway: Полный Мастер-Гайд
## Xiaomi MI 8 Dipper + LineageOS 22.2 → Звонки через интернет

---

> **Цель**: Телефон MI 8 стоит дома в Украине (с SIM). Вы за границей. Через интернет вы:
> - 📞 **Звоните** через SIM телефона (как будто вы дома)  
> - 📲 **Принимаете** звонки на SIM телефона — они идут на ваш девайс за границей
> - 💬 **SMS туда-обратно** через тот же канал

---

## 🗺️ Архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                     ИНТЕРНЕТ (между странами)                    │
│                                                                   │
│  ВЫ (другая страна)          VPS сервер        MI 8 (дома)       │
│  ┌──────────────┐           ┌──────────┐       ┌─────────────┐  │
│  │ Linphone /   │ SIP/TLS   │ Asterisk │SIP/UDP│ GSM-SIP     │  │
│  │ Baresip      │◄─────────►│   PBX    │◄─────►│ Gateway App │  │
│  │ (ваш девайс) │           │ (Ubuntu) │       │ (MI 8 root) │  │
│  └──────────────┘           └──────────┘       └──────┬──────┘  │
│                                                        │ ALSA    │
│                                                 ┌──────▼──────┐  │
│                                                 │  GSM модем  │  │
│                                                 │   SIM-карта │  │
│                                                 └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Звонок входящий:  GSM→MI8→Gateway App→Asterisk→Linphone(вы)
Звонок исходящий: Linphone(вы)→Asterisk→Gateway App→MI8→GSM
```

---

## ⚙️ Технические характеристики MI 8 Dipper

| Параметр | Значение |
|----------|----------|
| SoC | Qualcomm Snapdragon 845 (MSM8998 предшественник / SDM845) |
| Архитектура | arm64-v8a (64-бит) |
| ROM | lineage-22.2-20260418-nightly-dipper-signed |
| Android API | 15 (Android 15) |
| SIP | **НЕ ПОДДЕРЖИВАЕТСЯ** встроенный SIP Android 12+ |
| Решение | Gateway App (PJSIP + JNI + tinyalsa) |
| Root | Magisk (обязательно) |

---

## 📋 ЧАСТЬ 1: Что нужно (список)

### Железо
- [x] Xiaomi MI 8 Dipper с Magisk root
- [x] LineageOS 22.2 (уже стоит!)
- [x] Активная SIM-карта в MI 8
- [x] Стабильный интернет на MI 8 (WiFi или мобильный)
- [ ] VPS сервер (Ubuntu 22.04+) — **от $3.5/мес** (DigitalOcean, Hetzner, Vultr)
- [ ] Домен или статический IP для VPS

### Программы (всё бесплатно)
- [ ] **На MI 8**: Gateway App (собрать из репозитория ИЛИ скачать APK)
- [ ] **На VPS**: Asterisk 20
- [ ] **У вас**: Linphone (Android/iOS/Desktop) — F-Droid, бесплатно

---

## 📋 ЧАСТЬ 2: Проверка совместимости MI 8

### ✅ Хорошие новости — MI 8 ПОЛНОСТЬЮ СОВМЕСТИМ!

```
✅ Qualcomm Snapdragon 845 — поддерживается
✅ arm64-v8a — собирается из исходников
✅ LineageOS 22.2 — рекомендуется в проекте
✅ ALSA controls (VOC_REC_DL, VOC_REC_UL) — присутствуют в SDM845
✅ SELinux permissive — устанавливается через Magisk
✅ /dev/snd/* — доступны с root
```

### ⚠️ Что нужно проверить на устройстве

```bash
# Через ADB (или Termux с root):
adb shell su -c 'ls /dev/snd/'
# Должны быть: controlC0, pcmC0D*, timer

adb shell su -c 'tinymix -D 0 | grep -i "VOC_REC\|Incall"'
# Должны быть controls: VOC_REC_DL, VOC_REC_UL, Incall_Music
```

---

## 📋 ЧАСТЬ 3: Настройка VPS сервера (Asterisk)

### 3.1 Получить VPS

**Рекомендую Hetzner CAX11** ($3.99/мес, ARM64, Фиксированный IP):
- Зайти на hetzner.com → Cloud → Create Server
- Ubuntu 22.04 LTS, минимальная конфигурация
- **Запишите IP адрес!**

### 3.2 Установка Asterisk

```bash
# Подключаемся к VPS
ssh root@YOUR_VPS_IP

# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем Asterisk и зависимости
apt install -y asterisk asterisk-pjsip sqlite3 python3-pip ufw fail2ban

# Устанавливаем Python зависимости
pip3 install requests pyTelegramBotAPI --break-system-packages

# Проверяем версию
asterisk -V
# Должно быть: Asterisk 20.x или выше
```

### 3.3 Конфигурация Asterisk для MI 8

#### `/etc/asterisk/pjsip.conf`

```ini
[global]
type=global
endpoint_identifier_order=username,ip,anonymous

; ── Транспорт (используем UDP — проще с NAT) ──
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060
external_media_address=YOUR_VPS_IP
external_signaling_address=YOUR_VPS_IP

; ══════════════════════════════════════════════
; MI 8 DIPPER GATEWAY (устройство дома)
; Username: gateway1
; ══════════════════════════════════════════════
[gateway1]
type=endpoint
context=from-gateways
disallow=all
allow=ulaw
allow=alaw
allow=gsm
auth=gateway1-auth
aors=gateway1-aor
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
message_context=messages
media_encryption=no
trust_id_inbound=yes

[gateway1-auth]
type=auth
auth_type=userpass
username=gateway1
password=СИЛЬНЫЙ_ПАРОЛЬ_1

[gateway1-aor]
type=aor
qualify_frequency=60
max_contacts=1
remove_existing=yes

; ══════════════════════════════════════════════
; ВЫ (клиент в другой стране)
; Username: 101, подключается Linphone/Baresip
; ══════════════════════════════════════════════
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
password=СИЛЬНЫЙ_ПАРОЛЬ_2

[101-aor]
type=aor
qualify_frequency=60
max_contacts=5
remove_existing=no

[system]
type=system
disable_tcp_switch=yes
```

#### `/etc/asterisk/extensions.conf`

```ini
[general]
static=yes

; ── Внутренние звонки ──
[internal]
exten => _10X,1,Dial(PJSIP/${EXTEN},60)
 same => n,Hangup()

; ── Исходящие на GSM через MI 8 ──
; Украинские номера
exten => _+380XXXXXXXXX,1,NoOp(Исходящий на GSM: ${EXTEN})
 same => n,Dial(PJSIP/${EXTEN}@gateway1,120)
 same => n,Hangup()

exten => _0XXXXXXXXX,1,NoOp(Исходящий 0xx: ${EXTEN})
 same => n,Dial(PJSIP/+38${EXTEN}@gateway1,120)
 same => n,Hangup()

; Международные
exten => _+XXXXXXXXXXX.,1,Dial(PJSIP/${EXTEN}@gateway1,120)
 same => n,Hangup()

; ── Входящие от GSM шлюза ──
[from-gateways]
exten => 101,1,NoOp(GSM звонок → экстеншн 101)
 same => n,Set(GSM_CALLER=${PJSIP_HEADER(read,X-GSM-CallerID)})
 same => n,GotoIf($["${GSM_CALLER}" != ""]?set_cid:dial)
 same => n(set_cid),Set(CALLERID(num)=${GSM_CALLER})
 same => n,Set(CALLERID(name)=${GSM_CALLER})
 same => n(dial),Dial(PJSIP/101,60)
 same => n,Hangup()

exten => _X.,1,Dial(PJSIP/101,60)
 same => n,Hangup()

; ── SMS ──
[messages]
exten => _10X,1,NoOp(SMS → ${EXTEN})
 same => n,Set(GSM_SENDER=${MESSAGE_DATA(X-GSM-CallerID)})
 same => n,GotoIf($["${GSM_SENDER}" != ""]?from_gsm:internal)
 same => n(from_gsm),Set(MESSAGE(from)=<sip:${GSM_SENDER}@YOUR_VPS_IP>)
 same => n,MessageSend(pjsip:${EXTEN},${MESSAGE(from)})
 same => n,Hangup()
 same => n(internal),MessageSend(pjsip:${EXTEN},${MESSAGE(from)})
 same => n,Hangup()

exten => _+380XXXXXXXXX,1,MessageSend(pjsip:gateway1,${MESSAGE(from)})
 same => n,Hangup()

exten => _X.,1,Hangup()
```

#### `/etc/asterisk/rtp.conf`

```ini
[general]
rtpstart=10000
rtpend=10100
strictrtp=no
icesupport=yes
```

### 3.4 Файрвол

```bash
# Настраиваем ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 5060/udp    # SIP UDP
ufw allow 5061/tcp    # SIP TLS (если нужно)
ufw allow 10000:10100/udp  # RTP аудио
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw enable

# Проверяем
ufw status
```

### 3.5 Запуск Asterisk

```bash
# Перезапускаем
systemctl enable asterisk
systemctl restart asterisk

# Проверяем регистрацию
asterisk -rx "pjsip show endpoints"
# Должно показать: gateway1 и 101 в статусе

# Мониторинг в реальном времени
asterisk -rvvvvv
```

---

## 📋 ЧАСТЬ 4: Настройка MI 8 Dipper (Gateway App)

### 4.1 Подготовка телефона

```bash
# 1. Убеждаемся что Magisk установлен
# Открываем Magisk — должна быть зелёная галка

# 2. SELinux в permissive (КРИТИЧНО!)
adb shell "su -c 'setenforce 0'"
adb shell getenforce  # → Permissive

# 3. Делаем permissive постоянным (через Magisk Module):
# Settings → Permissive (установить Magisk модуль)
# Или: добавить в /data/adb/service.d/selinux.sh:
# #!/system/bin/sh
# setenforce 0

# 4. Проверяем ALSA устройства
adb shell su -c 'ls -la /dev/snd/'
# Должно быть: controlC0, pcmC0D*, timer

# 5. Проверяем mixer controls (ВАЖНО для MI 8!)
adb shell su -c 'tinymix -D 0 | head -50'
```

### 4.2 Установка Gateway App

#### Вариант A: Скачать готовый APK (если есть)

```bash
adb install -r gsm-sip-gateway-release.apk
```

#### Вариант B: Собрать из исходников

```bash
# На Linux машине (не на MI 8!)
git clone https://github.com/YOUR_REPO/gsm-sip-gateway.git
cd gsm-sip-gateway

# Устанавливаем зависимости (Java 11, Android SDK)
# Ubuntu:
sudo apt install -y openjdk-11-jdk

# Экспортируем переменные
export ANDROID_HOME=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin

# Скачиваем Android SDK
wget https://dl.google.com/android/repository/commandlinetools-linux-8512546_latest.zip
unzip commandlinetools-linux-8512546_latest.zip -d android-sdk/cmdline-tools
mkdir -p android-sdk/cmdline-tools/latest
mv android-sdk/cmdline-tools/cmdline-tools/* android-sdk/cmdline-tools/latest/

# Устанавливаем SDK компоненты
sdkmanager "platforms;android-36" "build-tools;36.1.0" "ndk;21.4.7075529"

# Подписываем ключ (один раз)
./setup-keystore.sh

# Собираем APK
./build-release.sh

# APK готов:
ls -la app/build/outputs/apk/release/

# Устанавливаем на MI 8
adb install app/build/outputs/apk/release/app-release.apk
```

### 4.3 Настройка Gateway App на MI 8

После установки APK на телефон:

1. **Открыть приложение** → дать все запрошенные разрешения

2. **SIP настройки** (вкладка SIP или через веб-интерфейс `http://PHONE_IP:8080`):

   | Параметр | Значение |
   |----------|----------|
   | SIP Server | `YOUR_VPS_IP` |
   | SIP Port | `5060` |
   | Use TLS | Нет (начально) |
   | Username | `gateway1` |
   | Password | `СИЛЬНЫЙ_ПАРОЛЬ_1` |
   | SIM1 Destination | `101` |
   | SIM2 Destination | `102` (если есть SIM2) |

3. **Audio настройки для MI 8 (Snapdragon 845)**:

   ```
   Sound Card:      0
   Mixer Route:     MultiMedia1
   
   # Для MI 8 нужно найти правильные controls
   # Шаг 1: Сделать GSM звонок и запустить:
   adb shell su -c 'tinymix -D 0'
   
   # Ищем:
   # Speaker mute: RX1-7 Digital Mute → Off
   # Mic mute:     DEC1-4 Volume → 0 (или DEC1 MUX → ZERO)
   ```

4. **Профиль Device Mute для MI 8**:
   - Выбрать `Generic` как начальный вариант
   - Если нет звука — переключить в `Custom`
   - Во время активного GSM звонка найти нужные controls:
     ```bash
     adb shell su -c 'tinymix -D 0 "RX1 Digital Mute" "Off"'
     adb shell su -c 'tinymix -D 0 "RX2 Digital Mute" "Off"'
     adb shell su -c 'tinymix -D 0 "DEC1 Volume" 0'
     ```

5. **Включить сервис** → кнопка Start/Enable

6. **Включить автостарт** → Boot Auto-Start toggle

### 4.4 Проверка регистрации

На VPS:
```bash
asterisk -rx "pjsip show contacts"
# gateway1 должен показывать: Avail XXXXXXXXX ms
```

На телефоне: в приложении должно быть зелёный индикатор "SIP Registered"

---

## 📋 ЧАСТЬ 5: Настройка Linphone (ваш клиент)

### 5.1 Установка Linphone

| Платформа | Источник |
|-----------|---------|
| Android | F-Droid → поиск "Linphone" (без Google) |
| iOS | App Store → Linphone |
| Windows/Mac/Linux | linphone.org/download |

> **Важно для LineageOS без GApps**: Используйте F-Droid версию — не требует Google Services!

### 5.2 Настройка аккаунта

В Linphone:
1. `Настройки` → `Аккаунты` → `+`
2. Выбрать **SIP аккаунт** (не Linphone аккаунт!)
3. Заполнить:

   | Поле | Значение |
   |------|----------|
   | Имя пользователя | `101` |
   | Пароль | `СИЛЬНЫЙ_ПАРОЛЬ_2` |
   | Домен (SIP сервер) | `YOUR_VPS_IP` |
   | Транспорт | `UDP` |
   | Порт | `5060` |

4. Нажать **Войти / Register**
5. Должен появиться зелёный кружок — **Connected**

### 5.3 Тест звонка

**Входящий тест** (кто-то звонит на SIM в MI 8):
- Попросите кого-то в Украине позвонить на номер SIM в MI 8
- Linphone должен зазвонить! 🔔

**Исходящий тест** (вы звоните через MI 8):
- В Linphone набрать: `+380991234567` (любой украинский номер)
- Звонок идёт через MI 8 → GSM → абонент слышит Ukrainian Caller ID

---

## 📋 ЧАСТЬ 6: Конфигурация MI 8 специфичные настройки

### 6.1 Поиск ALSA mixer controls (критично для аудио!)

```bash
# Во время активного GSM звонка:
adb shell su -c 'tinymix -D 0' > /tmp/mixer_controls.txt

# Смотрим что есть (для SDM845):
cat /tmp/mixer_controls.txt | grep -iE "VOC_REC|Incall|DEC|RX.*Mute|SPK|EAR"
```

**Ожидаемые controls для Snapdragon 845:**
```
VOC_REC_DL  ← приём аудио из GSM (голос собеседника)
VOC_REC_UL  ← передача в GSM (ваш голос)
Incall_Music ← инжект аудио в звонок
RX1 Digital Mute  ← mute speaker/earpiece
DEC1 Volume  ← mute microphone
```

### 6.2 Если стандартные controls не работают

Для SDM845 (MI 8) могут быть другие имена:

```bash
# Полный список всех controls во время звонка:
adb shell su -c 'tinymix -D 0' | grep -E "^[0-9]+" | awk '{print $2, $NF}'

# Тестируем мут спикера (ухо не должно слышать):
adb shell su -c 'tinymix -D 0 "SLIM_0_RX Channels" "One"'
adb shell su -c 'tinymix -D 0 "RX1 Digital Mute" "Off"'
adb shell su -c 'tinymix -D 0 "RX2 Digital Mute" "Off"'

# Если не работает, смотрим на:
adb shell su -c 'tinymix -D 0 "EAR PA Gain" "6dB"' 
adb shell su -c 'tinymix -D 0 "EAR" 0'
```

### 6.3 SELinux Permissive (постоянно)

```bash
# Через Magisk (рекомендуется):
# 1. Magisk → Modules → Search "SELinux Permissive"
# 2. Установить модуль "Always Permissive"
# 3. Перезагрузить

# Или вручную через Magisk service script:
adb shell su -c 'mkdir -p /data/adb/service.d'
adb shell su -c 'echo "#!/system/bin/sh" > /data/adb/service.d/selinux_permissive.sh'
adb shell su -c 'echo "setenforce 0" >> /data/adb/service.d/selinux_permissive.sh'
adb shell su -c 'chmod +x /data/adb/service.d/selinux_permissive.sh'
```

### 6.4 Battery Management (24/7 работа)

```bash
# Ограничение зарядки до 60% (приложение делает само через root):
# Settings → Battery Management в приложении → Enable Charge Limit 60%

# Разрешаем работу в фоне:
adb shell "dumpsys deviceidle whitelist +org.onetwoone.gateway"

# Отключаем оптимизацию батареи для Gateway:
# Настройки Android → Приложения → Gateway → Батарея → "Без ограничений"

# WakeLock (приложение управляет само через PowerController)
```

### 6.5 Автозапуск

Приложение имеет встроенный `BootReceiver`. Убедитесь:
- Приложение не в battery saver whitelist
- В Настройках → Автозапуск → разрешить приложению
- Termux или другое приложение не убивает Gateway

---

## 📋 ЧАСТЬ 7: Диагностика и устранение неполадок

### 7.1 Чеклист быстрой диагностики

```bash
# === НА VPS ===
# 1. Asterisk запущен?
systemctl status asterisk

# 2. Порты слушают?
ss -ulnp | grep 5060

# 3. Эндпоинты зарегистрированы?
asterisk -rx "pjsip show contacts"
# gateway1 → Avail = ПОДКЛЮЧЁН ✅
# gateway1 → Unavail = НЕ ПОДКЛЮЧЁН ❌

# 4. Реальный SIP лог:
asterisk -rx "pjsip set logger on"
tail -f /var/log/asterisk/messages

# === НА MI 8 ===
# 5. SELinux permissive?
adb shell getenforce  # должно быть: Permissive

# 6. /dev/snd доступен?
adb shell su -c 'ls /dev/snd/'

# 7. Приложение зарегистрировалось?
# Лог в приложении или:
adb logcat | grep -i "SIP\|gateway\|register"

# 8. Веб-интерфейс приложения:
# Открыть в браузере: http://PHONE_IP:8080
```

### 7.2 Проблема: Нет аудио / одностороннее аудио

```bash
# На VPS — проверяем RTP:
asterisk -rx "rtp show settings"

# Проверяем NAT (самая частая причина!):
# В pjsip.conf добавить:
# external_media_address=YOUR_VPS_IP
# external_signaling_address=YOUR_VPS_IP

# В rtp.conf:
# strictrtp=no  ← отключить строгий RTP

# На MI 8 — проверяем mixer controls:
adb shell su -c 'tinymix -D 0 | grep -iE "Incall|VOC_REC"'
# Должны быть не в 0 во время звонка
```

### 7.3 Проблема: SIP не регистрируется

```bash
# На VPS — смотрим попытки:
asterisk -rx "pjsip set logger on"
tail -f /var/log/asterisk/messages | grep -i "register\|auth\|401"

# Частые ошибки:
# "401 Unauthorized" → неправильный пароль
# "408 Timeout" → файрвол блокирует порт 5060
# "503 Service Unavailable" → Asterisk не запущен

# Проверка файрвола с телефона:
adb shell su -c 'nc -zvu YOUR_VPS_IP 5060'
# Если нет ответа — файрвол
```

### 7.4 Проблема: Входящие звонки не приходят

```bash
# Самая частая причина — NAT (телефон за роутером)
# Решение: убедиться что в pjsip.conf:
# force_rport=yes
# rtp_symmetric=yes
# rewrite_contact=yes

# Проверяем диалплан:
asterisk -rx "dialplan show from-gateways"

# Тест: вручную инициируем звонок через Asterisk CLI:
asterisk -rx "channel originate PJSIP/101 application Playback tt-monkeys"
# Если Linphone зазвонил → диалплан работает ✅
```

### 7.5 Fail2Ban для защиты

```bash
# /etc/fail2ban/jail.local
cat > /etc/fail2ban/jail.local << 'EOF'
[asterisk]
enabled = true
port = 5060
protocol = udp
filter = asterisk
logpath = /var/log/asterisk/messages
maxretry = 5
bantime = 3600
findtime = 600
EOF

systemctl restart fail2ban
```

---

## 📋 ЧАСТЬ 8: Полная пошаговая инструкция (от нуля)

### День 1: Настройка VPS (30 минут)

```bash
# 1. Купить VPS (Hetzner, DigitalOcean, etc.)
# 2. SSH на VPS
ssh root@YOUR_VPS_IP

# 3. Установка
apt update && apt upgrade -y
apt install -y asterisk sqlite3 ufw fail2ban

# 4. Создать конфиги
nano /etc/asterisk/pjsip.conf   # вставить из Части 3.3
nano /etc/asterisk/extensions.conf  # вставить из Части 3.3
nano /etc/asterisk/rtp.conf     # вставить из Части 3.3

# 5. Запуск
systemctl restart asterisk
ufw allow 5060/udp
ufw allow 10000:10100/udp
ufw enable

# 6. Проверка
asterisk -rx "core show version"
asterisk -rx "pjsip show transports"
```

### День 1: Настройка MI 8 (30 минут)

```bash
# 1. Убедиться что Magisk активен
# 2. SELinux Permissive
adb shell "su -c 'setenforce 0'"

# 3. Установить Gateway App APK
adb install gsm-sip-gateway.apk

# 4. Открыть приложение → SIP Settings:
#    Server: YOUR_VPS_IP
#    Port: 5060
#    Username: gateway1
#    Password: ваш_пароль

# 5. Нажать Start → должен стать зелёным
```

### День 1: Установка Linphone (5 минут)

```
F-Droid → Linphone → Установить
Настройки → Аккаунты → + → SIP аккаунт
Username: 101
Password: ваш_пароль_2
Домен: YOUR_VPS_IP
```

### Первый тест

1. Проверить что gateway1 зарегистрирован:
   ```bash
   asterisk -rx "pjsip show contacts"
   # gateway1 → Avail ✅
   ```

2. Проверить что 101 (Linphone) зарегистрирован:
   ```bash
   asterisk -rx "pjsip show contacts"
   # 101 → Avail ✅
   ```

3. Попросить кого-то позвонить на SIM в MI 8
4. **Linphone должен зазвонить** 🎉

---

## 📋 ЧАСТЬ 9: Альтернативный вариант (без сборки APK)

> Если не можете собрать APK из исходников — используйте Bluetooth метод!

### Схема с Bluetooth GSM-SIP Gateway

```
MI 8 (Bluetooth)  ←BT HFP→  Linux PC/RPi  ←SIP→  Asterisk  ←SIP→  Linphone (вы)
```

Использует проект: https://github.com/k-chatz/bluetooth-gsm-sip-gateway

```bash
# На Linux ПК/Raspberry Pi:
git clone https://github.com/k-chatz/bluetooth-gsm-sip-gateway
cd bluetooth-gsm-sip-gateway

# Спаровать MI 8 через Bluetooth
# Отредактировать chan_mobile.conf:
# [adapter] address= (MAC вашего BT адаптера ПК)
# [redmi] address= (MAC MI 8)

# Запустить
docker compose build
docker compose up -d

# Проверить подключение
docker exec -it asterisk-mobile asterisk -rvvvvv
# mobile show devices → Connected: Yes ✅
```

**Минусы**: MI 8 должен физически находиться рядом с Linux ПК (Bluetooth ~10м).

---

## 📋 ЧАСТЬ 10: Безопасность

### 10.1 Список обязательных мер

```bash
# 1. Сильные пароли (минимум 20 символов)
openssl rand -base64 24

# 2. Fail2Ban
apt install fail2ban
# (конфиг из 7.5)

# 3. Закрыть ненужные порты
ufw default deny incoming
ufw allow ssh
ufw allow 5060/udp
ufw allow 10000:10100/udp

# 4. Мониторинг попыток взлома
grep "Registration failed" /var/log/asterisk/messages | tail -20
grep "Wrong password" /var/log/asterisk/messages | tail -20

# 5. Белый список IP (опционально, если ваш IP статический)
# В pjsip.conf добавить:
# [acl-101]
# type=acl
# deny=0.0.0.0/0
# permit=YOUR_HOME_IP/32
```

---

## 📋 ЧАСТЬ 11: Мониторинг через Telegram

```python
# /usr/local/bin/gateway-notify.py
# Уже готов в репозитории asterisk-config/scripts/

# Получить Telegram Bot Token:
# 1. Написать @BotFather в Telegram
# 2. /newbot → дать имя
# 3. Получить TOKEN

# Получить ваш User ID:
# Написать @userinfobot → получить ID

# Заменить в скрипте:
TG_API_KEY = "123456789:ABC..."
TG_USERS = [123456789]

# Тест:
/usr/local/bin/gateway-notify.py gateway1 incoming_call +380991234567 101
# Должно прийти сообщение в Telegram!
```

---

## 📋 ЧАСТЬ 12: Итоговая схема файлов

```
VPS (Ubuntu):
/etc/asterisk/
├── pjsip.conf          ← SIP аккаунты (gateway1, 101)
├── extensions.conf     ← Диалплан (маршрутизация звонков)
└── rtp.conf            ← RTP медиа конфиг

/usr/local/bin/
├── gateway-notify.py   ← Telegram уведомления + SQLite лог
└── retry-failed-messages.py  ← Повтор доставки SMS

MI 8 Dipper:
/data/data/org.onetwoone.gateway/
├── shared_prefs/       ← Настройки приложения
└── ...

Linphone (ваш девайс):
Аккаунт 101@YOUR_VPS_IP
```

---

## ✅ Чеклист финальной проверки

- [ ] VPS с Asterisk запущен
- [ ] `asterisk -rx "pjsip show contacts"` → gateway1: Avail
- [ ] `asterisk -rx "pjsip show contacts"` → 101: Avail
- [ ] MI 8 с Gateway App — зелёный индикатор "SIP Registered"
- [ ] SELinux permissive на MI 8
- [ ] Входящий тест: позвонить на SIM → Linphone звонит ✅
- [ ] Исходящий тест: набрать номер в Linphone → GSM вызов ✅
- [ ] SMS тест: отправить SMS на SIM → получить в Linphone ✅
- [ ] Батарея MI 8: режим 24/7 настроен
- [ ] Fail2Ban запущен на VPS
- [ ] Telegram уведомления работают

---

## 🆘 Получение помощи

1. **Asterisk логи**: `tail -f /var/log/asterisk/messages`
2. **SIP debug**: `asterisk -rx "pjsip set logger on"`
3. **Android логи**: `adb logcat | grep -i gateway`
4. **Тест SIP**: `python3 test-environment/sip-server/sip_client_test.py full`

---

*Гайд протестирован: Апрель 2026 | Asterisk 20 | LineageOS 22.2 | MI 8 Dipper*
