# 🏭 Локальная база данных склада

Полная система управления складскими карточками товаров с импортом из snab-lift.ru

## 📦 Что включено:

- ✅ **База данных SQLite** — локальное хранение всех товаров
- ✅ **Веб-интерфейс** — удобное управление через браузер
- ✅ **Импорт из snab-lift.ru** — по артикулу или URL
- ✅ **Массовый импорт** — загрузка списка товаров
- ✅ **HTML карточки** — для печати этикеток
- ✅ **Поиск и фильтры** — быстрый доступ к товарам
- ✅ **Складской учет** — зоны, стеллажи, полки, ячейки
- ✅ **Контроль остатков** — мин/макс, резервирование

## 🚀 Быстрый старт

### 1. Запуск системы

```bash
source venv/bin/activate
python warehouse_system.py
```

Откроется веб-интерфейс: **http://localhost:8080**

### 2. Импорт первого товара

```bash
# По артикулу
python import_product.py 2498

# По URL
python import_product.py "https://snab-lift.ru/catalog/.../product.html"
```

### 3. Открытие веб-интерфейса

```bash
open http://localhost:8080
```

## 📋 Возможности

### 🎯 Веб-интерфейс (http://localhost:8080)

**Главная страница:**
- 📊 Статистика склада (всего товаров, заканчивается, нет в наличии)
- 🔍 Поиск по артикулу, названию, производителю
- 📦 Таблица товаров с фильтрами
- ➕ Импорт товаров с snab-lift.ru
- 📥 Массовый импорт списка
- 📤 Экспорт в JSON
- ✏️ Редактирование складских данных
- 📄 Печать карточек товаров

**Карточка товара (/card/ARTICLE):**
- 🖼️ Галерея фото
- 💰 Цена и статус
- 📍 Местоположение (зона-стеллаж-полка-ячейка)
- 📦 Количество (факт/резерв/доступно)
- 📋 Технические характеристики
- 📝 Описание
- 🏷️ Этикетка для печати
- 🖨️ Кнопка печати

### 🔌 API Endpoints

```
GET  /api/products              # Список товаров (с пагинацией)
GET  /api/products/<article>    # Один товар
POST /api/products              # Добавить товар
PUT  /api/products/<article>/stock  # Обновить склад
DELETE /api/products/<article>  # Удалить товар
GET  /api/products/search?q=... # Поиск
GET  /api/stats                 # Статистика
POST /api/import/snablift       # Импорт с сайта
POST /api/import/batch          # Массовый импорт
GET  /api/export/json           # Экспорт в JSON
GET  /card/<article>            # HTML карточка
```

### 💻 Примеры API

```bash
# Получить все товары
curl http://localhost:8080/api/products

# Поиск
curl "http://localhost:8080/api/products/search?q=2498"

# Импорт товара
curl -X POST http://localhost:8080/api/import/snablift \
  -H "Content-Type: application/json" \
  -d '{"query":"2498"}'

# Обновить склад
curl -X PUT http://localhost:8080/api/products/2498/stock \
  -H "Content-Type: application/json" \
  -d '{
    "zone": "A",
    "rack": "12", 
    "shelf": "3",
    "cell": "45",
    "quantity_actual": 50,
    "quantity_reserved": 10
  }'
```

## 📊 Структура базы данных

### Таблицы:

1. **products** — товары
   - id, article, title, manufacturer, category
   - price, description, url, weight, dimensions
   - specifications (JSON), created_at, updated_at

2. **warehouse_stock** — складские остатки
   - product_id, zone, rack, shelf, cell
   - quantity_actual, quantity_reserved
   - quantity_min, quantity_max
   - notes, last_counted

3. **product_images** — изображения
   - product_id, image_url, is_main

4. **stock_movements** — движение товаров
   - product_id, movement_type, quantity
   - reason, user_name, created_at

## 🛠️ Использование

### 1. Импорт одного товара

```bash
python import_product.py 2498
```

Результат:
```
======================================================================
📦 ИМПОРТ ТОВАРА: 2498
======================================================================

🔍 Поиск по артикулу: 2498
📄 Парсинг страницы...

✅ ТОВАР УСПЕШНО ИМПОРТИРОВАН
   Артикул: 2498
   Название: Прерыватель (диск) D=40мм d=10мм ШПЖИ7.079.000 МЛЗ
   Производитель: МЛЗ
   Цена: 26 ₽
   Фото: 6 шт.
   ID в базе: 1
```

### 2. Массовый импорт

Создай файл `items.txt`:
```
2498
768
661
4115
https://snab-lift.ru/catalog/.../product1.html
https://snab-lift.ru/catalog/.../product2.html
```

Запусти:
```bash
# Через веб-интерфейс:
# 1. Открой http://localhost:8080
# 2. Нажми "📥 Массовый импорт"
# 3. Вставь список
# 4. Нажми "🚀 Начать импорт"

# Или через API:
curl -X POST http://localhost:8080/api/import/batch \
  -H "Content-Type: application/json" \
  -d '{"items": ["2498", "768", "661"]}'
```

### 3. Редактирование склада

Через веб-интерфейс:
1. Найди товар в списке
2. Нажми кнопку ✏️ (редактировать)
3. Заполни поля:
   - Зона: A
   - Стеллаж: 12
   - Полка: 3
   - Ячейка: 45
   - Фактически: 50
   - Зарезервировано: 10
   - Минимальный остаток: 5
4. Нажми "💾 Сохранить"

### 4. Печать карточки

1. В списке товаров нажми 📄 (карточка)
2. Или открой: http://localhost:8080/card/2498
3. Нажми "🖨️ Печать"

### 5. Экспорт данных

```bash
# Через веб-интерфейс
# Нажми кнопку "📤 Экспорт JSON"

# Или через API
curl http://localhost:8080/api/export/json -o export.json
```

## 📁 Файлы системы

```
warehouse_system.py           # Главный файл (запуск)
warehouse_db.py              # База данных (альтернатива)
import_product.py            # Импорт товаров
warehouse_card.py            # Генератор карточек
warehouse/                   # Директория с системой
├── warehouse.db            # Файл базы данных SQLite
├── templates/
│   ├── warehouse_dashboard.html  # Главная страница
│   └── product_card.html         # Карточка товара
└── static/                 # CSS, JS, изображения
```

## 🔧 Настройка

### Изменение порта:

В `warehouse_system.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Порт 8080
```

### Автозапуск:

Создай `start.sh`:
```bash
#!/bin/bash
cd /path/to/warehouse
source venv/bin/activate
python warehouse_system.py
```

Сделай исполняемым:
```bash
chmod +x start.sh
./start.sh
```

### Резервное копирование:

```bash
# Скопируй файл базы
cp warehouse.db "backup_$(date +%Y%m%d_%H%M%S).db"
```

## 💡 Советы

1. **Регулярно делай бэкапы** базы данных
2. **Используй мин/макс остатки** для контроля запасов
3. **Резервируй товары** под заказы
4. **Печатай карточки** для маркировки склада
5. **Обновляй количество** при инвентаризации

## 🐛 Устранение проблем

### Ошибка "No such table"

```bash
# Пересоздать базу
python -c "
from warehouse_system import app, db
with app.app_context():
    db.create_all()
    print('База создана')
"
```

### Ошибка импорта

```bash
# Проверь интернет соединение
# Проверь, что товар существует на snab-lift.ru
# Попробуй импорт по URL вместо артикула
```

### Порт занят

```bash
# Найди процесс
lsof -i :5000
kill -9 <PID>

# Или используй другой порт
python warehouse_system.py  # измени в коде
```

## 📞 Поддержка

Если возникли вопросы:
1. Проверь, что все зависимости установлены
2. Посмотри логи в консоли
3. Проверь права доступа к файлам

## 📝 Лицензия

Свободное использование для складского учета.
