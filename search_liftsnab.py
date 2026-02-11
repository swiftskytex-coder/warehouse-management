#!/usr/bin/env python3
"""
Парсер поиска с poisk-liftsnab.ru
Ищет товар по артикулу или названию
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

BASE_URL = "https://poisk-liftsnab.ru"

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

def search_product(driver, query):
    """Ищет товар на poisk-liftsnab.ru"""
    
    # Формируем URL поиска
    search_url = f"{BASE_URL}/search?q={urllib.parse.quote(query)}"
    print(f"🔍 Поиск: {query}")
    print(f"🔗 URL: {search_url}")
    
    driver.get(search_url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Ищем результаты поиска
    results = []
    
    # Пробуем разные селекторы для результатов
    product_cards = soup.find_all('div', class_='product-card') or \
                   soup.find_all('div', class_='search-item') or \
                   soup.find_all('article') or \
                   soup.find_all('div', class_='item')
    
    print(f"📦 Найдено результатов: {len(product_cards)}")
    
    for card in product_cards[:5]:  # Берем первые 5 результатов
        try:
            product = {
                'title': '',
                'article': '',
                'manufacturer': '',
                'description': '',
                'price': '',
                'url': '',
                'image': ''
            }
            
            # Название
            title_elem = card.find('h2') or card.find('h3') or card.find('a', class_='title')
            if title_elem:
                product['title'] = title_elem.get_text(strip=True)
            
            # Артикул
            article_elem = card.find('span', class_='article') or card.find('div', class_='sku')
            if article_elem:
                product['article'] = article_elem.get_text(strip=True)
            
            # Производитель
            manuf_elem = card.find('span', class_='manufacturer') or card.find('div', class_='brand')
            if manuf_elem:
                product['manufacturer'] = manuf_elem.get_text(strip=True)
            
            # Цена
            price_elem = card.find('span', class_='price') or card.find('div', class_='cost')
            if price_elem:
                product['price'] = price_elem.get_text(strip=True)
            
            # Ссылка
            link_elem = card.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if href.startswith('/'):
                    href = BASE_URL + href
                product['url'] = href
            
            # Изображение
            img_elem = card.find('img')
            if img_elem:
                src = img_elem.get('src') or img_elem.get('data-src')
                if src:
                    if src.startswith('/'):
                        src = BASE_URL + src
                    elif src.startswith('//'):
                        src = 'https:' + src
                    product['image'] = src
            
            # Описание
            desc_elem = card.find('div', class_='description') or card.find('p')
            if desc_elem:
                product['description'] = desc_elem.get_text(strip=True)
            
            if product['title']:  # Добавляем только если есть название
                results.append(product)
                
        except Exception as e:
            print(f"⚠️ Ошибка при парсинге карточки: {e}")
            continue
    
    return results

def enrich_product_data(original_product, search_results):
    """Обогащает данные товара результатами поиска"""
    
    enriched = original_product.copy()
    enriched['search_results'] = search_results
    
    # Если нашли похожие товары, берем доп. информацию
    if search_results:
        first_match = search_results[0]
        
        # Дополняем недостающие поля
        if not enriched.get('manufacturer') and first_match.get('manufacturer'):
            enriched['manufacturer'] = first_match['manufacturer']
        
        if not enriched.get('description') and first_match.get('description'):
            enriched['description'] = first_match['description']
        
        enriched['analogs_found'] = len(search_results)
    
    return enriched

def main():
    # Товар, который мы уже спарсили
    original_product = {
        "title": "Кнопочный модуль АК1-01-Кр с маркировкой 10",
        "sku": "768",
        "price": "435 ₽",
        "url": "https://snab-lift.ru/catalog/zapchasti-k-liftam/postyi-vyizyivnyie-i-moduli/knopki-dlya-liftov-mlz/jhsgqt-knopochnyy-modul-ak1-01-kr-s-markirovkoy-10.html"
    }
    
    print("=" * 60)
    print("🔍 Поиск аналогов на poisk-liftsnab.ru")
    print("=" * 60)
    
    driver = create_driver()
    
    try:
        # Ищем по артикулу
        search_query = original_product['sku']
        results = search_product(driver, search_query)
        
        # Обогащаем данные
        enriched = enrich_product_data(original_product, results)
        
        # Выводим результаты
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ПОИСКА")
        print("=" * 60)
        
        print(f"\n📝 Исходный товар: {enriched['title']}")
        print(f"🏷️ Артикул: {enriched['sku']}")
        print(f"💰 Цена: {enriched['price']}")
        
        if results:
            print(f"\n✅ Найдено аналогов: {len(results)}")
            print("\n📋 Результаты:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['title']}")
                if result['article']:
                    print(f"   Артикул: {result['article']}")
                if result['manufacturer']:
                    print(f"   Производитель: {result['manufacturer']}")
                if result['price']:
                    print(f"   Цена: {result['price']}")
                if result['url']:
                    print(f"   Ссылка: {result['url']}")
        else:
            print("\n❌ Аналоги не найдены")
        
        # Сохраняем результат
        with open('product_with_search.json', 'w', encoding='utf-8') as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Данные сохранены в: product_with_search.json")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
