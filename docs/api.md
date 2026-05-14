# API Документация

Базовый URL (production): `https://diplloma-api.onrender.com`  
Базовый URL (локально): `http://localhost:8000`  
Интерактивная документация: `/docs` (Swagger UI)

Все ответы имеют единый формат:
```json
{
  "status": "ok" | "error",
  "data": { ... },
  "error": null | "сообщение об ошибке"
}
```

---

## Аутентификация

### POST /api/auth/login

Получить JWT-токен по логину и паролю.

**Тело запроса:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "admin"
  },
  "error": null
}
```

**Ошибка (401):**
```json
{
  "detail": "Invalid username or password"
}
```

---

### GET /api/auth/verify

Проверить валидность токена.

**Заголовок:** `Authorization: Bearer <token>`

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "data": { "username": "admin" },
  "error": null
}
```

**Ошибка (401):** `"Invalid or expired token"`

---

## Предсказание

### POST /api/predict

Запустить ансамбль на одном векторе признаков.

**Тело запроса:**
```json
{
  "features": {
    "Flow Duration": 12345,
    "Total Fwd Packets": 10,
    "Total Backward Packets": 8,
    "...": "..."
  },
  "source_ip": "192.168.1.1",
  "destination_ip": "8.8.8.8",
  "protocol": "TCP",
  "timestamp": "2026-05-14T12:00:00"
}
```

`features` должен содержать все 77 числовых признаков CICIDS2017 (ненормализованных — скейлер применяется автоматически).

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "data": {
    "prediction": "INTRUSION",
    "model_votes": {
      "isolation_forest": 1,
      "lof": 1,
      "svm": 0,
      "random_forest": 1
    },
    "attack_confidence": 0.75,
    "vote_sum": 3,
    "alert_id": 42,
    "attack_type": "DDoS"
  },
  "error": null
}
```

**Ошибки:**
- `422` — отсутствуют обязательные признаки
- `503` — модели не загружены

---

### POST /api/simulate

Запустить симуляцию на 100 случайных строках из датасета.

**Тело запроса:** пустое `{}`

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "data": {
    "rows_evaluated": 100,
    "intrusions_detected": 23,
    "normal_count": 77,
    "detection_rate": 0.23,
    "alerts_saved": 23,
    "model_agreement": {
      "isolation_forest": 15,
      "lof": 18,
      "svm": 20,
      "random_forest": 23
    },
    "rows": [
      {
        "index": 0,
        "label": "DDoS",
        "prediction": "INTRUSION",
        "model_votes": {"isolation_forest": 1, "lof": 1, "svm": 1, "random_forest": 1},
        "attack_confidence": 1.0,
        "attack_type": "DDoS"
      }
    ]
  },
  "error": null
}
```

---

## Алерты

### GET /api/alerts

Получить список алертов с пагинацией.

**Query-параметры:**

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `limit` | int | 50 | Количество записей (1–500) |
| `offset` | int | 0 | Смещение для пагинации |
| `prediction` | string | — | Фильтр: `INTRUSION` или `NORMAL` |

**Пример запроса:** `GET /api/alerts?limit=20&offset=0&prediction=INTRUSION`

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "data": {
    "total": 156,
    "offset": 0,
    "limit": 20,
    "alerts": [
      {
        "id": 42,
        "timestamp": "2026-05-14T12:34:56",
        "source_ip": "192.168.1.45",
        "destination_ip": "8.8.4.4",
        "protocol": "TCP",
        "prediction": "INTRUSION",
        "model_votes": {"isolation_forest": 1, "lof": 1, "svm": 0, "random_forest": 1},
        "attack_confidence": 0.75,
        "attack_type": "DDoS",
        "created_at": "2026-05-14T12:34:56"
      }
    ]
  },
  "error": null
}
```

---

### GET /api/alerts/export/csv

Скачать все алерты в формате CSV.

**Ответ:** файл `nids_alerts_YYYYMMDD_HHMMSS.csv`

**Колонки:** `id, timestamp, source_ip, destination_ip, protocol, prediction, attack_type, confidence, vote_IF, vote_LOF, vote_SVM, vote_RF`

---

### GET /api/alerts/export/pdf

Скачать все алерты в формате PDF (A4 landscape).

**Ответ:** файл `nids_alerts_YYYYMMDD_HHMMSS.pdf`

---

## Статистика

### GET /api/stats

Агрегированная статистика по всем алертам.

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "data": {
    "total_alerts": 500,
    "intrusion_count": 115,
    "normal_count": 385,
    "detection_rate": 0.23,
    "model_vote_totals": {
      "isolation_forest": 80,
      "lof": 95,
      "svm": 105,
      "random_forest": 115
    },
    "attack_type_breakdown": {
      "DDoS": 45,
      "DoS Hulk": 38,
      "PortScan": 22,
      "Bot": 10
    }
  },
  "error": null
}
```

---

## Live Capture

### POST /api/capture/start

Начать захват пакетов на сетевом интерфейсе.

**Тело запроса:**
```json
{
  "interface": "Wi-Fi"
}
```

**Ответ:** `{"status": "ok", "data": {"message": "Capture started on Wi-Fi"}}`

---

### POST /api/capture/stop

Остановить захват пакетов.

**Ответ:** `{"status": "ok", "data": {"message": "Capture stopped"}}`

---

### GET /api/capture/status

Текущие счётчики захвата.

**Ответ:**
```json
{
  "status": "ok",
  "data": {
    "running": true,
    "interface": "Wi-Fi",
    "packets_seen": 1250,
    "flows_finalized": 87,
    "intrusions": 3
  }
}
```

---

### GET /api/capture/interfaces

Список доступных сетевых интерфейсов.

**Ответ:**
```json
{
  "status": "ok",
  "data": {
    "interfaces": ["Wi-Fi", "Ethernet", "Loopback Pseudo-Interface 1"]
  }
}
```

---

### WebSocket /api/ws/live

Стрим результатов в реальном времени.

**Подключение:** `ws://localhost:8000/api/ws/live`

**Сообщение при обнаружении потока:**
```json
{
  "src_ip": "192.168.1.5",
  "dst_ip": "93.184.216.34",
  "src_port": 54321,
  "dst_port": 443,
  "protocol": "TCP",
  "bytes": 4096,
  "prediction": "INTRUSION",
  "attack_type": "PortScan",
  "confidence": 0.75,
  "votes": {
    "isolation_forest": 1,
    "lof": 1,
    "svm": 0,
    "random_forest": 1
  },
  "timestamp": "2026-05-14T12:34:56"
}
```

---

## Служебные эндпоинты

### GET /api/health

Проверка доступности API.

```json
{"status": "ok", "data": {"message": "NIDS API is running"}, "error": null}
```

### GET /api/notification-status

Статус Telegram-уведомлений.

```json
{"status": "ok", "data": {"telegram_configured": true}, "error": null}
```
