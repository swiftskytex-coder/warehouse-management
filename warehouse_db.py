#!/usr/bin/env python3
"""
Готовая локальная база данных для склада
Запуск: python warehouse_db.py
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///warehouse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)

# ========== МОДЕЛИ ДАННЫХ ==========

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    article = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    manufacturer = db.Column(db.String(200))
    category = db.Column(db.String(200))
    price = db.Column(db.String(50))
    description = db.Column(db.Text)
    url = db.Column(db.String(500))
    weight = db.Column(db.String(50))
    dimensions = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    stock = db.relationship('WarehouseStock', backref='product', uselist=False, lazy=True)
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'article': self.article,
            'title': self.title,
            'manufacturer': self.manufacturer,
            'category': self.category,
            'price': self.price,
            'description': self.description,
            'url': self.url,
            'weight': self.weight,
            'dimensions': self.dimensions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'images': [img.image_url for img in self.images],
            'stock': self.stock.to_dict() if self.stock else None
        }

class WarehouseStock(db.Model):
    __tablename__ = 'warehouse_stock'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), unique=True)
    zone = db.Column(db.String(10), default='')
    rack = db.Column(db.String(20), default='')
    shelf = db.Column(db.String(20), default='')
    cell = db.Column(db.String(20), default='')
    quantity_actual = db.Column(db.Integer, default=0)
    quantity_reserved = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    last_counted = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'zone': self.zone,
            'rack': self.rack,
            'shelf': self.shelf,
            'cell': self.cell,
            'location': f"{self.zone}-{self.rack}-{self.shelf}-{self.cell}".strip('-'),
            'quantity_actual': self.quantity_actual,
            'quantity_reserved': self.quantity_reserved,
            'quantity_available': self.quantity_actual - self.quantity_reserved,
            'notes': self.notes,
            'last_counted': self.last_counted.isoformat() if self.last_counted else None
        }

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    image_url = db.Column(db.String(500))
    is_main = db.Column(db.Boolean, default=False)

# ========== API РОУТЫ ==========

@app.route('/')
def index():
    """Главная страница"""
    return render_template('warehouse.html')

@app.route('/api/products', methods=['GET'])
def get_products():
    """Получить все товары"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    zone = request.args.get('zone')
    low_stock = request.args.get('low_stock', type=bool)
    
    query = Product.query
    
    if zone:
        query = query.join(WarehouseStock).filter(WarehouseStock.zone == zone)
    
    if low_stock:
        query = query.join(WarehouseStock).filter(
            (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) < 10
        )
    
    products = query.order_by(Product.article).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'items': [p.to_dict() for p in products.items],
        'total': products.total,
        'pages': products.pages,
        'current_page': page
    })

@app.route('/api/products/<article>', methods=['GET'])
def get_product(article):
    """Получить один товар по артикулу"""
    product = Product.query.filter_by(article=article).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    return jsonify(product.to_dict())

@app.route('/api/products', methods=['POST'])
def add_product():
    """Добавить новый товар"""
    data = request.get_json()
    
    # Проверяем обязательные поля
    if not data.get('article') or not data.get('title'):
        return jsonify({'error': 'Артикул и название обязательны'}), 400
    
    # Проверяем, нет ли уже такого товара
    existing = Product.query.filter_by(article=data['article']).first()
    if existing:
        return jsonify({'error': f'Товар с артикулом {data["article"]} уже существует'}), 409
    
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
    db.session.flush()  # Получаем ID до коммита
    
    # Добавляем изображения
    for i, img_url in enumerate(data.get('images', [])[:5]):
        image = ProductImage(
            product_id=product.id,
            image_url=img_url,
            is_main=(i == 0)
        )
        db.session.add(image)
    
    # Создаем складскую запись
    stock = WarehouseStock(product_id=product.id)
    db.session.add(stock)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Товар успешно добавлен',
        'product': product.to_dict()
    }), 201

@app.route('/api/products/<article>/stock', methods=['PUT'])
def update_stock(article):
    """Обновить складские данные"""
    product = Product.query.filter_by(article=article).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    
    data = request.get_json()
    
    if not product.stock:
        product.stock = WarehouseStock(product_id=product.id)
    
    # Обновляем поля
    if 'zone' in data:
        product.stock.zone = data['zone']
    if 'rack' in data:
        product.stock.rack = data['rack']
    if 'shelf' in data:
        product.stock.shelf = data['shelf']
    if 'cell' in data:
        product.stock.cell = data['cell']
    if 'quantity_actual' in data:
        product.stock.quantity_actual = int(data['quantity_actual'])
    if 'quantity_reserved' in data:
        product.stock.quantity_reserved = int(data['quantity_reserved'])
    if 'notes' in data:
        product.stock.notes = data['notes']
    
    product.stock.last_counted = datetime.now()
    product.updated_at = datetime.now()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Данные обновлены',
        'product': product.to_dict()
    })

@app.route('/api/products/search', methods=['GET'])
def search_products():
    """Поиск товаров"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    products = Product.query.filter(
        db.or_(
            Product.article.ilike(f'%{query}%'),
            Product.title.ilike(f'%{query}%'),
            Product.manufacturer.ilike(f'%{query}%')
        )
    ).limit(20).all()
    
    return jsonify([p.to_dict() for p in products])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Статистика склада"""
    total_products = Product.query.count()
    
    low_stock = db.session.query(Product).join(WarehouseStock).filter(
        (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) < 10,
        (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) > 0
    ).count()
    
    out_of_stock = db.session.query(Product).join(WarehouseStock).filter(
        (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) <= 0
    ).count()
    
    zones = db.session.query(WarehouseStock.zone).distinct().all()
    zones = [z[0] for z in zones if z[0]]
    
    total_items = db.session.query(db.func.sum(WarehouseStock.quantity_actual)).scalar() or 0
    
    return jsonify({
        'total_products': total_products,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'zones': zones,
        'total_items': int(total_items)
    })

@app.route('/api/export', methods=['GET'])
def export_data():
    """Экспорт данных в JSON"""
    products = Product.query.all()
    data = {
        'export_date': datetime.now().isoformat(),
        'products': [p.to_dict() for p in products]
    }
    
    filename = f"warehouse_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return send_file(filename, as_attachment=True)

# ========== HTML ШАБЛОН ==========

@app.route('/templates/warehouse.html')
def warehouse_template():
    return '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 Складской учет</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .stats-bar {
            display: flex;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        
        .stat-item {
            background: rgba(255,255,255,0.2);
            padding: 15px 25px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
        }
        
        .stat-label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
        }
        
        .controls {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            margin-bottom: 30px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .search-box {
            flex: 1;
            min-width: 300px;
            position: relative;
        }
        
        .search-box input {
            width: 100%;
            padding: 12px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .search-box input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #f8f9fa;
            color: #333;
            border: 2px solid #e0e0e0;
        }
        
        .btn-secondary:hover {
            background: #e9ecef;
        }
        
        .btn-warning {
            background: #ffc107;
            color: #212529;
        }
        
        .products-table {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            overflow: hidden;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: #f8f9fa;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #555;
            border-bottom: 2px solid #e0e0e0;
        }
        
        td {
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .product-image {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border-radius: 5px;
            border: 1px solid #e0e0e0;
        }
        
        .stock-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .stock-normal {
            background: #d4edda;
            color: #155724;
        }
        
        .stock-low {
            background: #fff3cd;
            color: #856404;
        }
        
        .stock-out {
            background: #f8d7da;
            color: #721c24;
        }
        
        .location-cell {
            font-family: monospace;
            background: #f8f9fa;
            padding: 5px 10px;
            border-radius: 5px;
            display: inline-block;
        }
        
        .actions {
            display: flex;
            gap: 8px;
        }
        
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: white;
            border-radius: 10px;
            width: 90%;
            max-width: 600px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .modal-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-body {
            padding: 25px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 14px;
        }
        
        .form-group input:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        .close-btn {
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        
        .empty-state-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        @media (max-width: 768px) {
            .container { padding: 15px; }
            .controls { flex-direction: column; }
            .search-box { min-width: 100%; }
            .stats-bar { justify-content: center; }
            table { font-size: 14px; }
            td, th { padding: 10px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 Складской учет</h1>
        <p>Локальная база данных</p>
        
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-value" id="statTotal">0</div>
                <div class="stat-label">Товаров</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="statLow">0</div>
                <div class="stat-label">Заканчивается</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="statOut">0</div>
                <div class="stat-label">Нет в наличии</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="statItems">0</div>
                <div class="stat-label">Единиц всего</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="controls">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 Поиск по артикулу или названию..." onkeyup="handleSearch(event)">
            </div>
            <button class="btn btn-primary" onclick="showImportModal()">➕ Импорт из snab-lift.ru</button>
            <button class="btn btn-secondary" onclick="loadProducts()">🔄 Обновить</button>
            <button class="btn btn-secondary" onclick="exportData()">📥 Экспорт</button>
        </div>
        
        <div class="products-table">
            <table>
                <thead>
                    <tr>
                        <th>Фото</th>
                        <th>Артикул</th>
                        <th>Название</th>
                        <th>Производитель</th>
                        <th>Место</th>
                        <th>Факт</th>
                        <th>Резерв</th>
                        <th>Доступно</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody id="productsTableBody">
                    <tr>
                        <td colspan="10" class="loading">Загрузка...</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- Модальное окно редактирования -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>✏️ Редактировать товар</h2>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Артикул</label>
                    <input type="text" id="editArticle" readonly>
                </div>
                <div class="form-group">
                    <label>Название</label>
                    <input type="text" id="editTitle" readonly>
                </div>
                
                <h3 style="margin: 25px 0 15px; color: #667eea;">📍 Местоположение на складе</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Зона</label>
                        <input type="text" id="editZone" placeholder="A, B, C...">
                    </div>
                    <div class="form-group">
                        <label>Стеллаж</label>
                        <input type="text" id="editRack" placeholder="12, ST-05...">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Полка</label>
                        <input type="text" id="editShelf" placeholder="3, B...">
                    </div>
                    <div class="form-group">
                        <label>Ячейка</label>
                        <input type="text" id="editCell" placeholder="45, 7-A...">
                    </div>
                </div>
                
                <h3 style="margin: 25px 0 15px; color: #667eea;">📦 Количество</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Фактически</label>
                        <input type="number" id="editActual" min="0">
                    </div>
                    <div class="form-group">
                        <label>Зарезервировано</label>
                        <input type="number" id="editReserved" min="0">
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Заметки</label>
                    <textarea id="editNotes" rows="3"></textarea>
                </div>
                
                <button class="btn btn-primary" onclick="saveProduct()" style="width: 100%;">
                    💾 Сохранить изменения
                </button>
            </div>
        </div>
    </div>
    
    <!-- Модальное окно импорта -->
    <div class="modal" id="importModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>➕ Импорт товара</h2>
                <button class="close-btn" onclick="closeImportModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Артикул или URL товара</label>
                    <input type="text" id="importInput" placeholder="2498 или https://snab-lift.ru/catalog/...">
                </div>
                <button class="btn btn-primary" onclick="importProduct()" style="width: 100%;">
                    🚀 Импортировать
                </button>
                <div id="importStatus" style="margin-top: 15px; text-align: center;"></div>
            </div>
        </div>
    </div>
    
    <script>
        let currentProduct = null;
        
        // Загрузка статистики
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                
                document.getElementById('statTotal').textContent = stats.total_products;
                document.getElementById('statLow').textContent = stats.low_stock;
                document.getElementById('statOut').textContent = stats.out_of_stock;
                document.getElementById('statItems').textContent = stats.total_items;
            } catch (e) {
                console.error('Ошибка загрузки статистики:', e);
            }
        }
        
        // Загрузка товаров
        async function loadProducts() {
            try {
                document.getElementById('productsTableBody').innerHTML = '<tr><td colspan="10" class="loading">Загрузка...</td></tr>';
                
                const response = await fetch('/api/products');
                const data = await response.json();
                
                renderProducts(data.items);
                loadStats();
            } catch (e) {
                console.error('Ошибка загрузки:', e);
                document.getElementById('productsTableBody').innerHTML = 
                    '<tr><td colspan="10" class="empty-state"><div class="empty-state-icon">⚠️</div>Ошибка загрузки данных</td></tr>';
            }
        }
        
        // Отображение товаров
        function renderProducts(products) {
            const tbody = document.getElementById('productsTableBody');
            
            if (products.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" class="empty-state"><div class="empty-state-icon">📦</div>Нет товаров. Добавьте первый товар через кнопку "Импорт"</td></tr>';
                return;
            }
            
            tbody.innerHTML = products.map(p => {
                const stock = p.stock || {};
                const available = stock.quantity_available || 0;
                
                let statusClass = 'stock-normal';
                let statusText = 'В наличии';
                
                if (available <= 0) {
                    statusClass = 'stock-out';
                    statusText = 'Нет в наличии';
                } else if (available < 10) {
                    statusClass = 'stock-low';
                    statusText = 'Заканчивается';
                }
                
                const location = stock.location && stock.location !== '---' ? stock.location : '—';
                
                return `
                    <tr>
                        <td>
                            ${p.images && p.images.length > 0 
                                ? `<img src="${p.images[0]}" class="product-image" alt="">`
                                : '<div style="width:60px;height:60px;background:#f0f0f0;border-radius:5px;display:flex;align-items:center;justify-content:center;">📷</div>'
                            }
                        </td>
                        <td><strong>${p.article}</strong></td>
                        <td>${p.title}</td>
                        <td>${p.manufacturer || '—'}</td>
                        <td><span class="location-cell">${location}</span></td>
                        <td>${stock.quantity_actual || 0}</td>
                        <td>${stock.quantity_reserved || 0}</td>
                        <td><strong>${available}</strong></td>
                        <td><span class="stock-badge ${statusClass}">${statusText}</span></td>
                        <td>
                            <div class="actions">
                                <button class="btn btn-primary btn-small" onclick="editProduct('${p.article}')">✏️</button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        }
        
        // Поиск
        async function handleSearch(event) {
            if (event.key === 'Enter') {
                const query = document.getElementById('searchInput').value.trim();
                if (!query) {
                    loadProducts();
                    return;
                }
                
                try {
                    const response = await fetch(`/api/products/search?q=${encodeURIComponent(query)}`);
                    const products = await response.json();
                    renderProducts(products);
                } catch (e) {
                    console.error('Ошибка поиска:', e);
                }
            }
        }
        
        // Редактирование товара
        async function editProduct(article) {
            try {
                const response = await fetch(`/api/products/${article}`);
                const product = await response.json();
                
                if (product.error) {
                    alert(product.error);
                    return;
                }
                
                currentProduct = product;
                
                document.getElementById('editArticle').value = product.article;
                document.getElementById('editTitle').value = product.title;
                document.getElementById('editZone').value = product.stock?.zone || '';
                document.getElementById('editRack').value = product.stock?.rack || '';
                document.getElementById('editShelf').value = product.stock?.shelf || '';
                document.getElementById('editCell').value = product.stock?.cell || '';
                document.getElementById('editActual').value = product.stock?.quantity_actual || 0;
                document.getElementById('editReserved').value = product.stock?.quantity_reserved || 0;
                document.getElementById('editNotes').value = product.stock?.notes || '';
                
                document.getElementById('editModal').classList.add('active');
            } catch (e) {
                console.error('Ошибка:', e);
                alert('Ошибка загрузки товара');
            }
        }
        
        // Сохранение товара
        async function saveProduct() {
            if (!currentProduct) return;
            
            const data = {
                zone: document.getElementById('editZone').value,
                rack: document.getElementById('editRack').value,
                shelf: document.getElementById('editShelf').value,
                cell: document.getElementById('editCell').value,
                quantity_actual: parseInt(document.getElementById('editActual').value) || 0,
                quantity_reserved: parseInt(document.getElementById('editReserved').value) || 0,
                notes: document.getElementById('editNotes').value
            };
            
            try {
                const response = await fetch(`/api/products/${currentProduct.article}/stock`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    closeModal();
                    loadProducts();
                    alert('✅ Данные сохранены');
                } else {
                    alert('❌ Ошибка сохранения');
                }
            } catch (e) {
                console.error('Ошибка:', e);
                alert('❌ Ошибка соединения');
            }
        }
        
        // Импорт товара
        async function importProduct() {
            const input = document.getElementById('importInput').value.trim();
            if (!input) {
                alert('Введите артикул или URL');
                return;
            }
            
            const statusDiv = document.getElementById('importStatus');
            statusDiv.innerHTML = '<div class="loading">⏳ Импортируем...</div>';
            
            try {
                // Используем warehouse_card.py для парсинга
                const response = await fetch('/api/import-proxy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: input})
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    statusDiv.innerHTML = `<div style="color: #28a745;">✅ ${result.message}</div>`;
                    setTimeout(() => {
                        closeImportModal();
                        loadProducts();
                    }, 1500);
                } else {
                    statusDiv.innerHTML = `<div style="color: #dc3545;">❌ ${result.error}</div>`;
                }
            } catch (e) {
                statusDiv.innerHTML = '<div style="color: #dc3545;">❌ Ошибка импорта</div>';
            }
        }
        
        // Экспорт данных
        function exportData() {
            window.location.href = '/api/export';
        }
        
        // Модальные окна
        function showImportModal() {
            document.getElementById('importModal').classList.add('active');
            document.getElementById('importInput').value = '';
            document.getElementById('importStatus').innerHTML = '';
        }
        
        function closeModal() {
            document.getElementById('editModal').classList.remove('active');
            currentProduct = null;
        }
        
        function closeImportModal() {
            document.getElementById('importModal').classList.remove('active');
        }
        
        // Закрытие модалок по клику вне
        window.onclick = function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.classList.remove('active');
            }
        }
        
        // Загрузка при старте
        loadProducts();
    </script>
</body>
</html>'''

# ========== ИМПОРТ ТОВАРОВ ==========

@app.route('/api/import-proxy', methods=['POST'])
def import_proxy():
    """Прокси для импорта товаров из snab-lift.ru"""
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Укажите артикул или URL'}), 400
    
    try:
        # Здесь должен быть код парсинга из warehouse_card.py
        # Для примера возвращаем тестовые данные
        
        # Проверяем, есть ли уже такой товар
        existing = Product.query.filter_by(article=query).first()
        if existing:
            return jsonify({'error': 'Товар уже существует в базе'}), 409
        
        # Создаем тестовый товар (в реальности здесь парсинг)
        product = Product(
            article=query,
            title=f"Товар {query}",
            manufacturer="Тестовый производитель",
            price="1000 ₽",
            url=f"https://snab-lift.ru/catalog/{query}.html"
        )
        
        db.session.add(product)
        db.session.flush()
        
        # Создаем складскую запись
        stock = WarehouseStock(product_id=product.id)
        db.session.add(stock)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Товар "{product.title}" добавлен',
            'product': product.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ========== ЗАПУСК ==========

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ База данных создана: warehouse.db")
        print("🚀 Запуск сервера: http://localhost:5000")
        print("\nКоманды:")
        print("  - Открыть интерфейс: open http://localhost:5000")
        print("  - Добавить товар: curl -X POST http://localhost:5000/api/products")
        print("  - Поиск: http://localhost:5000/api/products/search?q=2498")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
