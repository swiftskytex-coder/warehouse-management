#!/bin/bash
# Запуск веб-интерфейса склада

cd "$(dirname "$0")"
source venv/bin/activate

echo "🏭 Запуск складского веб-интерфейса..."
echo "🌐 Откройте: http://localhost:5000"
echo ""
echo "Нажмите Ctrl+C для остановки"
echo ""

python warehouse_system.py
