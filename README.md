# 🔐 Lock&Go - Умная система аренды ячеек

> Современная H5 веб-платформа для управления сетью умных ячеек хранения

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-00C7B7?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker)](https://www.docker.com/)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-FF6B6B?style=flat)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

---

## 🎯 О проекте

**Lock&Go** - это полнофункциональная система управления умными ячейками хранения с real-time синхронизацией, веб-интерфейсом (H5), админ-панелью и интеграцией с IoT устройствами через MQTT.

### ✨ Основные возможности:

- 🌐 **H5 Web App** - работает на всех устройствах (iOS, Android, Desktop)
- 📱 **PWA Support** - можно установить как приложение
- 🔄 **Real-time обновления** - WebSocket для мгновенной синхронизации
- 👤 **Социальная авторизация** - Alfa-Bank, T-Bank, Sber ID, Gosuslugi, Mos.ru
- 💳 **Система оплаты** - баланс, пополнение, история транзакций
- 📊 **Admin панель** - управление ячейками, пользователями, аналитика
- 🔒 **IoT интеграция** - MQTT для управления физическими замками
- 🎨 **Современный UI** - Tailwind CSS + Framer Motion

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    H5 Web App (React)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   User App   │  │  Admin Panel │  │     PWA      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ WebSocket + REST API
┌────────────────────────┴────────────────────────────────┐
│              Backend (FastAPI + PostgreSQL)             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Auth API    │  │  Admin API   │  │ Security API │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ MQTT
┌────────────────────────┴────────────────────────────────┐
│                  IoT Devices (ESP32)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Station 1   │  │  Station 2   │  │  Station 3   │  │
│  │  32 lockers  │  │  32 lockers  │  │  32 lockers  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Быстрый старт

### Требования:
- Docker & Docker Compose
- Node.js 18+ (для локальной разработки)
- Python 3.11+ (для локальной разработки)

### 1. Клонирование репозитория:
```bash
git clone <repository-url>
cd lock-go
```

### 2. Запуск всей системы:
```bash
docker compose up -d
```

### 3. Доступ к приложению:

| Сервис | URL | Описание |
|--------|-----|----------|
| **H5 Web App** | http://localhost:5173 | Пользовательское приложение |
| **Admin Panel** | http://localhost:5173/?admin=true | Панель администратора |
| **API Docs** | http://localhost:8000/docs | Swagger документация |
| **WebSocket** | ws://localhost:8000/ws | Real-time подключение |

---

## 📱 H5 Web App (Frontend)

### Технологии:
- **React 18** - UI библиотека
- **Vite** - сборщик и dev server
- **Tailwind CSS** - utility-first CSS
- **Framer Motion** - анимации
- **Lucide React** - иконки
- **QR Code** - генерация QR кодов

### Структура:
```
frontend/src/
├── components/          # React компоненты
│   ├── BottomSheetMenu.jsx     # Нижнее меню
│   ├── LockerMap.jsx           # Карта ячеек
│   ├── PaymentModal.jsx        # Модальное окно оплаты
│   ├── SizeSelectModal.jsx     # Выбор размера ячейки
│   └── ...                     # Admin компоненты
├── hooks/              # Custom React hooks
│   ├── useAuth.js              # Аутентификация
│   ├── useBottomSheet.js       # Bottom sheet управление
│   ├── useCountAnimation.js    # Анимация чисел
│   └── usePullToRefresh.js     # Pull-to-refresh
├── config/
│   └── api.js                  # API конфигурация
├── App.jsx             # Главный компонент
├── Admin.jsx           # Admin панель
└── main.jsx            # Entry point
```

### Основные функции:

#### Пользовательское приложение:
- ✅ Социальная авторизация (5 провайдеров)
- ✅ Просмотр доступных ячеек на карте
- ✅ Выбор размера ячейки (S, M, L)
- ✅ Генерация QR-кода для доступа
- ✅ Управление балансом и пополнение
- ✅ История аренд и транзакций
- ✅ Активные аренды с удаленным открытием
- ✅ Профиль пользователя

#### Admin панель:
- ✅ Dashboard с аналитикой
- ✅ Управление пользователями
- ✅ Управление ячейками и станциями
- ✅ Финансовая отчетность
- ✅ Динамическое ценообразование
- ✅ Управление инцидентами
- ✅ Управление персоналом и сменами
- ✅ Система задач
- ✅ Live карта с тепловой картой

---

## 🔧 Backend (FastAPI)

### Технологии:
- **FastAPI** - современный Python web framework
- **SQLAlchemy 2.0** - ORM с async support
- **PostgreSQL** - основная база данных
- **aiomqtt** - асинхронный MQTT клиент
- **WebSocket** - real-time коммуникация

### API Endpoints:

#### Authentication (`/api/auth`):
```python
POST   /api/auth/login/{provider}     # Социальная авторизация
POST   /api/auth/register             # Регистрация
GET    /api/auth/me                   # Текущий пользователь
POST   /api/auth/logout               # Выход
```

#### User API:
```python
GET    /api/users/me                  # Профиль
PATCH  /api/users/me                  # Обновление профиля
POST   /api/users/me/topup            # Пополнение баланса
GET    /api/users/me/transactions     # История транзакций
GET    /api/users/me/rents            # История аренд
```

#### Lockers API:
```python
GET    /api/lockers                   # Список всех ячеек
GET    /api/lockers/{id}              # Информация о ячейке
POST   /api/rent                      # Аренда ячейки
POST   /api/unlock/{locker_id}        # Открыть ячейку
POST   /api/end_rent/{rent_id}        # Завершить аренду
```

#### Admin API (`/api/admin`):
```python
# Users
GET    /api/admin/users               # Все пользователи
PATCH  /api/admin/users/{id}          # Обновить пользователя

# Lockers
GET    /api/admin/lockers             # Все ячейки
PATCH  /api/admin/lockers/{id}        # Обновить ячейку

# Analytics
GET    /api/admin/stats               # Общая статистика
GET    /api/admin/revenue             # Финансовая аналитика

# Pricing
POST   /api/admin/pricing/bulk-update # Массовое обновление цен
GET    /api/admin/pricing-rules       # Правила ценообразования

# Incidents
GET    /api/admin/incidents           # Инциденты
POST   /api/admin/incidents           # Создать инцидент

# Staff & Shifts
GET    /api/admin/staff               # Персонал
GET    /api/admin/shifts/active       # Активные смены
POST   /api/admin/shifts/start        # Начать смену

# Tasks
GET    /api/admin/tasks               # Задачи
POST   /api/admin/tasks               # Создать задачу
```

#### Security API (`/api/security`):
```python
POST   /api/security/emergency-lock   # Аварийная блокировка
POST   /api/security/emergency-unlock # Разблокировка
GET    /api/security/audit-log        # Журнал аудита
```

### Database Models:

```python
User          # Пользователи
Locker        # Ячейки
Station       # Станции
Rent          # Аренды
Transaction   # Транзакции
PricingRule   # Правила ценообразования
Incident      # Инциденты
Shift         # Смены персонала
Task          # Задачи
AuditLog      # Журнал аудита
MaintenanceLog # Журнал обслуживания
```

---

## 🔌 IoT Integration (MQTT)

### MQTT Topics:

```
lockers/+/status       # Статус ячейки (subscribe)
lockers/+/command      # Команды ячейке (publish)
lockers/+/unlock       # Открыть ячейку (publish)
lockers/+/lock         # Закрыть ячейку (publish)
```

### Firmware (ESP32):
```cpp
// PlatformIO project
platform = espressif32
framework = arduino
lib_deps = 
    knolleary/PubSubClient
    bblanchon/ArduinoJson
```

---

## 🎨 UI/UX Features

### Адаптивный дизайн:
- ✅ Mobile-first подход
- ✅ Работает на всех размерах экранов
- ✅ Touch-friendly интерфейс
- ✅ Swipe жесты

### Анимации:
- ✅ Framer Motion для плавных переходов
- ✅ Skeleton loaders при загрузке
- ✅ Haptic feedback (вибрация)
- ✅ Pull-to-refresh

### PWA:
- ✅ Можно установить на домашний экран
- ✅ Работает offline (частично)
- ✅ Push notifications (готово к интеграции)
- ✅ App-like experience

---

## 🔐 Безопасность

### Реализовано:
- ✅ JWT токены для аутентификации
- ✅ Хеширование паролей (bcrypt)
- ✅ CORS настроен
- ✅ Rate limiting (готово к настройке)
- ✅ Журнал аудита всех действий
- ✅ Аварийная блокировка системы
- ✅ Доступ по ролям (USER, STAFF, ADMIN, SECURITY)

---

## 📊 Мониторинг и логирование

### Логи:
```bash
# Backend logs
docker compose logs -f backend

# Frontend logs
docker compose logs -f frontend

# MQTT broker logs
docker compose logs -f mosquitto
```

### Метрики:
- ✅ Количество активных аренд
- ✅ Выручка по периодам
- ✅ Загруженность станций
- ✅ Популярные размеры ячеек
- ✅ Время аренды (среднее/медиана)

---

## 🧪 Разработка

### Frontend (локально):
```bash
cd frontend
npm install
npm run dev
```

### Backend (локально):
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Firmware (PlatformIO):
```bash
cd firmware
pio run -t upload
pio device monitor
```

---

## 🐛 Отладка

### Проверка статуса:
```bash
docker compose ps
```

### Перезапуск сервиса:
```bash
docker compose restart backend
docker compose restart frontend
```

### Полная пересборка:
```bash
docker compose down
docker compose up -d --build
```

### Очистка базы данных:
```bash
docker compose down -v
docker compose up -d
```

---

## 📦 Deployment

### Production готовность:
- ✅ Docker Compose для оркестрации
- ✅ Nginx для reverse proxy (готово к настройке)
- ✅ PostgreSQL с persistent storage
- ✅ HTTPS ready
- ✅ Environment variables для конфигурации

### Переменные окружения:
```env
# Backend
DATABASE_URL=postgresql+asyncpg://...
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
SECRET_KEY=your-secret-key

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

---

## 📝 Документация

| Файл | Описание |
|------|----------|
| `README.md` | Этот файл - основная документация |
| `CLEANUP_COMPLETE.md` | Отчет о генеральной уборке |
| `ECOSYSTEM_STATUS.md` | Статус всей экосистемы |
| `CLEANUP_REPORT.md` | Предыдущий отчет об очистке |

---

## 🤝 Contributing

Проект находится в активной разработке. Основной фокус - **H5 веб-приложение** с максимальной функциональностью и UX.

---

## 📄 License

Proprietary - все права защищены.

---

## 🎯 Roadmap

### В разработке:
- [ ] Интеграция с реальными платежными системами
- [ ] Карта с геолокацией (Yandex Maps / Google Maps)
- [ ] Push notifications
- [ ] Offline mode (Service Worker)
- [ ] Multilanguage support

### Планируется:
- [ ] Система лояльности и промокодов
- [ ] Реферальная программа
- [ ] Интеграция с CRM
- [ ] Мобильные приложения (iOS/Android native)

---

## 📞 Контакты

Для вопросов и предложений: [contact info]

---

**Made with ❤️ for Lock&Go**
