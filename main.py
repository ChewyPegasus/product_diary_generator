import random
import datetime
import os
import yaml
import pandas as pd
from random import getrandbits

# --- Константы ---
PRODUCTS_PATH = os.path.join("data", "products")
RECIPES_PATH = os.path.join("data", "recipes")
REPORTS_DIR = "reports"
PURCHASE_LOCATIONS = ["магазин", "рынок", "физ. лицо"]
CONSUMPTION_SOURCES = ["куплено ранее", "из личного подсобного хозяйства", "в подарок"]

# --- Функции загрузки данных ---
def load_yaml_from_dir(path):
    """Загружает данные из всех yaml-файлов в указанной директории."""
    items = {}
    for filename in os.listdir(path):
        if filename.endswith(".yaml"):
            category = os.path.splitext(filename)[0]
            filepath = os.path.join(path, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                # Для продуктов - словарь, для рецептов - список
                if isinstance(data, dict):
                    for item_name, info in data.items():
                        info['category'] = category
                        items[item_name] = info
                elif isinstance(data, list):
                    if category not in items:
                        items[category] = []
                    items[category].extend(data)
    return items

class FamilySimulator:
    def __init__(self, family_size, initial_stock, products_db, recipes_db):
        self.family_size = family_size
        self.pantry = initial_stock.copy() # Реальная кладовая, пополняется покупками
        self.initial_pantry_tracker = initial_stock.copy() # Только для отслеживания потребления из начальных запасов
        self.products_db = products_db # База данных продуктов
        self.recipes_db = recipes_db # База данных рецептов
        self.all_purchases = [] # Все покупки
        self.all_consumptions = [] # Все потребления
        self.purchased_product_names = set() # Множество для хранения названий купленных продуктов
        print("--- Симуляция начинается! ---")
        print(f"Начальные запасы в кладовой: {self.pantry}\n")

    def _get_random_values(self, base_info, var_percent):
        """Возвращает случайные значения массы и цены с учетом процента отклонения."""
        high = bool(getrandbits(1))
        mass = base_info["mass"]
        price = base_info["price"]
        mass_variation = mass * (var_percent["mass"] / 100)
        price_variation = price * (var_percent["price"] / 100)
        if high:
            return [
                round(random.uniform(price, price + price_variation), 2),
                round(random.uniform(mass, mass + mass_variation), 2)
            ]
        return [
            round(random.uniform(price - price_variation, price), 2),
            round(random.uniform(mass - mass_variation, mass), 2)
        ]

    def consume_products(self, meal_type, current_date):
        """
        Симулирует потребление. В отчет о потреблении попадают только продукты,
        взятые из начальных запасов.
        """
        if meal_type not in self.recipes_db:
            print(f"Нет рецептов для '{meal_type}'")
            return
            
        recipe = random.choice(self.recipes_db[meal_type])
        print(f"Готовим '{recipe['name']}' на {meal_type}.")

        for item in recipe['ingredients']:
            product_name = item['product']
            required_amount = item['amount']
            
            # Уменьшаем запасы в реальной кладовой, чтобы симулировать необходимость покупок
            self.pantry[product_name] = self.pantry.get(product_name, 0) - required_amount
            
            # 1. Проверяем, был ли этот продукт когда-либо куплен.
            if product_name in self.purchased_product_names:
                continue # Если да, то его потребление больше не логируется.

            # 2. Если не был куплен, проверяем, есть ли он в начальных запасах.
            available_from_initial = self.initial_pantry_tracker.get(product_name, 0)
            
            if available_from_initial > 0:
                # В лог потребления идет только то, что было в начальных запасах
                amount_to_log = min(required_amount, available_from_initial)
                
                self.all_consumptions.append({
                    "Дата": current_date,
                    "Название продукта": product_name,
                    "Откуда получено": random.choice(CONSUMPTION_SOURCES),
                    "Сколько потреблено": round(amount_to_log, 2),
                    "Единица измерения": item['unit'],
                    "Примечание": f"для блюда '{recipe['name']}'"
                })
                
                # Уменьшаем остаток в трекере начальных запасов
                self.initial_pantry_tracker[product_name] -= amount_to_log

    def receive_products(self, current_date):
        """Симулирует получение продуктов не через покупку (подарок, свой урожай)."""
        # Событие происходит не каждый день, а с вероятностью 1 к 10
        if random.randint(1, 10) == 1:
            product_to_receive = random.choice(list(self.products_db.keys()))
            base_info = self.products_db[product_to_receive]
            # Получаем небольшое количество продукта
            amount_received = round(base_info['mass'] * random.uniform(0.5, 1.5), 2)
            r = random.random()
            if r < 0.1:
                source = "из личного подсобного хозяйства"
            elif r < 0.2:
                source = "в подарок"
            else:
                source = "куплено ранее"
            
            print(f"\nПолучен продукт: {amount_received} {base_info['unit']} '{product_to_receive}' ({source}).")

            # Добавляем продукт в оба хранилища, т.к. он не был куплен
            self.pantry[product_to_receive] = self.pantry.get(product_to_receive, 0) + amount_received
            self.initial_pantry_tracker[product_to_receive] = self.initial_pantry_tracker.get(product_to_receive, 0) + amount_received

    def go_shopping(self, current_date):
        """Симулирует поход в магазин за продуктами, которых мало или нет."""
        # Выбираем 3-5 случайных товаров для проверки в этот день
        products_to_check = random.sample(list(self.products_db.keys()), k=random.randint(20, 30))
        
        for product_name in products_to_check:
            base_info = self.products_db[product_name]
            # Условие для покупки: продукта мало ИЛИ это импульсивная покупка
            is_low_on_stock = self.pantry.get(product_name, 0) < base_info["mass"] * 2
            is_impulse_buy = random.randint(1, 20) == 1

            if is_low_on_stock or is_impulse_buy:
                if is_impulse_buy and not is_low_on_stock:
                    print(f"Импульсивная покупка: {product_name}")

                quantity_to_buy = random.randint(1, 4)
                
                # Получаем случайную цену и массу
                var_percents = base_info["variation_percent"]
                [unit_price, unit_mass] = self._get_random_values(base_info, var_percents)
                
                # quantity_to_buy * 
                bought_mass = round(unit_mass, 2)
                # GOIDA * bought_mass
                total_price = round(unit_price, 2) if base_info['unit'] != 'шт' else round(unit_price * quantity_to_buy, 2)

                self.all_purchases.append({
                    "Дата": current_date,
                    "Что купили": product_name,
                    "Где купили": random.choice(PURCHASE_LOCATIONS),
                    "Сколько купили": bought_mass,
                    "Единица измерения": base_info["unit"],
                    "Сколько уплачено": total_price,
                    "Примечание": f"цена в базе: {unit_price}"
                })
                # Пополняем запасы
                self.pantry[product_name] = self.pantry.get(product_name, 0) + bought_mass
                # Добавляем название продукта в "черный список"
                self.purchased_product_names.add(product_name)

    def run_simulation(self, days):
        start_date = datetime.date.today()
        for day in range(1, days + 1):
            current_date_obj = start_date + datetime.timedelta(days=day-1)
            current_date_str = current_date_obj.strftime('%Y-%m-%d') # Форматируем дату в строку
            print(f"--- День {day} ({current_date_str}) ---")

            # 1. Потребление (завтрак, обед и ужин)
            for _ in range(random.randint(2, 3)):
                self.consume_products("breakfast", current_date_str)
            for _ in range(random.randint(2, 3)):
                self.consume_products("lunch", current_date_str)
            for _ in range(random.randint(2, 3)):
                self.consume_products("dinner", current_date_str)
            
            # 2. Случайное получение продуктов (не покупка)
            self.receive_products(current_date_str)

            # 3. Покупки (теперь каждый день)
            print("\nИдем за покупками...")
            self.go_shopping(current_date_str)

            # Округляем значения в кладовой для чистоты
            self.pantry = {k: round(v, 2) for k, v in self.pantry.items()}
        
        self.save_reports()

    def save_reports(self):
        """Сохраняет отчеты о покупках и потреблении в XLSX файл."""
        if not os.path.exists(REPORTS_DIR):
            os.makedirs(REPORTS_DIR)
        
        report_filename = os.path.join(REPORTS_DIR, f"report_{datetime.date.today()}.xlsx")
        
        df_purchases = pd.DataFrame(self.all_purchases)
        df_consumption = pd.DataFrame(self.all_consumptions)
        
        with pd.ExcelWriter(report_filename, engine='openpyxl') as writer:
            df_purchases.to_excel(writer, sheet_name='Расходы на покупку', index=False)
            df_consumption.to_excel(writer, sheet_name='Потребление продуктов', index=False)
            
        print(f"--- Симуляция завершена. Отчет сохранен в файл: {report_filename} ---")


if __name__ == "__main__":
    # Загружаем данные
    products = load_yaml_from_dir(PRODUCTS_PATH)
    recipes = load_yaml_from_dir(RECIPES_PATH)

    # Начальные запасы семьи
    initial_pantry_stock = {
        product: info['mass'] * random.randint(1, 3) 
        for product, info in products.items()
    }
    print("Сгенерированы начальные запасы:")
    print(initial_pantry_stock)

    sim = FamilySimulator(
        family_size=4, 
        initial_stock=initial_pantry_stock,
        products_db=products,
        recipes_db=recipes
    )
    sim.run_simulation(14)