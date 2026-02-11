#!/usr/bin/env python3
"""
Создание карточки товара по артикулу
Ищет товар на snab-lift.ru и создает HTML карточку
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import time
import urllib.parse
import sys

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

def find_product_by_article(driver, article):
    """Ищет товар по артикулу через поиск"""
    
    search_url = f"{SEARCH_URL}?query={urllib.parse.quote(str(article))}"
    print(f"🔍 Поиск товара по артикулу: {article}")
    print(f"🔗 {search_url}")
    
    driver.get(search_url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Ищем ссылки на товары в результатах поиска
    links = soup.find_all('a', href=True)
    product_links = []
    
    for link in links:
        href = link.get('href', '')
        if '/catalog/' in href and '.html' in href:
            # Проверяем, что это ссылка на товар
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
    
    if unique_links:
        print(f"✅ Найдено товаров: {len(unique_links)}")
        return unique_links[0]['url']  # Возвращаем URL первого товара
    
    return None

def parse_product_page(driver, url):
    """Парсит страницу товара"""
    
    print(f"\n📄 Парсинг страницы: {url}")
    driver.get(url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    product = {
        'url': url,
        'title': '',
        'price': '',
        'sku': '',
        'description': '',
        'images': [],
        'specifications': {},
        'in_stock': False,
    }
    
    # Название
    title_elem = soup.find('h1')
    if title_elem:
        product['title'] = title_elem.get_text(strip=True)
        print(f"📝 Название: {product['title']}")
    
    # Цена
    price_selectors = ['.price_value', '.current-price', '.price']
    for selector in price_selectors:
        try:
            price_elem = driver.find_element(By.CSS_SELECTOR, selector)
            if price_elem:
                product['price'] = price_elem.text.strip()
                print(f"💰 Цена: {product['price']}")
                break
        except:
            continue
    
    # Артикул
    sku_elem = soup.select_one('.product-article')
    if sku_elem:
        product['sku'] = sku_elem.get_text(strip=True)
        print(f"🏷️ Артикул: {product['sku']}")
    
    # Описание
    desc_elem = soup.select_one('#prod-desc')
    if desc_elem:
        product['description'] = desc_elem.get_text(strip=True)
        print(f"📄 Описание: {len(product['description'])} символов")
    
    # Производитель
    vendor_elem = soup.select_one('.product-sidebar-vendor')
    if vendor_elem:
        vendor_text = vendor_elem.get_text(strip=True)
        if 'Производитель:' in vendor_text:
            product['specifications']['Производитель'] = vendor_text.replace('Производитель:', '').strip()
    
    # Характеристики
    char_rows = soup.select('.product-sidebar-char')
    for row in char_rows:
        spans = row.find_all('span')
        if len(spans) >= 2:
            key = spans[0].get_text(strip=True).replace(':', '')
            value = spans[1].get_text(strip=True)
            if key and value:
                product['specifications'][key] = value
    
    print(f"📋 Характеристик: {len(product['specifications'])}")
    
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
    
    print(f"🖼️ Изображений: {len(product['images'])}")
    
    return product

def create_html_card(product):
    """Создает HTML карточку товара"""
    
    # Генерируем HTML
    images_html = ""
    for img in product['images'][:5]:
        images_html += f'<img src="{img}" onclick="document.getElementById(\'mainImage\').src=\'{img}\'">'
    
    specs_html = ""
    for key, value in product['specifications'].items():
        specs_html += f'<div class="spec-item"><span class="spec-label">{key}</span><span>{value}</span></div>'
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product['title']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
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
        
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        
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
        
        .gallery img:hover {{ border-color: #667eea; transform: translateY(-3px); }}
        
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
        
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
        }}
        
        .footer a {{ color: #667eea; text-decoration: none; }}
        
        @media (max-width: 900px) {{
            .content {{ grid-template-columns: 1fr; }}
            .header h1 {{ font-size: 1.8em; }}
            .price {{ font-size: 2em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{product['title']}</h1>
            <div class="sku-badge">Артикул: {product['sku']}</div>
        </div>
        
        <div class="content">
            <div class="left-column">
                <img src="{product['images'][0] if product['images'] else ''}" 
                     alt="{product['title']}" 
                     class="main-image"
                     id="mainImage">
                
                <div class="gallery">
                    {images_html}
                </div>
            </div>
            
            <div class="right-column">
                <div class="price-block">
                    <div class="price">{product['price']}</div>
                    <div style="font-size: 1.2em;">В наличии</div>
                </div>
                
                <div class="description">
                    <h3 style="color: #667eea; margin-bottom: 15px;">Описание</h3>
                    <p>{product['description'][:500] if product['description'] else 'Описание отсутствует'}</p>
                </div>
                
                <div class="specs">
                    <h2>Характеристики</h2>
                    {specs_html}
                </div>
            </div>
        </div>
        
        <div class="footer">
            Источник: <a href="{product['url']}" target="_blank">snab-lift.ru</a>
        </div>
    </div>
</body>
</html>"""
    
    filename = f"card_article_{product['sku']}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filename

def main():
    # Артикул для поиска
    # Можно получить из аргументов командной строки: python create_card_by_article.py 2498
    if len(sys.argv) > 1:
        article = sys.argv[1]
    else:
        article = "2498"  # Артикул по умолчанию
    
    print("=" * 70)
    print(f"🎯 СОЗДАНИЕ КАРТОЧКИ ТОВАРА ПО АРТИКУЛУ: {article}")
    print("=" * 70)
    
    driver = create_driver()
    
    try:
        # 1. Ищем товар по артикулу
        product_url = find_product_by_article(driver, article)
        
        if not product_url:
            print(f"❌ Товар с артикулом {article} не найден")
            return
        
        # 2. Парсим страницу товара
        product = parse_product_page(driver, product_url)
        
        # 3. Сохраняем JSON
        json_filename = f"product_{article}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(product, f, ensure_ascii=False, indent=2)
        
        # 4. Создаем HTML карточку
        html_filename = create_html_card(product)
        
        # 5. Выводим результат
        print("\n" + "=" * 70)
        print("✅ КАРТОЧКА ТОВАРА СОЗДАНА")
        print("=" * 70)
        print(f"\n📝 {product['title']}")
        print(f"🏷️ Артикул: {product['sku']}")
        print(f"💰 Цена: {product['price']}")
        print(f"🖼️ Фото: {len(product['images'])} шт.")
        print(f"📋 Характеристик: {len(product['specifications'])}")
        print(f"\n💾 JSON: {json_filename}")
        print(f"🌐 HTML: {html_filename}")
        
        # Открываем карточку в браузере
        import subprocess
        subprocess.run(['open', html_filename])
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
