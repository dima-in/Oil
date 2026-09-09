# OilPress - Магазин масел

Веб-приложение для управления производством и заказами масел: каталог, заказы,
прайс-лист, аналитика и **AI-ассистент по базе на естественном языке**.
Чистая профессиональная тема с переключателем светлая/тёмная (индиго-акцент,
выбор запоминается, тема первого визита — по настройке ОС).

## Быстрый старт

### 1. Запуск backend (Docker)

```bash
docker compose up -d
```

Backend доступен на http://localhost:8000

### 2. Запуск frontend (локальная разработка)

```bash
cd frontend
npm install
npm run dev
```

Frontend доступен на http://localhost:5173

## Структура проекта

```
Oil/
├── frontend/          # React + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/
│   │   │   ├── Catalog.jsx       # Каталог товаров
│   │   │   ├── OrdersView.jsx    # Просмотр заказов
│   │   │   ├── AdminPanel.jsx    # Админ-панель
│   │   │   ├── PricelistManager.jsx  # Управление ценами
│   │   │   └── UploadPricelist.jsx   # Загрузка прайс-листа
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── main.py            # FastAPI backend
├── Database.py        # Работа с БД
├── docker-compose.yml # Docker конфигурация
└── README.md
```

## API Endpoints

### Catalog
- `GET /api/catalog` - Получить каталог товаров

### Orders
- `GET /api/orders` - Получить все заказы
- `POST /api/order` - Создать заказ
- `DELETE /api/order/{id}` - Удалить заказ

### Admin: Pricelist
- `GET /api/admin/pricelist` - Получить прайс-лист
- `POST /api/admin/pricelist` - Добавить товар
- `PUT /api/admin/pricelist/{id}` - Обновить цену
- `DELETE /api/admin/pricelist/{id}` - Удалить товар
- `POST /api/admin/pricelist/clear` - Очистить прайс-лист
- `POST /api/admin/upload-pricelist` - Загрузить PDF/CSV

### AI-ассистент (text-to-SQL)
- `POST /api/analytics/assistant` - вопрос на естественном языке → ответ по базе.
  Требует админ-авторизацию. Пайплайн: вопрос → LLM генерирует **только `SELECT`**
  (валидатор блокирует любые изменяющие/опасные конструкции: INSERT/UPDATE/DELETE/
  DDL/GRANT/CALL/LOAD, `INTO OUTFILE`, `FOR UPDATE`, ...) → безопасное выполнение
  (read-only, до 50 строк) → второй вызов LLM формулирует ответ.
  Тело: `{ "question": "..." }` → `{ "answer", "sql", "rows_count" }`.
  Ассистент «видит» всю схему (9 таблиц + связи по FOREIGN KEY).

### Admin: Analytics
- `GET /api/admin/analytics` - сводная аналитика
- `GET /api/analytics/customers` - аналитика по клиентам
- `GET /api/analytics/products` - аналитика по товарам
- `GET /api/analytics/summary` - сводка

### Admin: Expenses & Production
- `GET|POST /api/admin/expenses`, `DELETE /api/admin/expenses/{id}` - расходы
- `GET|POST /api/admin/production-profiles`, `DELETE /api/admin/production-profiles/{id}`
  - профили производства (выход масла, размер закладки, дневной лимит)
- `GET|POST /api/admin/production-batches`, `DELETE /api/admin/production-batches/{id}` - закладки

## Переменные окружения

| Переменная | Назначение |
| --- | --- |
| `OPENROUTER_API_KEY` | Ключ шлюза LLM (novpnai) для AI-ассистента. Без него `/api/analytics/assistant` вернёт ошибку. |

## Учётные данные

**Логин:** `oilpress`  
**Пароль:** `MarshallJCM800`

## Технологии

**Frontend:**
- React 19
- Vite 8
- Tailwind CSS 4
- React Router 7

**Backend:**
- FastAPI
- MySQL 8.0
- Uvicorn

**DevOps:**
- Docker & Docker Compose

## Развёртывание на Yandex Cloud

### 1. Создать ВМ (Compute Cloud)

```bash
# Минимальная конфигурация: 2 vCPU, 2GB RAM
yc compute instance create \
  --name oilpress \
  --zone ru-central1-a \
  --platform standard-v3 \
  --cores 2 --memory 2 \
  --image-folder id=standard-images \
  --image-name ubuntu-2204-lts \
  --public-ip \
  --metadata user-data-from-file=cloud-init.yaml
```

### 2. Подключиться и установить Docker

```bash
ssh ubuntu@<VM_IP>

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt update && sudo apt install docker-compose-plugin
```

### 3. Развернуть приложение

```bash
# Клонировать репозиторий
git clone https://github.com/dima-in/Oil.git
cd Oil

# Собрать frontend
cd frontend
npm install
npm run build
cd ..

# Скопировать статику
cp -r frontend/dist/* static/

# Запустить Docker
docker compose up -d
```

## Лицензия

MIT
