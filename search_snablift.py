#!/usr/bin/env python3
"""
Поиск аналогов и связанных товаров на snab-lift.ru
Использует встроенный поиск сайта
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

def search_on_site(driver, query):
    """Ищет товары на snab-lift.ru через форму поиска"""
    
    search_url = f"{SEARCH_URL}?query={urllib.parse.quote(query)}"
    print(f"🔍 Поиск: '{query}'")
    print(f"🔗 URL: {search_url}")
    
    driver.get(search_url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    results = []
    
    # Ищем карточки товаров в результатах поиска
    # Digi Search использует свою структуру
    product_cards = soup.find_all('div', class_='digi-product') or \
                   soup.find_all('div', class_='product-card') or \
                   soup.find_all('div', class_='ms2_product') or \
                   soup.select('.digi-products-grid > div')
    
    print(f"📦 Найдено товаров: {len(product_cards)}")
    
    for card in product_cards[:10]:  # Ограничиваем 10 результатами
        try:
            product = {
                'title': '',
                'article': '',
                'price': '',
                'url': '',
                'image': '',
                'in_stock': False
            }
            
            # Название товара - ищем в digi-структуре
            title_elem = card.find('a', class_='digi-product__label') or \
                        card.find('h2') or card.find('h3') or \
                        card.find('a', href=True)
            if title_elem:
                product['title'] = title_elem.get_text(strip=True)
            
            # Артикул - обычно в параметрах товара
            article_elem = card.find('div', class_='digi-product__param') or \
                          card.find('span', class_='article')
            if article_elem:
                article_text = article_elem.get_text(strip=True)
                if 'артикул' in article_text.lower() or article_text.isdigit():
                    product['article'] = article_text
            
            # Цена - в digi-структуре может быть в разных местах
            price_elem = card.find('span', class_='digi-product__price') or \
                        card.find('span', class_='price') or \
                        card.find('div', class_='cost')
            if price_elem:
                product['price'] = price_elem.get_text(strip=True)
            
            # Ссылка на товар
            link_elem = card.find('a', class_='digi-product__label') or \
                       card.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if href.startswith('/'):
                    href = BASE_URL + href
                elif not href.startswith('http'):
                    href = BASE_URL + '/' + href
                product['url'] = href
            
            # Изображение - ищем в разных местах
            img_elem = None
            
            # Пробуем найти в digi-структуре
            img_wrapper = card.find('div', class_='digi-product__image-wrapper')
            if img_wrapper:
                img_elem = img_wrapper.find('img')
            
            # Если не нашли, ищем любое изображение в карточке
            if not img_elem:
                img_elem = card.find('img')
            
            if img_elem:
                # Пробуем разные атрибуты
                src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
                if src:
                    # Очищаем URL от параметров
                    if '?' in src:
                        src = src.split('?')[0]
                    
                    # Фиксим URL
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/') and not src.startswith('//'):
                        # Уже относительный путь - добавляем домен
                        if not src.startswith('/'):
                            src = '/' + src
                        src = BASE_URL + src
                    elif src.startswith('http'):
                        # Абсолютный URL - оставляем как есть
                        pass
                    elif not src.startswith('http'):
                        # Относительный без слеша
                        src = BASE_URL + '/' + src
                    
                    product['image'] = src
            
            # Наличие
            stock_elem = card.find('div', class_='digi-product__meta')
            if stock_elem:
                stock_text = stock_elem.get_text(strip=True).lower()
                product['in_stock'] = 'в наличии' in stock_text or 'есть' in stock_text
            
            # Добавляем только если есть название
            if product['title'] and len(product['title']) > 3:
                results.append(product)
                
        except Exception as e:
            continue
    
    return results

def find_related_products(driver, product_data):
    """Ищет связанные товары на основе данных о товаре"""
    
    related_products = []
    
    # 1. Ищем по артикулу (если есть)
    if product_data.get('sku'):
        print(f"\n📌 Поиск по артикулу: {product_data['sku']}")
        results = search_on_site(driver, product_data['sku'])
        related_products.extend(results)
        time.sleep(2)
    
    # 2. Ищем по названию товара (короткое слово)
    if product_data.get('title'):
        # Берем первые 2-3 слова из названия
        title_words = product_data['title'].split()[:3]
        search_term = ' '.join(title_words)
        print(f"\n📌 Поиск по названию: {search_term}")
        results = search_on_site(driver, search_term)
        related_products.extend(results)
        time.sleep(2)
    
    # 3. Ищем по производителю
    manufacturer = product_data.get('specifications', {}).get('Производитель', '')
    if manufacturer and 'МЛЗ' in manufacturer:
        print(f"\n📌 Поиск по производителю: МЛЗ")
        results = search_on_site(driver, 'МЛЗ кнопка АК1')
        related_products.extend(results)
    
    # Убираем дубликаты по URL
    seen_urls = set()
    unique_products = []
    for product in related_products:
        if product['url'] and product['url'] not in seen_urls:
            seen_urls.add(product['url'])
            unique_products.append(product)
    
    return unique_products

def create_enriched_card(original_product, related_products):
    """Создает обогащенную карточку товара с аналогами"""
    
    enriched = original_product.copy()
    enriched['related_products'] = related_products
    enriched['total_related'] = len(related_products)
    
    return enriched

def main():
    # Исходный товар (спарсенный ранее)
    original_product = {
        "title": "Кнопочный модуль АК1-01-Кр с маркировкой 10",
        "sku": "768",
        "price": "435 ₽",
        "description": "Кнопочный модуль АК1-01-Кр с круглым серебристым толкателем...",
        "url": "https://snab-lift.ru/catalog/zapchasti-k-liftam/postyi-vyizyivnyie-i-moduli/knopki-dlya-liftov-mlz/jhsgqt-knopochnyy-modul-ak1-01-kr-s-markirovkoy-10.html",
        "specifications": {
            "Производитель": "МЛЗ (Могилевский завод лифтового машиностроения)",
            "Высота": "29 мм",
            "Ширина": "40 мм",
            "Длина": "40 мм",
            "Вес": "0,02 кг"
        },
        "images": [
            "https://snab-lift.ru/media/products/images/768/knopochnyy_modul_ak1-01-kr_s_markirovkoy_10_524243_500_v3.png"
        ]
    }
    
    print("=" * 70)
    print("🔍 ПОИСК АНАЛОГОВ И СВЯЗАННЫХ ТОВАРОВ НА SNAB-LIFT.RU")
    print("=" * 70)
    print(f"\n📝 Исходный товар: {original_product['title']}")
    print(f"🏷️ Артикул: {original_product['sku']}")
    print(f"💰 Цена: {original_product['price']}")
    print(f"🏭 Производитель: {original_product['specifications']['Производитель']}")
    
    driver = create_driver()
    
    try:
        # Ищем связанные товары
        print("\n" + "=" * 70)
        print("⏳ Ищем аналоги и связанные товары...")
        print("=" * 70)
        
        related_products = find_related_products(driver, original_product)
        
        # Создаем обогащенную карточку
        enriched_card = create_enriched_card(original_product, related_products)
        
        # Выводим результаты
        print("\n" + "=" * 70)
        print("📊 РЕЗУЛЬТАТЫ ПОИСКА")
        print("=" * 70)
        
        print(f"\n✅ Найдено связанных товаров: {len(related_products)}")
        
        if related_products:
            print("\n📋 Найденные товары:")
            print("-" * 70)
            
            for i, product in enumerate(related_products[:15], 1):  # Показываем первые 15
                print(f"\n{i}. {product['title'][:60]}...")
                if product['article']:
                    print(f"   Артикул: {product['article']}")
                if product['price']:
                    print(f"   Цена: {product['price']}")
                if product['url']:
                    print(f"   Ссылка: {product['url']}")
                if product['in_stock']:
                    print(f"   ✅ В наличии")
        
        # Сохраняем результаты
        with open('product_with_related.json', 'w', encoding='utf-8') as f:
            json.dump(enriched_card, f, ensure_ascii=False, indent=2)
        
        # Создаем HTML карточку с поиском
        create_html_card_with_search(enriched_card)
        
        print(f"\n💾 Данные сохранены в: product_with_related.json")
        print(f"🌐 HTML карточка с поиском: product_card_with_search.html")
        
    finally:
        driver.quit()

def create_html_card_with_search(product_data):
    """Создает HTML карточку товара с разделом поиска аналогов"""
    
    related_html = ""
    for i, product in enumerate(product_data['related_products'][:8], 1):
        image_html = f'<img src="{product["image"]}" alt="{product["title"][:30]}" class="related-image">' if product.get('image') else '<div class="no-image">Нет фото</div>'
        
        related_html += f"""
        <div class="related-item">
            {image_html}
            <div class="related-info">
                <div class="related-title">{product['title'][:50]}...</div>
                <div class="related-article">Артикул: {product.get('article', '—')}</div>
                <div class="related-price">{product.get('price', 'Цена по запросу')}</div>
                <a href="{product['url']}" class="related-link" target="_blank">Подробнее →</a>
            </div>
        </div>
        """
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product_data['title']} - с аналогами</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{ font-size: 2em; margin-bottom: 10px; }}
        
        .sku-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 20px;
            border-radius: 25px;
            margin-top: 10px;
        }}
        
        .content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            padding: 40px;
        }}
        
        .left-column {{ display: flex; flex-direction: column; gap: 20px; }}
        
        .main-image {{
            width: 100%;
            height: 400px;
            object-fit: contain;
            border-radius: 15px;
            background: #f8f9fa;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        
        .gallery {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
        }}
        
        .gallery img {{
            width: 100%;
            height: 80px;
            object-fit: cover;
            border-radius: 10px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.3s;
        }}
        
        .gallery img:hover {{
            border-color: #667eea;
            transform: translateY(-3px);
        }}
        
        .right-column {{ display: flex; flex-direction: column; gap: 25px; }}
        
        .price-block {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
        }}
        
        .price {{ font-size: 3em; font-weight: bold; margin-bottom: 10px; }}
        
        .description {{
            background: #f8f9fa;
            padding: 25px;
            border-radius: 15px;
            line-height: 1.8;
        }}
        
        .specs {{
            background: #fff;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            overflow: hidden;
        }}
        
        .specs h2 {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 25px;
        }}
        
        .spec-item {{
            display: flex;
            justify-content: space-between;
            padding: 15px 25px;
            border-bottom: 1px solid #e9ecef;
        }}
        
        .spec-item:last-child {{ border-bottom: none; }}
        
        .spec-label {{ font-weight: 600; color: #667eea; }}
        
        /* Раздел с аналогами */
        .related-section {{
            grid-column: 1 / -1;
            margin-top: 40px;
            padding: 30px;
            background: #f8f9fa;
            border-radius: 15px;
        }}
        
        .related-section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        .related-count {{
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-left: 10px;
        }}
        
        .related-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .related-item {{
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        
        .related-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        
        .related-image {{
            width: 100%;
            height: 180px;
            object-fit: contain;
            background: #f8f9fa;
            padding: 15px;
        }}
        
        .no-image {{
            width: 100%;
            height: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #e9ecef;
            color: #6c757d;
        }}
        
        .related-info {{ padding: 20px; }}
        
        .related-title {{
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            font-size: 1.1em;
        }}
        
        .related-article {{
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 8px;
        }}
        
        .related-price {{
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .related-link {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            transition: opacity 0.3s;
        }}
        
        .related-link:hover {{ opacity: 0.9; }}
        
        @media (max-width: 900px) {{
            .content {{ grid-template-columns: 1fr; }}
            .header h1 {{ font-size: 1.5em; }}
            .price {{ font-size: 2em; }}
            .related-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{product_data['title']}</h1>
            <div class="sku-badge">Артикул: {product_data['sku']}</div>
        </div>
        
        <div class="content">
            <div class="left-column">
                <img src="{product_data['images'][0] if product_data['images'] else ''}" 
                     alt="{product_data['title']}" 
                     class="main-image"
                     id="mainImage">
                
                <div class="gallery">
                    {''.join([f'<img src="{img}" onclick="document.getElementById(\'mainImage\').src=\'{img}\'">' for img in product_data['images'][:5]])}
                </div>
            </div>
            
            <div class="right-column">
                <div class="price-block">
                    <div class="price">{product_data['price']}</div>
                    <div style="font-size: 1.2em;">В наличии</div>
                </div>
                
                <div class="description">
                    <h3 style="color: #667eea; margin-bottom: 15px;">Описание</h3>
                    <p>{product_data['description'][:300]}...</p>
                </div>
                
                <div class="specs">
                    <h2>Характеристики</h2>
                    {''.join([f'<div class="spec-item"><span class="spec-label">{k}</span><span>{v}</span></div>' for k, v in product_data['specifications'].items()])}
                </div>
            </div>
            
            <div class="related-section">
                <h2>
                    🔍 Похожие товары и аналоги
                    <span class="related-count">{product_data['total_related']} найдено</span>
                </h2>
                <div class="related-grid">
                    {related_html}
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    with open('product_card_with_search.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
