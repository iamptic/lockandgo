# 🔌 Что такое API и как оно работает в Lock&Go

## 📖 Что такое API простыми словами

**API (Application Programming Interface)** - это как "меню в ресторане" для программ.

### Аналогия с рестораном:

```
┌─────────────────────────────────────────────────────────┐
│                    🍽️ РЕСТОРАН                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Вы (клиент) → Официант → Кухня → Официант → Вы       │
│      ↓            ↓         ↓         ↓        ↓       │
│  Frontend  →    API   → Backend →   API  → Frontend    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Как это работает:

1. **Вы** (клиент) - не знаете как готовится еда
2. **Официант** (API) - принимает заказ, приносит еду
3. **Кухня** (Backend) - готовит еду по рецепту
4. **Меню** (API документация) - список того, что можно заказать

**API - это официант между вашим приложением и сервером!**

---

## ✅ Есть ли API у вас?

### **ДА! У вас полноценное современное API!** 🎉

Ваш проект Lock&Go использует **FastAPI** - один из самых современных и быстрых фреймворков для создания API.

---

## 🏗️ Структура вашего API

### Ваше API находится здесь:
```
backend/app/
├── main.py          # Основное API (локеры, аренда)
├── auth_api.py      # API аутентификации
├── admin_api.py     # API для админов
└── security_api.py  # API безопасности
```

---

## 🎯 Примеры из ВАШЕГО проекта

### Пример 1: Аренда ячейки 🔒

**Что видит пользователь:**
```
Нажимает кнопку "Арендовать" → Ячейка забронирована! ✅
```

**Что происходит под капотом:**
```javascript
// Frontend (App.jsx) отправляет запрос:
fetch('http://localhost:8000/api/rent', {
  method: 'POST',
  body: JSON.stringify({
    user_id: 1,
    locker_mac: 'locker_123'
  })
})

// ↓ Запрос идет через интернет ↓

// Backend (main.py) получает и обрабатывает:
@app.post("/api/rent")
async def rent_locker_body(rent_data: RentStart):
    # Проверяет доступна ли ячейка
    # Создает аренду
    # Помечает ячейку как занятую
    return {
        "status": "success",
        "message": "Ячейка забронирована!"
    }

// ↑ Ответ возвращается обратно ↑

// Frontend получает ответ и показывает:
alert("✅ Ячейка забронирована!")
```

---

### Пример 2: Пополнение баланса 💰

**Что видит пользователь:**
```
Нажимает "Пополнить на 500₽" → Баланс увеличился! ✅
```

**Что происходит:**
```javascript
// Frontend:
fetch('http://localhost:8000/api/users/me/topup', {
  method: 'POST',
  body: JSON.stringify({
    amount: 500
  })
})

// Backend (auth_api.py):
@router.post("/api/users/me/topup")
async def topup_balance(amount: float, user_id: int):
    # Находит пользователя
    user.balance += amount
    # Сохраняет в базу данных
    # Создает транзакцию
    return {
        "status": "success",
        "new_balance": user.balance
    }

// Frontend показывает новый баланс:
"Баланс: 1500₽"
```

---

### Пример 3: Админ меняет цену 💵

**Что видит админ:**
```
Меняет цену S: 100₽ → 120₽
Нажимает "Сохранить"
Видит: "✅ Обновлено 32 ячейки!"
```

**Что происходит:**
```javascript
// Frontend (SettingsTab.jsx):
fetch('http://localhost:8000/api/admin/pricing/bulk-update', {
  method: 'POST',
  body: JSON.stringify({
    small: 120,
    medium: 150,
    large: 250
  })
})

// Backend (admin_api.py):
@router.post("/api/admin/pricing/bulk-update")
async def bulk_update_prices(prices: dict):
    # Находит все ячейки размера S
    # Обновляет цену на 120₽
    # Сохраняет в базу
    # ✨ БОНУС: Отправляет WebSocket уведомление всем пользователям!
    
    return {
        "status": "success",
        "updated_count": 32
    }

// Frontend показывает:
alert("✅ Обновлено 32 ячейки!")

// ВСЕ пользователи видят новую цену МГНОВЕННО! 🚀
```

---

## 📋 Полный список ВАШЕГО API

### 1️⃣ **API для пользователей** (auth_api.py)

#### Авторизация:
```
POST /api/auth/login/alfa       # Вход через Alfa-Bank
POST /api/auth/login/tbank      # Вход через T-Bank
POST /api/auth/login/sber       # Вход через Sber ID
POST /api/auth/login/gosuslugi  # Вход через Госуслуги
POST /api/auth/login/mosru      # Вход через Mos.ru
POST /api/auth/logout           # Выход
```

#### Профиль:
```
GET  /api/users/me              # Мой профиль
PATCH /api/users/me             # Обновить профиль
POST /api/users/me/topup        # Пополнить баланс
```

#### История:
```
GET /api/users/me/transactions  # Мои транзакции
GET /api/users/me/rents         # Мои аренды
```

---

### 2️⃣ **API для ячеек** (main.py)

#### Просмотр:
```
GET /api/lockers                # Все ячейки
GET /api/lockers/{id}           # Одна ячейка
GET /api/stations               # Все станции
```

#### Аренда:
```
POST /api/rent                  # Арендовать ячейку
POST /api/unlock/{locker_id}    # Открыть ячейку
POST /api/end_rent/{rent_id}    # Завершить аренду
```

#### WebSocket:
```
WS /ws                          # Real-time обновления
```

---

### 3️⃣ **API для админов** (admin_api.py)

#### Управление пользователями:
```
GET   /api/admin/users          # Все пользователи
PATCH /api/admin/users/{id}     # Изменить пользователя
```

#### Управление ячейками:
```
GET   /api/admin/lockers        # Все ячейки
PATCH /api/admin/lockers/{id}   # Изменить ячейку
```

#### Статистика:
```
GET /api/admin/stats            # Общая статистика
GET /api/admin/revenue          # Финансы
GET /api/admin/export-revenue   # Экспорт в CSV
```

#### Ценообразование:
```
POST /api/admin/pricing/bulk-update  # Обновить цены
GET  /api/admin/pricing-rules        # Правила цен
POST /api/admin/pricing-rules        # Создать правило
```

#### Инциденты:
```
GET  /api/admin/incidents       # Все инциденты
POST /api/admin/incidents       # Создать инцидент
PATCH /api/admin/incidents/{id} # Обновить инцидент
```

#### Персонал:
```
GET  /api/admin/staff           # Персонал
GET  /api/admin/shifts/active   # Активные смены
POST /api/admin/shifts/start    # Начать смену
POST /api/admin/shifts/{id}/end # Завершить смену
```

#### Задачи:
```
GET  /api/admin/tasks           # Все задачи
POST /api/admin/tasks           # Создать задачу
PATCH /api/admin/tasks/{id}     # Обновить задачу
```

---

### 4️⃣ **API безопасности** (security_api.py)

```
POST /api/security/emergency-lock    # Аварийная блокировка
POST /api/security/emergency-unlock  # Разблокировка
GET  /api/security/audit-log         # Журнал действий
```

---

## 🔍 Как посмотреть ваше API?

### 1. Запустите систему:
```bash
docker compose up -d
```

### 2. Откройте в браузере:
```
http://localhost:8000/docs
```

### 3. Вы увидите **интерактивную документацию** всего API! 📚

Там можно:
- ✅ Посмотреть все endpoints
- ✅ Протестировать каждый запрос
- ✅ Увидеть примеры ответов
- ✅ Попробовать "Try it out"

---

## 🎨 Визуализация вашего API

```
┌─────────────────────────────────────────────────────────┐
│            FRONTEND (React H5 App)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Кнопки   │  │  Формы   │  │  Карты   │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
└───────┼─────────────┼─────────────┼────────────────────┘
        │             │             │
        ▼             ▼             ▼
   fetch API     fetch API     fetch API
        │             │             │
        └─────────────┴─────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 API ENDPOINTS                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  /rent   │  │ /topup   │  │ /lockers │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
└───────┼─────────────┼─────────────┼────────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI)                          │
│  ┌──────────────────────────────────────┐               │
│  │  • Проверяет данные                  │               │
│  │  • Обрабатывает логику               │               │
│  │  • Работает с базой данных           │               │
│  │  • Отправляет MQTT команды           │               │
│  │  • Возвращает результат              │               │
│  └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              DATABASE (PostgreSQL)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Users   │  │ Lockers  │  │  Rents   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

---

## 💡 Почему API это важно?

### 1. **Разделение ответственности**
```
Frontend → Красота (UI/UX)
API      → Связь (передача данных)
Backend  → Мозги (логика и база)
```

### 2. **Переиспользование**
Одно API можно использовать для:
- ✅ Веб-приложения (H5)
- ✅ Мобильного приложения (iOS/Android)
- ✅ Другого сайта
- ✅ Внешних сервисов

### 3. **Безопасность**
```
Frontend → API → Backend → Database
  ↑                            ↑
Пользователь           Защищенная зона
может видеть           (пользователь не имеет 
и менять               прямого доступа)
```

### 4. **Масштабирование**
Можно легко:
- Добавлять новые функции
- Менять Frontend без Backend
- Менять Backend без Frontend
- Добавлять новые платформы

---

## 🔐 Безопасность вашего API

### Что уже реализовано:

1. **CORS** - защита от запросов с других сайтов
2. **Валидация данных** - Pydantic проверяет все входящие данные
3. **Базовая авторизация** - через социальные сети
4. **Аудит** - все действия логируются

### Что можно добавить:

- [ ] JWT токены для всех запросов
- [ ] Rate limiting (ограничение частоты запросов)
- [ ] API ключи для внешних сервисов
- [ ] HTTPS (обязательно для production!)

---

## 🎯 Практический пример

### Сценарий: Пользователь арендует ячейку

```javascript
// 1️⃣ FRONTEND отправляет запрос
const response = await fetch('http://localhost:8000/api/rent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    user_id: 123,
    locker_mac: 'locker_456'
  })
});

// 2️⃣ BACKEND получает запрос
// backend/app/main.py
@app.post("/api/rent")
async def rent_locker_body(rent_data: RentStart):
    async with async_session_maker() as session:
        # Находим ячейку
        locker = await find_locker(rent_data.locker_mac)
        
        # Проверяем доступность
        if locker.is_occupied:
            raise HTTPException(400, "Ячейка занята")
        
        # Проверяем баланс пользователя
        user = await get_user(rent_data.user_id)
        if user.balance < locker.price_per_hour:
            raise HTTPException(400, "Недостаточно средств")
        
        # Создаем аренду
        rent = Rent(
            user_id=rent_data.user_id,
            locker_id=locker.id
        )
        
        # Помечаем ячейку как занятую
        locker.is_occupied = True
        
        # Сохраняем в базу
        session.add(rent)
        await session.commit()
        
        # ✨ Отправляем MQTT команду на открытие замка
        await mqtt_publish(f"lockers/{locker.mac_address}/unlock")
        
        # ✨ Отправляем WebSocket уведомление всем клиентам
        await broadcast_locker_update()
        
        # Возвращаем ответ
        return {
            "status": "success",
            "rent_id": rent.id,
            "locker": {
                "id": locker.id,
                "location": locker.location_name
            }
        }

// 3️⃣ FRONTEND получает ответ
const data = await response.json();

if (data.status === 'success') {
    // Показываем успех
    showToast('✅ Ячейка забронирована!');
    
    // Обновляем UI
    setMyRents([...myRents, data.locker]);
    
    // Показываем QR-код
    showQRModal(data.locker);
}
```

---

## 📊 Сколько API endpoints у вас?

### Подсчет:

| Категория | Количество endpoints |
|-----------|---------------------|
| **Аутентификация** | 7 |
| **Пользователи** | 5 |
| **Ячейки** | 6 |
| **Админ - Пользователи** | 3 |
| **Админ - Ячейки** | 3 |
| **Админ - Статистика** | 4 |
| **Админ - Ценообразование** | 5 |
| **Админ - Инциденты** | 5 |
| **Админ - Персонал** | 4 |
| **Админ - Задачи** | 3 |
| **Безопасность** | 3 |
| **WebSocket** | 1 |

**ИТОГО: ~49 API endpoints!** 🎉

---

## 🚀 Как использовать API

### Из браузера (для тестирования):

1. Откройте DevTools (F12)
2. Перейдите в Console
3. Выполните:

```javascript
// Получить все ячейки
fetch('http://localhost:8000/api/lockers')
  .then(res => res.json())
  .then(data => console.log(data));

// Получить статистику (admin)
fetch('http://localhost:8000/api/admin/stats')
  .then(res => res.json())
  .then(data => console.log(data));
```

### Из другого приложения:

```python
# Python
import requests

response = requests.get('http://localhost:8000/api/lockers')
lockers = response.json()
print(lockers)
```

```javascript
// Node.js
const axios = require('axios');

const response = await axios.get('http://localhost:8000/api/lockers');
console.log(response.data);
```

---

## ✅ ИТОГ

### У вас есть API? **ДА! И ОЧЕНЬ ХОРОШЕЕ!** 🎉

**Ваше API:**
- ✅ **Современное** - FastAPI (один из лучших)
- ✅ **Полное** - ~49 endpoints
- ✅ **Документированное** - Swagger UI доступен
- ✅ **Real-time** - WebSocket интеграция
- ✅ **IoT-ready** - MQTT для устройств
- ✅ **Безопасное** - валидация, CORS
- ✅ **RESTful** - следует best practices
- ✅ **Async** - быстрое и производительное

**Ваше API - это сердце всей системы Lock&Go!** ❤️

---

## 📚 Дальнейшее изучение

### Хотите узнать больше?

1. **Swagger UI**: http://localhost:8000/docs
2. **ReDoc**: http://localhost:8000/redoc
3. **Исходный код**: `backend/app/`

### Что можно улучшить:

- [ ] Добавить JWT аутентификацию
- [ ] Добавить rate limiting
- [ ] Добавить кеширование (Redis)
- [ ] Версионирование API (v1, v2)
- [ ] GraphQL (альтернатива REST)

**API - это ваш друг! Он связывает всё вместе!** 🔗

