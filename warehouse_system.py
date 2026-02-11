#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальная база данных склада
Полная система управления карточками товаров
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os
import re
from urllib.parse import urlparse

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///warehouse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'warehouse-secret-key-2024'
app.config['JSON_AS_ASCII'] = False

# Регистрируем фильтр fromjson для Jinja2
@app.template_filter('fromjson')
def fromjson_filter(value):
    """Преобразует JSON строку в объект Python"""
    if not value:
        return {}
    try:
        return json.loads(value)
    except:
        return {}

db = SQLAlchemy(app)

# ========== МОДЕЛИ БАЗЫ ДАННЫХ ==========

class Product(db.Model):
    """Таблица товаров"""
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
    specifications = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Связи
    stock = db.relationship('WarehouseStock', backref='product', uselist=False, lazy=True, cascade='all, delete')
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade='all, delete')
    movements = db.relationship('StockMovement', backref='product', lazy=True, cascade='all, delete')
    
    def to_dict(self, include_stock=True, include_images=True):
        data = {
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
            'specifications': json.loads(self.specifications) if self.specifications else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_stock and self.stock:
            data['stock'] = self.stock.to_dict()
        
        if include_images:
            data['images'] = [img.image_url for img in self.images]
        
        return data

class WarehouseStock(db.Model):
    """Складские остатки"""
    __tablename__ = 'warehouse_stock'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), unique=True)
    zone = db.Column(db.String(20), default='')
    rack = db.Column(db.String(30), default='')
    shelf = db.Column(db.String(30), default='')
    cell = db.Column(db.String(30), default='')
    quantity_actual = db.Column(db.Integer, default=0)
    quantity_reserved = db.Column(db.Integer, default=0)
    quantity_min = db.Column(db.Integer, default=0)  # Минимальный остаток
    quantity_max = db.Column(db.Integer, default=0)  # Максимальный остаток
    notes = db.Column(db.Text)
    last_counted = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        available = self.quantity_actual - self.quantity_reserved
        return {
            'zone': self.zone,
            'rack': self.rack,
            'shelf': self.shelf,
            'cell': self.cell,
            'location': f"{self.zone}-{self.rack}-{self.shelf}-{self.cell}".strip('-'),
            'quantity_actual': self.quantity_actual,
            'quantity_reserved': self.quantity_reserved,
            'quantity_available': available,
            'quantity_min': self.quantity_min,
            'quantity_max': self.quantity_max,
            'notes': self.notes,
            'last_counted': self.last_counted.isoformat() if self.last_counted else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class ProductImage(db.Model):
    """Изображения товаров"""
    __tablename__ = 'product_images'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    image_url = db.Column(db.String(500))
    is_main = db.Column(db.Boolean, default=False)
    filename = db.Column(db.String(200))

class StockMovement(db.Model):
    """Движение товаров (приход/расход)"""
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    movement_type = db.Column(db.String(20))  # 'in', 'out', 'reserve', 'correction'
    quantity = db.Column(db.Integer)
    reason = db.Column(db.String(200))
    user_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)

class Category(db.Model):
    """Категории товаров"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))

# ========== API МАРШРУТЫ ==========

@app.route('/')
def index():
    """Главная страница"""
    return render_template('warehouse_dashboard.html')

@app.route('/api/products', methods=['GET'])
def get_products():
    """Получить список товаров с пагинацией и фильтрами"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        zone = request.args.get('zone')
        manufacturer = request.args.get('manufacturer')
        low_stock = request.args.get('low_stock', type=lambda x: x.lower() == 'true')
        search = request.args.get('search', '').strip()
        
        query = Product.query
        
        # Фильтр по зоне
        if zone:
            query = query.join(WarehouseStock).filter(WarehouseStock.zone == zone)
        
        # Фильтр по производителю
        if manufacturer:
            query = query.filter(Product.manufacturer == manufacturer)
        
        # Фильтр по низким остаткам
        if low_stock:
            query = query.join(WarehouseStock).filter(
                (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) < WarehouseStock.quantity_min,
                WarehouseStock.quantity_min > 0
            )
        
        # Поиск
        if search:
            search_filter = db.or_(
                Product.article.ilike(f'%{search}%'),
                Product.title.ilike(f'%{search}%'),
                Product.manufacturer.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Сортировка по артикулу
        query = query.order_by(Product.article)
        
        # Пагинация
        products = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'items': [p.to_dict() for p in products.items],
            'total': products.total,
            'pages': products.pages,
            'current_page': page,
            'has_next': products.has_next,
            'has_prev': products.has_prev
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/<article>', methods=['GET'])
def get_product(article):
    """Получить один товар по артикулу"""
    try:
        product = Product.query.filter_by(article=article).first()
        if not product:
            return jsonify({'success': False, 'error': 'Товар не найден'}), 404
        
        return jsonify({
            'success': True,
            'product': product.to_dict(include_stock=True, include_images=True)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products', methods=['POST'])
def add_product():
    """Добавить новый товар"""
    try:
        data = request.get_json()
        
        # Проверяем обязательные поля
        if not data.get('article') or not data.get('title'):
            return jsonify({'success': False, 'error': 'Артикул и название обязательны'}), 400
        
        # Проверяем, нет ли уже такого товара
        existing = Product.query.filter_by(article=data['article']).first()
        if existing:
            return jsonify({
                'success': False, 
                'error': f'Товар с артикулом {data["article"]} уже существует',
                'existing_id': existing.id
            }), 409
        
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
            dimensions=data.get('dimensions'),
            specifications=json.dumps(data.get('specifications', {}), ensure_ascii=False)
        )
        
        db.session.add(product)
        db.session.flush()  # Получаем ID
        
        # Добавляем изображения
        for i, img_url in enumerate(data.get('images', [])[:10]):
            image = ProductImage(
                product_id=product.id,
                image_url=img_url,
                is_main=(i == 0)
            )
            db.session.add(image)
        
        # Создаем складскую запись
        stock_data = data.get('stock', {})
        stock = WarehouseStock(
            product_id=product.id,
            zone=stock_data.get('zone', ''),
            rack=stock_data.get('rack', ''),
            shelf=stock_data.get('shelf', ''),
            cell=stock_data.get('cell', ''),
            quantity_actual=stock_data.get('quantity_actual', 0),
            quantity_reserved=stock_data.get('quantity_reserved', 0),
            quantity_min=stock_data.get('quantity_min', 0),
            quantity_max=stock_data.get('quantity_max', 0),
            notes=stock_data.get('notes', '')
        )
        db.session.add(stock)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Товар успешно добавлен',
            'product': product.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/<article>/stock', methods=['PUT'])
def update_stock(article):
    """Обновить складские данные"""
    try:
        product = Product.query.filter_by(article=article).first()
        if not product:
            return jsonify({'success': False, 'error': 'Товар не найден'}), 404
        
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
        if 'quantity_min' in data:
            product.stock.quantity_min = int(data['quantity_min'])
        if 'quantity_max' in data:
            product.stock.quantity_max = int(data['quantity_max'])
        if 'notes' in data:
            product.stock.notes = data['notes']
        
        product.stock.last_counted = datetime.now()
        product.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Складские данные обновлены',
            'product': product.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/search', methods=['GET'])
def search_products():
    """Поиск товаров"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'success': True, 'items': []})
        
        products = Product.query.filter(
            db.or_(
                Product.article.ilike(f'%{query}%'),
                Product.title.ilike(f'%{query}%'),
                Product.manufacturer.ilike(f'%{query}%')
            )
        ).limit(20).all()
        
        return jsonify({
            'success': True,
            'items': [p.to_dict() for p in products]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Статистика склада"""
    try:
        total_products = Product.query.count()
        
        # Товары с низким остатком
        low_stock = db.session.query(Product).join(WarehouseStock).filter(
            (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) < WarehouseStock.quantity_min,
            WarehouseStock.quantity_min > 0
        ).count()
        
        # Отсутствующие товары
        out_of_stock = db.session.query(Product).join(WarehouseStock).filter(
            (WarehouseStock.quantity_actual - WarehouseStock.quantity_reserved) <= 0
        ).count()
        
        # Всего единиц
        total_items = db.session.query(db.func.sum(WarehouseStock.quantity_actual)).scalar() or 0
        
        # Зоны склада
        zones = db.session.query(WarehouseStock.zone).distinct().all()
        zones_list = [z[0] for z in zones if z[0]]
        
        # Производители
        manufacturers = db.session.query(Product.manufacturer).distinct().all()
        manufacturers_list = [m[0] for m in manufacturers if m[0]]
        
        return jsonify({
            'success': True,
            'total_products': total_products,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'total_items': int(total_items),
            'zones': zones_list,
            'manufacturers': manufacturers_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/<article>', methods=['DELETE'])
def delete_product(article):
    """Удалить товар"""
    try:
        product = Product.query.filter_by(article=article).first()
        if not product:
            return jsonify({'success': False, 'error': 'Товар не найден'}), 404
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Товар {article} удален'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/json', methods=['GET'])
def export_json():
    """Экспорт всех данных в JSON"""
    try:
        products = Product.query.all()
        data = {
            'export_date': datetime.now().isoformat(),
            'total': len(products),
            'products': [p.to_dict() for p in products]
        }
        
        filename = f"warehouse_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ИМПОРТ ИЗ SNAB-LIFT.RU ==========

@app.route('/api/import/snablift', methods=['POST'])
def import_from_snablift():
    """Импорт товара с snab-lift.ru"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': 'Укажите артикул или URL'}), 400
        
        # Импортируем парсер
        from warehouse_card import create_driver, parse_product_page, is_url, find_product_by_article
        
        driver = create_driver()
        
        try:
            # Определяем тип входных данных
            if is_url(query):
                product_url = query
            else:
                product_url = find_product_by_article(driver, query)
                if not product_url:
                    return jsonify({'success': False, 'error': 'Товар не найден на snab-lift.ru'}), 404
            
            # Парсим товар
            product_data = parse_product_page(driver, product_url)
            
            # Проверяем, нет ли уже такого товара
            existing = Product.query.filter_by(article=product_data['article']).first()
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'Товар {product_data["article"]} уже существует в базе',
                    'existing_product': existing.to_dict()
                }), 409
            
            # Создаем товар в базе
            product = Product(
                article=product_data['article'],
                title=product_data['title'],
                manufacturer=product_data.get('manufacturer'),
                category=product_data.get('category'),
                price=product_data.get('price'),
                description=product_data.get('description'),
                url=product_data['url'],
                weight=product_data.get('weight'),
                dimensions=', '.join([f"{k}: {v}" for k, v in product_data.get('dimensions', {}).items()]),
                specifications=json.dumps(product_data.get('specifications', {}), ensure_ascii=False)
            )
            
            db.session.add(product)
            db.session.flush()
            
            # Добавляем изображения
            for i, img_url in enumerate(product_data.get('images', [])[:10]):
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
                'success': True,
                'message': 'Товар успешно импортирован',
                'product': product.to_dict()
            })
            
        finally:
            driver.quit()
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/import/batch', methods=['POST'])
def batch_import():
    """Массовый импорт товаров"""
    try:
        data = request.get_json()
        items = data.get('items', [])
        
        if not items:
            return jsonify({'success': False, 'error': 'Список товаров пуст'}), 400
        
        results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
        
        from warehouse_card import create_driver, parse_product_page, find_product_by_article
        
        driver = create_driver()
        
        try:
            for item in items:
                query = item.strip()
                if not query:
                    continue
                
                try:
                    # Проверяем, существует ли товар
                    existing = Product.query.filter(
                        db.or_(
                            Product.article == query,
                            Product.url == query
                        )
                    ).first()
                    
                    if existing:
                        results['skipped'].append({
                            'query': query,
                            'reason': 'Уже существует',
                            'article': existing.article
                        })
                        continue
                    
                    # Парсим товар
                    if query.startswith('http'):
                        product_url = query
                    else:
                        product_url = find_product_by_article(driver, query)
                    
                    if not product_url:
                        results['failed'].append({
                            'query': query,
                            'reason': 'Не найден на сайте'
                        })
                        continue
                    
                    product_data = parse_product_page(driver, product_url)
                    
                    # Создаем товар
                    product = Product(
                        article=product_data['article'],
                        title=product_data['title'],
                        manufacturer=product_data.get('manufacturer'),
                        category=product_data.get('category'),
                        price=product_data.get('price'),
                        description=product_data.get('description'),
                        url=product_data['url'],
                        weight=product_data.get('weight'),
                        dimensions=', '.join([f"{k}: {v}" for k, v in product_data.get('dimensions', {}).items()]),
                        specifications=json.dumps(product_data.get('specifications', {}), ensure_ascii=False)
                    )
                    
                    db.session.add(product)
                    db.session.flush()
                    
                    # Добавляем изображения
                    for i, img_url in enumerate(product_data.get('images', [])[:5]):
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
                    
                    results['success'].append({
                        'query': query,
                        'article': product_data['article'],
                        'title': product_data['title']
                    })
                    
                except Exception as e:
                    db.session.rollback()
                    results['failed'].append({
                        'query': query,
                        'reason': str(e)
                    })
            
            return jsonify({
                'success': True,
                'results': results,
                'summary': {
                    'total': len(items),
                    'imported': len(results['success']),
                    'failed': len(results['failed']),
                    'skipped': len(results['skipped'])
                }
            })
            
        finally:
            driver.quit()
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== HTML КАРТОЧКИ ==========

@app.route('/card/<article>')
def product_card(article):
    """HTML карточка товара для печати"""
    product = Product.query.filter_by(article=article).first()
    if not product:
        return "Товар не найден", 404
    
    return render_template('product_card.html', product=product)

# ========== ИИ-ПОИСК ==========

# Импортируем и регистрируем ИИ-поиск (если есть API ключ)
try:
    from ai_search_api import ai_search_bp
    app.register_blueprint(ai_search_bp)
    print("✅ ИИ-поиск подключен")
except Exception as e:
    print(f"⚠️ ИИ-поиск не подключен: {e}")

# ========== ЗАПУСК ==========

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("=" * 70)
        print("✅ ЛОКАЛЬНАЯ БАЗА ДАННЫХ СКЛАДА")
        print("=" * 70)
        print("\n📁 База данных: warehouse.db")
        print("🌐 Веб-интерфейс: http://localhost:5000")
        print("\n📋 API Endpoints:")
        print("  GET  /api/products - Список товаров")
        print("  GET  /api/products/<article> - Один товар")
        print("  POST /api/products - Добавить товар")
        print("  PUT  /api/products/<article>/stock - Обновить склад")
        print("  POST /api/import/snablift - Импорт с snab-lift.ru")
        print("  POST /api/import/batch - Массовый импорт")
        print("\n💡 Примеры:")
        print("  curl http://localhost:5000/api/products")
        print("  curl -X POST http://localhost:5000/api/import/snablift -d '{\"query\":\"2498\"}'")
        print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=False)

# ========== API ДЛЯ ОЗВУЧКИ ==========

@app.route('/api/speak', methods=['POST'])
def speak_text():
    """Озвучивает текст через macOS say"""
    try:
        import subprocess
        import platform
        
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'success': False, 'error': 'Пустой текст'})
        
        # Проверяем что это macOS
        if platform.system() == 'Darwin':
            # Ограничиваем длину
            text = text[:500]
            
            # Запускаем say в фоне
            subprocess.Popen(['say', '-r', '180', text], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            return jsonify({'success': True, 'message': 'Озвучивается'})
        else:
            return jsonify({'success': False, 'error': 'Озвучка доступна только на macOS'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
