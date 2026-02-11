#!/usr/bin/env python3
"""
Парсер нескольких товаров с snab-lift.ru
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

# Список URL товаров для парсинга
URLS = [
    "https://snab-lift.ru/catalog/zapchasti-k-liftam/postyi-vyizyivnyie-i-moduli/knopki-dlya-liftov-mlz/jhsgqt-knopochnyy-modul-ak1-01-kr-s-markirovkoy-10.html",
    # Добавь сюда другие URL:
    # "https://snab-lift.ru/catalog/.../product2.html",
    # "https://snab-lift.ru/catalog/.../product3.html",
]

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

def parse_product(driver, url):
    """Парсит одну карточку товара"""
    
    try:
        driver.get(url)
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        product_data = {
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
            product_data['title'] = title_elem.get_text(strip=True)
        
        # Цена
        price_selectors = ['.price_value', '.current-price', '.price']
        for selector in price_selectors:
            try:
                price_elem = driver.find_element(By.CSS_SELECTOR, selector)
                if price_elem:
                    product_data['price'] = price_elem.text.strip()
                    break
            except:
                continue
        
        # Артикул
        sku_elem = soup.select_one('.product-article')
        if sku_elem:
            product_data['sku'] = sku_elem.get_text(strip=True)
        
        # Описание
        desc_elem = soup.select_one('#prod-desc')
        if desc_elem:
            product_data['description'] = desc_elem.get_text(strip=True)
        
        # Характеристики
        vendor_elem = soup.select_one('.product-sidebar-vendor')
        if vendor_elem:
            vendor_text = vendor_elem.get_text(strip=True)
            if 'Производитель:' in vendor_text:
                product_data['specifications']['Производитель'] = vendor_text.replace('Производитель:', '').strip()
        
        char_rows = soup.select('.product-sidebar-char')
        for row in char_rows:
            spans = row.find_all('span')
            if len(spans) >= 2:
                key = spans[0].get_text(strip=True).replace(':', '')
                value = spans[1].get_text(strip=True)
                if key and value:
                    product_data['specifications'][key] = value
        
        # Изображения
        img_elems = soup.find_all('img')
        for img in img_elems:
            src = img.get('src') or img.get('data-src')
            if src and any(keyword in src.lower() for keyword in ['products', 'upload']):
                if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://snab-lift.ru' + src
                    if src not in product_data['images']:
                        product_data['images'].append(src)
        
        return product_data
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге {url}: {e}")
        return None

def main():
    print(f"🚀 Парсинг {len(URLS)} товаров")
    print("=" * 60)
    
    driver = create_driver()
    all_products = []
    
    try:
        for i, url in enumerate(URLS, 1):
            print(f"\n📦 Товар {i}/{len(URLS)}")
            print(f"🔗 {url}")
            
            product = parse_product(driver, url)
            
            if product:
                all_products.append(product)
                print(f"✅ {product['title'][:50]}...")
                print(f"💰 {product['price']}")
                print(f"🖼️  {len(product['images'])} фото")
                print(f"📋 {len(product['specifications'])} характеристик")
            
            # Пауза между запросами (чтобы не забанили)
            if i < len(URLS):
                time.sleep(2)
        
        # Сохраняем все товары
        with open('all_products.json', 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        
        print(f"\n" + "=" * 60)
        print(f"✅ Готово! Сохранено {len(all_products)} товаров")
        print(f"📁 Файл: all_products.json")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
