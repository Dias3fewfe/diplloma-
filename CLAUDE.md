# Network Intrusion Detection System — Diploma Project

## Project Goal
Working web dashboard that detects network intrusions using an ensemble of 
3 outlier detection algorithms: Isolation Forest, Local Outlier Factor, One-Class SVM.
Ensemble uses majority voting. Dataset: CICIDS2017.

## Stack
- Backend: Python 3.11, FastAPI, scikit-learn, pandas, numpy, joblib
- Frontend: React 18, Recharts, TailwindCSS
- DB: SQLite via SQLAlchemy
- Dataset: CICIDS2017 (CSV files in /data/raw/)

## Project Structure
project/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── models/              # ML model files (.pkl)
│   ├── pipeline/
│   │   ├── preprocess.py    # Data cleaning & feature engineering
│   │   ├── train.py         # Train 4 ensemble models (IF/LOF/SVM/RF binary)
│   │   ├── train_classifier.py  # Train multiclass attack-type classifier
│   │   └── predict.py       # Inference logic
│   ├── api/
│   │   ├── routes.py        # All API endpoints
│   │   └── schemas.py       # Pydantic models
│   └── db/
│       └── database.py      # SQLite setup, alerts table
├── frontend/
│   ├── src/
│   │   ├── components/      # Dashboard, AlertTable, Charts
│   │   └── App.jsx
├── data/
│   └── raw/                 # Put CICIDS2017 CSV files here
├── notebooks/               # Exploration only, not production
└── CLAUDE.md

## Key Business Logic
1. Input: network traffic features (44 columns from CICIDS2017)
2. Each model votes: 1 = anomaly, 0 = normal
3. Ensemble: if 2 or 3 models vote anomaly → flag as intrusion
4. Alert saved to SQLite with timestamp, severity, attack type
5. Dashboard shows: live alerts, detection rate, model agreement chart

## Conventions
- All ML code in backend/pipeline/
- Never hardcode file paths — use config.py
- Every function must have a docstring
- API responses always return JSON with {status, data, error}
- Keep frontend components small, max 150 lines per file

## Current Status — Updated 02.06.2026 (5)

### Completed ✅
- [x] Project structure created (backend/ frontend/ data/)
- [x] Dataset: CICIDS2017 from Kaggle (~170MB, single CSV, 2.2M rows)
- [x] backend/pipeline/preprocess.py — cleans data, saves cleaned.csv + scaler.pkl
- [x] backend/pipeline/train.py — trains IF (200k rows), LOF (50k), SVM (30k), saves .pkl files
- [x] backend/pipeline/evaluate.py — ensemble majority vote, F1=0.534
- [x] backend/pipeline/predict.py — inference logic with lru_cache
- [x] backend/db/database.py — SQLite, alerts table
- [x] backend/api/schemas.py — Pydantic models
- [x] backend/api/routes.py — /predict /simulate /alerts /stats /health
- [x] backend/main.py — FastAPI + CORS
- [x] frontend — React + Vite + Recharts + Tailwind
- [x] All 5 tabs working: Overview, Live Detection, Packet Capture, Alerts, Models
- [x] UI redesigned: professional dark theme, no emojis, Grafana-style
- [x] backend/pipeline/capture.py — live packet capture via scapy
      - FlowRecord dataclass: накапливает fwd/bwd статистику пакетов
      - extract_features(): вычисляет ~78 CICIDS2017-совместимых фич из реальных пакетов
      - FlowCapture: фоновый снифер, группирует пакеты в 5-tuple потоки,
        завершает поток по TCP FIN/RST или таймауту (30 сек), вызывает predict_single()
- [x] backend/api/capture_routes.py — REST + WebSocket для живого захвата
      - POST /api/capture/start — запуск захвата на интерфейсе
      - POST /api/capture/stop — остановка
      - GET  /api/capture/status — счётчики (packets_seen, flows_finalized, intrusions)
      - GET  /api/capture/interfaces — список NIC
      - WS   /api/ws/live — стрим результатов в браузер
- [x] frontend/src/components/LiveCapturePanel.jsx — таб "Packet Capture"
      - Dropdown выбора сетевого интерфейса
      - Start/Stop захвата, WebSocket-статус индикатор
      - Живая таблица потоков: IP, порт, протокол, байты, предикшн, голоса IF/LOF/SVM
- [x] requirements.txt — добавлен scapy
- [x] backend/pipeline/train.py — добавлен 4-й supervised Random Forest (150k строк, stratified по всем классам)
      - train_random_forest(): загружает cleaned.csv, пропорциональная стратифицированная выборка,
        бинарные метки (0=BENIGN, 1=attack), class_weight='balanced'
      - run_training() теперь обучает и сохраняет 4 модели
- [x] backend/pipeline/predict.py — RF интегрирован в ансамбль как 4-й голос
      - _load_models(): RF загружается опционально (если random_forest.pkl существует)
      - _run_ensemble(): hasattr(model, 'classes_') определяет supervised vs outlier детектор
      - attack_confidence теперь делится на n_models динамически (3 или 4)
- [x] backend/pipeline/evaluate.py — RF учитывается в отчёте оценки
- [x] frontend: ModelsPanel, LiveDetection, App обновлены для 4 моделей
      - ModelsPanel: 4-колоночная сетка, бейджи SUPERVISED/UNSUPERVISED
      - LiveDetection: колонка RF, динамический счёт голосов
      - App: заголовок обновлён "IF + LOF + OC-SVM + RF"
- [x] Классификация типа атаки (multiclass):
      - backend/pipeline/train_classifier.py — RF(200 деревьев), multiclass по Label,
        stratified 150k строк, сохраняет attack_classifier.pkl
      - backend/pipeline/predict.py — classify_attack_type(raw_features) и classify_attack_type_batch(X)
        опциональная загрузка (_load_attack_classifier с lru_cache), fallback="Unknown"
      - backend/api/schemas.py — attack_type добавлен в PredictResponse, SimulateRow, AlertOut;
        attack_type_breakdown в StatsResponse; ModelVotes расширен random_forest
      - backend/db/database.py — колонка attack_type в Alert; init_db() делает ALTER TABLE миграцию
      - backend/api/routes.py — /predict и /simulate вызывают classify_attack_type[_batch],
        сохраняют attack_type в БД; /stats возвращает attack_type_breakdown (GROUP BY)
      - frontend/AlertsTable.jsx — колонка "Attack Type" с цветными бейджами AttackBadge
        (DDoS=красный, PortScan=жёлтый, BruteForce=оранжевый, Bot=фиолетовый, и др.)
      - frontend/Overview.jsx — BarChart топ-5 типов атак из /api/stats
- [x] Telegram уведомления при обнаружении атаки:
      - backend/notifications.py — класс TelegramNotifier
          is_configured(): bool, send_alert(alert_data) async через httpx
          Формат Markdown: тип атаки, уверенность, IP, протокол, голоса моделей, время
          Отправляет только если confidence >= NOTIFY_CONFIDENCE_THRESHOLD (0.75)
          При ошибке сети — logging.warning, никогда не кидает исключение
      - backend/config.py — load_dotenv(), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
        NOTIFY_CONFIDENCE_THRESHOLD = 0.75
      - backend/main.py — TelegramNotifier инициализируется при старте,
        хранится в app.state.notifier, передаётся в capture_routes через set_notifier()
      - backend/api/routes.py — /predict и /simulate используют BackgroundTasks
        для отправки уведомлений (не блокируют API ответ);
        новый GET /api/notification-status → {"telegram_configured": bool}
      - backend/api/capture_routes.py — set_notifier(), уведомление в _on_flow_complete
        через asyncio.run_coroutine_threadsafe из фонового потока
      - frontend/Overview.jsx — индикатор статуса Telegram (зелёная/серая точка)
      - requirements.txt — добавлены httpx, python-dotenv
      - .env — создан с токеном и chat_id (в .gitignore, не коммитить)
      - .env.example — шаблон без реальных значений

### How to Run
Terminal 1 (backend — требует прав администратора для захвата пакетов):
uvicorn backend.main:app --reload --port 8000

Terminal 2 (frontend):
cd frontend && npm run dev

Dashboard: http://localhost:5173
API docs: http://localhost:8000/docs

### Live Packet Capture — требования
- pip install scapy
- Windows: установить Npcap с https://npcap.com/
- Запускать бэкенд от имени Администратора (Windows) или sudo (Linux)

### Telegram — настройка
1. Создать .env в корне проекта (уже создан)
2. pip install httpx python-dotenv (или pip install -r requirements.txt)
3. Перезапустить uvicorn — в консоли появится "Telegram notifier: configured"

- [x] Страница входа redesigned: animated network graph canvas (65 узлов, синие рёбра, красные вспышки атак с рябью, летящие пакеты), split-screen layout (брендинг слева, форма справа с backdrop-blur), count-up анимация счётчиков, теги моделей
      - frontend/src/components/LoginPage.jsx — NetworkCanvas (canvas 65 nodes, ripple, packets), CountUp, split layout
- [x] Attack Scenario Simulation — реальные паттерны атак из CICIDS2017 через ML ансамбль:
      - backend/api/routes.py — POST /api/simulate/attack/{attack_type}: фильтрует датасет по Label, 25 строк, predict_batch_scaled, реальные IP атакующих (_SCENARIO_IPS dict), сохраняет в БД
      - frontend/src/components/LiveDetection.jsx — 5 кнопок сценариев (PortScan/DDoS/DoS Hulk/Bot/DoS GoldenEye), построчная анимация 120мс, прогресс-бар, баннер INTRUSIONS DETECTED, цветовая схема по типу атаки

### Remaining
- [x] Запустить train.py → random_forest.pkl обучен (10MB)
- [x] Запустить train_classifier.py → attack_classifier.pkl обучен (40MB)
- [x] Запустить evaluate.py — F1=0.784 (INTRUSION), macro avg F1=0.862, accuracy=90.6%
- [x] Авторизация (JWT):
      - backend/api/auth_routes.py — POST /api/auth/login, GET /api/auth/verify
        JWT HS256, 24ч срок, credentials из .env (ADMIN_USERNAME / ADMIN_PASSWORD)
        Defaults: admin / admin123
      - backend/config.py — SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, ACCESS_TOKEN_EXPIRE_HOURS
      - backend/main.py — подключён router_auth
      - frontend/src/components/LoginPage.jsx — форма входа, тёмная тема
      - frontend/src/App.jsx — проверка токена при загрузке, имя пользователя + кнопка Logout в хедере
      - requirements.txt — добавлен python-jose[cryptography]
- [x] Экспорт алертов в PDF/CSV:
      - backend/api/routes.py — GET /api/alerts/export/csv и /api/alerts/export/pdf
        CSV: все поля + голоса IF/LOF/SVM/RF, filename с timestamp
        PDF: таблица A4 landscape через fpdf2, тёмная тема, автопагинация
      - frontend/AlertsTable.jsx — кнопки "Export CSV" (зелёная) и "Export PDF" (синяя)
      - requirements.txt — добавлен fpdf2
- [x] README.md для диплома — архитектура, метрики, API, инструкция запуска
- [x] docs/ папка с документацией на русском:
      - architecture.md — архитектура, поток данных, схема БД, безопасность
      - models.md — теория ML, 4 модели, гиперпараметры, результаты оценки
      - api.md — полная документация API с примерами запросов/ответов
      - user_guide.md — руководство пользователя по всем 5 вкладкам
      - deployment.md — локальный запуск, Render + Vercel деплой