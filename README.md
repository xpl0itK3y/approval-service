# approval-service

Backend-сервис согласования контента: принимает заявки на согласование
публикаций/сценариев/готовых материалов, фиксирует решение (approve/reject/
cancel) и оставляет след, кто и что изменил. Внешние сущности (публикации,
пользователи, workspace) передаются как идентификаторы — сервис их не
хранит и не валидирует через другие сервисы.

Стек: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL (prod/docker)
или SQLite (быстрый локальный запуск и тесты).

## Запуск через Docker Compose (рекомендуется)

```bash
docker compose up --build
```

Поднимет Postgres и сам сервис на `http://localhost:8000`. Миграции
применяются автоматически при старте контейнера (`docker-entrypoint.sh`
делает `alembic upgrade head` перед запуском uvicorn).

Проверка:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Локальный запуск без Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

export DATABASE_URL="sqlite:///./data/approval.db"
mkdir -p data
alembic upgrade head

uvicorn app.main:app --reload
```

## Тесты

```bash
source .venv/bin/activate
pytest -q
# с покрытием:
pytest --cov=app
```

Тесты используют in-memory SQLite (schema создаётся через
`Base.metadata.create_all`, идентична схеме из миграций) и не требуют
поднятого Postgres.

## Auth-заглушка

Полноценной аутентификации нет — согласно ТЗ используется заглушка. Вызывающая
сторона обязана передать три заголовка, описывающие, от чьего имени и с какими
правами выполняется запрос:

| Заголовок | Назначение |
|---|---|
| `X-Auth-Workspace-Id` | workspace, для которого авторизован вызывающий |
| `X-Auth-User-Id` | id пользователя, выполняющего действие |
| `X-Auth-Actions` | список разрешённых действий через запятую |

Действия: `approval:read`, `approval:create`, `approval:decide`, `approval:cancel`
(таблица соответствия действий и сценариев — как в ТЗ).

Сервис никогда не доверяет `workspace_id` из URL сам по себе: он сверяется с
`X-Auth-Workspace-Id`, и при несовпадении запрос отклоняется с 403 — это и
есть механизм, которым обеспечивается изоляция между workspace на уровне API.
Если запрошенное действие отсутствует в `X-Auth-Actions` — тоже 403. Отсутствие
заголовков `X-Auth-Workspace-Id`/`X-Auth-User-Id` — 401.

В реальном продукте этот слой заменяется на реальную проверку
сессии/токена вышестоящим API-gateway или auth-сервисом; контракт (три
источника правды: workspace, user, actions) остаётся тем же.

### Пример запроса

```bash
curl -X POST http://localhost:8000/api/v1/workspaces/ws_1/approval-requests \
  -H "Content-Type: application/json" \
  -H "X-Auth-Workspace-Id: ws_1" \
  -H "X-Auth-User-Id: usr_admin" \
  -H "X-Auth-Actions: approval:read,approval:create,approval:decide,approval:cancel" \
  -H "Idempotency-Key: 3f0b6e8e-2f38-4c9a-9a3a-111111111111" \
  -d '{
    "sourceType": "publication",
    "sourceId": "pub_123",
    "title": "Instagram reel draft",
    "description": "Needs final approval",
    "reviewerUserIds": ["usr_1", "usr_2"]
  }'
```

## HTTP API

```
GET   /health
GET   /ready

POST  /api/v1/workspaces/{workspace_id}/approval-requests
GET   /api/v1/workspaces/{workspace_id}/approval-requests
GET   /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}
GET   /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/audit-log   (бонус, см. DESIGN.md)
POST  /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/approve
POST  /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/reject
POST  /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/cancel
```

`GET .../approval-requests` поддерживает `?status=pending|approved|rejected|cancelled`,
`?limit=` (по умолчанию 20, максимум 100) и `?offset=`.

Все mutating-запросы (create/approve/reject/cancel) поддерживают опциональный
заголовок `Idempotency-Key` — подробности в `DESIGN.md`.

Автоматическая документация (Swagger UI): `http://localhost:8000/docs`.

## Демонстрация outbox → события

```bash
source .venv/bin/activate
export DATABASE_URL="sqlite:///./data/approval.db"
python -m scripts.relay_outbox --once
```

Печатает в stdout ещё не опубликованные события и помечает их
опубликованными. См. `DESIGN.md`, раздел "События/интеграции".

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/approval.db` | строка подключения SQLAlchemy (Postgres в docker-compose) |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `APP_ENV` | `local` | метка окружения |

См. `.env.example`.
