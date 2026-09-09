# Quiz Test

Full-stack приложение для создания тестов и прохождения квизов. Backend предоставляет REST API для пользователей, тестов, вопросов, попыток и ответов; frontend подготовлен на React и находится в разработке.

![Quiz Test — макет интерфейса](./quiz_picture.png)

## Возможности

- управление пользователями;
- создание и редактирование тестов;
- добавление вопросов и правильных ответов;
- сохранение попыток прохождения теста;
- сохранение ответа пользователя и результата проверки;
- интерактивная документация API через Swagger UI и ReDoc;
- регистрация и вход через PostgreSQL, Argon2 и RSA JWT;
- обновление токенов с ротацией refresh-сессий в БД и выход.

> [!NOTE]
> Проект находится в разработке. Регистрация, JWT и refresh-сессии подключены к PostgreSQL. Проверка владельцев тестов и попыток ещё не реализована; интерфейс пока содержит заготовку React/Vite.

Инструкция по регистрации, входу, refresh, выходу и Swagger: [Авторизация](backend/api_v1/auth/README.md).

## Стек

**Backend:** Python 3.14, FastAPI, SQLAlchemy 2, asyncpg, PostgreSQL 16, Alembic, Pydantic Settings, PyJWT.

**Frontend:** React 19, TypeScript, Vite 8, ESLint.

**Инфраструктура:** Docker Compose, uv, npm.

## Структура проекта

```text
.
├── backend/
│   ├── api_v1/          # роутеры, схемы, зависимости и CRUD-операции
│   ├── core/            # конфигурация, подключение к БД и ORM-модели
│   ├── alembic/         # миграции базы данных
│   ├── compose.yaml     # PostgreSQL для локальной разработки
│   ├── main.py          # точка входа FastAPI
│   └── pyproject.toml   # Python-зависимости
├── src/
│   ├── src/             # исходный код React-приложения
│   └── package.json     # frontend-зависимости и команды
├── quiz_picture.png     # макет интерфейса
└── README.md
```

## Быстрый старт

### Требования

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- Docker с поддержкой Compose

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd Quiz_test43
```

### 2. Настройка backend

Перейдите в каталог backend и создайте файл `.env`:

```bash
cd backend
```

Содержимое `.env`:

```dotenv
POSTGRES_USER=quiz
POSTGRES_PASSWORD=quiz_password
POSTGRES_DB=quiz_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Установите зависимости, запустите PostgreSQL и примените миграции:

```bash
uv sync
docker compose up -d db
uv run alembic upgrade head
```

Запустите API в режиме разработки:

```bash
uv run fastapi dev main.py
```

После запуска доступны:

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 3. Запуск frontend

В отдельном терминале из корня репозитория:

```bash
cd src
npm install
npm run dev
```

Frontend будет доступен по адресу [http://localhost:5173](http://localhost:5173).

## API

Основной префикс API — `/api/v1`.

| Ресурс | Endpoint | Операции |
| --- | --- | --- |
| Пользователи | `/api/v1/users/me`, `/api/v1/users/{id}` | получение собственного профиля |
| Тесты | `/api/v1/tests/` | список, создание, получение, изменение, удаление |
| Вопросы | `/api/v1/questions/` | список, создание, получение, изменение, удаление |
| Попытки | `/api/v1/attempts/` | список, создание, получение, изменение, удаление |
| Ответы в попытках | `/api/v1/attempt-answers/` | список, создание, получение, изменение, удаление |
| Auth | `/api/v1/auth/` | register, login, refresh, logout |

Актуальные форматы запросов и ответов удобнее смотреть в Swagger UI: FastAPI формирует документацию непосредственно из схем приложения.

Пример регистрации:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email": "user@example.com", "password": "A-long-personal-password"}'
```

Для входа `/api/v1/auth/login` принимает form-поля `username` (email) и `password`.
Перед запуском API настройте RSA-ключи по [инструкции авторизации](backend/api_v1/auth/README.md).

## Модель данных

```text
User ──< Test ──< Question
  │         │
  └──< Attempt >── Test
          │
          └──< AttemptAnswer >── Question
```

- пользователь может создать несколько тестов и совершить несколько попыток;
- тест содержит вопросы;
- попытка связывает пользователя с тестом и хранит время начала и завершения;
- ответ попытки связывает попытку с вопросом, хранит введённый ответ и признак корректности;
- в рамках одной попытки для каждого вопроса может существовать только один ответ.

## Полезные команды

Backend — выполнять из `backend/`:

```bash
uv run alembic upgrade head   # применить все миграции
uv run alembic downgrade -1   # откатить последнюю миграцию
uv run fastapi dev main.py    # запустить API с автоперезагрузкой
docker compose down           # остановить PostgreSQL
```

Frontend — выполнять из `src/`:

```bash
npm run dev       # сервер разработки
npm run build     # production-сборка
npm run lint      # проверка ESLint
npm run preview   # просмотр production-сборки
```

## Статус разработки

- [x] ORM-модели и связи
- [x] миграции Alembic
- [x] асинхронный CRUD API
- [x] OpenAPI-документация
- [x] регистрация, Argon2, JWT, refresh-сессии и выход
- [ ] проверка владельца тестов, вопросов и попыток
- [ ] подключение frontend к API
- [ ] интерфейс создания и прохождения тестов
- [x] интеграционные тесты регистрации и токенов на PostgreSQL
- [ ] тесты бизнес-логики прохождения
- [ ] production-конфигурация и деплой

## Лицензия

Лицензия пока не указана. Перед публичным распространением проекта добавьте файл `LICENSE`.
