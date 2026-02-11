#!/usr/bin/env python3
"""
Парсер карточки товара с snab-lift.ru
Имитирует браузер для обхода защиты
"""

import requests
from bs4 import BeautifulSoup
import json

# URL товара
URL = "https://snab-lift.ru/catalog/zapchasti-k-liftam/postyi-vyizyivnyie-i-moduli/knopki-dlya-liftov-mlz/jhsgqt-knopochnyy-modul-ak1-01-kr-s-markirovkoy-10.html"

# Заголовки, имитирующие реальный браузер
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

def parse_product(url):
    """Парсит карточку товара"""
    
    # Создаем сессию для сохранения кук
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Первый запрос - получаем куку
    print("Получаем куку...")
    response = session.get(url, timeout=30)
    
    # Если пришел редирект на куку, делаем повторный запрос
    if 'set_cookie' in response.text or len(response.text) < 500:
        print("Обходим защиту, ждем перезагрузку...")
        # Ждем немного и делаем повторный запрос
        import time
        time.sleep(2)
        response = session.get(url, timeout=30)
    
    print(f"Статус: {response.status_code}")
    print(f"Размер ответа: {len(response.text)} bytes")
    
    # Парсим HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Извлекаем данные
    product_data = {
        'url': url,
        'title': '',
        'price': '',
        'price_old': '',
        'sku': '',
        'description': '',
        'images': [],
        'specifications': {},
        'in_stock': False,
    }
    
    # Название товара
    title_elem = soup.find('h1')
    if title_elem:
        product_data['title'] = title_elem.get_text(strip=True)
    
    # Цена
    price_elem = soup.find('span', class_='price') or soup.find('div', class_='price')
    if price_elem:
        product_data['price'] = price_elem.get_text(strip=True)
    
    # Артикул/SKU
    sku_elem = soup.find('div', class_='sku') or soup.find('span', class_='sku')
    if sku_elem:
        product_data['sku'] = sku_elem.get_text(strip=True)
    
    # Описание
    desc_elem = soup.find('div', class_='description') or soup.find('div', class_='detail-text')
    if desc_elem:
        product_data['description'] = desc_elem.get_text(strip=True)
    
    # Изображения
    img_elems = soup.find_all('img')
    for img in img_elems:
        src = img.get('src') or img.get('data-src')
        if src and ('product' in src or 'upload' in src):
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = 'https://snab-lift.ru' + src
            product_data['images'].append(src)
    
    # Характеристики
    specs_table = soup.find('table', class_='props') or soup.find('div', class_='specifications')
    if specs_table:
        rows = specs_table.find_all('tr') or specs_table.find_all('div', class_='prop')
        for row in rows:
            cells = row.find_all(['td', 'dt', 'dd'])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key and value:
                    product_data['specifications'][key] = value
    
    # Наличие
    stock_elem = soup.find('span', class_='in-stock') or soup.find('div', class_='availability')
    if stock_elem:
        stock_text = stock_elem.get_text(strip=True).lower()
        product_data['in_stock'] = 'в наличии' in stock_text or 'есть' in stock_text
    
    return product_data


def main():
    print(f"Парсинг: {URL}")
    print("=" * 60)
    
    try:
        product = parse_product(URL)
        
        # Выводим результат
        print("\nРезультат парсинга:")
        print("=" * 60)
        print(f"Название: {product['title']}")
        print(f"Цена: {product['price']}")
        print(f"Артикул: {product['sku']}")
        print(f"Наличие: {'В наличии' if product['in_stock'] else 'Нет в наличии'}")
        print(f"\nОписание: {product['description'][:200]}..." if len(product['description']) > 200 else f"\nОписание: {product['description']}")
        print(f"\nИзображений найдено: {len(product['images'])}")
        if product['images']:
            for img in product['images'][:3]:
                print(f"  - {img}")
        
        print(f"\nХарактеристик: {len(product['specifications'])}")
        for key, value in list(product['specifications'].items())[:5]:
            print(f"  {key}: {value}")
        
        # Сохраняем в JSON
        filename = 'product_data.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(product, f, ensure_ascii=False, indent=2)
        print(f"\nДанные сохранены в: {filename}")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
