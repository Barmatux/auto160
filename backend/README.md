# Auto160 Backend (FastAPI)

Первая итерация backend для каталога автомобилей:
- REST API для auth и объявлений
- HTML-заглушки на Jinja (`/`, `/catalog`, `/login`, `/register`, `/create-listing`)
- PostgreSQL через `DATABASE_URL` (или SQLite по умолчанию для быстрого локального старта)
- Alembic миграции для схемы БД
- Отдельная таблица `catalog_items` для импортируемого CSV-каталога

## Быстрый запуск

1. Создать и активировать venv:
   - `python -m venv .venv`
   - `.venv\\Scripts\\activate`
2. Установить зависимости:
   - `pip install -r requirements.txt`
3. (Опционально) поднять Postgres:
   - `docker compose up -d`
4. Создать `.env` по примеру `.env.example` (если используешь Postgres).
5. Применить миграции:
   - `alembic upgrade head`
6. Запустить приложение:
   - `uvicorn app.main:app --reload`

## Запуск в Docker Compose

1. Перейти в папку backend:
   - `cd D:\Users\tsyga\auto160\backend`
2. Собрать и запустить сервисы:
   - `docker compose up --build -d`
3. Проверить:
   - API: `http://localhost:8000/health`
   - Swagger: `http://localhost:8000/docs`
   - MinIO API: `http://localhost:9000`
   - MinIO Console: `http://localhost:9001`
4. Остановить:
   - `docker compose down`

Примечание: при старте контейнера `api` автоматически выполняется `alembic upgrade head`, затем запускается `uvicorn`.

## Упрощенный деплой на 1 VM (Yandex Cloud)

Ниже вариант "как есть" для теста: `api + postgres + minio` на одной виртуальной машине.

1. Создать VM в Yandex Cloud (Ubuntu 22.04/24.04, минимум 2 vCPU / 4 GB RAM / 30 GB disk).
2. Открыть в Security Group:
   - `22/tcp` (только с вашего IP),
   - `80/tcp` и `443/tcp` (публично),
   - при необходимости `8000/tcp` временно для прямой проверки API.
3. Подключиться к VM по SSH и установить Docker:
   - `curl -fsSL https://get.docker.com | sh`
   - `sudo usermod -aG docker $USER`
   - переподключиться по SSH.
4. Клонировать проект и перейти в `backend`.
5. Создать env-файл для VM:
   - `cp .env.vm.example .env.vm`
   - обязательно поменять `POSTGRES_PASSWORD`, `SECRET_KEY`, `BOOTSTRAP_ADMIN_PASSWORD`, `MINIO_ROOT_PASSWORD`.
   - важно: `DATABASE_URL` должен использовать тот же пароль, что и `POSTGRES_PASSWORD`.
6. Запустить контейнеры:
   - `docker compose -f docker-compose.vm.yml up --build -d`
7. Проверка:
   - `docker compose -f docker-compose.vm.yml ps`
   - `docker compose -f docker-compose.vm.yml logs -f api`
   - локально на VM: `curl http://127.0.0.1:8000/health`
8. Публикация наружу:
   - быстрый вариант: открыть `8000/tcp` и использовать `http://<VM_IP>:8000`.
   - рекомендуемый вариант: поставить Nginx и проксировать `80/443 -> 127.0.0.1:8000`.

Примечания:
- В `docker-compose.vm.yml` порты `api` и `minio` привязаны к `127.0.0.1`, чтобы не торчали в интернет напрямую.
- Данные PostgreSQL и MinIO сохраняются в docker volumes (`pgdata`, `minio_data`).
- Для обновления приложения:
  - `git pull`
  - `docker compose -f docker-compose.vm.yml up --build -d`
- Для остановки:
  - `docker compose -f docker-compose.vm.yml down`

## Основные URL

- `GET /health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/listings`
- `POST /api/v1/listings` (admin only)
- `PATCH /api/v1/listings/{id}` (admin only)
- `DELETE /api/v1/listings/{id}` (admin only)
- `POST /api/v1/catalog/{id}/photos/presign` (admin only)
- `POST /api/v1/catalog/{id}/photos/confirm` (admin only)
- `GET /api/v1/catalog/{id}/photos`
- `DELETE /api/v1/catalog/photos/{photo_id}` (admin only)
- `PATCH /api/v1/catalog/photos/{photo_id}/cover` (admin only)
- `GET /api/v1/admin/users` (admin only)
- `PATCH /api/v1/admin/users/{id}/role` (admin only)
- `GET /` (шаблонная главная)
- `GET /catalog`
- `GET /profile/my-listings` (admin UI)
- `GET /admin/catalog/{id}/photos` (admin UI фото)
- `GET /admin/users` (admin UI)

## Примечания по auth

- Вход выполняется по `login + password`.
- Регистрация выполняется по email, логин генерируется автоматически.
- `login` возвращает пару `access_token` + `refresh_token`.
- `refresh` выдает новую пару токенов.
- `logout` в текущей версии делает revoke токена в памяти процесса (для MVP; для production нужен Redis/БД).
- Публичная регистрация не позволяет создать пользователя с ролью `admin`.
- Доступ к объявлениям разделен:
  - `guest`: только `published` (только просмотр)
  - `seller`: только `published` (только просмотр)
  - `admin`: полный доступ
- Все операции изменения каталога (`create/update/delete`) доступны только `admin`.

## UI (шаблоны)

- После логина/регистрации токены сохраняются в cookie.
- Каталог отображает данные из `catalog_items` (CSV), поддерживает фильтры, сортировку и пагинацию.
- Админка пользователей поддерживает смену роли прямо из UI.
- Управление объявлениями доступно только в админских страницах.

## Импорт CSV каталога

- CSV-файл включен в проект: `app/data/catalog_u160_audi_bmw_mini.csv`
- При старте приложения (после миграций) данные автоматически загружаются в `catalog_items`, если таблица пустая.
- Путь можно переопределить через `CATALOG_SEED_CSV_PATH`.

## Фото в MinIO

- Фото хранятся в MinIO bucket `auto160-media`.
- Backend выдает pre-signed URL для загрузки (`presign`), затем запись подтверждается (`confirm`).
- Каталог и карточка позиции показывают фото через pre-signed URL чтения.
- Базовый доступ к MinIO console:
  - login: `minioadmin`
  - password: `minioadmin`

### Массовое заполнение фото из AV.BY в MinIO/S3

Если в `raw_specs.modification_detail.photos` уже есть URL фото после парсинга, можно массово загрузить обложки в хранилище:

- Локально:
  - `python tools/sync_catalog_photos.py`
- В Docker:
  - `docker compose exec api python tools/sync_catalog_photos.py`
- На VM:
  - `docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api python tools/sync_catalog_photos.py`

Полезные флаги:
- `--limit 200` — обработать только часть карточек.
- `--force` — перезаписать/добавить даже если фото уже есть.
- `--make BMW --model X1 --generation U11` — точечный запуск по фильтрам.
- `--dry-run` — проверить, что будет сделано, без загрузки файлов.

## Импорт с AV.BY

- Добавлена гибридная схема для `catalog_items`:
  - структурированные поля для фильтров (`make`, `model`, `generation`, `year_from`, ...)
  - плюс `raw_specs` (JSON) для "всех параметров" как на источнике.
- Источник и связь с AV.BY сохраняются в:
  - `source_site`
  - `source_url`
  - `source_external_id`
- Импортер: `tools/import_avby.py`
- Запуск:
  - `python tools/import_avby.py --urls-file .\\avby_urls.txt`
- Формат `avby_urls.txt`: один URL AV.BY на строку.
- Можно указывать как URL модели (`/catalog/bmw_x1`), так и URL поколения (`/catalog/bmw_x1_u11-2022-`).
- Для URL модели скрипт сам раскроет поколения и импортирует их модификации.

## Предсозданный админ

- При старте приложения автоматически создается админ, если его еще нет.
- По умолчанию:
  - login: `admin`
  - email: `admin@auto160.com`
  - password: `admin12345`
  - role: `admin`
- Изменить можно через переменные:
  - `BOOTSTRAP_ADMIN_EMAIL`
  - `BOOTSTRAP_ADMIN_LOGIN`
  - `BOOTSTRAP_ADMIN_NAME`
  - `BOOTSTRAP_ADMIN_PASSWORD`

## Что дальше

- Добавить seed-скрипты и фикстуры для тестовых данных
- Подключить загрузку фото (S3-compatible)
- Добавить тесты (`pytest`)
