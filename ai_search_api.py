#!/usr/bin/env python3
"""
API endpoint для ИИ-поиска
"""

from flask import Blueprint, request, jsonify
import requests
from warehouse_system import app, db, Product

ai_search_bp = Blueprint('ai_search', __name__)

OPENROUTER_API_KEY = "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"
MODEL = "meta-llama/llama-3.1-8b-instruct"

@ai_search_bp.route('/api/ai-search', methods=['POST'])
def ai_search():
    """ИИ-поиск через API"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': 'Пустой запрос'}), 400
        
        # Получаем товары
        with app.app_context():
            products = Product.query.limit(50).all()
            
            if not products:
                return jsonify({
                    'success': True,
                    'answer': '❌ База данных пуста. Сначала импортируйте товары.',
                    'cost': 0
                })
            
            # Формируем контекст
            context = []
            for p in products:
                stock = p.stock.quantity_actual if p.stock else 0
                context.append(f"{p.article}: {p.title} ({p.manufacturer or '?'}) - {stock} шт.")
            
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
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://localhost",
                    "X-Title": "Warehouse AI"
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 400
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result['choices'][0]['message']['content']
                
                # Считаем стоимость
                usage = result.get('usage', {})
                tokens = usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
                cost = tokens * (0.18 / 1000000)  # $0.18 за 1M токенов
                
                return jsonify({
                    'success': True,
                    'answer': answer,
                    'cost': round(cost, 6),
                    'tokens': tokens
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'API Error: {response.status_code}'
                }), 500
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Добавляем blueprint в основное приложение
if __name__ != '__main__':
    from warehouse_system import app
    app.register_blueprint(ai_search_bp)
    print("✅ ИИ-поиск подключен к API")
