#!/usr/bin/env python3
"""
ИИ-поиск с озвучкой ответа (macOS say)
"""

import requests
import json
import sys
import subprocess
import threading
from warehouse_system import app, db, Product

# OpenRouter API ключ
OPENROUTER_API_KEY = "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"
MODEL = "meta-llama/llama-3.1-8b-instruct"

class AISearchWithVoice:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = MODEL
        self.base_url = "https://openrouter.ai/api/v1"
        
    def search(self, query, speak=False):
        """ИИ-поиск с опциональной озвучкой"""
        
        with app.app_context():
            products = Product.query.all()
            
            if not products:
                result = "❌ База данных пуста. Сначала импортируйте товары."
                if speak:
                    self.speak("База данных пуста. Сначала импортируйте товары.")
                return result
            
            # Формируем контекст
            context = self._format_products(products)
            
            # Запрос к AI
            response = self._ask_ai(query, context)
            
            # Озвучиваем если нужно
            if speak and response:
                # Озвучиваем в отдельном потоке чтобы не блокировать
                threading.Thread(target=self.speak, args=(response,)).start()
            
            return response
    
    def _format_products(self, products):
        """Форматирует товары для контекста AI"""
        items = []
        for p in products[:50]:
            stock_qty = p.stock.quantity_actual if p.stock else 0
            item = f"Артикул {p.article}: {p.title}, {p.manufacturer or 'не указан'}, {stock_qty} штук"
            items.append(item)
        return "\n".join(items)
    
    def _ask_ai(self, query, context):
        """Отправляет запрос к OpenRouter"""
        
        prompt = f"""Ты - помощник для поиска товаров на складе лифтовых запчастей.

Товары на складе:
{context}

Запрос пользователя: "{query}"

Найди подходящие товары. Ответь кратко и понятно:
1. Назови артикул и название
2. Почему подходит
3. Сколько на складе

Если не нашел - скажи прямо."""

        try:
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
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
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result['choices'][0]['message']['content']
                
                # Считаем стоимость
                usage = result.get('usage', {})
                tokens = usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
                cost = tokens * (0.18 / 1000000)
                
                return f"{answer}\n\n💰 Стоимость: ${cost:.6f} | Токенов: {tokens}"
            else:
                return f"❌ Ошибка API: {response.status_code}"
                
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
    
    def speak(self, text):
        """Озвучивает текст через macOS say"""
        try:
            # Очищаем текст от эмодзи и спецсимволов для лучшей озвучки
            clean_text = self._clean_text_for_speech(text)
            
            # Используем macOS say команду
            # -v Anna - русский голос (если установлен)
            # -r 180 - скорость речи
            subprocess.run(['say', '-r', '180', clean_text], 
                         check=True, capture_output=True)
            
        except Exception as e:
            print(f"⚠️ Ошибка озвучки: {e}")
    
    def _clean_text_for_speech(self, text):
        """Очищает текст для лучшей озвучки"""
        import re
        
        # Убираем эмодзи
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+",
            flags=re.UNICODE
        )
        
        text = emoji_pattern.sub(r'', text)
        
        # Убираем спецсимволы
        text = re.sub(r'[#*•]', '', text)
        
        # Убираем строки со стоимостью и технической инфой
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            if not any(x in line for x in ['💰', 'Стоимость:', 'Токенов:', '$0.0000']):
                clean_lines.append(line)
        
        return '\n'.join(clean_lines[:10])  # Берем первые 10 строк

def main():
    # Проверяем аргументы
    speak = '--speak' in sys.argv or '-s' in sys.argv
    
    # Убираем флаги из аргументов
    query_args = [arg for arg in sys.argv[1:] if arg not in ['--speak', '-s']]
    
    if not query_args:
        print("❌ Использование: python ai_search_voice.py 'запрос' [--speak]")
        print("\nПримеры:")
        print('  python ai_search_voice.py "красная кнопка"')
        print('  python ai_search_voice.py "двигатель Otis" --speak')
        sys.exit(1)
    
    query = " ".join(query_args)
    
    print("=" * 70)
    print("🤖 ИИ-ПОИСК С ОЗВУЧКОЙ" if speak else "🤖 ИИ-ПОИСК")
    print("=" * 70)
    print(f"\n🔍 Запрос: {query}")
    
    if speak:
        print("🔊 Озвучка включена")
        # Приветствие
        subprocess.run(['say', '-r', '200', 'Ищу товары по вашему запросу'], 
                      check=False, capture_output=True)
    
    print("⏳ Ищем через AI...\n")
    
    ai = AISearchWithVoice()
    result = ai.search(query, speak=speak)
    
    print(result)
    print("\n" + "=" * 70)
    
    if speak:
        print("✅ Готово! Ответ озвучен.")

if __name__ == "__main__":
    main()
