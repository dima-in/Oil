# Автодеплой

Деплой настроен через GitHub Actions:

- GitHub Actions собирает Docker-образ приложения.
- Образ публикуется в GitHub Container Registry: `ghcr.io/dima-in/oil-web:latest`.
- Сервер по SSH делает `docker compose pull web` и `docker compose up -d --no-build --remove-orphans`.

Сервер больше не собирает приложение сам, а только скачивает готовый образ.

## GitHub Secrets

В репозитории GitHub открой `Settings -> Secrets and variables -> Actions` и добавь:

- `DEPLOY_HOST` - IP или домен сервера.
- `DEPLOY_USER` - пользователь для SSH, например `root` или `ubuntu`.
- `DEPLOY_PORT` - SSH-порт, обычно `22`.
- `DEPLOY_SSH_KEY` - приватный SSH-ключ, у которого есть доступ на сервер.
- `DEPLOY_PATH` - путь к проекту на сервере, например `/opt/oil`.

`GITHUB_TOKEN` создавать вручную не нужно. GitHub Actions выдает его автоматически для публикации и скачивания образа из GHCR.

## Подготовка сервера

На сервере должны быть установлены `git`, Docker и Docker Compose plugin:

```bash
sudo apt update
sudo apt install -y git
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install -y docker-compose-plugin
```

Добавь публичный ключ от `DEPLOY_SSH_KEY` в `~/.ssh/authorized_keys` пользователя `DEPLOY_USER`.

## Первый запуск

После добавления Secrets сделай push в `master` или запусти workflow вручную через `Actions -> Deploy -> Run workflow`.

Workflow сам клонирует репозиторий в `DEPLOY_PATH`, если проекта там еще нет. При каждом деплое рабочая копия на сервере приводится к `origin/master`, поэтому локальные правки в папке проекта на сервере будут перезаписаны.
