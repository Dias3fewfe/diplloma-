# Развёртывание системы

## Архитектура развёртывания

```
GitHub (исходный код)
       │
       ├──► Vercel (frontend)
       │         React SPA → статические файлы → CDN
       │
       └──► Render (backend)
                 FastAPI → uvicorn → Python 3.11
                 SQLite файл на диске
```

Оба сервиса подключены к GitHub-репозиторию и **автоматически деплоятся** при каждом push в ветку `master`.

---

## Локальный запуск

### Требования

- Python 3.11+
- Node.js 18+
- pip
- Windows: [Npcap](https://npcap.com/) для live capture

### Шаг 1 — Клонировать репозиторий

```bash
git clone https://github.com/Dias3fewfe/diplloma-.git
cd diplloma-
```

### Шаг 2 — Python зависимости

```bash
pip install -r requirements.txt
```

### Шаг 3 — Переменные окружения

```bash
cp .env.example .env
```

Содержимое `.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHAT_ID=ваш_chat_id
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=ваш-случайный-секретный-ключ
```

### Шаг 4 — Подготовка данных

```
data/
└── raw/
    └── CICIDS2017.csv   ← положить сюда датасет
```

```bash
python -m backend.pipeline.preprocess      # создаёт cleaned.csv + scaler.pkl
python -m backend.pipeline.train           # обучает 4 модели
python -m backend.pipeline.train_classifier  # обучает классификатор типов атак
python -m backend.pipeline.evaluate       # проверка качества
```

### Шаг 5 — Запуск бэкенда

```bash
# Обычный запуск
uvicorn backend.main:app --reload --port 8000

# С правами администратора (для live capture на Windows)
# Запустить PowerShell/CMD от имени администратора, затем:
uvicorn backend.main:app --reload --port 8000
```

### Шаг 6 — Запуск фронтенда

```bash
cd frontend
npm install
npm run dev
```

### Шаг 7 — Проверка

| Сервис | URL |
|---|---|
| Дашборд | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

---

## Деплой на Render (бэкенд)

### Первоначальная настройка

1. Зарегистрироваться на [render.com](https://render.com)
2. New → **Web Service**
3. Подключить GitHub-репозиторий
4. Настройки:

| Параметр | Значение |
|---|---|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Free |

5. Переменные окружения (Environment):

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен бота |
| `TELEGRAM_CHAT_ID` | chat id |
| `ADMIN_USERNAME` | admin |
| `ADMIN_PASSWORD` | admin123 |
| `SECRET_KEY` | случайная строка |

6. **Deploy**

### Особенности Render Free tier

- Сервис засыпает после 15 минут неактивности
- Первый запрос после сна занимает ~30 секунд (cold start)
- Диск сбрасывается при каждом деплое (SQLite-данные теряются)
- Модели `.pkl` должны быть закоммичены в репозиторий

### Решение с SQLite

Так как Render не сохраняет файлы между деплоями, алерты хранятся только в рамках текущей сессии. Для persistence можно использовать Render PostgreSQL (платная функция) с заменой `DATABASE_URL` в `config.py`.

### Автодеплой

При каждом `git push origin master` Render автоматически:
1. Устанавливает зависимости (`pip install -r requirements.txt`)
2. Перезапускает сервис

---

## Деплой на Vercel (фронтенд)

### Первоначальная настройка

1. Зарегистрироваться на [vercel.com](https://vercel.com)
2. New Project → Import GitHub-репозиторий
3. Настройки:

| Параметр | Значение |
|---|---|
| **Framework Preset** | Vite |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |

4. Переменные окружения:

| Key | Value |
|---|---|
| `VITE_API_URL` | `https://diplloma-api.onrender.com` |

5. **Deploy**

### Production vs Preview

- **Production** деплой — при push в `master`
- **Preview** деплой — при создании Pull Request (отдельный URL)

### Автодеплой

Vercel автоматически деплоит при каждом push в `master`. Деплой занимает ~1 минуту.

---

## Конфигурационные файлы

### frontend/.env.development

```env
VITE_API_URL=http://localhost:8000
```

Используется при `npm run dev` локально.

### frontend/.env.production

```env
VITE_API_URL=https://diplloma-api.onrender.com
```

Используется при `npm run build` (Vercel берёт этот файл).

### .env.example

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=change-this-to-a-random-string
```

---

## CORS настройка

В `backend/main.py` перечислены разрешённые origins:

```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "https://diplloma.vercel.app",
]
```

При изменении URL Vercel — добавить новый origin в этот список.

---

## Обновление деплоя

```bash
# Внести изменения в код
git add .
git commit -m "описание изменений"
git push origin master
```

Vercel и Render подхватят изменения автоматически через 1-2 минуты.

---

## Мониторинг

| Сервис | Логи |
|---|---|
| Render | Dashboard → сервис → **Logs** |
| Vercel | Dashboard → деплой → **Functions** |

Ключевые сообщения в логах Render при старте:
```
Database initialised.
Telegram notifier: configured
```
