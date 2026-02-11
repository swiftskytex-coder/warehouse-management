#!/usr/bin/env python3
"""
Парсер товаров из файла urls.txt
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import time

def load_urls(filename='urls.txt'):
    """Загружает URL из файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return urls

def create_driver():
    """Создает headless Chrome"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''Object.defineProperty(navigator, 'webdriver', {get: () => undefined})'''
    })
    return driver

def parse_product(driver, url):
    """Парсит товар"""
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        product = {
            'url': url,
            'title': soup.find('h1').get_text(strip=True) if soup.find('h1') else '',
            'price': '',
            'sku': soup.select_one('.product-article').get_text(strip=True) if soup.select_one('.product-article') else '',
            'description': soup.select_one('#prod-desc').get_text(strip=True) if soup.select_one('#prod-desc') else '',
            'images': [],
            'specifications': {},
            'in_stock': False,
        }
        
        # Цена
        price_elem = soup.select_one('.price_value, .current-price, .price')
        if price_elem:
            product['price'] = price_elem.get_text(strip=True)
        
        # Характеристики
        vendor = soup.select_one('.product-sidebar-vendor')
        if vendor:
            product['specifications']['Производитель'] = vendor.get_text(strip=True).replace('Производитель:', '').strip()
        
        for row in soup.select('.product-sidebar-char'):
            spans = row.find_all('span')
            if len(spans) >= 2:
                key = spans[0].get_text(strip=True).replace(':', '')
                value = spans[1].get_text(strip=True)
                product['specifications'][key] = value
        
        # Изображения
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'products' in src.lower():
                if src.startswith('/'):
                    src = 'https://snab-lift.ru' + src
                elif src.startswith('//'):
                    src = 'https:' + src
                if src not in product['images']:
                    product['images'].append(src)
        
        return product
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def main():
    urls = load_urls('urls.txt')
    print(f"📋 Загружено {len(urls)} URL из urls.txt")
    
    driver = create_driver()
    products = []
    
    try:
        for i, url in enumerate(urls, 1):
            print(f"\n{i}/{len(urls)}: {url}")
            product = parse_product(driver, url)
            if product:
                products.append(product)
                print(f"✅ {product['title'][:40]}...")
            if i < len(urls):
                time.sleep(2)
        
        with open('products_from_file.json', 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Сохранено {len(products)} товаров")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
