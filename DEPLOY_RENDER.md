# Деплой на Render.com

## Шаг 1: Подготовка репозитория

Убедись что все изменения закоммичены и запушены на GitHub:

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin master
```

## Шаг 2: Создание сервиса на Render

1. Зайди на https://render.com и войди через GitHub
2. Нажми **New** → **Web Service**
3. Подключи свой GitHub репозиторий
4. Заполни настройки:

| Параметр | Значение |
|----------|----------|
| **Name** | `odoo-ai-agent` (или любое) |
| **Region** | Выбери ближайший |
| **Branch** | `master` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `chainlit run src/ui/chainlit_app.py --host 0.0.0.0 --port $PORT` |

## Шаг 3: Environment Variables

В разделе **Environment** добавь переменные:

### Обязательные:

| Variable | Value | Описание |
|----------|-------|----------|
| `CHAINLIT_AUTH_SECRET` | *(сгенерируй)* | JWT секрет для сессий |
| `CHAINLIT_AUTH_USER` | `admin` | Логин админа |
| `CHAINLIT_AUTH_PASSWORD` | *(твой пароль)* | Пароль админа |
| `PYTHON_VERSION` | `3.11.9` | Версия Python |

### Генерация CHAINLIT_AUTH_SECRET:

Локально выполни:
```bash
source venv/bin/activate
chainlit create-secret
```

Скопируй полученный секрет в Render.

## Шаг 4: Disk (опционально)

Для сохранения истории чатов между деплоями:

1. В настройках сервиса → **Disks**
2. **Add Disk**:
   - **Name**: `data`
   - **Mount Path**: `/app/logs`
   - **Size**: `1 GB`

## Шаг 5: Deploy

1. Нажми **Create Web Service**
2. Дождись окончания билда (5-10 минут)
3. Открой URL твоего сервиса

## Использование

### Вход:
- **Username**: `admin` (или значение CHAINLIT_AUTH_USER)
- **Password**: твой пароль из CHAINLIT_AUTH_PASSWORD

### Регистрация нового пользователя:
- **Username**: `new:username` (префикс `new:`)
- **Password**: желаемый пароль

После регистрации входи просто по `username` без префикса.

### После входа:
Заполни поля подключения:
- **OPENAI_API_KEY**: твой OpenAI API ключ
- **ODOO_URL**: `https://woodenfish-dev.run-odoo.com`
- **ODOO_DB**: `wfv_hrms`
- **ODOO_USERNAME**: `api_external_wfv`
- **ODOO_PASSWORD**: токен Odoo API

## Troubleshooting

### Ошибка "No module found"
Проверь что все зависимости в `requirements.txt`

### Ошибка "JWT secret"
Убедись что `CHAINLIT_AUTH_SECRET` задан в Environment Variables

### Приложение падает при старте
Проверь логи в Render Dashboard → Logs

### База данных сбрасывается
Добавь Disk для персистентного хранения `/app/logs`

## Полезные команды

Проверить логи:
```
Render Dashboard → твой сервис → Logs
```

Рестарт сервиса:
```
Render Dashboard → твой сервис → Manual Deploy → Deploy latest commit
```

## Стоимость

- **Free tier**: 750 часов/месяц, сервис засыпает после 15 мин неактивности
- **Starter** ($7/мес): всегда онлайн, больше ресурсов
