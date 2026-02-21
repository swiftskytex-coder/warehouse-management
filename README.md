# 🏭 Складская система управления

Интеллектуальная система управления складскими карточками товаров с интеграцией snab-lift.ru, ИИ-поиском и голосовым управлением.

## ✨ Основные возможности

### 🔍 Умный поиск
- **Обычный поиск** — по артикулу, названию, производителю
- **🤖 ИИ-поиск** — понимает запросы на естественном языке
  - "красная кнопка для вызова лифта"
  - "двигатель от Otis для дверей"
  - "что есть в наличии от МЛЗ"
- **🔊 Голосовой поиск** — macOS произносит результаты
- **Фильтры** — по зоне, производителю, статусу наличия

### 📦 Импорт товаров
- **По артикулу** — `python import_product.py 2498`
- **По URL** — `python import_product.py "https://..."`
- **Массовый импорт** — списком из файла
- **Автопарсинг** — Selenium + BeautifulSoup извлекают данные с сайта

### 🌐 Веб-интерфейс
- **Управление складом** — зоны, стеллажи, полки, ячейки
- **Контроль остатков** — минимальные запасы для предупреждений
- **Статусы товаров** — в наличии / заканчивается / нет
- **Фильтры и сортировка** — быстрый доступ к нужным товарам
- **Пагинация** — удобный просмотр больших списков

### 🖨️ Карточки товаров
- **HTML карточки** — готовы к печати этикеток
- **Редактирование названия** — прямо в карточке товара
- **QR-код места** — формат: зона-стеллаж-полка-ячейка
- **Галерея фото** — все изображения товара с сайта
- **Технические характеристики** — извлекаются автоматически

### 💾 База данных
- **SQLite** — локальное хранение, не требует сервера
- **REST API** — интеграция с другими системами
- **Экспорт JSON** — резервное копирование данных

## 🚀 Быстрый старт

### 1. Установка

```bash
# Клонируй репозиторий
git clone https://github.com/swiftskytex-coder/warehouse-management.git
cd warehouse-management

# Создай виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

# Установи зависимости
pip install -r requirements.txt
```

### 2. Запуск веб-интерфейса

```bash
python warehouse_system.py
```

Откройте в браузере: **http://localhost:8080**

### 3. Импорт первого товара

```bash
python import_product.py 2498
```

## 📋 Команды управления

### Запуск системы

```bash
# Через основной скрипт
python warehouse_system.py

# Или через скрипт автозапуска (Linux/Mac)
chmod +x start_warehouse.sh
./start_warehouse.sh

# Или через альтернативный скрипт
./start_server.sh
```

### Остановка сервера

```bash
# Если запущен в терминале - нажмите Ctrl+C

# Если запущен в фоне - найдите и завершите процесс
pkill -f warehouse_system.py

# Или найдите PID и завершите
lsof -i :8080      # Найти процесс
kill -9 <PID>      # Завершить процесс
```

### Быстрые команды

```bash
# Запуск веб-интерфейса
python warehouse_system.py

# Импорт товаров
python import_product.py 2498                    # По артикулу
python import_product.py "https://..."           # По URL

# ИИ-поиск
python ai_search_voice.py "запрос" --speak       # С озвучкой
python ai_search_voice.py "запрос"               # Без озвучки

# Карточки товаров
python create_all_cards.py                       # Все товары
python create_card_by_article.py 2498           # По артикулу

# API
curl http://localhost:8080/api/products
curl -X POST http://localhost:8080/api/ai-search \
  -H "Content-Type: application/json" \
  -d '{"query":"запрос"}'
```

### Скрипты автоматизации

```bash
# Экспорт данных
curl http://localhost:8080/api/export/json -o export.json

# Создание базы данных
python -c "
from warehouse_system import app, db
with app.app_context():
    db.create_all()
    print('База создана')
"
```

## 💻 Использование

### ИИ-поиск с голосом

```bash
# Ищем и озвучиваем результат
python ai_search_voice.py "красная кнопка" --speak

# Тихий поиск (без озвучки)
python ai_search_voice.py "двигатель Otis"
```

### Веб-интерфейс

1. Открой **http://localhost:8080**
2. Нажми **"➕ Импорт с snab-lift.ru"** для добавления товаров
3. Используй **фильтры** для поиска по критериям
4. Нажми **✏️** для редактирования склада
5. Нажми **📄** для печати карточки товара
6. Используй **🤖 ИИ-поиск** для сложных запросов

### API Endpoints

```bash
# Получить все товары
curl http://localhost:8080/api/products

# ИИ-поиск
curl -X POST http://localhost:8080/api/ai-search \
  -H "Content-Type: application/json" \
  -d '{"query":"красная кнопка"}'

# Импорт товара
curl -X POST http://localhost:8080/api/import/snablift \
  -d '{"query":"2498"}'

# Обновить складские данные
curl -X PUT http://localhost:8080/api/products/2498/stock \
  -d '{"zone":"A","rack":"12","quantity_actual":50}'

# Озвучить текст (macOS)
curl -X POST http://localhost:8080/api/speak \
  -d '{"text":"Товар найден"}'
```

## 🏗️ Структура проекта

```
warehouse/
├── warehouse_system.py          # Главный сервер (Flask)
├── warehouse_card.py            # Генератор HTML карточек
├── import_product.py            # Импорт товаров
├── ai_search_voice.py           # ИИ-поиск с озвучкой
├── ai_search_api.py             # API для ИИ-поиска
├── create_all_cards.py          # Массовое создание карточек
├── create_card_by_article.py    # Создание карточки по артикулу
├── parser*.py                   # Различные парсеры
├── templates/
│   ├── warehouse_dashboard.html # Веб-интерфейс
│   └── product_card.html        # Шаблон карточки товара
├── instance/
│   └── warehouse.db            # База данных SQLite
└── requirements.txt            # Зависимости Python
```

## 🛠️ Технические требования

### Минимальные
- **Python**: 3.8+
- **ОЗУ**: 2 GB
- **Диск**: 500 MB + место под базу
- **Браузер**: Chrome/Chromium (для парсинга)
- **ОС**: macOS / Linux / Windows

### Рекомендуемые (для комфортной работы)
- **ОЗУ**: 4 GB+ (Selenium + Chrome занимают память)
- **Диск**: 1 GB (для базы с 10,000+ товарами)
- **Интернет**: только для импорта товаров и ИИ-поиска

### macOS (идеально)
- macOS 10.14+
- Встроенный синтезатор речи `say`
- Python 3.8+ из Homebrew

### Дисковое пространство
```
Код проекта:           ~5 MB
Виртуальное окружение: ~150 MB
ChromeDriver:          ~10 MB
База данных:           ~50 MB (на 1000 товаров)
HTML карточки:         ~1 MB каждая
```

## 💰 Стоимость ИИ-поиска

- **Модель**: Llama 3.1 8B (через OpenRouter)
- **Цена**: $0.18 за 1 миллион токенов
- **Один запрос**: ~$0.0001 (0.01 цента)
- **Пример**: поиск "красная кнопка" = 446 токенов = $0.00008

## 🔧 Конфигурация

### Настройка голоса (macOS)

```bash
# Проверить доступные голоса
say -v '?' | grep ru

# Использовать конкретный голос
say -v Anna "Привет, я готов к работе"
```

### Смена порта сервера

В `warehouse_system.py` измените:
```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Порт 8080
```

## 🤝 Полный список API

### Товары
- `GET /api/products` — список товаров с пагинацией
- `GET /api/products/<article>` — один товар
- `POST /api/products` — добавить товар вручную
- `PUT /api/products/<article>/stock` — обновить складские данные
- `DELETE /api/products/<article>` — удалить товар

### Импорт
- `POST /api/import/snablift` — импорт с сайта snab-lift.ru
- `POST /api/import/batch` — массовый импорт списком

### ИИ и голос
- `POST /api/ai-search` — ИИ-поиск по описанию
- `POST /api/speak` — озвучка текста (macOS)

### Статистика
- `GET /api/stats` — статистика склада
- `GET /api/export/json` — экспорт всей базы

## 📝 Пример рабочего сценария

```bash
# 1. Импортируем несколько товаров
$ python import_product.py 2498
✅ Импортировано: Прерыватель (диск) D=40мм

$ python import_product.py 768
✅ Импортировано: Кнопочный модуль АК1-01-Кр

# 2. Ищем через ИИ с озвучкой
$ python ai_search_voice.py "красная кнопка для вызова" --speak
🤖 ИИ-ассистент: Найдено - Артикул 768...
🔊 [голосовой ответ]
💰 Стоимость: $0.00008

# 3. Открываем веб-интерфейс для управления
$ open http://localhost:8080
# Редактируем количество, зоны, печатаем карточки

# 4. Создаем HTML карточки для всех товаров
$ python create_all_cards.py
✅ Создано 50 карточек
```

## 🌟 Особенности проекта

✅ **Полностью локальная** — данные только на твоем компьютере  
✅ **Быстрая работа** — SQLite работает мгновенно  
✅ **Дешевый ИИ** — $0.01 за 100 поисков  
✅ **Голосовое управление** — macOS say + Web Speech API  
✅ **Печать этикеток** — HTML карточки готовы к печати  
✅ **REST API** — интегрируй с 1C, Excel, другими системами  
✅ **Без абонентской платы** — платишь только за ИИ-запросы (~$0.01)  

## 🐛 Устранение проблем

### Порт 5000 занят (macOS AirPlay)
```bash
# Уже настроен на порт 8080 в warehouse_system.py
python warehouse_system.py  # Работает на 8080
```

### Chrome не найден
```bash
# macOS
brew install --cask google-chrome

# Linux Ubuntu/Debian
sudo apt install chromium-browser

# Linux Fedora
sudo dnf install chromium
```

### Ошибка импорта товара
```bash
# Проверить интернет
ping snab-lift.ru

# Обновить драйверы
pip install --upgrade selenium webdriver-manager
```

### Нет звука на macOS
```bash
# Проверить, что say работает
say "Тест" -v Anna

# Увеличить громкость
osascript -e "set Volume 5"
```

## 📊 Производительность

- **Запуск сервера**: 2-3 секунды
- **Импорт товара**: 5-10 секунд (зависит от сайта)
- **Веб-интерфейс**: мгновенно (локальная база)
- **ИИ-поиск**: 2-3 секунды (зависит от интернета)
- **Генерация карточки**: < 1 секунды

## 📞 Поддержка

Если нашел баг или есть идеи:
1. Создай Issue на GitHub
2. Опиши проблему подробно
3. Приложи скриншоты если применимо

## 🎯 Roadmap

- [ ] Интеграция с 1C
- [ ] QR-коды для быстрого сканирования
- [ ] Мобильное приложение
- [ ] Облачная синхронизация
- [ ] Голосовое управление полностью

## 📜 Лицензия

MIT License — свободное использование для любых целей

---

**Создано с ❤️ для складского учета**  
**Автор**: [@swiftskytex-coder](https://github.com/swiftskytex-coder)  
**Версия**: 1.0.0  
**Дата**: 2024

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
