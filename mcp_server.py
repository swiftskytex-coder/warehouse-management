#!/usr/bin/env python3
"""
MCP (Model Context Protocol) сервер для складской системы
Позволяет AI ассистентам (Claude, GPT и др.) управлять складом
"""

import json
import sys
import asyncio
from typing import Any, Dict, List, Optional
from warehouse_system import app, db, Product, WarehouseStock
from warehouse_card import create_driver, parse_product_page, find_product_by_article, is_url
from datetime import datetime

class MCPServer:
    """MCP сервер для складского управления"""
    
    def __init__(self):
        self.name = "warehouse-management"
        self.version = "1.0.0"
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных инструментов с JSON Schema"""
        return [
            {
                "name": "list_products",
                "description": "Получить список всех товаров на складе",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Максимальное количество товаров (по умолчанию 50)",
                            "default": 50
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Смещение для пагинации (по умолчанию 0)",
                            "default": 0
                        }
                    }
                }
            },
            {
                "name": "get_product",
                "description": "Получить детальную информацию о товаре по артикулу",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "article": {
                            "type": "string",
                            "description": "Артикул товара (например: 2498)"
                        }
                    },
                    "required": ["article"]
                }
            },
            {
                "name": "search_products",
                "description": "Поиск товаров по названию, производителю или описанию",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_stock_stats",
                "description": "Получить статистику склада: общее количество, заканчивающиеся товары и т.д.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "import_product",
                "description": "Импортировать товар с сайта snab-lift.ru по артикулу или URL",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Артикул товара или URL (например: 2498 или https://snab-lift.ru/catalog/...)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "update_stock",
                "description": "Обновить складские данные товара: количество, местоположение и т.д.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "article": {
                            "type": "string",
                            "description": "Артикул товара"
                        },
                        "zone": {
                            "type": "string",
                            "description": "Зона склада (например: A, B)"
                        },
                        "rack": {
                            "type": "string",
                            "description": "Номер стеллажа"
                        },
                        "shelf": {
                            "type": "string",
                            "description": "Номер полки"
                        },
                        "cell": {
                            "type": "string",
                            "description": "Номер ячейки"
                        },
                        "quantity_actual": {
                            "type": "integer",
                            "description": "Фактическое количество на складе"
                        },
                        "quantity_min": {
                            "type": "integer",
                            "description": "Минимальный остаток для предупреждения"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Заметки о товаре"
                        }
                    },
                    "required": ["article"]
                }
            },
            {
                "name": "get_low_stock",
                "description": "Получить список товаров с низким остатком (меньше минимума)",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "create_product_card",
                "description": "Создать HTML карточку товара для печати",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "article": {
                            "type": "string",
                            "description": "Артикул товара"
                        }
                    },
                    "required": ["article"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Выполняет вызванный инструмент"""
        
        with app.app_context():
            if tool_name == "list_products":
                return self._list_products(arguments)
            elif tool_name == "get_product":
                return self._get_product(arguments)
            elif tool_name == "search_products":
                return self._search_products(arguments)
            elif tool_name == "get_stock_stats":
                return self._get_stock_stats()
            elif tool_name == "import_product":
                return self._import_product(arguments)
            elif tool_name == "update_stock":
                return self._update_stock(arguments)
            elif tool_name == "get_low_stock":
                return self._get_low_stock()
            elif tool_name == "create_product_card":
                return self._create_product_card(arguments)
            else:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Неизвестный инструмент: {tool_name}"}]
                }
    
    def _list_products(self, args: Dict) -> Dict:
        """Получает список товаров"""
        limit = args.get("limit", 50)
        offset = args.get("offset", 0)
        
        products = Product.query.offset(offset).limit(limit).all()
        
        result = []
        for p in products:
            stock = p.stock
            result.append({
                "article": p.article,
                "title": p.title,
                "manufacturer": p.manufacturer,
                "quantity": stock.quantity_actual if stock else 0,
                "zone": stock.zone if stock else None
            })
        
        return {
            "content": [{
                "type": "text",
                "text": f"Найдено {len(result)} товаров:\n" + 
                        "\n".join([f"- {p['article']}: {p['title']} ({p['quantity']} шт.)" for p in result])
            }]
        }
    
    def _get_product(self, args: Dict) -> Dict:
        """Получает товар по артикулу"""
        article = args.get("article")
        product = Product.query.filter_by(article=article).first()
        
        if not product:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Товар с артикулом {article} не найден"}]
            }
        
        stock = product.stock
        text = f"""
Товар: {product.title}
Артикул: {product.article}
Производитель: {product.manufacturer or 'не указан'}
Цена: {product.price or 'не указана'}

Складские данные:
- Количество: {stock.quantity_actual if stock else 0} шт.
- Минимальный остаток: {stock.quantity_min if stock else 0} шт.
- Местоположение: {f"{stock.zone}-{stock.rack}-{stock.shelf}-{stock.cell}" if stock and any([stock.zone, stock.rack, stock.shelf, stock.cell]) else 'не указано'}

{product.description[:200] if product.description else ''}
"""
        
        return {
            "content": [{"type": "text", "text": text.strip()}]
        }
    
    def _search_products(self, args: Dict) -> Dict:
        """Поиск товаров"""
        query = args.get("query", "").lower()
        
        products = Product.query.filter(
            db.or_(
                Product.article.ilike(f'%{query}%'),
                Product.title.ilike(f'%{query}%'),
                Product.manufacturer.ilike(f'%{query}%')
            )
        ).limit(20).all()
        
        if not products:
            return {
                "content": [{"type": "text", "text": f"По запросу '{query}' ничего не найдено"}]
            }
        
        text = f"Найдено {len(products)} товаров по запросу '{query}':\n\n"
        for p in products:
            stock_qty = p.stock.quantity_actual if p.stock else 0
            text += f"- {p.article}: {p.title} ({p.manufacturer or '?'}), {stock_qty} шт.\n"
        
        return {"content": [{"type": "text", "text": text}]}
    
    def _get_stock_stats(self) -> Dict:
        """Статистика склада"""
        total = Product.query.count()
        total_items = db.session.query(db.func.sum(WarehouseStock.quantity_actual)).scalar() or 0
        
        low_stock = Product.query.join(WarehouseStock).filter(
            WarehouseStock.quantity_actual < WarehouseStock.quantity_min,
            WarehouseStock.quantity_min > 0
        ).count()
        
        out_of_stock = Product.query.join(WarehouseStock).filter(
            WarehouseStock.quantity_actual == 0
        ).count()
        
        text = f"""
📊 Статистика склада:

- Всего товаров: {total}
- Единиц на складе: {total_items}
- ⚠️ Заканчивается: {low_stock}
- ❌ Нет в наличии: {out_of_stock}
"""
        
        return {"content": [{"type": "text", "text": text}]}
    
    def _import_product(self, args: Dict) -> Dict:
        """Импортирует товар с snab-lift.ru"""
        query = args.get("query")
        
        driver = create_driver()
        try:
            if is_url(query):
                product_url = query
            else:
                product_url = find_product_by_article(driver, query)
                if not product_url:
                    return {
                        "isError": True,
                        "content": [{"type": "text", "text": f"Товар {query} не найден на сайте"}]
                    }
            
            product_data = parse_product_page(driver, product_url)
            
            # Проверяем, не существует ли уже
            existing = Product.query.filter_by(article=product_data['article']).first()
            if existing:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Товар {product_data['article']} уже существует"}]
                }
            
            # Создаем товар
            from warehouse_system import ProductImage
            import json as json_lib
            
            product = Product(
                article=product_data['article'],
                title=product_data['title'],
                manufacturer=product_data.get('manufacturer'),
                price=product_data.get('price'),
                description=product_data.get('description'),
                url=product_data['url'],
                specifications=json_lib.dumps(product_data.get('specifications', {}))
            )
            db.session.add(product)
            db.session.flush()
            
            # Добавляем изображения
            for i, img_url in enumerate(product_data.get('images', [])[:5]):
                image = ProductImage(product_id=product.id, image_url=img_url, is_main=(i==0))
                db.session.add(image)
            
            # Создаем складскую запись
            stock = WarehouseStock(product_id=product.id)
            db.session.add(stock)
            db.session.commit()
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"✅ Импортировано: {product.title}\nАртикул: {product.article}\nФото: {len(product_data.get('images', []))}"
                }]
            }
            
        finally:
            driver.quit()
    
    def _update_stock(self, args: Dict) -> Dict:
        """Обновляет складские данные"""
        article = args.get("article")
        product = Product.query.filter_by(article=article).first()
        
        if not product:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Товар {article} не найден"}]
            }
        
        if not product.stock:
            product.stock = WarehouseStock(product_id=product.id)
        
        # Обновляем поля
        if "zone" in args:
            product.stock.zone = args["zone"]
        if "rack" in args:
            product.stock.rack = args["rack"]
        if "shelf" in args:
            product.stock.shelf = args["shelf"]
        if "cell" in args:
            product.stock.cell = args["cell"]
        if "quantity_actual" in args:
            product.stock.quantity_actual = args["quantity_actual"]
        if "quantity_min" in args:
            product.stock.quantity_min = args["quantity_min"]
        if "notes" in args:
            product.stock.notes = args["notes"]
        
        product.stock.last_counted = datetime.now()
        db.session.commit()
        
        location = f"{product.stock.zone or '-'}-{product.stock.rack or '-'}-{product.stock.shelf or '-'}-{product.stock.cell or '-'}"
        
        return {
            "content": [{
                "type": "text",
                "text": f"✅ Обновлено: {product.title}\nКоличество: {product.stock.quantity_actual} шт.\nМесто: {location}"
            }]
        }
    
    def _get_low_stock(self) -> Dict:
        """Получает товары с низким остатком"""
        products = Product.query.join(WarehouseStock).filter(
            WarehouseStock.quantity_actual < WarehouseStock.quantity_min,
            WarehouseStock.quantity_min > 0
        ).all()
        
        if not products:
            return {
                "content": [{"type": "text", "text": "✅ Нет товаров с низким остатком"}]
            }
        
        text = f"⚠️ Товары с низким остатком ({len(products)}):\n\n"
        for p in products:
            text += f"- {p.article}: {p.title} ({p.stock.quantity_actual} из {p.stock.quantity_min} мин.)\n"
        
        return {"content": [{"type": "text", "text": text}]}
    
    def _create_product_card(self, args: Dict) -> Dict:
        """Создает HTML карточку товара"""
        article = args.get("article")
        product = Product.query.filter_by(article=article).first()
        
        if not product:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Товар {article} не найден"}]
            }
        
        # Генерируем карточку
        product_dict = product.to_dict()
        from warehouse_card import create_warehouse_card
        filename = create_warehouse_card(product_dict)
        
        return {
            "content": [{
                "type": "text",
                "text": f"✅ Карточка создана: {filename}"
            }]
        }

def main():
    """Главная функция MCP сервера (stdio transport)"""
    server = MCPServer()
    
    # Отправляем информацию о сервере
    server_info = {
        "jsonrpc": "2.0",
        "id": 0,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": server.name,
                "version": server.version
            }
        }
    }
    print(json.dumps(server_info), flush=True)
    
    # Основной цикл обработки запросов
    for line in sys.stdin:
        try:
            message = json.loads(line)
            method = message.get("method")
            msg_id = message.get("id")
            params = message.get("params", {})
            
            if method == "tools/list":
                # Возвращаем список инструментов
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": server.get_tools()
                    }
                }
                print(json.dumps(response), flush=True)
                
            elif method == "tools/call":
                # Вызываем инструмент
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                result = server.execute_tool(tool_name, arguments)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": result
                }
                print(json.dumps(response), flush=True)
                
        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": msg_id if 'msg_id' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    main()
