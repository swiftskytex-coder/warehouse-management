#!/usr/bin/env python3
"""
ИИ-поиск с fallback на обычный поиск если API не работает
"""

import requests
import json
import sys
from warehouse_system import app, db, Product

# Попробуем получить ключ из переменной окружения или использовать тестовый
OPENROUTER_API_KEY = "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"
MODEL = "meta-llama/llama-3.1-8b-instruct"

class AISearchWithFallback:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = MODEL
        self.api_working = True  # Флаг работоспособности API
        
    def search(self, query, speak=False):
        """ИИ-поиск с fallback"""
        
        with app.app_context():
            # Сначала пробуем ИИ-поиск
            if self.api_working:
                try:
                    result = self._ai_search(query)
                    if result:
                        return result
                except Exception as e:
                    print(f"⚠️ API недоступен, переключаюсь на обычный поиск: {e}")
                    self.api_working = False
            
            # Fallback: обычный поиск по базе
            return self._fallback_search(query)
    
    def _ai_search(self, query):
        """ИИ-поиск через OpenRouter"""
        
        products = Product.query.limit(50).all()
        if not products:
            return "❌ База данных пуста. Сначала импортируйте товары."
        
        # Формируем контекст
        context = []
        for p in products:
            stock = p.stock.quantity_actual if p.stock else 0
            context.append(f"{p.article}: {p.title}, {p.manufacturer or 'не указан'}, {stock} шт.")
        
        # Запрос к AI
        prompt = f"""Ты - помощник склада лифтовых запчастей.

Товары:
{chr(10).join(context)}

Запрос: "{query}"

Найди подходящие товары. Ответь кратко:
- Артикул и название
- Почему подходит  
- Количество на складе"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost",
                "X-Title": "Warehouse AI"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 400
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            usage = result.get('usage', {})
            tokens = usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
            cost = tokens * (0.18 / 1000000)
            
            return f"🤖 ИИ-ассистент:\n\n{answer}\n\n💰 Стоимость: ${cost:.6f}"
        elif response.status_code == 401:
            raise Exception("API ключ недействителен (401)")
        else:
            raise Exception(f"API ошибка: {response.status_code}")
    
    def _fallback_search(self, query):
        """Обычный поиск если API не работает"""
        
        query_lower = query.lower()
        products = Product.query.filter(
            db.or_(
                Product.article.ilike(f'%{query_lower}%'),
                Product.title.ilike(f'%{query_lower}%'),
                Product.manufacturer.ilike(f'%{query_lower}%')
            )
        ).limit(10).all()
        
        if not products:
            return f"❌ По запросу '{query}' ничего не найдено"
        
        result = f"📋 Результаты поиска (обычный режим):\n\n"
        for p in products:
            stock = p.stock.quantity_actual if p.stock else 0
            result += f"🏷️  Артикул: {p.article}\n"
            result += f"   Название: {p.title}\n"
            result += f"   Производитель: {p.manufacturer or 'не указан'}\n"
            result += f"   Количество: {stock} шт.\n\n"
        
        result += "💡 Для ИИ-поиска обновите API ключ в ai_search_voice.py"
        return result

def main():
    if len(sys.argv) < 2:
        print("❌ Использование: python ai_search_fallback.py 'запрос'")
        print("\nПримеры:")
        print('  python ai_search_fallback.py "красная кнопка"')
        print('  python ai_search_fallback.py "двигатель Otis"')
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    print("=" * 70)
    print("🤖 ИИ-ПОИСК (с fallback)")
    print("=" * 70)
    print(f"\n🔍 Запрос: {query}\n")
    
    ai = AISearchWithFallback()
    result = ai.search(query)
    
    print(result)
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
