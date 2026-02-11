#!/usr/bin/env python3
"""
Скрипт для импорта товаров из snab-lift.ru в локальную базу данных
"""

import sys
import json
from sqlalchemy import or_
from warehouse_system import app, db, Product, WarehouseStock, ProductImage
from warehouse_card import create_driver, parse_product_page, find_product_by_article, is_url

def import_single_product(query):
    """Импорт одного товара"""
    print("=" * 70)
    print(f"📦 ИМПОРТ ТОВАРА: {query}")
    print("=" * 70)
    
    driver = create_driver()
    
    try:
        # Определяем тип входных данных
        if is_url(query):
            product_url = query
        else:
            print(f"\n🔍 Поиск по артикулу: {query}")
            product_url = find_product_by_article(driver, query)
            
            if not product_url:
                print(f"❌ Товар не найден на сайте")
                return False
        
        # Парсим товар
        print(f"📄 Парсинг страницы...")
        product_data = parse_product_page(driver, product_url)
        
        with app.app_context():
            # Проверяем, существует ли товар
            existing = Product.query.filter_by(article=product_data['article']).first()
            if existing:
                print(f"⚠️ Товар {product_data['article']} уже существует в базе")
                print(f"   Название: {existing.title}")
                return False
            
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
            
            print(f"\n✅ ТОВАР УСПЕШНО ИМПОРТИРОВАН")
            print(f"   Артикул: {product.article}")
            print(f"   Название: {product.title}")
            print(f"   Производитель: {product.manufacturer or '—'}")
            print(f"   Цена: {product.price or '—'}")
            print(f"   Фото: {len(product.images)} шт.")
            print(f"   ID в базе: {product.id}")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Ошибка импорта: {e}")
        try:
            with app.app_context():
                db.session.rollback()
        except:
            pass
        return False
        
    finally:
        driver.quit()

def import_from_list(items):
    """Массовый импорт из списка"""
    print("=" * 70)
    print(f"📦 МАССОВЫЙ ИМПОРТ: {len(items)} товаров")
    print("=" * 70)
    
    success = []
    failed = []
    skipped = []
    
    driver = create_driver()
    
    try:
        for i, item in enumerate(items, 1):
            query = item.strip()
            if not query:
                continue
            
            print(f"\n[{i}/{len(items)}] {query}")
            
            try:
                # Проверяем, существует ли товар
                with app.app_context():
                    existing = Product.query.filter(
                        or_(
                            Product.article == query,
                            Product.url == query if is_url(query) else False
                        )
                    ).first()
                    
                    if existing:
                        print(f"   ⏭️ Уже существует")
                        skipped.append({'query': query, 'article': existing.article})
                        continue
                
                # Парсим товар
                if is_url(query):
                    product_url = query
                else:
                    product_url = find_product_by_article(driver, query)
                    if not product_url:
                        print(f"   ❌ Не найден на сайте")
                        failed.append({'query': query, 'reason': 'Не найден'})
                        continue
                
                product_data = parse_product_page(driver, product_url)
                
                # Сохраняем в базу
                with app.app_context():
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
                    for j, img_url in enumerate(product_data.get('images', [])[:5]):
                        image = ProductImage(
                            product_id=product.id,
                            image_url=img_url,
                            is_main=(j == 0)
                        )
                        db.session.add(image)
                    
                    # Создаем складскую запись
                    stock = WarehouseStock(product_id=product.id)
                    db.session.add(stock)
                    
                    db.session.commit()
                    
                    print(f"   ✅ Импортирован: {product_data['title'][:50]}...")
                    success.append({'query': query, 'article': product_data['article']})
                    
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                failed.append({'query': query, 'reason': str(e)})
                db.session.rollback()
                
    finally:
        driver.quit()
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ИМПОРТА")
    print("=" * 70)
    print(f"✅ Успешно: {len(success)}")
    print(f"⏭️ Пропущено: {len(skipped)}")
    print(f"❌ Ошибок: {len(failed)}")
    
    if failed:
        print("\n❌ Список ошибок:")
        for item in failed:
            print(f"   {item['query']}: {item['reason']}")

def main():
    # Создаем таблицы базы данных
    print("📦 Инициализация базы данных...")
    with app.app_context():
        db.create_all()
        print("✅ База данных готова\n")
    
    # Импорт одного товара
    if len(sys.argv) > 1:
        query = sys.argv[1]
        import_single_product(query)
    else:
        print("❌ Ошибка: укажите артикул или URL")
        print("\nПримеры:")
        print("  python import_product.py 2498")
        print("  python import_product.py \"https://snab-lift.ru/catalog/.../product.html\"")
        print("\nДля массового импорта создайте файл items.txt с артикулами/URL")
        print("и запустите:")
        print("  python import_product.py --file items.txt")

if __name__ == "__main__":
    main()
