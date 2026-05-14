# Архитектура системы

## Общее описание

NIDS построена по трёхзвенной архитектуре: фронтенд (React), бэкенд (FastAPI) и база данных (SQLite). Фронтенд и бэкенд развёрнуты на отдельных платформах и общаются через REST API и WebSocket.

```
Браузер (Vercel)
      │
      │  HTTPS / WSS
      ▼
FastAPI Backend (Render)
      │
      ├── ML Pipeline (scikit-learn)
      │     ├── Isolation Forest
      │     ├── Local Outlier Factor
      │     ├── One-Class SVM
      │     └── Random Forest
      │
      ├── SQLite Database
      │     └── alerts table
      │
      └── Telegram Bot API
```

---

## Компоненты

### Frontend (React 18 + Vite)

Одностраничное приложение (SPA) с пятью вкладками. Взаимодействует с бэкендом через HTTP-запросы (axios) и WebSocket. Состояние авторизации хранится в `localStorage` в виде JWT-токена.

**Ключевые компоненты:**

| Файл | Назначение |
|---|---|
| `App.jsx` | Корневой компонент: маршрутизация вкладок, проверка авторизации |
| `LoginPage.jsx` | Форма входа, получение JWT |
| `Overview.jsx` | Метрики, графики, статус Telegram |
| `LiveDetection.jsx` | Симуляция детекции на 100 строках |
| `LiveCapturePanel.jsx` | Live-захват пакетов через WebSocket |
| `AlertsTable.jsx` | Таблица алертов, экспорт CSV/PDF |
| `ModelsPanel.jsx` | Карточки моделей с параметрами |

### Backend (FastAPI + Python 3.11)

RESTful API с асинхронной обработкой запросов. Модели ML загружаются один раз при старте и кэшируются через `lru_cache`. Тяжёлые операции (Telegram-уведомления) выполняются в фоновых задачах (`BackgroundTasks`).

**Модули:**

| Файл | Назначение |
|---|---|
| `main.py` | Инициализация FastAPI, CORS, подключение роутеров |
| `config.py` | Централизованная конфигурация путей и гиперпараметров |
| `notifications.py` | Отправка Telegram-уведомлений (asyncio + httpx) |
| `api/routes.py` | Основные эндпоинты: predict, simulate, alerts, stats, export |
| `api/auth_routes.py` | Аутентификация: login, verify (JWT HS256) |
| `api/capture_routes.py` | Live-захват: start/stop/status + WebSocket |
| `api/schemas.py` | Pydantic-модели запросов и ответов |
| `db/database.py` | SQLAlchemy ORM, таблица alerts, миграции |
| `pipeline/preprocess.py` | Очистка датасета, обучение StandardScaler |
| `pipeline/train.py` | Обучение 4 ансамблевых моделей |
| `pipeline/train_classifier.py` | Обучение мультиклассового классификатора |
| `pipeline/predict.py` | Инференс: predict_single, predict_batch_scaled |
| `pipeline/evaluate.py` | Оценка ансамбля, метрики качества |
| `pipeline/capture.py` | Захват пакетов: FlowRecord, FlowCapture (Scapy) |

### База данных (SQLite)

Один файл `backend/db/alerts.db`. Содержит единственную таблицу `alerts`.

**Схема таблицы alerts:**

| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | Автоинкрементный идентификатор |
| `timestamp` | DATETIME | Время события |
| `source_ip` | VARCHAR | IP-адрес источника |
| `destination_ip` | VARCHAR | IP-адрес назначения |
| `protocol` | VARCHAR | Транспортный протокол |
| `prediction` | VARCHAR | INTRUSION или NORMAL |
| `model_votes` | JSON | `{"isolation_forest": 1, "lof": 0, ...}` |
| `attack_confidence` | FLOAT | Доля моделей, проголосовавших за атаку (0.0–1.0) |
| `attack_type` | VARCHAR | Тип атаки: DDoS, PortScan, BENIGN и др. |
| `created_at` | DATETIME | Время записи в БД |

---

## Поток данных

### Симуляция (/api/simulate)

```
POST /api/simulate
       │
       ▼
Загрузить 100 случайных строк из cleaned.csv
       │
       ▼
predict_batch_scaled(X)
       │
       ├── Isolation Forest → vote[i]
       ├── LOF             → vote[i]
       ├── One-Class SVM   → vote[i]
       └── Random Forest   → vote[i]
              │
              ▼
       vote_sum = sum(votes)
       prediction = "INTRUSION" if vote_sum >= 2
              │
              ▼
classify_attack_type_batch(X) → attack_type
              │
              ▼
Сохранить INTRUSION-строки в alerts
              │
              ▼
BackgroundTask: send_alert() → Telegram
              │
              ▼
Вернуть SimulateSummary клиенту
```

### Live Capture (WebSocket)

```
POST /api/capture/start
       │
       ▼
FlowCapture.start(interface)  [фоновый поток]
       │
       ├── Sniff пакеты → группировать в 5-tuple потоки
       │
       ├── TCP FIN/RST или таймаут 30с → завершить поток
       │
       ▼
extract_features(flow) → 78 признаков CICIDS2017
       │
       ▼
predict_single(features) → ensemble result
       │
       ├── Сохранить в БД если INTRUSION
       │
       ├── asyncio.run_coroutine_threadsafe → WS broadcast
       │
       └── Telegram уведомление если confidence >= 0.75
```

---

## Безопасность

- **Авторизация:** JWT HS256 с 24-часовым сроком действия. Токен передаётся в заголовке `Authorization: Bearer <token>`.
- **CORS:** разрешены только конкретные origins (localhost:5173 и production URL Vercel).
- **Секреты:** токены и пароли хранятся в `.env` (не коммитится), передаются через переменные окружения.
- **Валидация входных данных:** все тела запросов валидируются через Pydantic-схемы.

---

## Масштабируемость

- Модели загружаются один раз через `lru_cache` — повторные запросы не вызывают I/O.
- Фоновые задачи (Telegram) не блокируют ответ API.
- Live capture работает в отдельном потоке; WebSocket-броадкаст использует asyncio через `run_coroutine_threadsafe`.
- SQLite достаточен для учебного проекта; при промышленном использовании замена на PostgreSQL не требует изменений в логике — только строку `DATABASE_URL` в `config.py`.
