#!/bin/bash
# Скрипт для запуска складской системы

echo "🏭 Запуск локальной базы данных склада..."
echo ""

# Активируем виртуальное окружение
source venv/bin/activate

# Создаем базу данных
echo "📦 Создание базы данных..."
python -c "
from warehouse_system import app, db
with app.app_context():
    db.create_all()
    print('✅ База данных создана')
"

echo ""
echo "🚀 Запуск сервера..."
echo "🌐 Открой: http://localhost:8080"
echo ""
echo "Команды:"
echo "  Ctrl+C - остановить сервер"
echo ""

# Запускаем сервер
python warehouse_system.py
