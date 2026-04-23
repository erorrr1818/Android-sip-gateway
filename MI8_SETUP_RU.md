# Настройка GSM-SIP Gateway на Xiaomi Mi 8 (dipper)

## Зачем это нужно?

Схема работы:

```
Клиент звонит на ваш номер
        ↓
SIM-карта в Mi 8 (дома/в офисе)
        ↓
GSM-SIP Gateway (это приложение)
        ↓
VoIP/SIP через интернет
        ↓
MicroSIP на вашем ноутбуке (в другой стране)
        ↓
Вы отвечаете — без роуминга, с вашим номером
```

**Итог:** телефон лежит дома с SIM-картой, вы в любой стране мира звоните и принимаете звонки через интернет со своего номера.

---

## Часть 1: Подготовка Xiaomi Mi 8

### 1.1 Что уже должно быть (у вас уже есть)
- ✅ LineageOS на Mi 8 (dipper)
- ✅ Root (Magisk)

### 1.2 Установка необходимых приложений через ADB

Подключите Mi 8 к ПК через USB, включите отладку по USB (Настройки → Для разработчиков → Отладка USB).

```bash
# Проверить подключение
adb devices
# Должны увидеть: [серийник]  device

# Установить APK приложения (после сборки)
adb install -r app-release.apk
```

### 1.3 Обязательно: отключить SELinux

Без этого приложение НЕ будет работать — оно не сможет открыть аудио устройства.

```bash
# Переключить SELinux в permissive режим
adb shell "su -c 'setenforce 0'"

# Проверить
adb shell getenforce
# Должно показать: Permissive
```

**Чтобы SELinux оставался permissive после перезагрузки**, добавьте в Magisk:
- Создайте Magisk-модуль с boot-скриптом `post-fs-data.sh`:
```bash
# /data/adb/modules/selinux-permissive/service.sh
setenforce 0
```

Или используйте Magisk-модуль "SELinux Mode Changer".

### 1.4 Предоставить права приложению

```bash
# Root права (через Magisk — дать при первом запуске)
# Разрешить звонки через InCallService
adb shell "pm grant org.onetwoone.gateway android.permission.READ_PHONE_STATE"
adb shell "pm grant org.onetwoone.gateway android.permission.READ_CALL_LOG"
adb shell "pm grant org.onetwoone.gateway android.permission.READ_SMS"
adb shell "pm grant org.onetwoone.gateway android.permission.RECEIVE_SMS"
adb shell "pm grant org.onetwoone.gateway android.permission.SEND_SMS"
```

### 1.5 Назначить приложение как Phone App

**Это критически важно!** Без этого приложение не может перехватывать входящие GSM-звонки.

1. Настройки → Приложения → Приложения по умолчанию → **Телефон**
2. Выбрать **GSM-SIP Gateway**

Или через ADB:
```bash
adb shell "cmd phone set-default-dialer org.onetwoone.gateway"
```

### 1.6 Исключить из оптимизации батареи

Настройки → Батарея → Оптимизация батареи → Найти "GSM-SIP Gateway" → **Не оптимизировать**

---

## Часть 2: Поиск правильных ALSA-контролов для Mi 8

Mi 8 использует кодек **Qualcomm Tavil WCD9340** (Snapdragon 845). 
В приложении уже добавлен пресет "Xiaomi Mi 8 (SD845)", но аудио контролы **могут отличаться** в зависимости от версии LineageOS.

### Как проверить и откалибровать:

#### Шаг 1: Установить tinymix на телефон

```bash
# Скопировать бинарник tinymix (из сборки проекта)
adb push tinymix_arm64 /data/local/tmp/tinymix
adb shell "chmod +x /data/local/tmp/tinymix"
```

#### Шаг 2: Позвонить с Mi 8 на любой номер (держать активным)

Пока звонок активен:

```bash
adb shell
su
/data/local/tmp/tinymix -D 0 | head -100
```

#### Шаг 3: Найти контролы динамика/наушника

Ищите строки с:
- `EAR` — наушник (earpiece)
- `SPK` — динамик (speaker)
- `HPHL`, `HPHR` — наушники (headphone left/right)
- `RX` — выход (RX path)

Тест — отключить звук во время звонка:
```bash
# Попробовать заглушить наушник
su -c '/data/local/tmp/tinymix -D 0 set "EAR SPKR PA" 0'

# Если звук исчез - нашли нужный контрол!
# Восстановить:
su -c '/data/local/tmp/tinymix -D 0 set "EAR SPKR PA" 1'
```

#### Шаг 4: Найти контролы микрофона

Ищите `DEC1` — `DEC8` (Decimator — контролы микрофона).

Тест:
```bash
# Попробовать заглушить микрофон (собеседник не слышит вас)
su -c '/data/local/tmp/tinymix -D 0 set "DEC1 Volume" 0'
su -c '/data/local/tmp/tinymix -D 0 set "DEC2 Volume" 0'

# Если собеседник перестал вас слышать - нашли!
# Восстановить:
su -c '/data/local/tmp/tinymix -D 0 set "DEC1 Volume" 84'
```

#### Шаг 5: Если стандартный пресет не работает

В приложении выберите **Custom** и введите найденные контролы.

---

## Часть 3: Настройка SIP-сервера

### Вариант A: Облачный SIP-провайдер (проще всего)

Зарегистрируйтесь на любом SIP-провайдере (например, Zadarma, SipNET, VoIP.ms):
- Создайте **2 внутренних номера**: один для телефона (gateway), один для ПК (MicroSIP)
- Используйте данные провайдера в настройках

### Вариант B: Собственный сервер Asterisk (из проекта)

Настройте Asterisk по инструкции в `asterisk-config/README.md`.

Минимальный `pjsip.conf` для одного телефона и одного клиента:

```ini
; Транспорт
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

; Gateway (Mi 8 телефон)
[gateway1]
type=endpoint
context=from-gateway
disallow=all
allow=ulaw,alaw,g729
auth=gateway1-auth
aors=gateway1
transport=transport-udp

[gateway1-auth]
type=auth
auth_type=userpass
username=gateway1
password=СЛОЖНЫЙ_ПАРОЛЬ_ЗДЕСЬ

[gateway1]
type=aor
max_contacts=1
remove_existing=yes

; Клиент (MicroSIP на ноутбуке)
[client101]
type=endpoint
context=from-internal
disallow=all
allow=ulaw,alaw,g729
auth=client101-auth
aors=client101
transport=transport-udp

[client101-auth]
type=auth
auth_type=userpass
username=101
password=ДРУГОЙ_ПАРОЛЬ_ЗДЕСЬ

[client101]
type=aor
max_contacts=3
remove_existing=yes
```

---

## Часть 4: Настройка приложения на Mi 8

### Запустить приложение

После установки APK откройте **GSM-SIP Gateway**.

При первом запуске Magisk спросит root-права — **разрешить**.

### Настройки SIP

| Поле | Значение |
|------|----------|
| SIP Server | IP или домен вашего SIP-сервера |
| SIP Port | 5060 (UDP) или 5061 (TLS) |
| Username | `gateway1` (имя аккаунта шлюза) |
| Password | Пароль от gateway-аккаунта |
| Realm | Домен сервера (или оставьте `*`) |
| Use TLS | Включите, если сервер поддерживает |
| SIM1 Destination | `101` (внутренний номер MicroSIP) |
| SIM2 Destination | `102` (если есть вторая SIM) |

### Настройки аудио

| Поле | Значение |
|------|----------|
| Sound Card | Card 0 |
| Capture Device | 0: MultiMedia1 (или VOC_REC) |
| Playback Device | 0: MultiMedia1 (или Incall_Music) |
| Mixer Route | MultiMedia1 |
| Device Preset | **Xiaomi Mi 8 (SD845)** |

### Нажать Save → Connect

Статус должен показать **Registered** (зелёным).

### Включить Web Interface (для удобной настройки)

Включите тумблер **Web Interface** — появится ссылка вида `http://192.168.x.x:8080`.
Откройте в браузере на ПК для удобной настройки.

---

## Часть 5: Настройка MicroSIP на ноутбуке

### Установка

Скачайте MicroSIP: https://www.microsip.org/

### Добавить аккаунт

1. Нажать стрелку → **Add Account**
2. Заполнить:

| Поле | Значение |
|------|----------|
| Account name | Мой номер (любое) |
| SIP server | IP/домен вашего SIP-сервера |
| SIP proxy | (оставить пустым) |
| Username | `101` |
| Domain | IP/домен сервера |
| Password | пароль client101 |

3. Нажать **Save**

MicroSIP должен показать статус **Online** (зелёный кружок).

---

## Часть 6: Тест и проверка

### Тест 1: Исходящий звонок (с ноутбука через GSM)

1. В MicroSIP набрать любой телефонный номер: `+7XXXXXXXXXX`
2. Asterisk должен направить звонок через gateway1 (Mi 8)
3. Mi 8 наберёт номер через GSM
4. Вы разговариваете с вашего номера, без роуминга ✅

### Тест 2: Входящий звонок (на ваш номер)

1. Кто-то звонит на номер SIM-карты в Mi 8
2. Gateway перехватывает звонок
3. MicroSIP звенит на ноутбуке
4. Отвечаете в MicroSIP ✅

### Тест 3: Проверка аудио

Во время разговора через шлюз проверьте:
- Собеседник вас слышит (microphone работает)
- Вы слышите собеседника (earpiece/speaker работает)
- Нет эха (mute контролы работают)

---

## Устранение проблем

### Нет регистрации SIP

```bash
# Проверить доступность сервера
adb shell "ping -c 3 ВАШ_SIP_СЕРВЕР"

# Посмотреть логи приложения
adb logcat -s GatewaySvc PjsipSvc SipAccount
```

### Нет аудио

```bash
# Проверить SELinux
adb shell getenforce  # Должно быть Permissive

# Проверить права на аудио устройства
adb shell "su -c 'ls -la /dev/snd/'"

# Найти правильные PCM устройства
adb shell "su -c 'ls /proc/asound/card0/pcm*/'"
```

### Эхо во время разговора

Mute-контролы работают неправильно. Попробуйте:
1. Переключить на пресет **Custom**
2. Вручную найти контролы для Mi 8 (Шаг 3 выше)
3. Ввести их в поле Manual Controls

### Звонок обрывается через несколько секунд

Проблема с аудио-путём. Проверьте:
```bash
# Во время звонка проверить mixer
adb shell "su -c '/data/local/tmp/tinymix -D 0 contents | grep -i multimedia1'"

# Должны увидеть включённые маршруты:
# MultiMedia1 Mixer VOC_REC_DL: 1
# Incall_Music Audio Mixer MultiMedia1: 1
```

### Приложение закрывается в фоне

LineageOS может принудительно останавливать фоновые службы. Решение:
1. Убрать из ограничений батареи (шаг 1.6)
2. В Developer Options отключить "Don't keep activities"
3. Использовать ADB для постоянного запуска:
```bash
adb shell "am start-foreground-service -n org.onetwoone.gateway/.PjsipSipService"
```

---

## Важные замечания

### Безопасность
- Используйте сложные пароли для SIP-аккаунтов (минимум 12 символов)
- Если используете публичный IP — настройте firewall, ограничьте порты 5060/5061 и 10000-10100
- Рекомендуется TLS для шифрования SIP-сигнализации

### Зарядка телефона
- Приложение ограничивает заряд до 60% (можно изменить в настройках)
- Держите телефон постоянно подключённым к зарядке
- Рекомендуется не снимать задний скотч с разъёма USB для надёжного контакта

### Сеть
- Телефон должен иметь стабильный WiFi (не только мобильный интернет)
- Чем лучше интернет у телефона и у вас — тем лучше качество звука
- Рекомендуется статический IP или DynDNS для SIP-сервера

---

## Схема финального решения

```
┌─────────────────────────────────────────────────────────┐
│                    ДОМА / В ОФИСЕ                       │
│                                                         │
│   ┌──────────────┐    WiFi/LAN    ┌─────────────────┐  │
│   │ Xiaomi Mi 8  │◄──────────────►│  SIP Server     │  │
│   │ (GSM Gateway)│                │  (Asterisk/     │  │
│   │  + SIM карта │                │   облако)       │  │
│   └──────────────┘                └────────┬────────┘  │
│          │ GSM                             │           │
│          ▼                                 │ SIP/TLS   │
│    GSM Оператор                           │           │
└─────────────────────────────────────────────────────────┘
                                             │
                                        Интернет
                                             │
┌─────────────────────────────────────────────────────────┐
│                   ДРУГАЯ СТРАНА                         │
│                                                         │
│   ┌──────────────────────────────┐                      │
│   │  Ноутбук + MicroSIP          │                      │
│   │  Входящие: звонит MicroSIP   │◄─────────────────────┘
│   │  Исходящие: через Mi 8 GSM   │
│   └──────────────────────────────┘
│                                                         │
│   Без роуминга! Ваш номер! Через интернет!             │
└─────────────────────────────────────────────────────────┘
```
