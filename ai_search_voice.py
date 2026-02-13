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
                # Озвучиваем в отдельном потоке
                import time
                speech_thread = threading.Thread(target=self.speak, args=(response,))
                speech_thread.daemon = False  # Ждем завершения потока
                speech_thread.start()
                speech_thread.join(timeout=20)  # Ждем максимум 20 секунд
            
            return response
    
    def _format_products(self, products):
        """Форматирует товары для контекста AI"""
        items = []
        for p in products[:50]:
            stock_qty = p.stock.quantity_actual if p.stock else 0
            # Формируем местоположение
            location = "не указано"
            if p.stock and any([p.stock.zone, p.stock.rack, p.stock.shelf, p.stock.cell]):
                location = f"{p.stock.zone or '-'}-{p.stock.rack or '-'}-{p.stock.shelf or '-'}-{p.stock.cell or '-'}"
            
            item = f"Артикул {p.article}: {p.title}, {p.manufacturer or 'не указан'}, {stock_qty} штук, место: {location}"
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
4. **Укажи местоположение** (зона-стеллаж-полка-ячейка)

Если местоположение не задано - напиши об этом.
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
        import re
        try:
            # Очищаем текст от эмодзи и спецсимволов для лучшей озвучки
            clean_text = self._clean_text_for_speech(text)
            
            # Если текст слишком длинный, берем только первые 300 символов
            if len(clean_text) > 300:
                # Ищем конец предложения
                end_pos = clean_text[:300].rfind('.')
                if end_pos > 100:
                    clean_text = clean_text[:end_pos+1]
                else:
                    clean_text = clean_text[:300] + "..."
            
            # Используем macOS say команду с таймаутом
            # -r 200 - скорость речи (быстрее)
            result = subprocess.run(
                ['say', '-r', '200', clean_text], 
                check=True, 
                capture_output=True,
                timeout=15  # Таймаут 15 секунд
            )
            
        except subprocess.TimeoutExpired:
            print("⚠️ Озвучка: превышен таймаут")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Ошибка озвучки (код {e.returncode})")
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
        
        # Берем только первые 5 строк (для краткости озвучки)
        text = '\n'.join(clean_lines[:5])
        
        # Убираем артикулы (цифры в начале строк или после "Артикул")
        text = re.sub(r'\b\d+\s*:', '', text)
        text = re.sub(r'Артикул\s*\d*\s*:', '', text, flags=re.IGNORECASE)
        
        # Убираем "подходит по названию" и похожие фразы
        text = re.sub(r'подходит\s+по\s+названию', '', text, flags=re.IGNORECASE)
        text = re.sub(r'подходит\s+по\s+описанию', '', text, flags=re.IGNORECASE)
        text = re.sub(r'по\s+названию\s+подходит', '', text, flags=re.IGNORECASE)
        
        # Убираем лишние пробелы и пустые строки
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r'  +', ' ', text)
        
        return text.strip()

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
                      check=False, capture_output=True, timeout=10)
        import time
        time.sleep(0.5)  # Небольшая пауза между фразами
    
    print("⏳ Ищем через AI...\n")
    
    ai = AISearchWithVoice()
    result = ai.search(query, speak=speak)
    
    print(result)
    print("\n" + "=" * 70)
    
    if speak:
        print("✅ Готово! Ответ озвучен.")

if __name__ == "__main__":
    main()
