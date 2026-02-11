#!/usr/bin/env python3
"""
Универсальный создатель карточек товара для склада
Работает с артикулом или прямой ссылкой
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import time
import urllib.parse
import sys
import os
from urllib.parse import urlparse

BASE_URL = "https://snab-lift.ru"
SEARCH_URL = f"{BASE_URL}/rezultatyi-poiska.html"

def create_driver():
    """Создает headless Chrome"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''Object.defineProperty(navigator, 'webdriver', {get: () => undefined})'''
    })
    
    return driver

def is_url(string):
    """Проверяет, является ли строка URL"""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except:
        return False

def find_product_by_article(driver, article):
    """Ищет товар по артикулу через поиск"""
    
    search_url = f"{SEARCH_URL}?query={urllib.parse.quote(str(article))}"
    print(f"🔍 Поиск по артикулу: {article}")
    
    driver.get(search_url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Ищем ссылки на товары
    links = soup.find_all('a', href=True)
    product_links = []
    
    for link in links:
        href = link.get('href', '')
        if '/catalog/' in href and '.html' in href:
            if href.startswith('/'):
                href = BASE_URL + href
            product_links.append({
                'url': href,
                'title': link.get_text(strip=True)
            })
    
    # Убираем дубликаты
    seen = set()
    unique_links = []
    for item in product_links:
        if item['url'] not in seen:
            seen.add(item['url'])
            unique_links.append(item)
    
    return unique_links[0]['url'] if unique_links else None

def parse_product_page(driver, url):
    """Парсит страницу товара со всеми складскими данными"""
    
    print(f"\n📄 Парсинг: {url}")
    driver.get(url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    product = {
        'url': url,
        'title': '',
        'price': '',
        'price_old': '',
        'sku': '',
        'article': '',
        'description': '',
        'images': [],
        'specifications': {},
        'stock_info': {},
        'in_stock': False,
        'stock_quantity': '',
        'warehouse_location': '',  # Положение на складе (стеллаж, полка, ячейка)
        'warehouse_zone': '',      # Зона склада
        'actual_quantity': '',     # Фактическое количество
        'reserved_quantity': '',   # Зарезервировано
        'delivery_info': [],
        'manufacturer': '',
        'category': '',
        'weight': '',
        'dimensions': {}
    }
    
    # Название
    title_elem = soup.find('h1')
    if title_elem:
        product['title'] = title_elem.get_text(strip=True)
    
    # Цена
    try:
        price_elem = driver.find_element(By.CSS_SELECTOR, '.price_value')
        if price_elem:
            product['price'] = price_elem.text.strip()
    except:
        pass
    
    # Старая цена (если есть скидка)
    try:
        old_price = soup.select_one('.old_price')
        if old_price:
            product['price_old'] = old_price.get_text(strip=True)
    except:
        pass
    
    # Артикул/SKU
    sku_elem = soup.select_one('.product-article')
    if sku_elem:
        product['sku'] = sku_elem.get_text(strip=True)
        product['article'] = product['sku']
    
    # Описание
    desc_elem = soup.select_one('#prod-desc')
    if desc_elem:
        product['description'] = desc_elem.get_text(strip=True)
    
    # Производитель
    vendor_elem = soup.select_one('.product-sidebar-vendor')
    if vendor_elem:
        vendor_text = vendor_elem.get_text(strip=True)
        if 'Производитель:' in vendor_text:
            product['manufacturer'] = vendor_text.replace('Производитель:', '').strip()
    
    # Характеристики и размеры
    char_rows = soup.select('.product-sidebar-char')
    for row in char_rows:
        spans = row.find_all('span')
        if len(spans) >= 2:
            key = spans[0].get_text(strip=True).replace(':', '')
            value = spans[1].get_text(strip=True)
            if key and value:
                product['specifications'][key] = value
                # Выделяем размеры и вес
                if key.lower() in ['высота', 'ширина', 'длина', 'диаметр']:
                    product['dimensions'][key] = value
                elif key.lower() == 'вес':
                    product['weight'] = value
    
    # Информация о доставке
    delivery_blocks = soup.select('.product-sidebar-delivery')
    for block in delivery_blocks:
        title = block.find('div', class_='product-sidebar-title')
        content = block.find('div')
        if title and content:
            product['delivery_info'].append({
                'title': title.get_text(strip=True),
                'content': content.get_text(strip=True)
            })
    
    # Наличие на складе
    stock_elem = soup.select_one('.availability') or soup.select_one('.in-stock')
    if stock_elem:
        stock_text = stock_elem.get_text(strip=True).lower()
        product['in_stock'] = 'в наличии' in stock_text or 'есть' in stock_text
        product['stock_info']['status'] = stock_elem.get_text(strip=True)
    
    # Количество на складе (если есть)
    try:
        qty_elem = soup.select_one('.stock-quantity') or soup.select_one('.product-quantity')
        if qty_elem:
            product['stock_quantity'] = qty_elem.get_text(strip=True)
    except:
        pass
    
    # Категория товара
    breadcrumbs = soup.select('.breadcrumb a, .breadcrumbs a')
    if breadcrumbs:
        product['category'] = ' > '.join([a.get_text(strip=True) for a in breadcrumbs[-2:]])
    
    # Изображения
    img_elems = soup.find_all('img')
    for img in img_elems:
        src = img.get('src') or img.get('data-src')
        if src and any(keyword in src.lower() for keyword in ['products', 'upload']):
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                if src.startswith('/'):
                    src = BASE_URL + src
                elif src.startswith('//'):
                    src = 'https:' + src
                if src not in product['images']:
                    product['images'].append(src)
    
    return product

def create_warehouse_card(product):
    """Создает HTML карточку товара для склада с полной информацией"""
    
    # Генерируем галерею
    gallery_html = ""
    for i, img in enumerate(product['images'][:6]):
        gallery_html += f'<img src="{img}" onclick="changeMainImage(\'{img}\')" class="gallery-thumb">'
    
    # Характеристики
    specs_html = ""
    for key, value in product['specifications'].items():
        specs_html += f'<div class="spec-row"><span class="spec-name">{key}</span><span class="spec-value">{value}</span></div>'
    
    # Информация о доставке
    delivery_html = ""
    for item in product['delivery_info'][:3]:
        delivery_html += f'<div class="delivery-item"><strong>{item["title"]}</strong><br>{item["content"][:100]}...</div>'
    
    # Статус наличия
    stock_class = "in-stock" if product['in_stock'] else "out-of-stock"
    stock_text = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
    
    # Размеры для этикетки
    dimensions_str = " | ".join([f"{k}: {v}" for k, v in product['dimensions'].items()])
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>СКЛАД: {product['title']} | Арт. {product['article']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        /* Шапка */
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .header-left {{
            flex: 1;
            margin-right: 20px;
        }}
        
        .header-left h1 {{
            font-size: 1.4em;
            margin-bottom: 10px;
            line-height: 1.3;
            word-wrap: break-word;
        }}
        
        .title-input {{
            width: 100%;
            padding: 10px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 1.4em;
            font-weight: bold;
            line-height: 1.3;
            font-family: inherit;
        }}
        
        .title-input:focus {{
            outline: none;
            border-color: #ff6b35;
            background: rgba(255,255,255,0.2);
        }}
        
        .title-input::placeholder {{
            color: rgba(255,255,255,0.6);
        }}
        
        .article-badge {{
            background: rgba(255,255,255,0.2);
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 0.9em;
            font-weight: bold;
            white-space: nowrap;
        }}
        
        .warehouse-label {{
            background: #ff6b35;
            color: white;
            padding: 5px 15px;
            border-radius: 5px;
            font-size: 0.9em;
            margin-top: 10px;
            display: inline-block;
        }}
        
        /* Основной контент */
        .main-content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            padding: 30px;
        }}
        
        /* Левая колонка - фото */
        .photo-section {{ }}
        
        .main-image-container {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            text-align: center;
        }}
        
        .main-image {{
            max-width: 100%;
            max-height: 400px;
            object-fit: contain;
        }}
        
        .gallery {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 10px;
        }}
        
        .gallery-thumb {{
            width: 100%;
            height: 80px;
            object-fit: cover;
            border-radius: 5px;
            cursor: pointer;
            border: 2px solid #e0e0e0;
            transition: all 0.3s;
        }}
        
        .gallery-thumb:hover {{ border-color: #2a5298; }}
        
        /* Правая колонка - информация */
        .info-section {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        /* Цена */
        .price-block {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .price-current {{
            font-size: 3em;
            font-weight: bold;
        }}
        
        .price-old {{
            font-size: 1.2em;
            text-decoration: line-through;
            opacity: 0.7;
            margin-top: 5px;
        }}
        
        /* Статус наличия */
        .stock-block {{
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            font-size: 1.3em;
            font-weight: bold;
        }}
        
        .in-stock {{
            background: #d4edda;
            color: #155724;
            border: 2px solid #28a745;
        }}
        
        .out-of-stock {{
            background: #f8d7da;
            color: #721c24;
            border: 2px solid #dc3545;
        }}
        
        /* Производитель и категория */
        .meta-block {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #2a5298;
        }}
        
        .meta-item {{
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        
        .meta-label {{
            font-weight: bold;
            color: #2a5298;
        }}
        
        /* Характеристики */
        .specs-section {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }}
        
        .specs-header {{
            background: #2a5298;
            color: white;
            padding: 15px 20px;
            font-size: 1.2em;
            font-weight: bold;
        }}
        
        .spec-row {{
            display: flex;
            justify-content: space-between;
            padding: 12px 20px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .spec-row:last-child {{ border-bottom: none; }}
        
        .spec-name {{
            font-weight: 600;
            color: #2a5298;
        }}
        
        /* Этикетка для склада */
        .label-section {{
            grid-column: 1 / -1;
            background: #fff3cd;
            border: 2px dashed #ffc107;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }}
        
        .label-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #856404;
            margin-bottom: 15px;
        }}
        
        .label-content {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            font-family: monospace;
            font-size: 1.1em;
        }}
        
        .label-item {{
            background: white;
            padding: 10px;
            border-radius: 5px;
        }}
        
        .qr-placeholder {{
            width: 100px;
            height: 100px;
            background: #e0e0e0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8em;
            color: #666;
        }}
        
        /* Доставка */
        .delivery-section {{
            grid-column: 1 / -1;
            background: #e7f3ff;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }}
        
        .delivery-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #004085;
            margin-bottom: 15px;
        }}
        
        .delivery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }}
        
        .delivery-item {{
            background: white;
            padding: 15px;
            border-radius: 5px;
        }}
        
        /* Описание */
        .description-section {{
            grid-column: 1 / -1;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
            line-height: 1.8;
        }}
        
        .description-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #2a5298;
            margin-bottom: 10px;
        }}
        
        /* Подвал */
        .footer {{
            background: #2a5298;
            color: white;
            padding: 20px;
            text-align: center;
        }}
        
        .footer a {{ color: #fff; }}
        
        /* 📍 Складское местоположение */
        .warehouse-location-block {{
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 10px;
            padding: 20px;
        }}
        
        .warehouse-location-title {{
            font-size: 1.1em;
            font-weight: bold;
            color: #856404;
            margin-bottom: 15px;
            text-align: center;
        }}
        
        .warehouse-field {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            gap: 10px;
        }}
        
        .warehouse-label-text {{
            font-weight: 600;
            color: #856404;
            min-width: 100px;
            font-size: 0.95em;
        }}
        
        .warehouse-input {{
            flex: 1;
            padding: 8px 12px;
            border: 2px solid #ffc107;
            border-radius: 5px;
            font-size: 1em;
            background: white;
        }}
        
        .warehouse-input:focus {{
            outline: none;
            border-color: #ff6b35;
            box-shadow: 0 0 0 3px rgba(255, 193, 7, 0.3);
        }}
        
        /* 📦 Количество */
        .quantity-block {{
            background: #d1ecf1;
            border: 2px solid #17a2b8;
            border-radius: 10px;
            padding: 20px;
        }}
        
        .quantity-title {{
            font-size: 1.1em;
            font-weight: bold;
            color: #0c5460;
            margin-bottom: 15px;
            text-align: center;
        }}
        
        .quantity-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .quantity-item {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        
        .quantity-label {{
            font-weight: 600;
            color: #0c5460;
            font-size: 0.9em;
        }}
        
        .quantity-input {{
            width: 100%;
            padding: 10px;
            border: 2px solid #17a2b8;
            border-radius: 5px;
            font-size: 1.2em;
            font-weight: bold;
            text-align: center;
            background: white;
        }}
        
        .quantity-input:focus {{
            outline: none;
            border-color: #0c5460;
            box-shadow: 0 0 0 3px rgba(23, 162, 184, 0.3);
        }}
        
        .quantity-unit {{
            font-size: 0.9em;
            color: #6c757d;
            text-align: center;
        }}
        
        .quantity-summary {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            font-size: 1.1em;
            margin-top: 10px;
            border: 2px solid #28a745;
        }}
        
        .available-count {{
            font-size: 1.5em;
            font-weight: bold;
            color: #28a745;
        }}
        
        .last-updated {{
            margin-top: 10px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }}
        
        .date-input {{
            padding: 5px 10px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        
        @media print {{
            body {{ background: white; }}
            .container {{ box-shadow: none; }}
            .gallery {{ display: none; }}
        }}
        
        @media (max-width: 900px) {{
            .main-content {{ grid-template-columns: 1fr; }}
            .header {{ flex-direction: column; text-align: center; }}
            .label-content {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Шапка -->
        <div class="header">
            <div class="header-left">
                <div class="warehouse-label">📦 КАРТОЧКА ТОВАРА ДЛЯ СКЛАДА</div>
                <input type="text" class="title-input" id="productTitle" value="{product['title']}" placeholder="Название товара">
            </div>
            <div class="article-badge">
                Арт. {product['article']}
            </div>
        </div>
        
        <!-- Основной контент -->
        <div class="main-content">
            <!-- Фото -->
            <div class="photo-section">
                <div class="main-image-container">
                    <img src="{product['images'][0] if product['images'] else ''}" 
                         alt="{product['title']}" 
                         class="main-image"
                         id="mainImage">
                </div>
                <div class="gallery">
                    {gallery_html}
                </div>
            </div>
            
            <!-- Информация -->
            <div class="info-section">
                <!-- Цена -->
                <div class="price-block">
                    <div class="price-current">{product['price']}</div>
                    {f'<div class="price-old">{product["price_old"]}</div>' if product['price_old'] else ''}
                </div>
                
                <!-- Наличие -->
                <div class="stock-block {stock_class}">
                    {stock_text}
                    {f'<br><small>На сайте: {product["stock_quantity"]} шт.</small>' if product['stock_quantity'] else ''}
                </div>
                
                <!-- 📍 ПОЛОЖЕНИЕ НА СКЛАДЕ (редактируемое) -->
                <div class="warehouse-location-block">
                    <div class="warehouse-location-title">📍 МЕСТОПОЛОЖЕНИЕ НА СКЛАДЕ</div>
                    
                    <div class="warehouse-field">
                        <label class="warehouse-label-text">Зона/Сектор:</label>
                        <input type="text" class="warehouse-input" id="warehouseZone" 
                               value="{product.get('warehouse_zone', '')}" 
                               placeholder="Напр: A, B, Зона 1">
                    </div>
                    
                    <div class="warehouse-field">
                        <label class="warehouse-label-text">Стеллаж:</label>
                        <input type="text" class="warehouse-input" id="warehouseRack" 
                               value="{product.get('warehouse_location', '').split('-')[0] if product.get('warehouse_location') else ''}" 
                               placeholder="Напр: 12, ST-05">
                    </div>
                    
                    <div class="warehouse-field">
                        <label class="warehouse-label-text">Полка/Ярус:</label>
                        <input type="text" class="warehouse-input" id="warehouseShelf" 
                               value="{product.get('warehouse_location', '').split('-')[1] if product.get('warehouse_location') and '-' in product.get('warehouse_location', '') else ''}" 
                               placeholder="Напр: 3, B">
                    </div>
                    
                    <div class="warehouse-field">
                        <label class="warehouse-label-text">Ячейка:</label>
                        <input type="text" class="warehouse-input" id="warehouseCell" 
                               value="{product.get('warehouse_location', '').split('-')[2] if product.get('warehouse_location') and product.get('warehouse_location', '').count('-') >= 2 else ''}" 
                               placeholder="Напр: 45, 7-A">
                    </div>
                </div>
                
                <!-- 📦 КОЛИЧЕСТВО НА СКЛАДЕ (редактируемое) -->
                <div class="quantity-block">
                    <div class="quantity-title">📦 КОЛИЧЕСТВО НА СКЛАДЕ</div>
                    
                    <div class="quantity-row">
                        <div class="quantity-item">
                            <label class="quantity-label">Фактически:</label>
                            <input type="number" class="quantity-input" id="actualQty" 
                                   value="{product.get('actual_quantity', '')}" 
                                   placeholder="0" min="0">
                            <span class="quantity-unit">шт.</span>
                        </div>
                        
                        <div class="quantity-item">
                            <label class="quantity-label">Минимальный остаток:</label>
                            <input type="number" class="quantity-input" id="minQty" 
                                   value="{product.get('min_quantity', '')}" 
                                   placeholder="0" min="0">
                            <span class="quantity-unit">шт.</span>
                        </div>
                    </div>
                    
                    <div class="last-updated">
                        Обновлено: <input type="datetime-local" class="date-input" id="lastUpdated">
                    </div>
                </div>
                
                <!-- Мета-информация -->
                <div class="meta-block">
                    <div class="meta-item">
                        <span class="meta-label">🏭 Производитель:</span> {product['manufacturer'] or '—'}
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">📁 Категория:</span> {product['category'] or '—'}
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">⚖️ Вес:</span> {product['weight'] or '—'}
                    </div>
                </div>
                
                <!-- Характеристики -->
                <div class="specs-section">
                    <div class="specs-header">📋 Технические характеристики</div>
                    {specs_html}
                </div>
            </div>
            
            <!-- Этикетка для склада -->
            <div class="label-section">
                <div class="label-title">🏷️ ДАННЫЕ ДЛЯ ЭТИКЕТКИ / QR-КОДА</div>
                <div class="label-content">
                    <div class="label-item" style="grid-column: span 2;">
                        <strong>📍 Местоположение на складе:</strong><br>
                        <span id="labelLocation">Зона: <span id="lblZone">—</span> | 
                        Стеллаж: <span id="lblRack">—</span> | 
                        Полка: <span id="lblShelf">—</span> | 
                        Ячейка: <span id="lblCell">—</span></span>
                    </div>
                    <div class="label-item">
                        <strong>Артикул:</strong><br>
                        {product['article']}
                    </div>
                    <div class="label-item" style="grid-column: span 2;">
                        <strong>Название:</strong><br>
                        <span id="lblTitle">{product['title'][:40]}{'...' if len(product['title']) > 40 else ''}</span>
                    </div>
                    <div class="label-item">
                        <strong>📦 Количество:</strong><br>
                        <span id="lblActual">—</span> шт.
                    </div>
                    <div class="label-item">
                        <strong>Размеры:</strong><br>
                        {dimensions_str or '—'}
                    </div>
                    <div class="label-item">
                        <strong>Вес:</strong><br>
                        {product['weight'] or '—'}
                    </div>
                    <div class="label-item">
                        <strong>Цена:</strong><br>
                        {product['price']}
                    </div>
                    <div class="qr-placeholder">
                        QR<br>место
                    </div>
                </div>
            </div>
            
            <!-- Доставка -->
            <div class="delivery-section">
                <div class="delivery-title">🚚 Информация о доставке</div>
                <div class="delivery-grid">
                    {delivery_html}
                </div>
            </div>
            
            <!-- Описание -->
            <div class="description-section">
                <div class="description-title">📝 Описание товара</div>
                <p>{product['description'][:800] if product['description'] else 'Описание отсутствует'}</p>
            </div>
        </div>
        
        <!-- Подвал -->
        <div class="footer">
            Источник: <a href="{product['url']}" target="_blank">snab-lift.ru</a> | 
            Сгенерировано: {time.strftime('%d.%m.%Y %H:%M')}
        </div>
    </div>
    
    <script>
        function changeMainImage(src) {{
            document.getElementById('mainImage').src = src;
        }}
        
        // 📍 Обновление данных местоположения на этикетке
        function updateLocationLabel() {{
            document.getElementById('lblZone').textContent = document.getElementById('warehouseZone').value || '—';
            document.getElementById('lblRack').textContent = document.getElementById('warehouseRack').value || '—';
            document.getElementById('lblShelf').textContent = document.getElementById('warehouseShelf').value || '—';
            document.getElementById('lblCell').textContent = document.getElementById('warehouseCell').value || '—';
        }}
        
        // Обновление количества на этикетке
        function updateQuantityLabel() {{
            const actual = parseInt(document.getElementById('actualQty').value) || 0;
            document.getElementById('lblActual').textContent = actual || '—';
        }}
        
        // Слушаем изменения в поле количества
        document.getElementById('actualQty').addEventListener('input', updateQuantityLabel);
        
        // 📍 Автосохранение данных в localStorage
        function saveWarehouseData() {{
            const data = {{
                productTitle: document.getElementById('productTitle').value,
                warehouseZone: document.getElementById('warehouseZone').value,
                warehouseRack: document.getElementById('warehouseRack').value,
                warehouseShelf: document.getElementById('warehouseShelf').value,
                warehouseCell: document.getElementById('warehouseCell').value,
                actualQty: document.getElementById('actualQty').value,
                minQty: document.getElementById('minQty').value,
                lastUpdated: document.getElementById('lastUpdated').value,
                article: '{product['article']}',
                savedAt: new Date().toISOString()
            }};
            localStorage.setItem('warehouse_{product['article']}', JSON.stringify(data));
            console.log('💾 Данные сохранены:', data);
        }}
        
        // Обновление названия на этикетке
        function updateTitleLabel() {{
            const title = document.getElementById('productTitle').value;
            document.getElementById('lblTitle').textContent = title ? title.substring(0, 30) + (title.length > 30 ? '...' : '') : '—';
        }}
        
        // Загрузка данных из localStorage
        function loadWarehouseData() {{
            const saved = localStorage.getItem('warehouse_{product['article']}');
            if (saved) {{
                const data = JSON.parse(saved);
                if (data.productTitle) document.getElementById('productTitle').value = data.productTitle;
                if (data.warehouseZone) document.getElementById('warehouseZone').value = data.warehouseZone;
                if (data.warehouseRack) document.getElementById('warehouseRack').value = data.warehouseRack;
                if (data.warehouseShelf) document.getElementById('warehouseShelf').value = data.warehouseShelf;
                if (data.warehouseCell) document.getElementById('warehouseCell').value = data.warehouseCell;
                if (data.actualQty) document.getElementById('actualQty').value = data.actualQty;
                if (data.minQty) document.getElementById('minQty').value = data.minQty;
                if (data.lastUpdated) document.getElementById('lastUpdated').value = data.lastUpdated;
                updateQuantityLabel();
                updateLocationLabel();
                updateTitleLabel();
                console.log('📂 Данные загружены:', data);
            }}
        }}
        
        // Устанавливаем текущую дату при загрузке
        document.getElementById('lastUpdated').value = new Date().toISOString().slice(0, 16);
        
        // Загружаем сохраненные данные
        loadWarehouseData();
        
        // Автосохранение при изменении любого поля
        document.querySelectorAll('.warehouse-input, .quantity-input, .date-input').forEach(input => {{
            input.addEventListener('change', function() {{
                saveWarehouseData();
                updateLocationLabel();
            }});
            input.addEventListener('blur', function() {{
                saveWarehouseData();
                updateLocationLabel();
            }});
        }});
        
        // Автосохранение названия
        document.getElementById('productTitle').addEventListener('input', function() {{
            saveWarehouseData();
            updateTitleLabel();
        }});
        
        // Обновляем этикетки при загрузке
        updateLocationLabel();
        updateTitleLabel();
        
        // Печать карточки
        function printCard() {{
            window.print();
        }}
    </script>
</body>
</html>"""
    
    # Генерируем имя файла
    safe_title = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in product['title'][:30]])
    filename = f"warehouse_card_{product['article']}_{safe_title}.html"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filename

def main():
    # Получаем входные данные
    if len(sys.argv) > 1:
        input_data = sys.argv[1]
    else:
        print("❌ Ошибка: укажите артикул или URL")
        print("\nПримеры:")
        print("  python warehouse_card.py 2498")
        print("  python warehouse_card.py https://snab-lift.ru/catalog/.../product.html")
        sys.exit(1)
    
    print("=" * 70)
    print("📦 СОЗДАНИЕ СКЛАДСКОЙ КАРТОЧКИ ТОВАРА")
    print("=" * 70)
    
    driver = create_driver()
    
    try:
        # Определяем тип входных данных
        if is_url(input_data):
            print(f"\n🔗 Режим: парсинг по URL")
            product_url = input_data
        else:
            print(f"\n🏷️ Режим: поиск по артикулу")
            product_url = find_product_by_article(driver, input_data)
            
            if not product_url:
                print(f"❌ Товар не найден")
                sys.exit(1)
        
        # Парсим товар
        product = parse_product_page(driver, product_url)
        
        # Создаем карточку
        html_filename = create_warehouse_card(product)
        
        # Сохраняем JSON
        json_filename = f"warehouse_{product['article']}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(product, f, ensure_ascii=False, indent=2)
        
        # Выводим результат
        print("\n" + "=" * 70)
        print("✅ СКЛАДСКАЯ КАРТОЧКА СОЗДАНА")
        print("=" * 70)
        print(f"\n📝 {product['title']}")
        print(f"🏷️ Артикул: {product['article']}")
        print(f"💰 Цена: {product['price']}")
        print(f"🏭 Производитель: {product['manufacturer'] or '—'}")
        print(f"📦 Наличие: {'✅ В наличии' if product['in_stock'] else '❌ Нет'}")
        print(f"🖼️ Фото: {len(product['images'])} шт.")
        print(f"📋 Характеристик: {len(product['specifications'])}")
        print(f"\n💾 JSON: {json_filename}")
        print(f"🌐 HTML: {html_filename}")
        
        # Открываем в браузере
        import subprocess
        subprocess.run(['open', html_filename])
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
