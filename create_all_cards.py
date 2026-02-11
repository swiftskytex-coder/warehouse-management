#!/usr/bin/env python3
"""
Создание HTML карточек для всех товаров в базе
"""

from warehouse_system import app, db, Product, WarehouseStock
from warehouse_card import create_warehouse_card

with app.app_context():
    products = Product.query.all()
    
    print("=" * 70)
    print("📄 СОЗДАНИЕ HTML КАРТОЧЕК ДЛЯ ВСЕХ ТОВАРОВ")
    print("=" * 70)
    print()
    
    for product in products:
        # Подготавливаем данные для карточки
        product_data = {
            'url': product.url,
            'title': product.title,
            'price': product.price or '',
            'price_old': '',
            'sku': product.article,
            'article': product.article,
            'description': product.description or '',
            'images': [img.image_url for img in product.images],
            'specifications': {},
            'manufacturer': product.manufacturer or '',
            'category': product.category or '',
            'weight': product.weight or '',
            'dimensions': {},
            'in_stock': False
        }
        
        # Добавляем характеристики из JSON
        if hasattr(product, 'specifications') and product.specifications:
            try:
                import json
                product_data['specifications'] = json.loads(product.specifications)
            except:
                pass
        
        # Добавляем складские данные
        if product.stock:
            stock = product.stock
            product_data['warehouse_zone'] = stock.zone
            product_data['warehouse_location'] = f"{stock.rack}-{stock.shelf}-{stock.cell}"
            product_data['actual_quantity'] = stock.quantity_actual
            product_data['reserved_quantity'] = stock.quantity_reserved
            product_data['in_stock'] = (stock.quantity_actual - stock.quantity_reserved) > 0
            product_data['stock_quantity'] = stock.quantity_actual
        else:
            product_data['stock_quantity'] = ''
        
        # Добавляем delivery_info (пустой список)
        product_data['delivery_info'] = []
        
        # Создаем карточку
        filename = create_warehouse_card(product_data)
        print(f"✅ {product.article}: {filename}")
    
    print()
    print("=" * 70)
    print(f"📦 Создано карточек: {len(products)}")
    print("=" * 70)
    print()
    print("Открыть карточки:")
    for p in products:
        safe_title = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in p.title[:30]])
        print(f"open warehouse_card_{p.article}_{safe_title}.html")
