# 🚀 Деплой Lock&Go на REG.RU

## 📋 Содержание
1. [Требования](#требования)
2. [Подготовка проекта](#подготовка-проекта)
3. [Настройка VPS на REG.RU](#настройка-vps-на-regru)
4. [Установка Docker](#установка-docker)
5. [Деплой приложения](#деплой-приложения)
6. [Настройка домена](#настройка-домена)
7. [SSL сертификат](#ssl-сертификат)
8. [Автоматическое обновление](#автоматическое-обновление)

---

## 🎯 Требования

### Минимальные требования к серверу:
- **CPU:** 2 ядра
- **RAM:** 4 GB
- **Диск:** 40 GB SSD
- **ОС:** Ubuntu 22.04 LTS

### Что нужно иметь:
- ✅ Аккаунт на REG.RU
- ✅ VPS сервер (можно заказать на reg.ru)
- ✅ Домен (например, `lockgo.ru`)
- ✅ SSH доступ к серверу

---

## 📦 Подготовка проекта

### 1. Создайте production конфигурацию

Создайте файл `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: lockgo-backend-prod
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./data/lockgo.db
      - MQTT_BROKER_HOST=mosquitto
      - MQTT_BROKER_PORT=1883
      - ENVIRONMENT=production
    volumes:
      - ./data:/app/data
    depends_on:
      - mosquitto
    networks:
      - lockgo-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    container_name: lockgo-frontend-prod
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
    networks:
      - lockgo-network

  mosquitto:
    image: eclipse-mosquitto:2.0
    container_name: lockgo-mqtt-prod
    restart: always
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
    networks:
      - lockgo-network

networks:
  lockgo-network:
    driver: bridge

volumes:
  data:
```

### 2. Создайте production Dockerfile для frontend

`frontend/Dockerfile.prod`:

```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 3. Создайте конфигурацию Nginx

`frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name lockgo.ru www.lockgo.ru;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

### 4. Обновите конфигурацию API для production

`frontend/src/config/api.js`:

```javascript
const isDevelopment = import.meta.env.DEV;

export const config = {
  // API Base URL
  apiUrl: isDevelopment 
    ? 'http://localhost:8000'
    : 'https://lockgo.ru', // Ваш домен
  
  // WebSocket URL
  wsUrl: isDevelopment
    ? 'ws://localhost:8000/ws/lockers'
    : 'wss://lockgo.ru/ws/lockers', // Ваш домен с wss://
  
  // Feature flags
  features: {
    hapticFeedback: true,
    soundEffects: false,
    darkMode: false,
    analytics: !isDevelopment,
  },
  
  pollingInterval: 5000,
  wsReconnectDelay: 5000,
  wsPingInterval: 30000,
};

export default config;
```

---

## 🖥️ Настройка VPS на REG.RU

### 1. Заказ VPS

1. Зайдите на [reg.ru](https://www.reg.ru)
2. Перейдите в раздел **VPS/VDS**
3. Выберите тариф (минимум: 2 CPU, 4 GB RAM, 40 GB SSD)
4. Выберите ОС: **Ubuntu 22.04 LTS**
5. Оформите заказ

### 2. Получите доступ к серверу

После создания VPS вы получите:
- **IP адрес:** например, `123.45.67.89`
- **Логин:** `root`
- **Пароль:** придет на email

### 3. Подключитесь к серверу

```bash
ssh root@123.45.67.89
```

При первом подключении введите пароль из email.

### 4. Обновите систему

```bash
apt update && apt upgrade -y
```

### 5. Создайте нового пользователя (рекомендуется)

```bash
# Создать пользователя
adduser lockgo

# Добавить в sudo группу
usermod -aG sudo lockgo

# Переключиться на нового пользователя
su - lockgo
```

---

## 🐳 Установка Docker

### 1. Установите Docker

```bash
# Удалите старые версии (если есть)
sudo apt remove docker docker-engine docker.io containerd runc

# Установите зависимости
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Добавьте Docker GPG ключ
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавьте Docker репозиторий
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установите Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Проверьте установку
docker --version
docker compose version
```

### 2. Настройте Docker для пользователя

```bash
# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER

# Перезайдите в систему
exit
ssh lockgo@123.45.67.89
```

---

## 🚀 Деплой приложения

### Вариант 1: Через Git (рекомендуется)

#### 1. Установите Git

```bash
sudo apt install -y git
```

#### 2. Клонируйте репозиторий

Сначала создайте репозиторий на GitHub/GitLab:

```bash
# На вашем локальном компьютере
cd /Users/danila/Desktop/Lock\&Go/Firmware+back+front/lock-go
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/lockgo.git
git push -u origin main
```

Затем на сервере:

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/lockgo.git
cd lockgo
```

#### 3. Запустите приложение

```bash
# Создайте необходимые директории
mkdir -p data mosquitto/{config,data,log}

# Запустите контейнеры
docker compose -f docker-compose.prod.yml up -d

# Проверьте статус
docker compose -f docker-compose.prod.yml ps
```

### Вариант 2: Через SCP (для быстрого теста)

На вашем локальном компьютере:

```bash
# Создайте архив проекта
cd /Users/danila/Desktop/Lock\&Go/Firmware+back+front
tar -czf lockgo.tar.gz lock-go/

# Загрузите на сервер
scp lockgo.tar.gz lockgo@123.45.67.89:~

# Подключитесь к серверу
ssh lockgo@123.45.67.89

# Распакуйте архив
tar -xzf lockgo.tar.gz
cd lock-go

# Запустите
docker compose -f docker-compose.prod.yml up -d
```

---

## 🌐 Настройка домена

### 1. Привяжите домен к серверу

В панели управления REG.RU:

1. Перейдите в **Домены** → Выберите ваш домен
2. Нажмите **Управление DNS**
3. Добавьте A-записи:

```
Тип    Имя    Значение           TTL
A      @      123.45.67.89       3600
A      www    123.45.67.89       3600
```

### 2. Дождитесь обновления DNS

Проверьте обновление DNS (может занять до 24 часов):

```bash
# На локальном компьютере
nslookup lockgo.ru
dig lockgo.ru
```

---

## 🔒 SSL сертификат (Let's Encrypt)

### 1. Установите Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Получите SSL сертификат

```bash
# Остановите Nginx в контейнере
docker compose -f docker-compose.prod.yml stop frontend

# Получите сертификат
sudo certbot certonly --standalone -d lockgo.ru -d www.lockgo.ru

# Сертификаты будут сохранены в:
# /etc/letsencrypt/live/lockgo.ru/fullchain.pem
# /etc/letsencrypt/live/lockgo.ru/privkey.pem
```

### 3. Обновите конфигурацию Nginx

Создайте `nginx/nginx-ssl.conf`:

```nginx
server {
    listen 80;
    server_name lockgo.ru www.lockgo.ru;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name lockgo.ru www.lockgo.ru;

    # SSL certificates
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

### 4. Скопируйте сертификаты

```bash
# Создайте директорию для SSL
mkdir -p nginx/ssl

# Скопируйте сертификаты
sudo cp /etc/letsencrypt/live/lockgo.ru/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/lockgo.ru/privkey.pem nginx/ssl/
sudo chown -R $USER:$USER nginx/ssl
```

### 5. Обновите docker-compose.prod.yml

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile.prod
  container_name: lockgo-frontend-prod
  restart: always
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
    - ./nginx/ssl:/etc/nginx/ssl:ro
  depends_on:
    - backend
  networks:
    - lockgo-network
```

### 6. Перезапустите контейнеры

```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### 7. Настройте автообновление сертификата

```bash
# Создайте скрипт обновления
sudo nano /usr/local/bin/renew-lockgo-cert.sh
```

Содержимое скрипта:

```bash
#!/bin/bash
docker compose -f /home/lockgo/lockgo/docker-compose.prod.yml stop frontend
certbot renew --quiet
cp /etc/letsencrypt/live/lockgo.ru/fullchain.pem /home/lockgo/lockgo/nginx/ssl/
cp /etc/letsencrypt/live/lockgo.ru/privkey.pem /home/lockgo/lockgo/nginx/ssl/
docker compose -f /home/lockgo/lockgo/docker-compose.prod.yml start frontend
```

Сделайте скрипт исполняемым:

```bash
sudo chmod +x /usr/local/bin/renew-lockgo-cert.sh
```

Добавьте в cron:

```bash
sudo crontab -e
```

Добавьте строку:

```
0 3 * * * /usr/local/bin/renew-lockgo-cert.sh
```

---

## 🔄 Автоматическое обновление

### Создайте скрипт деплоя

`deploy.sh`:

```bash
#!/bin/bash

echo "🚀 Starting deployment..."

# Перейти в директорию проекта
cd /home/lockgo/lockgo

# Получить последние изменения
echo "📥 Pulling latest changes..."
git pull origin main

# Остановить контейнеры
echo "🛑 Stopping containers..."
docker compose -f docker-compose.prod.yml down

# Пересобрать образы
echo "🔨 Building images..."
docker compose -f docker-compose.prod.yml build --no-cache

# Запустить контейнеры
echo "▶️ Starting containers..."
docker compose -f docker-compose.prod.yml up -d

# Очистить неиспользуемые образы
echo "🧹 Cleaning up..."
docker image prune -f

echo "✅ Deployment complete!"
docker compose -f docker-compose.prod.yml ps
```

Сделайте скрипт исполняемым:

```bash
chmod +x deploy.sh
```

Используйте:

```bash
./deploy.sh
```

---

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Все логи
docker compose -f docker-compose.prod.yml logs

# Логи конкретного сервиса
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs frontend

# Следить за логами в реальном времени
docker compose -f docker-compose.prod.yml logs -f
```

### Проверка статуса

```bash
# Статус контейнеров
docker compose -f docker-compose.prod.yml ps

# Использование ресурсов
docker stats
```

---

## 🔧 Полезные команды

### Перезапуск сервисов

```bash
# Перезапустить все
docker compose -f docker-compose.prod.yml restart

# Перезапустить конкретный сервис
docker compose -f docker-compose.prod.yml restart backend
```

### Обновление приложения

```bash
# Получить изменения
git pull

# Пересобрать и перезапустить
docker compose -f docker-compose.prod.yml up -d --build
```

### Резервное копирование

```bash
# Создать бэкап базы данных
docker compose -f docker-compose.prod.yml exec backend \
  cp /app/data/lockgo.db /app/data/lockgo_backup_$(date +%Y%m%d).db

# Скачать бэкап на локальный компьютер
scp lockgo@123.45.67.89:~/lockgo/data/lockgo_backup_*.db ~/backups/
```

---

## ✅ Чек-лист деплоя

- [ ] VPS заказан и настроен
- [ ] Docker установлен
- [ ] Проект загружен на сервер
- [ ] Домен привязан к IP
- [ ] SSL сертификат установлен
- [ ] Приложение запущено
- [ ] Открыты порты: 80, 443, 1883
- [ ] Настроен firewall
- [ ] Настроено автообновление SSL
- [ ] Созданы бэкапы

---

## 🆘 Решение проблем

### Приложение не открывается

```bash
# Проверьте статус контейнеров
docker compose -f docker-compose.prod.yml ps

# Проверьте логи
docker compose -f docker-compose.prod.yml logs

# Проверьте порты
sudo netstat -tulpn | grep -E '80|443|8000'
```

### SSL не работает

```bash
# Проверьте сертификаты
sudo certbot certificates

# Обновите сертификаты
sudo certbot renew --force-renewal
```

### WebSocket не подключается

Убедитесь что в Nginx правильно настроен proxy для WebSocket:

```nginx
location /ws {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## 📞 Поддержка REG.RU

- **Телефон:** 8 (495) 580-11-11
- **Email:** support@reg.ru
- **Личный кабинет:** https://www.reg.ru/user/

---

## 🎉 Готово!

Ваше приложение Lock&Go теперь доступно по адресу:
- **HTTP:** http://lockgo.ru
- **HTTPS:** https://lockgo.ru
- **Админка:** https://lockgo.ru?admin=true

**Успешного деплоя! 🚀**

