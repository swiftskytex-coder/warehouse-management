#!/usr/bin/env python3
"""
Парсер карточки товара с snab-lift.ru
Использует Selenium для обхода JavaScript-защиты
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

# URL товара
URL = "https://snab-lift.ru/catalog/zapchasti-k-liftam/postyi-vyizyivnyie-i-moduli/knopki-dlya-liftov-mlz/jhsgqt-knopochnyy-modul-ak1-01-kr-s-markirovkoy-10.html"

def create_driver():
    """Создает headless Chrome с настройками для обхода защиты"""
    chrome_options = Options()
    
    # Headless режим
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Имитация реального браузера
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Отключаем автоматизацию
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Скрываем признаки автоматизации
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    
    return driver

def parse_product_selenium(url):
    """Парсит карточку товара с помощью Selenium"""
    
    driver = create_driver()
    
    try:
        print(f"Загружаем страницу: {url}")
        driver.get(url)
        
        # Ждем загрузки страницы (максимум 15 секунд)
        print("Ждем загрузку контента...")
        time.sleep(3)
        
        # Проверяем, есть ли редирект на куку
        if 'set_cookie' in driver.page_source or len(driver.page_source) < 1000:
            print("Обнаружена защита, ждем перезагрузку...")
            time.sleep(5)  # Даем время на установку куки и редирект
            driver.get(url)  # Перезагружаем страницу
            time.sleep(3)
        
        # Ждем появления основного контента
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )
        except:
            print("Предупреждение: h1 не найдена за 10 секунд")
        
        print(f"Размер страницы: {len(driver.page_source)} bytes")
        
        # Сохраняем HTML для отладки (первые 5000 символов)
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source[:10000])
        print("Сохранена отладочная HTML страница: debug_page.html")
        
        # Парсим HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
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
        
        # Название товара (ищем h1)
        title_elem = soup.find('h1')
        if title_elem:
            product_data['title'] = title_elem.get_text(strip=True)
            print(f"Найдено название: {product_data['title']}")
        
        # Пробуем найти по ID или классам 1С-Битрикс
        if not product_data['title']:
            title_elem = soup.find('div', {'id': 'pagetitle'}) or soup.find('div', class_='product-title')
            if title_elem:
                product_data['title'] = title_elem.get_text(strip=True)
        
        # Цена
        price_selectors = [
            '.price_value',
            '.current-price',
            '.price',
            '[itemprop="price"]',
            '.product-price'
        ]
        for selector in price_selectors:
            try:
                price_elem = driver.find_element(By.CSS_SELECTOR, selector)
                if price_elem:
                    product_data['price'] = price_elem.text.strip()
                    break
            except:
                continue
        
        # Артикул/SKU - конкретный селектор для snab-lift.ru
        try:
            sku_elem = driver.find_element(By.CSS_SELECTOR, '.product-article')
            if sku_elem:
                product_data['sku'] = sku_elem.text.strip()
                print(f"Найден артикул: {product_data['sku']}")
        except:
            pass
        
        # Описание - конкретный селектор для вкладки "Описание"
        try:
            desc_elem = driver.find_element(By.CSS_SELECTOR, '#prod-desc')
            if desc_elem:
                product_data['description'] = desc_elem.text.strip()
                print(f"Найдено описание ({len(product_data['description'])} символов)")
        except:
            pass
        
        # Если не нашли через Selenium, пробуем через BeautifulSoup
        if not product_data['sku']:
            sku_elem = soup.select_one('.product-article')
            if sku_elem:
                product_data['sku'] = sku_elem.get_text(strip=True)
        
        if not product_data['description']:
            desc_elem = soup.select_one('#prod-desc')
            if desc_elem:
                product_data['description'] = desc_elem.get_text(strip=True)
        
        # Изображения - собираем все фото товара из всех источников
        print("Поиск изображений...")
        
        # Ищем в блоках похожих товаров
        related_selectors = [
            '.product-sidebar-chars img',  # Изображения в сайдбаре (похожие товары)
            '.product-related img',
            '.similar-products img'
        ]
        
        for selector in related_selectors:
            try:
                images = driver.find_elements(By.CSS_SELECTOR, selector)
                for img in images:
                    src = img.get_attribute('src') or img.get_attribute('data-src')
                    if src and src not in product_data['images']:
                        # Преобразуем относительные URL в абсолютные
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://snab-lift.ru' + src
                        # Проверяем что это изображение товара
                        if any(keyword in src.lower() for keyword in ['products', 'upload', 'iblock']):
                            product_data['images'].append(src)
            except:
                continue
        
        # Основные изображения товара через BeautifulSoup
        img_elems = soup.find_all('img')
        for img in img_elems:
            src = img.get('src') or img.get('data-src') or img.get('data-zoom-image')
            if src and src not in product_data['images']:
                # Фильтруем только изображения товаров
                if any(keyword in src.lower() for keyword in ['products', 'upload', 'iblock']):
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://snab-lift.ru' + src
                        product_data['images'].append(src)
        
        # Характеристики - конкретные селекторы для snab-lift.ru
        try:
            # Производитель
            vendor_elem = driver.find_element(By.CSS_SELECTOR, '.product-sidebar-vendor')
            if vendor_elem:
                vendor_text = vendor_elem.text.strip()
                if 'Производитель:' in vendor_text:
                    product_data['specifications']['Производитель'] = vendor_text.replace('Производитель:', '').strip()
        except:
            pass
        
        # Характеристики из блока .product-sidebar-char
        try:
            char_rows = driver.find_elements(By.CSS_SELECTOR, '.product-sidebar-char')
            for row in char_rows:
                try:
                    spans = row.find_elements(By.TAG_NAME, 'span')
                    if len(spans) >= 2:
                        key = spans[0].text.strip().replace(':', '')
                        value = spans[1].text.strip()
                        if key and value:
                            product_data['specifications'][key] = value
                except:
                    continue
            print(f"Найдено характеристик: {len(product_data['specifications'])}")
        except Exception as e:
            print(f"Ошибка при парсинге характеристик: {e}")
        
        # Если не нашли через Selenium, пробуем через BeautifulSoup
        if not product_data['specifications']:
            # Производитель
            vendor_elem = soup.select_one('.product-sidebar-vendor')
            if vendor_elem:
                vendor_text = vendor_elem.get_text(strip=True)
                if 'Производитель:' in vendor_text:
                    product_data['specifications']['Производитель'] = vendor_text.replace('Производитель:', '').strip()
            
            # Характеристики
            char_rows = soup.select('.product-sidebar-char')
            for row in char_rows:
                spans = row.find_all('span')
                if len(spans) >= 2:
                    key = spans[0].get_text(strip=True).replace(':', '')
                    value = spans[1].get_text(strip=True)
                    if key and value:
                        product_data['specifications'][key] = value
        
        # Наличие
        stock_selectors = [
            '.availability',
            '.stock',
            '.in-stock',
            '.product-availability'
        ]
        for selector in stock_selectors:
            try:
                stock_elem = driver.find_element(By.CSS_SELECTOR, selector)
                if stock_elem:
                    stock_text = stock_elem.text.strip().lower()
                    product_data['in_stock'] = 'в наличии' in stock_text or 'есть' in stock_text
                    break
            except:
                continue
        
        return product_data
        
    finally:
        driver.quit()


def main():
    print(f"Парсинг с Selenium: {URL}")
    print("=" * 60)
    
    try:
        product = parse_product_selenium(URL)
        
        # Выводим результат
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ ПАРСИНГА")
        print("=" * 60)
        print(f"\n📝 Название: {product['title']}")
        print(f"💰 Цена: {product['price']}")
        print(f"🏷️  Артикул/SKU: {product['sku'] if product['sku'] else 'Не найден'}")
        print(f"📦 Наличие: {'✅ В наличии' if product['in_stock'] else '❌ Нет в наличии'}")
        
        if product['description']:
            desc = product['description'][:300] + "..." if len(product['description']) > 300 else product['description']
            print(f"\n📄 Описание:\n{desc}")
        else:
            print("\n📄 Описание: Не найдено")
        
        print(f"\n🖼️  Изображений найдено: {len(product['images'])}")
        for i, img in enumerate(product['images'], 1):
            print(f"  {i}. {img}")
        
        if product['specifications']:
            print(f"\n📋 Характеристики ({len(product['specifications'])} шт.):")
            for key, value in product['specifications'].items():
                print(f"  • {key}: {value}")
        else:
            print("\n📋 Характеристики: Не найдены")
        
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
