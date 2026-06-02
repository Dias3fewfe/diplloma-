# NIDS — Полное описание функционала

Документ описывает каждый экран, компонент и API системы обнаружения сетевых вторжений.

---

## Общая архитектура

```
Пользователь (браузер)
       │
       ▼
React Frontend (Vercel — diplloma.vercel.app)
       │  HTTP REST + WebSocket
       ▼
FastAPI Backend (Render — diplloma-api.onrender.com)
       │
   ┌───┴──────────────────────────────┐
   │                                  │
ML Ансамбль (.pkl файлы)        SQLite БД (alerts.db)
IF + LOF + OC-SVM + RF           все детектированные алерты
   │
Attack Classifier (.pkl)
определяет тип атаки
```

Фронтенд и бэкенд полностью разделены. Фронтенд — статичное React-приложение, которое общается с бэкендом только через HTTP/WebSocket. Бэкенд хранит все данные в SQLite и держит ML-модели в памяти (загружаются один раз через `lru_cache`).

---

## Страница входа (LoginPage)

**Файл:** `frontend/src/components/LoginPage.jsx`

### Что видит пользователь
Split-screen экран: левая половина — анимированный фон с брендингом, правая — форма входа.

### Анимация (NetworkCanvas)
- Canvas на весь фон с 65 узлами (nodes), которые медленно движутся
- Между близкими узлами (расстояние < 130px) рисуются линии — имитация сетевой топологии
- Каждые 1.8–3.2 секунды случайный узел «детектирует атаку»: вспыхивает красным, от него расходятся кольца ряби, соседние рёбра краснеют
- По рёбрам движутся маленькие синие точки — «пакеты»
- Всё реализовано на чистом `canvas` + `requestAnimationFrame`, без библиотек

### Левая панель (брендинг)
- Метка «Diploma Project · IITU 2026»
- Заголовок «Network Intrusion Detection System»
- Описание системы
- Три счётчика с анимацией count-up при загрузке: **4 алгоритма**, **86% F1**, **90% Accuracy**
- Теги четырёх моделей: Isolation Forest, LOF, OC-SVM, Random Forest

### Правая панель (форма)
- Поля Username и Password с подсветкой при фокусе (синее свечение `box-shadow`)
- Кнопка **Sign In** → POST `/api/auth/login` → получает JWT токен → сохраняет в `localStorage`
- Кнопка **Sign in with Google** → редирект на `/api/auth/google` → Google OAuth → JWT
- Подсказка дефолтных credentials: `admin / admin123`

### Что происходит при успешном входе
JWT токен и username сохраняются в `localStorage` под ключами `nids_token` и `nids_user`. Компонент `App.jsx` проверяет токен при загрузке через GET `/api/auth/verify`. Если токен валидный — сразу открывается дашборд без повторного логина.

---

## Навигация (App.jsx)

**Файл:** `frontend/src/App.jsx`

Хедер содержит:
- Логотип NIDS и название системы
- Бейдж **LIVE** (красный пульсирующий)
- Строка с датасетом и составом ансамбля: `CICIDS2017 · Ensemble: IF + LOF + OC-SVM + RF`
- Имя залогиненного пользователя
- Кнопка **Logout** — очищает `localStorage`, возвращает на страницу входа

Шесть вкладок: **Overview · Live Detection · Packet Capture · Alerts · Attack Map · Models**

---

## Вкладка Overview

**Файл:** `frontend/src/components/Overview.jsx`

Обновляется автоматически каждые **10 секунд** (GET `/api/stats` + GET `/api/stats/timeline`).

### Карточки метрик (верхний ряд)

| Карточка | Что показывает | Источник |
|---|---|---|
| Total Intrusions | Количество алертов с prediction=INTRUSION в БД | `/api/stats` → `intrusion_count` |
| Detection Rate | Доля вторжений от всех алертов (%) | `intrusion_count / total_alerts` |
| Leading Detector | Модель с наибольшим числом голосов за аномалию | `model_vote_totals` — argmax |
| Ensemble Status | Всегда «4 / 4 models operational» | хардкод в UI |
| Threat Level | Уровень угрозы за последний час | `recent_intrusions_1h` из `/api/stats` |

### Threat Level — логика
Считается на бэкенде по количеству intrusion-алертов за последние 60 минут:
- **LOW** — 0 вторжений
- **MEDIUM** — 1–5 вторжений
- **HIGH** — 6–20 вторжений
- **CRITICAL** — более 20 вторжений

Карточка меняет цвет и текст: зелёный/жёлтый/оранжевый/красный.

### Intrusion Timeline — последние 24 часа
Area chart (Recharts) с двумя линиями:
- Красная — количество вторжений по часам
- Зелёная — нормальный трафик по часам

Бэкенд делает GROUP BY по часу (`created_at`), возвращает ровно 24 bucket-а — даже пустые, чтобы ось X всегда была полной.

### Anomaly Votes by Model
Горизонтальные бар-чарты для каждой из 4 моделей. Показывают, сколько раз каждая модель проголосовала за аномалию за всё время. Random Forest, как правило, лидирует — он supervised и хорошо знает паттерны атак.

### Top Attack Types Detected
Горизонтальный BarChart топ-6 типов атак по количеству алертов в БД. Цвета: DDoS — красный, PortScan — жёлтый, Bot — фиолетовый и т.д. Данные из `attack_type_breakdown` — GROUP BY attack_type в SQLite.

### Telegram статус
Маленькая строка под навигацией: зелёная точка если `TELEGRAM_BOT_TOKEN` настроен, серая — если нет.

---

## Вкладка Live Detection

**Файл:** `frontend/src/components/LiveDetection.jsx`

### Attack Scenarios (главная фича)

Пять кнопок для запуска конкретных сценариев атак. Каждая кнопка — отдельный тип атаки со своим цветом:

| Кнопка | Цвет | Тип атаки | Описание |
|---|---|---|---|
| Port Scan | жёлтый | PortScan | Перебор открытых портов |
| DDoS | красный | DDoS | Распределённая атака |
| DoS Hulk | оранжевый | DoS Hulk | HTTP GET flood |
| Botnet | фиолетовый | Bot | C&C трафик ботнета |
| DoS GoldenEye | голубой | DoS GoldenEye | HTTP keepalive DoS |

**Что происходит при нажатии:**
1. POST `/api/simulate/attack/{attack_type}`
2. Бэкенд загружает `sample.csv` (или `cleaned.csv`), фильтрует строки по полю `Label == attack_type`
3. Берёт 25 строк (реальные записи из CICIDS2017 именно этого типа атаки)
4. Прогоняет через `predict_batch_scaled()` — StandardScaler + все 4 модели
5. Сохраняет intrusion-алерты в SQLite с реальными IP атакующих из `_SCENARIO_IPS`
6. Возвращает 25 результатов на фронтенд

**Визуализация на фронтенде:**
- Строки появляются одна за другой с задержкой 120 мс — эффект «живого сканирования»
- Прогресс-бар `N / 25 flows analysed` с цветом под тип атаки
- Баннер `⚠ N INTRUSIONS DETECTED` с процентом detection rate
- В таблице: Label, Prediction (⚠ INTRUSION / ✓ NORMAL), Confidence bar, голоса IF/LOF/SVM/RF (цветные точки со свечением), Score N/4

**Почему это реально, а не заглушка:**
Данные — настоящие записи сетевого трафика из академического датасета CICIDS2017. Модели — обученные .pkl файлы. Весь путь: реальные фичи → StandardScaler → IF + LOF + SVM + RF → голосование → результат.

### Run Random Simulation
Кнопка запускает POST `/api/simulate` — 100 случайных строк из датасета (смешанные: BENIGN + разные атаки). Строки появляются с задержкой 60 мс. Используется для общей демонстрации работы ансамбля.

---

## Вкладка Packet Capture

**Файл:** `frontend/src/components/LiveCapturePanel.jsx`

> Требует локального запуска бэкенда с правами Администратора (Windows) или root (Linux), и установленного Npcap.

### Принцип работы
1. GET `/api/capture/interfaces` — список сетевых интерфейсов машины
2. Пользователь выбирает интерфейс (например, Wi-Fi)
3. POST `/api/capture/start` — Scapy начинает снифать пакеты в фоновом потоке
4. WebSocket `/api/ws/live` — бэкенд стримит результаты в браузер в реальном времени
5. POST `/api/capture/stop` — остановка

### Что делает бэкенд (capture.py)
- `FlowRecord` — накапливает пакеты одного TCP/UDP потока (5-tuple: src_ip, dst_ip, src_port, dst_port, protocol)
- `extract_features()` — вычисляет ~78 признаков совместимых с CICIDS2017: длины пакетов, IAT (inter-arrival time), флаги TCP, fwd/bwd статистику
- Поток завершается по TCP FIN/RST или таймауту 30 секунд
- Завершённый поток идёт в `predict_single()` → результат через WebSocket в браузер

### Таблица в UI
Колонки: Source IP, Source Port, Dst IP, Dst Port, Protocol, Bytes, Prediction, IF/LOF/SVM/RF голоса.

---

## Вкладка Alerts

**Файл:** `frontend/src/components/AlertsTable.jsx`

Таблица всех алертов из SQLite. Данные: GET `/api/alerts?limit=20&offset=N`.

### Колонки таблицы

| Колонка | Что показывает |
|---|---|
| Timestamp | Время создания алерта (UTC) |
| Source IP | IP атакующего (или симулированный) |
| Location | Геолокация IP: флаг страны + город, страна |
| Destination IP | IP жертвы |
| Proto | Протокол (TCP/UDP) |
| Prediction | INTRUSION (красный) / NORMAL (зелёный) |
| Attack Type | Тип атаки: цветной бейдж (DDoS=красный, PortScan=жёлтый, Bot=фиолетовый и т.д.) |
| Confidence | Уверенность ансамбля в % |
| Models Voted | Чипы IF/LOF/SVM/RF: красный=проголосовал за аномалию, серый=нет |

### Геолокация
Для каждой страницы алертов фронтенд собирает уникальные source IP и делает POST `/api/geo/batch`. Бэкенд проксирует запрос к `ip-api.com` (бесплатный сервис, без ключа). Возвращает: страну, город, countryCode (для флага), lat/lng. Приватные IP (192.168.x.x, 10.x.x.x) возвращают `null` — в UI показывается «Private».

### Фильтрация
Три кнопки: **All / Intrusions / Normal** — меняют параметр `prediction` в GET-запросе.

### Пагинация
20 алертов на страницу. Кнопки Prev/Next.

### Экспорт
- **Export CSV** — GET `/api/alerts/export/csv` — скачивает файл со всеми алертами, включая голоса IF/LOF/SVM/RF
- **Export PDF** — GET `/api/alerts/export/pdf` — PDF таблица A4 landscape через `fpdf2`, тёмная тема, автопагинация

---

## Вкладка Attack Map

**Файл:** `frontend/src/components/AttackMap.jsx`

Карта мира в реальном времени. Обновляется каждые **5 секунд**.

### Карта
- Leaflet.js + CartoDB Dark Matter тайлы (тёмная карта без надписей)
- Каждый алерт с публичным IP — цветной круговой маркер на координатах атакующего
- Цвет маркера зависит от типа атаки: DDoS/DoS Hulk — красный, PortScan — жёлтый, Bot — фиолетовый, Infiltration — бирюзовый, Heartbleed — розовый
- 5 последних атак имеют пульсирующее кольцо (CSS-анимация `nids-ping`)
- Клик по маркеру → попап: тип атаки, IP, город/страна, уверенность, время

### Логика обновления
1. GET `/api/alerts?prediction=INTRUSION&limit=200`
2. Новые алерты (не виденные ранее) — собирает их source IP
3. POST `/api/geo/batch` — получает координаты
4. Добавляет точки на карту (максимум 500 хранится в памяти)

### Статистика (верхняя панель)
- Зелёная/жёлтая точка статуса (Live / Loading)
- Attacks plotted — сколько точек на карте
- Unique IPs — уникальных атакующих
- Countries — из скольких стран

### Live Feed (правая панель)
12 последних атак списком: тип атаки, IP, город/страна, уверенность, время.

### Load Demo Data
Кнопка вставляет 25 заготовленных алертов с реальными публичными IP из 11 стран (Китай, Россия, США, Германия, Нидерланды, Бразилия, Индия, Южная Корея, Франция, Великобритания, Япония). Нужна для демонстрации карты без реального трафика. Не дублирует: проверяет `source_ip` на уникальность в БД.

---

## Вкладка Models

**Файл:** `frontend/src/components/ModelsPanel.jsx`

Статичная информационная страница о моделях (данные хардкодены в компоненте).

### Четыре карточки моделей

**Isolation Forest** (Unsupervised)
- Обучен на 200 000 строках BENIGN трафика
- Строит случайные бинарные деревья; аномалии изолируются быстрее нормальных точек
- Параметры: n_estimators=100, contamination=0.05

**Local Outlier Factor** (Unsupervised)
- Обучен на 50 000 строках BENIGN
- Сравнивает локальную плотность каждой точки с 20 ближайшими соседями
- Параметры: n_neighbors=20, novelty=True

**One-Class SVM** (Unsupervised)
- Обучен на 30 000 строках BENIGN
- Строит гиперсферу вокруг нормального трафика в пространстве RBF-ядра
- Параметры: kernel=rbf, nu=0.05

**Random Forest** (Supervised)
- Обучен на 150 000 строках всех классов (стратифицированная выборка)
- Единственная supervised-модель: знает реальные метки атак
- Параметры: n_estimators=100, class_weight=balanced

### Схема голосования
Визуальная диаграмма: 4 блока моделей → сумма голосов → порог:
- 0–1 голосов за аномалию → **NORMAL**
- 2–4 голосов за аномалию → **INTRUSION**

### Датасет CICIDS2017
Карточки: 2 212 030 потоков, 75.6% BENIGN, 9 категорий атак, 77 признаков.

---

## ML Pipeline (бэкенд)

### Предобработка (preprocess.py)
1. Загружает сырой CICIDS2017.csv (~170MB, 2.2M строк)
2. Удаляет столбцы с >40% пропусков
3. Заменяет `inf` и `NaN` на медиану
4. Обучает `StandardScaler` на BENIGN строках → сохраняет `scaler.pkl`
5. Сохраняет `cleaned.csv` + `sample.csv` (5k строк для деплоя на Render)

### Обучение моделей (train.py)
- Isolation Forest: 200k BENIGN строк → `isolation_forest.pkl`
- LOF: 50k BENIGN строк → `lof.pkl`
- OC-SVM: 30k BENIGN строк → `svm.pkl`
- Random Forest: 150k строк всех классов, stratified → `random_forest.pkl`

### Классификатор типов атак (train_classifier.py)
Отдельный Random Forest (200 деревьев, 150k строк) предсказывает конкретный тип: DDoS, PortScan, DoS Hulk, DoS GoldenEye, DoS slowloris, Bot, Infiltration, Heartbleed, BENIGN. Сохраняется в `attack_classifier.pkl`.

### Инференс (predict.py)
- `predict_single(features_dict)` — один поток: применяет scaler, прогоняет через все модели, возвращает prediction + model_votes + attack_confidence
- `predict_batch_scaled(X_df)` — батч уже нормализованных данных (из cleaned.csv)
- `classify_attack_type(features)` — классификатор типа атаки
- Все модели загружаются через `@lru_cache` — один раз при первом запросе

### Логика ансамбля
```
vote = IF_vote + LOF_vote + SVM_vote + RF_vote   # каждый: 0 или 1

if vote >= 2:
    prediction = "INTRUSION"
    confidence = vote / 4        # 0.5, 0.75 или 1.0
else:
    prediction = "NORMAL"
    confidence = (4 - vote) / 4
```

---

## API эндпоинты

### Аутентификация
| Метод | URL | Что делает |
|---|---|---|
| POST | `/api/auth/login` | Принимает `{username, password}`, возвращает JWT токен (HS256, 24ч) |
| GET | `/api/auth/verify` | Проверяет токен из заголовка `Authorization: Bearer <token>` |
| GET | `/api/auth/google` | Редирект на Google OAuth consent screen |
| GET | `/api/auth/google/callback` | Принимает code от Google, выдаёт JWT, редирект на фронтенд |

### Предсказания
| Метод | URL | Что делает |
|---|---|---|
| POST | `/api/predict` | Один вектор фич → prediction + votes + attack_type. Сохраняет в БД если INTRUSION |
| POST | `/api/simulate` | 100 случайных строк из датасета → batch prediction → сохранение |
| POST | `/api/simulate/attack/{type}` | 25 строк конкретного типа атаки → batch prediction → сохранение |

### Данные
| Метод | URL | Что делает |
|---|---|---|
| GET | `/api/alerts` | Список алертов, параметры: `limit`, `offset`, `prediction` |
| GET | `/api/alerts/export/csv` | Скачать все алерты как CSV |
| GET | `/api/alerts/export/pdf` | Скачать все алерты как PDF |
| GET | `/api/stats` | Агрегат: intrusion_count, detection_rate, model_vote_totals, attack_type_breakdown, threat_level |
| GET | `/api/stats/timeline` | Почасовые bucket-ы за последние N часов (параметр `hours`, default 24) |
| POST | `/api/geo/batch` | `{ips: [...]}` → геолокация через ip-api.com, возвращает `{ip: {country, city, lat, lon, countryCode}}` |

### Live Capture
| Метод | URL | Что делает |
|---|---|---|
| GET | `/api/capture/interfaces` | Список сетевых интерфейсов машины |
| POST | `/api/capture/start` | Запуск Scapy-снифера на указанном интерфейсе |
| POST | `/api/capture/stop` | Остановка снифера |
| GET | `/api/capture/status` | Счётчики: packets_seen, flows_finalized, intrusions |
| WS | `/api/ws/live` | WebSocket стрим: каждый завершённый поток → JSON с предсказанием |

### Сервисные
| Метод | URL | Что делает |
|---|---|---|
| GET | `/api/health` | Liveness probe: `{"status": "ok"}` |
| GET | `/api/notification-status` | Настроен ли Telegram: `{"telegram_configured": true/false}` |
| POST | `/api/demo/populate` | Вставляет 25 демо-алертов с реальными публичными IP для карты |

---

## Telegram уведомления

**Файл:** `backend/notifications.py`

При каждом детектированном вторжении с `confidence >= 0.75` (75%) бэкенд отправляет сообщение в Telegram через Bot API. Отправка происходит через `BackgroundTasks` FastAPI — не блокирует ответ API.

Формат уведомления:
```
INTRUSION DETECTED
Type: DDoS
Confidence: 100%
Source IP: 185.220.101.34
Protocol: TCP
Models: IF LOF SVM RF
Time: 2026-06-02 14:23:11
```

Настройка: `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` в `.env`.

---

## База данных

**Файл:** `backend/db/database.py`

SQLite, одна таблица `alerts`:

| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | Автоинкремент |
| timestamp | DATETIME | Время события (UTC) |
| source_ip | TEXT | IP атакующего |
| destination_ip | TEXT | IP жертвы |
| protocol | TEXT | TCP / UDP |
| prediction | TEXT | INTRUSION / NORMAL |
| model_votes | JSON | `{"isolation_forest":1,"lof":1,"svm":0,"random_forest":1}` |
| attack_confidence | FLOAT | 0.0–1.0 |
| attack_type | TEXT | DDoS / PortScan / DoS Hulk / Bot / ... |
| created_at | DATETIME | Время записи в БД |

`model_votes` хранится как JSON-строка в SQLite и десериализуется при чтении через SQLAlchemy.

---

## Деплой

| Компонент | Платформа | URL |
|---|---|---|
| Frontend | Vercel | https://diplloma.vercel.app |
| Backend | Render | https://diplloma-api.onrender.com |
| API docs | Render | https://diplloma-api.onrender.com/docs |

**Vercel** — автодеплой из ветки `master` при каждом `git push`. Билд: `cd frontend && npm run build`. Переменные среды: `VITE_API_URL=https://diplloma-api.onrender.com`.

**Render** — автодеплой из ветки `master`. Команда запуска: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. Деплой занимает 3–7 минут (установка зависимостей, загрузка .pkl моделей в память).

### Локальный запуск

```bash
# Терминал 1 — бэкенд (от Администратора для Packet Capture)
uvicorn backend.main:app --reload --port 8000

# Терминал 2 — фронтенд
cd frontend && npm run dev

# Открыть: http://localhost:5173
```

При локальном запуске фронтенд читает `frontend/.env.development` → `VITE_API_URL=http://localhost:8000`.
