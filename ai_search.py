#!/usr/bin/env python3
"""
ИИ-поиск по складу через OpenRouter
Дешевые модели с хорошим результатом
"""

import requests
import json
import sys
from warehouse_system import app, db, Product

# OpenRouter API ключ
OPENROUTER_API_KEY = "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"

# Дешевые и эффективные модели (цена за 1M токенов)
MODELS = {
    # Очень дешевые
    "llama-3.1-8b": "meta-llama/llama-3.1-8b-instruct",  # ~$0.18/M токенов
    "gemma-2-9b": "google/gemma-2-9b-it",  # ~$0.20/M токенов
    # Средний ценник - лучшее качество
    "llama-3.1-70b": "meta-llama/llama-3.1-70b-instruct",  # ~$0.88/M токенов
}

# Используем дешевую но хорошую модель
DEFAULT_MODEL = MODELS["llama-3.1-8b"]

class AISearch:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = DEFAULT_MODEL
        self.base_url = "https://openrouter.ai/api/v1"
        
    def search(self, query):
        """ИИ-поиск по описанию"""
        
        # Получаем все товары из базы
        with app.app_context():
            products = Product.query.all()
            
            if not products:
                return "❌ База данных пуста. Сначала импортируйте товары."
            
            # Формируем контекст для AI
            context = self._format_products(products)
            
            # Отправляем запрос к AI
            response = self._ask_ai(query, context)
            
            return response
    
    def _format_products(self, products):
        """Форматирует товары для контекста AI с местоположением"""
        items = []
        for p in products[:50]:  # Берем первые 50 для экономии токенов
            stock_qty = p.stock.quantity_actual if p.stock else 0
            # Формируем местоположение
            location = "не указано"
            if p.stock and any([p.stock.zone, p.stock.rack, p.stock.shelf, p.stock.cell]):
                location = f"{p.stock.zone or '-'}-{p.stock.rack or '-'}-{p.stock.shelf or '-'}-{p.stock.cell or '-'}"
            
            item = f"Артикул: {p.article}, Название: {p.title}, Производитель: {p.manufacturer or 'не указан'}, Количество: {stock_qty}, Место: {location}"
            items.append(item)
        return "\n".join(items)
    
    def _ask_ai(self, query, context):
        """Отправляет запрос к OpenRouter"""
        
        prompt = f"""Ты - помощник для поиска товаров на складе лифтовых запчастей.

Доступные товары:
{context}

Запрос пользователя: "{query}"

Найди подходящие товары из списка выше. Ответь в формате:
1. Назови артикул и название найденного товара
2. Объясни почему он подходит
3. Укажи количество на складе
4. **Укажи местоположение на складе** (зона-стеллаж-полка-ячейка)

Если местоположение не указано - напиши "местоположение не задано".
Если ничего не найдено - скажи об этом."""

        try:
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://localhost",  # Required by OpenRouter
                    "X-Title": "Warehouse AI Search"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Низкая температура для точных ответов
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result['choices'][0]['message']['content']
                
                # Добавляем информацию о цене
                cost = self._estimate_cost(result)
                
                return f"🤖 ИИ-ассистент:\n\n{answer}\n\n💰 Стоимость запроса: ${cost:.6f}"
            else:
                return f"❌ Ошибка API: {response.status_code}\n{response.text}"
                
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
    
    def _estimate_cost(self, response):
        """Оценивает стоимость запроса"""
        usage = response.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        
 # Цены для llama-3.1-8b (вход/выход за 1M токенов)
        input_price = 0.18 / 1000000
        output_price = 0.18 / 1000000
        
        cost = (prompt_tokens * input_price) + (completion_tokens * output_price)
        return cost

def main():
    if len(sys.argv) < 2:
        print("❌ Использование: python ai_search.py 'запрос'")
        print("\nПримеры:")
        print('  python ai_search.py "красная кнопка для вызова"')
        print('  python ai_search.py "двигатель для лифта"')
        print('  python ai_search.py "что есть от Otis"')
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    print("=" * 70)
    print("🤖 ИИ-ПОИСК ПО СКЛАДУ")
    print("=" * 70)
    print(f"\n🔍 Запрос: {query}")
    print("⏳ Ищем через AI...\n")
    
    ai = AISearch()
    result = ai.search(query)
    
    print(result)
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
