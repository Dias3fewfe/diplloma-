# Network Intrusion Detection System (NIDS)

Дипломный проект — веб-система обнаружения сетевых вторжений на основе ансамбля алгоритмов машинного обучения.

---

## Описание

NIDS анализирует параметры сетевого трафика и в реальном времени определяет, является ли соединение нормальным или потенциальным вторжением. Система использует **ансамбль из 4 моделей**: три алгоритма детектирования аномалий (обучение без учителя) и один классификатор на основе случайного леса (обучение с учителем). Результат принимается **голосованием большинства** (≥ 2 из 4 голосов = вторжение).

Дополнительно система определяет **тип атаки** (DDoS, PortScan, BruteForce и др.), отправляет уведомления в **Telegram**, отображает географию атак на **карте мира в реальном времени** и определяет **геолокацию** атакующих IP-адресов.

---

## Демо

| Компонент | URL |
|---|---|
| Дашборд (frontend) | https://diplloma.vercel.app |
| API (backend) | https://diplloma-api.onrender.com |
| API документация | https://diplloma-api.onrender.com/docs |

**Доступ:** `admin` / `admin123` или кнопка **Sign in with Google**

---

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                        React Dashboard                            │
│  Overview │ Live Detection │ Packet Capture │ Alerts │ Attack Map │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼───────────────────────────────────────────┐
│                      FastAPI Backend                              │
│  /api/predict   /api/simulate   /api/alerts   /api/capture        │
│  /api/stats     /api/auth       /api/geo/batch                    │
└──────────┬──────────────────┬────────────────┬────────────────────┘
           │                  │                │
┌──────────▼────────┐ ┌───────▼──────────┐ ┌──▼────────────────────┐
│   ML Ensemble     │ │ SQLite Database  │ │ ip-api.com            │
│  Isolation Forest │ │ alerts table     │ │ IP Geolocation        │
│  LOF              │ │ (prediction,     │ │ (country, city, lat,  │
│  One-Class SVM    │ │  attack_type,    │ │  lng)                 │
│  Random Forest    │ │  confidence,     │ └───────────────────────┘
└───────────────────┘ │  model_votes)    │
                      └──────────────────┘
```

---

## Технологический стек

| Слой | Технологии |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **ML** | scikit-learn, pandas, numpy, joblib |
| **Database** | SQLite, SQLAlchemy |
| **Frontend** | React 18, Vite, Recharts, TailwindCSS |
| **Map** | Leaflet.js, react-leaflet, CartoDB Dark tiles |
| **Live Capture** | Scapy |
| **Geolocation** | ip-api.com (бесплатный, без API ключа) |
| **Notifications** | Telegram Bot API, httpx |
| **Auth** | JWT (python-jose), Google OAuth 2.0 |
| **Deploy** | Vercel (frontend), Render (backend) |

---

## Модели машинного обучения

### Ансамбль

| Модель | Тип | Обучающая выборка | Описание |
|---|---|---|---|
| **Isolation Forest** | Unsupervised | 200 000 строк (BENIGN) | Изолирует аномалии через случайные разбиения |
| **Local Outlier Factor** | Unsupervised | 50 000 строк (BENIGN) | Сравнивает плотность точки с её соседями |
| **One-Class SVM** | Unsupervised | 30 000 строк (BENIGN) | Строит границу вокруг нормального трафика |
| **Random Forest** | Supervised | 150 000 строк (все классы) | Классифицирует на основе размеченных данных |

Три unsupervised-модели обучены **только на нормальном трафике** — они учатся тому, как выглядит норма, и сигнализируют о любом отклонении. Random Forest обучен на полном датасете с метками.

### Логика ансамбля

```
vote = IF_vote + LOF_vote + SVM_vote + RF_vote

if vote >= 2:
    prediction = "INTRUSION"
    confidence = vote / 4
else:
    prediction = "NORMAL"
```

### Классификатор типов атак

Отдельная модель Random Forest (200 деревьев, 150k строк) определяет конкретный тип атаки среди 9 классов: `DDoS`, `DoS Hulk`, `PortScan`, `DoS GoldenEye`, `DoS slowloris`, `DoS Slowhttptest`, `Bot`, `Infiltration`, `Heartbleed`.

### Датасет

**CICIDS2017** (Canadian Institute for Cybersecurity) — 2 212 030 записей сетевого трафика, 78 признаков, 10 классов.

| Класс | Количество |
|---|---|
| BENIGN | 1 567 853 |
| DoS Hulk | 231 073 |
| PortScan | 158 930 |
| DDoS | 128 027 |
| DoS GoldenEye | 10 293 |
| DoS slowloris | 5 796 |
| DoS Slowhttptest | 5 499 |
| Bot | 1 966 |
| Infiltration | 36 |
| Heartbleed | 11 |

---

## Результаты оценки (evaluate.py)

Тестовая выборка: **9 997 строк** (стратифицированная по всем классам).

### Ансамблевые метрики

| Метрика | Значение |
|---|---|
| **Accuracy** | **90.6%** |
| **F1-score (INTRUSION)** | **0.784** |
| **Precision (INTRUSION)** | 88.9% |
| **Recall (INTRUSION)** | 70.1% |
| **Macro avg F1** | **0.862** |

### Метрики по каждой модели

| Модель | True Positive | False Positive | Recall | FPR |
|---|---|---|---|---|
| Isolation Forest | 789 | 369 | 32.3% | 4.9% |
| Local Outlier Factor | 919 | 350 | 37.6% | 4.6% |
| One-Class SVM | 1 147 | 367 | 47.0% | 4.9% |
| **Random Forest** | **2 441** | **3** | **100.0%** | **0.0%** |

### Detection Rate по типам атак

| Тип атаки | Обнаружено |
|---|---|
| DoS Slowhttptest | 100% |
| Heartbleed | 100% |
| Infiltration | 100% |
| DoS Hulk | 78.2% |
| DDoS | 71.5% |
| DoS slowloris | 69.2% |
| PortScan | 57.9% |
| DoS GoldenEye | 56.5% |

---

## Структура проекта

```
diplloma/
├── backend/
│   ├── main.py                   # FastAPI приложение
│   ├── config.py                 # Все пути и гиперпараметры
│   ├── notifications.py          # Telegram уведомления
│   ├── models/                   # Обученные .pkl файлы
│   │   ├── isolation_forest.pkl
│   │   ├── lof.pkl
│   │   ├── svm.pkl
│   │   ├── random_forest.pkl
│   │   ├── attack_classifier.pkl
│   │   └── scaler.pkl
│   ├── pipeline/
│   │   ├── preprocess.py         # Очистка данных, StandardScaler
│   │   ├── train.py              # Обучение 4 ансамблевых моделей
│   │   ├── train_classifier.py   # Обучение классификатора типов атак
│   │   ├── predict.py            # Логика инференса, lru_cache
│   │   ├── evaluate.py           # Оценка ансамбля, метрики
│   │   └── capture.py            # Live-захват пакетов через Scapy
│   ├── api/
│   │   ├── routes.py             # /predict /simulate /alerts /stats /export
│   │   ├── auth_routes.py        # /auth/login /auth/verify (JWT) + Google OAuth
│   │   ├── capture_routes.py     # /capture/* + WebSocket /ws/live
│   │   ├── geo_routes.py         # /geo/batch — геолокация IP через ip-api.com
│   │   └── schemas.py            # Pydantic модели
│   └── db/
│       └── database.py           # SQLite, таблица alerts
├── frontend/
│   └── src/
│       ├── App.jsx               # Роутинг вкладок, авторизация
│       └── components/
│           ├── Overview.jsx      # Статистика, графики
│           ├── LiveDetection.jsx # Симуляция в реальном времени
│           ├── LiveCapturePanel.jsx # Живой захват пакетов
│           ├── AlertsTable.jsx   # Таблица алертов, геолокация, экспорт CSV/PDF
│           ├── AttackMap.jsx     # Карта атак в реальном времени (Leaflet)
│           ├── ModelsPanel.jsx   # Информация о моделях
│           └── LoginPage.jsx     # Страница входа (admin + Google OAuth)
├── data/
│   ├── raw/                      # CICIDS2017.csv (не в git)
│   └── processed/
│       ├── cleaned.csv           # После preprocess.py (не в git)
│       └── sample.csv            # 5k строк для деплоя
├── .env.example                  # Шаблон переменных окружения
├── requirements.txt
└── CLAUDE.md
```

---

## Функциональность дашборда

### Overview
- Ключевые метрики: всего алертов, вторжений, detection rate
- **Threat Level** — индикатор уровня угрозы в реальном времени: LOW / MEDIUM / HIGH / CRITICAL на основе количества вторжений за последний час
- **Intrusion Timeline** — Area chart за последние 24 часа: красная линия (вторжения) и зелёная (нормальный трафик) по часовым bucket-ам
- BarChart топ-6 типов атак
- Индикатор статуса Telegram

### Live Detection
- Запуск симуляции на 100 случайных строках из датасета
- Таблица результатов с голосами каждой модели (IF / LOF / SVM / RF)
- Цветовые бейджи типов атак

### Packet Capture
- Выбор сетевого интерфейса
- Живой захват трафика через Scapy
- WebSocket-стрим результатов в браузер
- Таблица потоков: IP, порт, протокол, байты, предикшн, голоса

### Alerts
- Пагинированная таблица всех алертов из БД
- Фильтр по типу (Intrusion / Normal / All)
- **Геолокация** source IP: флаг страны, город, страна (ip-api.com)
- **Экспорт в CSV и PDF**

### Attack Map
- Тёмная карта мира на основе Leaflet.js + CartoDB Dark Matter tiles
- Цветные маркеры на координатах атакующих IP (цвет по типу атаки)
- Клик по маркеру → попап с IP, городом, страной, типом атаки, уверенностью
- **Live Feed** — боковая панель с последними 12 атаками в реальном времени
- Статистика: кол-во точек на карте, уникальных IP, стран
- Авто-обновление каждые **5 секунд**
- Кнопка **Load Demo Data** — вставляет 25 алертов с реальными публичными IP из 11 стран (Китай, Россия, США, Германия, Нидерланды, Бразилия, Индия, Южная Корея, Франция, Великобритания, Япония) для демонстрации карты
- Геолокация (страна, город, координаты) проксируется через бэкенд `/api/geo/batch` → ip-api.com

### Models
- Карточки 4 моделей с параметрами обучения
- Бейджи SUPERVISED / UNSUPERVISED

---

## Авторизация

### Admin / Password
```
Логин: admin
Пароль: admin123
```

### Google OAuth
Кнопка **Sign in with Google** на странице входа. Доступ разрешён только для аккаунта `dkadirhanovv@gmail.com`.

Поток: браузер → `/api/auth/google` → Google consent screen → `/api/auth/google/callback` → JWT → дашборд.

---

## Запуск локально

### Требования
- Python 3.11+
- Node.js 18+
- Windows: [Npcap](https://npcap.com/) (для live capture)

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Dias3fewfe/diplloma-.git
cd diplloma-
```

### 2. Установить зависимости Python

```bash
pip install -r requirements.txt
```

### 3. Настроить переменные окружения

```bash
cp .env.example .env
# Заполнить переменные (Telegram опционально, Google OAuth опционально)
```

### 4. Подготовить данные и обучить модели

```bash
# Положить CICIDS2017.csv в data/raw/
python -m backend.pipeline.preprocess
python -m backend.pipeline.train
python -m backend.pipeline.train_classifier
python -m backend.pipeline.evaluate
```

### 5. Запустить бэкенд

```bash
# Требует прав администратора для live capture
uvicorn backend.main:app --reload --port 8000
```

### 6. Запустить фронтенд

```bash
cd frontend
npm install
npm run dev
```

### 7. Открыть дашборд

```
http://localhost:5173
```

---

## API эндпоинты

| Метод | URL | Описание |
|---|---|---|
| `POST` | `/api/auth/login` | Получить JWT токен (admin/password) |
| `GET` | `/api/auth/verify` | Проверить токен |
| `GET` | `/api/auth/google` | Редирект на Google OAuth |
| `GET` | `/api/auth/google/callback` | Обработка callback, выдача JWT |
| `POST` | `/api/predict` | Предсказание для одного вектора признаков |
| `POST` | `/api/simulate` | Симуляция на 100 случайных строках |
| `GET` | `/api/alerts` | Список алертов (с пагинацией и фильтром) |
| `GET` | `/api/alerts/export/csv` | Экспорт алертов в CSV |
| `GET` | `/api/alerts/export/pdf` | Экспорт алертов в PDF |
| `GET` | `/api/stats` | Агрегированная статистика |
| `GET` | `/api/health` | Проверка доступности API |
| `GET` | `/api/notification-status` | Статус Telegram |
| `POST` | `/api/geo/batch` | Геолокация списка IP (страна, город, lat/lon) |
| `POST` | `/api/demo/populate` | Вставить 25 демо-алертов с реальными публичными IP |
| `GET` | `/api/stats/timeline` | Почасовые bucket-ы вторжений за последние N часов |
| `POST` | `/api/capture/start` | Начать захват пакетов |
| `POST` | `/api/capture/stop` | Остановить захват |
| `GET` | `/api/capture/status` | Счётчики захвата |
| `WS` | `/api/ws/live` | WebSocket стрим результатов |

Полная интерактивная документация: `http://localhost:8000/docs`

---

## Настройка Telegram уведомлений

1. Создать бота через [@BotFather](https://t.me/BotFather), получить токен
2. Узнать свой `chat_id` через [@userinfobot](https://t.me/userinfobot)
3. Добавить в `.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_токен
TELEGRAM_CHAT_ID=ваш_chat_id
```

Уведомление приходит при `confidence >= 75%`. Формат:

```
INTRUSION DETECTED
Type: DDoS
Confidence: 100%
Source IP: 192.168.1.45
Protocol: TCP
Models: IF LOF SVM RF
Time: 2026-05-14 12:34:56
```

---

## Настройка Google OAuth

1. Создать проект в [Google Cloud Console](https://console.cloud.google.com)
2. APIs & Services → Credentials → OAuth 2.0 Client ID (Web application)
3. Добавить Authorized redirect URI: `https://your-backend.onrender.com/api/auth/google/callback`
4. Добавить в `.env`:

```env
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=https://your-backend.onrender.com/api/auth/google/callback
GOOGLE_ALLOWED_EMAIL=your_email@gmail.com
FRONTEND_URL=https://your-frontend.vercel.app
```

---

## Автор

**Dias Kadirhanov**  
Международный университет информационных технологий (МУИТ)  
Дипломная работа, 2026
