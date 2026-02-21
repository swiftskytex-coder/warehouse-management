# Локальная база данных для склада

## Преимущества:
✅ Полный контроль над данными
✅ Нет абонентской платы
✅ Работает без интернета
✅ Неограниченное количество записей
✅ Можно настроить под свои нужды
✅ Быстрый доступ (локально)
✅ Приватность данных

## Технологии:
- **SQLite** — база данных (файл)
- **Flask** — веб-сервер (Python)
- **HTML/CSS/JS** — интерфейс
- **Pandas** — отчеты и аналитика

## Структура базы данных:

```sql
-- Таблица товаров
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    manufacturer TEXT,
    category TEXT,
    price DECIMAL(10,2),
    description TEXT,
    url TEXT,
    weight TEXT,
    dimensions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица складских позиций
CREATE TABLE warehouse_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    zone TEXT,              -- Зона A, B, C...
    rack TEXT,              -- Стеллаж
    shelf TEXT,             -- Полка
    cell TEXT,              -- Ячейка
    quantity_actual INTEGER DEFAULT 0,
    quantity_reserved INTEGER DEFAULT 0,
    quantity_available INTEGER GENERATED ALWAYS AS (quantity_actual - quantity_reserved) STORED,
    last_counted TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Таблица изображений
CREATE TABLE product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    image_url TEXT,
    is_main BOOLEAN DEFAULT 0,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Таблица движения товаров
CREATE TABLE stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    movement_type TEXT,     -- 'in', 'out', 'reserve', 'correction'
    quantity INTEGER,
    reason TEXT,
    user_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Таблица пользователей
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT,              -- 'admin', 'manager', 'warehouse'
    full_name TEXT
);
```

## Установка и настройка:

### 1. Установи зависимости
```bash
pip install flask flask-sqlalchemy pandas openpyxl
```

### 2. Создай файл базы данных
```python
# database.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///warehouse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Определи модели (таблицы)
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    article = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    manufacturer = db.Column(db.String(200))
    category = db.Column(db.String(200))
    price = db.Column(db.Numeric(10,2))
    description = db.Column(db.Text)
    url = db.Column(db.String(500))
    weight = db.Column(db.String(50))
    dimensions = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Связи
    stock = db.relationship('WarehouseStock', backref='product', uselist=False)
    images = db.relationship('ProductImage', backref='product')

class WarehouseStock(db.Model):
    __tablename__ = 'warehouse_stock'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    zone = db.Column(db.String(10))
    rack = db.Column(db.String(20))
    shelf = db.Column(db.String(20))
    cell = db.Column(db.String(20))
    quantity_actual = db.Column(db.Integer, default=0)
    quantity_reserved = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    last_counted = db.Column(db.DateTime)

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    image_url = db.Column(db.String(500))
    is_main = db.Column(db.Boolean, default=False)

# Создай базу
with app.app_context():
    db.create_all()
    print("✅ База данных создана!")
```

### 3. API для работы с базой
```python
# api.py
from database import app, db, Product, WarehouseStock, ProductImage
from flask import request, jsonify

@app.route('/api/products', methods=['GET'])
def get_products():
    """Получить список товаров"""
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'article': p.article,
        'title': p.title,
        'manufacturer': p.manufacturer,
        'price': str(p.price),
        'stock': {
            'zone': p.stock.zone if p.stock else None,
            'rack': p.stock.rack if p.stock else None,
            'actual': p.stock.quantity_actual if p.stock else 0,
            'available': (p.stock.quantity_actual - p.stock.quantity_reserved) if p.stock else 0
        }
    } for p in products])

@app.route('/api/products', methods=['POST'])
def add_product():
    """Добавить товар"""
    data = request.json
    
    # Проверяем, есть ли уже такой товар
    existing = Product.query.filter_by(article=data['article']).first()
    if existing:
        return jsonify({'error': 'Товар с таким артикулом уже существует'}), 400
    
    # Создаем товар
    product = Product(
        article=data['article'],
        title=data['title'],
        manufacturer=data.get('manufacturer'),
        category=data.get('category'),
        price=data.get('price'),
        description=data.get('description'),
        url=data.get('url'),
        weight=data.get('weight'),
        dimensions=data.get('dimensions')
    )
    db.session.add(product)
    db.session.flush()  # Получаем ID
    
    # Добавляем фото
    for img_url in data.get('images', []):
        image = ProductImage(product_id=product.id, image_url=img_url)
        db.session.add(image)
    
    # Создаем складскую запись
    stock = WarehouseStock(product_id=product.id)
    db.session.add(stock)
    
    db.session.commit()
    return jsonify({'id': product.id, 'message': 'Товар добавлен'})

@app.route('/api/products/<article>', methods=['PUT'])
def update_stock(article):
    """Обновить складские данные"""
    product = Product.query.filter_by(article=article).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    
    data = request.json
    
    if not product.stock:
        product.stock = WarehouseStock(product_id=product.id)
    
    product.stock.zone = data.get('zone', product.stock.zone)
    product.stock.rack = data.get('rack', product.stock.rack)
    product.stock.shelf = data.get('shelf', product.stock.shelf)
    product.stock.cell = data.get('cell', product.stock.cell)
    product.stock.quantity_actual = data.get('actual', product.stock.quantity_actual)
    product.stock.quantity_reserved = data.get('reserved', product.stock.quantity_reserved)
    product.stock.notes = data.get('notes', product.stock.notes)
    
    db.session.commit()
    return jsonify({'message': 'Данные обновлены'})

@app.route('/api/products/search', methods=['GET'])
def search_products():
    """Поиск товаров"""
    query = request.args.get('q', '')
    products = Product.query.filter(
        db.or_(
            Product.article.contains(query),
            Product.title.contains(query),
            Product.manufacturer.contains(query)
        )
    ).all()
    
    return jsonify([{
        'article': p.article,
        'title': p.title,
        'zone': p.stock.zone if p.stock else None,
        'actual': p.stock.quantity_actual if p.stock else 0
    } for p in products])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

### 4. Интеграция с парсером
```python
# import_to_db.py
import requests
from warehouse_card import parse_product_page, create_driver

def import_product(article_or_url):
    """Импорт товара в локальную базу"""
    
    # Парсим товар
    driver = create_driver()
    try:
        if article_or_url.startswith('http'):
            product = parse_product_page(driver, article_or_url)
        else:
            # Ищем по артикулу
            from search_snablift import find_product_by_article
            url = find_product_by_article(driver, article_or_url)
            if not url:
                print("❌ Товар не найден")
                return
            product = parse_product_page(driver, url)
    finally:
        driver.quit()
    
    # Отправляем в API
    response = requests.post('http://localhost:8080/api/products', json={
        'article': product['article'],
        'title': product['title'],
        'manufacturer': product['manufacturer'],
        'category': product['category'],
        'price': product['price'].replace('₽', '').replace(' ', '') if product['price'] else None,
        'description': product['description'],
        'url': product['url'],
        'weight': product['weight'],
        'dimensions': ', '.join([f"{k}: {v}" for k, v in product['dimensions'].items()]),
        'images': product['images']
    })
    
    if response.status_code == 201:
        print(f"✅ Импортировано: {product['title']}")
    else:
        print(f"⚠️ Ошибка: {response.json()}")

# Использование
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        import_product(sys.argv[1])
    else:
        print("Укажи артикул или URL")
```

### 5. Веб-интерфейс
```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Склад - Управление</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #2a5298; color: white; padding: 20px; }
        .search-box { margin: 20px 0; }
        .search-box input { padding: 10px; width: 300px; font-size: 16px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .stock-low { background: #fff3cd; }
        .stock-out { background: #f8d7da; }
        .btn { padding: 8px 16px; background: #2a5298; color: white; 
               border: none; cursor: pointer; border-radius: 4px; }
        .btn:hover { background: #1e3c72; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 Складской учет</h1>
    </div>
    
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="Поиск по артикулу или названию...">
        <button class="btn" onclick="search()">🔍 Поиск</button>
        <button class="btn" onclick="loadAll()">📋 Все товары</button>
    </div>
    
    <table id="productsTable">
        <thead>
            <tr>
                <th>Артикул</th>
                <th>Название</th>
                <th>Производитель</th>
                <th>Зона</th>
                <th>Ячейка</th>
                <th>Факт</th>
                <th>Резерв</th>
                <th>Доступно</th>
                <th>Действия</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
    
    <script>
        async function loadAll() {
            const response = await fetch('/api/products');
            const products = await response.json();
            displayProducts(products);
        }
        
        async function search() {
            const query = document.getElementById('searchInput').value;
            const response = await fetch(`/api/products/search?q=${query}`);
            const products = await response.json();
            displayProducts(products);
        }
        
        function displayProducts(products) {
            const tbody = document.querySelector('#productsTable tbody');
            tbody.innerHTML = products.map(p => `
                <tr class="${p.stock.available <= 5 ? 'stock-low' : ''} ${p.stock.available === 0 ? 'stock-out' : ''}">
                    <td>${p.article}</td>
                    <td>${p.title}</td>
                    <td>${p.manufacturer || '-'}</td>
                    <td>${p.stock.zone || '-'}</td>
                    <td>${p.stock.rack || '-'}-${p.stock.shelf || '-'}-${p.stock.cell || '-'}</td>
                    <td>${p.stock.actual}</td>
                    <td>${p.stock.reserved}</td>
                    <td><strong>${p.stock.available}</strong></td>
                    <td>
                        <button class="btn" onclick="editProduct('${p.article}')">✏️</button>
                    </td>
                </tr>
            `).join('');
        }
        
        loadAll();
    </script>
</body>
</html>
```

## Запуск системы:

```bash
# 1. Установи зависимости
pip install flask flask-sqlalchemy requests pandas

# 2. Создай базу
python database.py

# 3. Запусти API
python api.py

# 4. Импортируй товары
python import_to_db.py 2498
python import_to_db.py 768
python import_to_db.py "https://snab-lift.ru/catalog/.../product.html"

# 5. Открой веб-интерфейс
open http://localhost:8080
```

## Дополнительные возможности локальной базы:

### Экспорт в Excel:
```python
import pandas as pd

def export_to_excel():
    products = Product.query.all()
    data = [{
        'Артикул': p.article,
        'Название': p.title,
        'Зона': p.stock.zone if p.stock else '',
        'Количество': p.stock.quantity_actual if p.stock else 0
    } for p in products]
    
    df = pd.DataFrame(data)
    df.to_excel('warehouse_report.xlsx', index=False)
    print("✅ Отчет сохранен: warehouse_report.xlsx")
```

### Бэкап базы:
```bash
# Автоматический бэкап
cp warehouse.db "backup_$(date +%Y%m%d_%H%M%S).db"
```

### Статистика:
```python
@app.route('/api/stats')
def get_stats():
    total = Product.query.count()
    low_stock = Product.query.join(WarehouseStock).filter(
        (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) < 5
    ).count()
    
    return jsonify({
        'total_products': total,
        'low_stock': low_stock,
        'zones': db.session.query(WarehouseStock.zone).distinct().count()
    })
```

## Сравнение вариантов:

| Критерий | Airtable | Локальная база |
|----------|----------|----------------|
| Стоимость | $10-20/мес | Бесплатно |
| Интернет | Нужен | Не нужен |
| Скорость | Зависит от сети | Мгновенно |
| Доступ | Из любой точки | Только локально/VPN |
| Настройка | 15 минут | 1-2 часа |
| Объем | До 50K записей | Неограниченно |
| Интерфейс | Готовый | Нужно разрабатывать |
| Бэкапы | Автоматические | Нужно настраивать |
| Мобильное приложение | ✅ Есть | ❌ Только веб |
| Совместная работа | ✅ Встроено | ⚠️ Нужно настраивать |

## Рекомендации:

**Выбирай Airtable, если:**
- Нужен быстрый старт
- Маленький склад (<1000 товаров)
- Нет программиста
- Нужен доступ с телефона
- Важна совместная работа

**Выбирай локальную базу, если:**
- Большой склад (>5000 товаров)
- Есть программист/ты готов разобраться
- Важна скорость работы
- Нужна интеграция с 1С/другими системами
- Нужны сложные отчеты
- Нет стабильного интернета

## Гибридный вариант:
Можно использовать **оба**! Локальная база как основная, а Airtable для:
- Мобильного доступа складских работников
- Совместной работы с менеджерами
- Быстрых правок через телефон
