from datetime import date

from UseDatabase import UseDatabase, config


def _fetchone_dict(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _column_exists(cursor, table_name, column_name):
    cursor.execute(
        """SELECT COUNT(*)
           FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (config['database'], table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def _add_column_if_missing(cursor, table_name, column_name, column_definition):
    if not _column_exists(cursor, table_name, column_name):
        cursor.execute(
            f"""ALTER TABLE {table_name}
                ADD COLUMN {column_name} {column_definition}"""
        )


async def create_tables():
    with UseDatabase(config) as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS customers (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(50) NOT NULL,
                            surname VARCHAR(50) NOT NULL,
                            phone VARCHAR(20) NOT NULL,
                            address VARCHAR(100) NOT NULL
                            )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS price_list
                            (id INT PRIMARY KEY AUTO_INCREMENT,
                            oil_name VARCHAR(100) NOT NULL,
                            volume INT NOT NULL,
                            price FLOAT NOT NULL
                            )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS statuses_list (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            order_id INT NOT NULL,
                            order_status INT NOT NULL,
                            name VARCHAR(50) NOT NULL,
                            datetime DATETIME DEFAULT CURRENT_TIMESTAMP
                            )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS order_statuses (
                                id INT PRIMARY KEY,
                                name VARCHAR(50) NOT NULL
                                )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS orders (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          customer_id INT NOT NULL,
                          date DATE NOT NULL,
                          shipping_date DATE NOT NULL,
                          total_price FLOAT NOT NULL,
                          status INT NOT NULL,
                          FOREIGN KEY (status) REFERENCES order_statuses(id),
                          FOREIGN KEY (customer_id) REFERENCES customers(id)
                          )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS order_details (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          order_id INT NOT NULL,
                          oil_name VARCHAR(100) NOT NULL,
                          volume INT NOT NULL,
                          count INT NOT NULL,
                          price FLOAT NOT NULL,
                          FOREIGN KEY (order_id) REFERENCES orders(id)
                          )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS expense_entries (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          expense_date DATE NOT NULL,
                          item_name VARCHAR(200) NOT NULL,
                          weight_kg FLOAT NOT NULL DEFAULT 0,
                          price_per_kg FLOAT NOT NULL DEFAULT 0,
                          goods_total FLOAT NOT NULL DEFAULT 0,
                          delivery_cost FLOAT NOT NULL DEFAULT 0,
                          carsharing_cost FLOAT NOT NULL DEFAULT 0,
                          note VARCHAR(255) NULL
                          )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS production_batches (
                          id INT PRIMARY KEY AUTO_INCREMENT,
                          batch_date DATE NOT NULL,
                          oil_name VARCHAR(100) NOT NULL,
                          seed_weight_kg FLOAT NOT NULL DEFAULT 0,
                          seed_price_per_kg FLOAT NOT NULL DEFAULT 0,
                          yield_percent FLOAT NOT NULL DEFAULT 0,
                          output_volume_ml FLOAT NOT NULL DEFAULT 0,
                          labor_cost FLOAT NOT NULL DEFAULT 0,
                          packaging_cost FLOAT NOT NULL DEFAULT 0,
                          other_cost FLOAT NOT NULL DEFAULT 0,
                          note VARCHAR(255) NULL
                          )""")

        _add_column_if_missing(cursor, 'price_list', 'seed_weight_kg', 'FLOAT NOT NULL DEFAULT 0')
        _add_column_if_missing(cursor, 'price_list', 'seed_price_per_kg', 'FLOAT NOT NULL DEFAULT 0')

        _add_column_if_missing(cursor, 'order_details', 'seed_weight_kg', 'FLOAT NOT NULL DEFAULT 0')
        _add_column_if_missing(cursor, 'order_details', 'seed_price_per_kg', 'FLOAT NOT NULL DEFAULT 0')
        _add_column_if_missing(cursor, 'order_details', 'seed_cost', 'FLOAT NOT NULL DEFAULT 0')
        _add_column_if_missing(cursor, 'order_details', 'revenue', 'FLOAT NOT NULL DEFAULT 0')
        _add_column_if_missing(cursor, 'order_details', 'profit', 'FLOAT NOT NULL DEFAULT 0')


async def insert_statuses_to_database():
    with UseDatabase(config) as cursor:
        cursor.execute("SELECT COUNT(*) FROM order_statuses")
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (0, 'новый')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (1, 'получена предоплата')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (2, 'Avito доставка')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (3, 'Ozon')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (4, 'завершен')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (5, 'готов к выдаче')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (6, 'отменен')""")
            cursor.execute("""INSERT INTO order_statuses (id, name)
                VALUES (7, 'ожидает предоплаты')""")


def insert_price_list_items(name, price, volume):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO price_list (oil_name, volume, price) SELECT %s, %s, %s
               FROM DUAL
               WHERE NOT EXISTS (SELECT 1 FROM price_list LIMIT 1)""",
            (name, volume, int(price)),
        )


async def save_status(order_id, status, status_name):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO statuses_list (order_id, order_status, name)
               VALUES (%s, %s, %s)""",
            (order_id, status, status_name),
        )


async def get_status_name(status):
    with UseDatabase(config) as cursor:
        cursor.execute("""SELECT name FROM order_statuses WHERE id = %s""", (status,))
        return cursor.fetchone()[0]


def get_price_item(oil_name, volume):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, oil_name, volume, price, seed_weight_kg, seed_price_per_kg
               FROM price_list
               WHERE oil_name = %s AND volume = %s
               LIMIT 1""",
            (oil_name, volume),
        )
        return _fetchone_dict(cursor)


async def save_order_details(order_id, product):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO order_details (
                    order_id, oil_name, volume, count, price,
                    seed_weight_kg, seed_price_per_kg, seed_cost, revenue, profit
               )
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                order_id,
                product.oil_name,
                product.volume,
                product.count,
                product.price,
                product.seed_weight_kg,
                product.seed_price_per_kg,
                product.total_seed_cost(),
                product.total_revenue(),
                product.total_profit(),
            ),
        )


async def save_order(customer_id, order_date, order, shipping_date, status):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO orders (customer_id, date, shipping_date, total_price, status)
               VALUES (%s, %s, %s, %s, %s)""",
            (customer_id, order_date, shipping_date, order.calculate_total_price(), status),
        )
        return cursor.lastrowid


async def save_customer(address, name, phone, surname):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO customers (name, surname, phone, address)
               VALUES (%s, %s, %s, %s)""",
            (name, surname, phone, address),
        )
        return cursor.lastrowid


async def get_customer_by_phone(phone):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, name, surname, phone FROM customers WHERE phone = %s""",
            (phone,),
        )
        return cursor.fetchone()


def select_all_orders():
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT
                    orders.id,
                    orders.customer_id,
                    orders.date,
                    orders.shipping_date,
                    orders.total_price,
                    orders.status,
                    customers.name,
                    customers.surname,
                    customers.phone,
                    customers.address,
                    order_details.oil_name,
                    order_details.volume,
                    order_details.count,
                    order_details.price,
                    order_details.seed_weight_kg,
                    order_details.seed_price_per_kg,
                    order_details.seed_cost,
                    order_details.revenue,
                    order_details.profit
               FROM orders
               JOIN customers ON orders.customer_id = customers.id
               JOIN order_details ON orders.id = order_details.order_id
               ORDER BY orders.date DESC, orders.id DESC, order_details.id ASC"""
        )
        return cursor.fetchall()


def delete_order_dy_id(order_id_to_delete):
    with UseDatabase(config) as cursor:
        cursor.execute("""DELETE FROM statuses_list WHERE order_id = %s""", (order_id_to_delete,))
        cursor.execute("""DELETE FROM order_details WHERE order_id = %s""", (order_id_to_delete,))
        cursor.execute("""DELETE FROM orders WHERE id = %s""", (order_id_to_delete,))


def is_id_exist(order_id):
    with UseDatabase(config) as cursor:
        cursor.execute("""SELECT id FROM orders WHERE id = %s""", (order_id,))
        return cursor.fetchone() is not None


def get_all_prices():
    with UseDatabase(config) as cursor:
        cursor.execute(
            """SELECT id, oil_name, volume, price, seed_weight_kg, seed_price_per_kg
               FROM price_list
               ORDER BY oil_name, volume"""
        )
        return cursor.fetchall()


def update_price_item(price_id, oil_name, volume, price, seed_weight_kg, seed_price_per_kg):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """UPDATE price_list
               SET oil_name = %s,
                   volume = %s,
                   price = %s,
                   seed_weight_kg = %s,
                   seed_price_per_kg = %s
               WHERE id = %s""",
            (oil_name, volume, price, seed_weight_kg, seed_price_per_kg, price_id),
        )


def delete_price(price_id):
    with UseDatabase(config) as cursor:
        cursor.execute("""DELETE FROM price_list WHERE id = %s""", (price_id,))


def add_price_item(oil_name, volume, price, seed_weight_kg=0, seed_price_per_kg=0):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO price_list (oil_name, volume, price, seed_weight_kg, seed_price_per_kg)
               VALUES (%s, %s, %s, %s, %s)""",
            (oil_name, volume, price, seed_weight_kg, seed_price_per_kg),
        )
        return cursor.lastrowid


def clear_price_list():
    with UseDatabase(config) as cursor:
        cursor.execute("""DELETE FROM price_list""")


def list_expense_entries(date_from=None, date_to=None):
    filters = []
    params = []
    if date_from:
        filters.append("expense_date >= %s")
        params.append(date_from)
    if date_to:
        filters.append("expense_date <= %s")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ''

    with UseDatabase(config) as cursor:
        cursor.execute(
            f"""SELECT
                    id,
                    expense_date,
                    item_name,
                    weight_kg,
                    price_per_kg,
                    goods_total,
                    delivery_cost,
                    carsharing_cost,
                    note,
                    goods_total + delivery_cost + carsharing_cost AS total_expense
                FROM expense_entries
                {where_clause}
                ORDER BY expense_date DESC, id DESC""",
            tuple(params),
        )
        return [
            {
                'id': row[0],
                'expense_date': str(row[1]) if row[1] else None,
                'item_name': row[2],
                'weight_kg': row[3],
                'price_per_kg': row[4],
                'goods_total': row[5],
                'delivery_cost': row[6],
                'carsharing_cost': row[7],
                'note': row[8],
                'total_expense': row[9],
            }
            for row in cursor.fetchall()
        ]


def add_expense_entry(expense_date, item_name, weight_kg, price_per_kg, goods_total, delivery_cost, carsharing_cost, note):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO expense_entries (
                    expense_date, item_name, weight_kg, price_per_kg,
                    goods_total, delivery_cost, carsharing_cost, note
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (expense_date, item_name, weight_kg, price_per_kg, goods_total, delivery_cost, carsharing_cost, note),
        )
        return cursor.lastrowid


def delete_expense_entry(expense_id):
    with UseDatabase(config) as cursor:
        cursor.execute("""DELETE FROM expense_entries WHERE id = %s""", (expense_id,))


def list_production_batches(date_from=None, date_to=None):
    filters = []
    params = []
    if date_from:
        filters.append("batch_date >= %s")
        params.append(date_from)
    if date_to:
        filters.append("batch_date <= %s")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ''

    with UseDatabase(config) as cursor:
        cursor.execute(
            f"""SELECT
                    id,
                    batch_date,
                    oil_name,
                    seed_weight_kg,
                    seed_price_per_kg,
                    yield_percent,
                    output_volume_ml,
                    labor_cost,
                    packaging_cost,
                    other_cost,
                    note
                FROM production_batches
                {where_clause}
                ORDER BY batch_date ASC, id ASC""",
            tuple(params),
        )
        return [
            {
                'id': row[0],
                'batch_date': str(row[1]) if row[1] else None,
                'oil_name': row[2],
                'seed_weight_kg': row[3],
                'seed_price_per_kg': row[4],
                'yield_percent': row[5],
                'output_volume_ml': row[6],
                'labor_cost': row[7],
                'packaging_cost': row[8],
                'other_cost': row[9],
                'note': row[10],
            }
            for row in cursor.fetchall()
        ]


def add_production_batch(
    batch_date,
    oil_name,
    seed_weight_kg,
    seed_price_per_kg,
    yield_percent,
    output_volume_ml,
    labor_cost,
    packaging_cost,
    other_cost,
    note,
):
    with UseDatabase(config) as cursor:
        cursor.execute(
            """INSERT INTO production_batches (
                    batch_date, oil_name, seed_weight_kg, seed_price_per_kg,
                    yield_percent, output_volume_ml, labor_cost, packaging_cost,
                    other_cost, note
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                batch_date,
                oil_name,
                seed_weight_kg,
                seed_price_per_kg,
                yield_percent,
                output_volume_ml,
                labor_cost,
                packaging_cost,
                other_cost,
                note,
            ),
        )
        return cursor.lastrowid


def delete_production_batch(batch_id):
    with UseDatabase(config) as cursor:
        cursor.execute("""DELETE FROM production_batches WHERE id = %s""", (batch_id,))


def get_order_sales_for_batch_allocation(date_to=None):
    filters = []
    params = []
    if date_to:
        filters.append("orders.date <= %s")
        params.append(date_to)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ''

    with UseDatabase(config) as cursor:
        cursor.execute(
            f"""SELECT
                    order_details.id,
                    orders.date,
                    order_details.oil_name,
                    order_details.volume,
                    order_details.count,
                    COALESCE(order_details.revenue, order_details.price * order_details.count) AS revenue
                FROM order_details
                JOIN orders ON orders.id = order_details.order_id
                {where_clause}
                ORDER BY orders.date ASC, order_details.id ASC""",
            tuple(params),
        )
        return [
            {
                'order_detail_id': row[0],
                'order_date': str(row[1]) if row[1] else None,
                'oil_name': row[2],
                'volume_ml': float(row[3]) * float(row[4]),
                'revenue': float(row[5] or 0),
            }
            for row in cursor.fetchall()
        ]


def get_batch_analytics(date_from=None, date_to=None, daily_batch_limit=3):
    all_batches = list_production_batches(None, date_to)
    sales = get_order_sales_for_batch_allocation(date_to)

    queues = {}
    batch_stats = {}
    for batch in all_batches:
        batch_cost = (
            float(batch['seed_weight_kg'] or 0) * float(batch['seed_price_per_kg'] or 0)
            + float(batch['labor_cost'] or 0)
            + float(batch['packaging_cost'] or 0)
            + float(batch['other_cost'] or 0)
        )
        output_volume_ml = float(batch['output_volume_ml'] or 0)
        batch_stats[batch['id']] = {
            **batch,
            'batch_cost': batch_cost,
            'sold_volume_ml': 0.0,
            'allocated_revenue': 0.0,
            'realized_cost': 0.0,
            'realized_profit': 0.0,
            'remaining_volume_ml': output_volume_ml,
            'remaining_value_cost': batch_cost,
        }
        queues.setdefault(batch['oil_name'], []).append({
            'batch_id': batch['id'],
            'remaining_volume_ml': output_volume_ml,
            'batch_cost': batch_cost,
            'output_volume_ml': output_volume_ml,
        })

    for sale in sales:
        demand = float(sale['volume_ml'] or 0)
        revenue = float(sale['revenue'] or 0)
        queue = queues.get(sale['oil_name'], [])
        if demand <= 0 or not queue:
            continue

        revenue_per_ml = revenue / demand if demand else 0
        for batch_queue in queue:
            available = batch_queue['remaining_volume_ml']
            if available <= 0 or demand <= 0:
                continue
            allocated = min(available, demand)
            demand -= allocated
            batch_queue['remaining_volume_ml'] -= allocated

            stat = batch_stats[batch_queue['batch_id']]
            stat['sold_volume_ml'] += allocated
            stat['allocated_revenue'] += allocated * revenue_per_ml

        if demand > 0:
            # If sales exceed tracked production, the excess remains unassigned.
            continue

    filtered_batches = []
    for batch in all_batches:
        batch_date = batch['batch_date']
        if date_from and batch_date < str(date_from):
            continue
        stat = batch_stats[batch['id']]
        output_volume_ml = float(stat['output_volume_ml'] or 0)
        batch_cost = float(stat['batch_cost'] or 0)
        sold_volume_ml = float(stat['sold_volume_ml'] or 0)
        realized_cost = batch_cost * sold_volume_ml / output_volume_ml if output_volume_ml else 0
        remaining_volume_ml = max(output_volume_ml - sold_volume_ml, 0)
        stat['realized_cost'] = realized_cost
        stat['realized_profit'] = float(stat['allocated_revenue']) - realized_cost
        stat['remaining_volume_ml'] = remaining_volume_ml
        stat['utilization_percent'] = sold_volume_ml / output_volume_ml * 100 if output_volume_ml else 0
        filtered_batches.append(stat)

    daily_map = {}
    for stat in filtered_batches:
        day = stat['batch_date']
        info = daily_map.setdefault(day, {
            'date': day,
            'batches_count': 0,
            'output_volume_ml': 0.0,
            'sold_volume_ml': 0.0,
            'realized_profit': 0.0,
        })
        info['batches_count'] += 1
        info['output_volume_ml'] += float(stat['output_volume_ml'] or 0)
        info['sold_volume_ml'] += float(stat['sold_volume_ml'] or 0)
        info['realized_profit'] += float(stat['realized_profit'] or 0)

    daily_batches = []
    for day in sorted(daily_map.keys()):
        item = daily_map[day]
        item['daily_batch_limit'] = daily_batch_limit
        item['capacity_used_percent'] = (
            item['batches_count'] / daily_batch_limit * 100 if daily_batch_limit else 0
        )
        item['remaining_slots'] = max(daily_batch_limit - item['batches_count'], 0)
        daily_batches.append(item)

    totals = {
        'batches_count': len(filtered_batches),
        'output_volume_ml': sum(float(item['output_volume_ml'] or 0) for item in filtered_batches),
        'sold_volume_ml': sum(float(item['sold_volume_ml'] or 0) for item in filtered_batches),
        'remaining_volume_ml': sum(float(item['remaining_volume_ml'] or 0) for item in filtered_batches),
        'batch_cost': sum(float(item['batch_cost'] or 0) for item in filtered_batches),
        'allocated_revenue': sum(float(item['allocated_revenue'] or 0) for item in filtered_batches),
        'realized_profit': sum(float(item['realized_profit'] or 0) for item in filtered_batches),
    }

    return {
        'totals': totals,
        'batches': filtered_batches,
        'daily_batches': daily_batches,
        'daily_batch_limit': daily_batch_limit,
    }


def get_profit_summary(date_from=None, date_to=None, period='month'):
    group_expressions = {
        'day': ("DATE_FORMAT(orders.date, '%Y-%m-%d')", "DATE(orders.date)"),
        'week': ("DATE_FORMAT(orders.date, '%x-W%v')", "YEARWEEK(orders.date, 3)"),
        'month': ("DATE_FORMAT(orders.date, '%Y-%m')", "DATE_FORMAT(orders.date, '%Y-%m')"),
    }
    label_expression, group_expression = group_expressions.get(period, group_expressions['month'])

    filters = []
    params = []
    if date_from:
        filters.append("orders.date >= %s")
        params.append(date_from)
    if date_to:
        filters.append("orders.date <= %s")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ''

    with UseDatabase(config) as cursor:
        cursor.execute(
            f"""SELECT
                    COUNT(DISTINCT orders.id) AS orders_count,
                    COALESCE(SUM(order_details.revenue), 0) AS revenue,
                    COALESCE(SUM(order_details.seed_cost), 0) AS seed_cost,
                    COALESCE(SUM(order_details.profit), 0) AS profit,
                    COALESCE(SUM(order_details.seed_weight_kg * order_details.count), 0) AS seed_weight_kg
                FROM orders
                JOIN order_details ON orders.id = order_details.order_id
                {where_clause}""",
            tuple(params),
        )
        totals = _fetchone_dict(cursor) or {
            'orders_count': 0,
            'revenue': 0,
            'seed_cost': 0,
            'profit': 0,
            'seed_weight_kg': 0,
        }

        expense_filters = []
        expense_params = []
        if date_from:
            expense_filters.append("expense_date >= %s")
            expense_params.append(date_from)
        if date_to:
            expense_filters.append("expense_date <= %s")
            expense_params.append(date_to)
        expense_where_clause = f"WHERE {' AND '.join(expense_filters)}" if expense_filters else ''

        cursor.execute(
            f"""SELECT
                    COALESCE(SUM(goods_total), 0) AS goods_total,
                    COALESCE(SUM(delivery_cost), 0) AS delivery_cost,
                    COALESCE(SUM(carsharing_cost), 0) AS carsharing_cost,
                    COALESCE(SUM(goods_total + delivery_cost + carsharing_cost), 0) AS total_expense,
                    COALESCE(SUM(weight_kg), 0) AS purchased_weight_kg
                FROM expense_entries
                {expense_where_clause}""",
            tuple(expense_params),
        )
        expense_totals = _fetchone_dict(cursor) or {
            'goods_total': 0,
            'delivery_cost': 0,
            'carsharing_cost': 0,
            'total_expense': 0,
            'purchased_weight_kg': 0,
        }
        totals['extra_expense'] = expense_totals['total_expense']
        totals['net_profit'] = (totals['profit'] or 0) - (expense_totals['total_expense'] or 0)
        totals['purchased_weight_kg'] = expense_totals['purchased_weight_kg']

        cursor.execute(
            f"""SELECT
                    {label_expression} AS label,
                    COUNT(DISTINCT orders.id) AS orders_count,
                    COALESCE(SUM(order_details.revenue), 0) AS revenue,
                    COALESCE(SUM(order_details.seed_cost), 0) AS seed_cost,
                    COALESCE(SUM(order_details.profit), 0) AS profit,
                    COALESCE(SUM(order_details.seed_weight_kg * order_details.count), 0) AS seed_weight_kg
                FROM orders
                JOIN order_details ON orders.id = order_details.order_id
                {where_clause}
                GROUP BY {group_expression}
                ORDER BY MIN(orders.date) ASC""",
            tuple(params),
        )
        by_period = [
            {
                'label': row[0],
                'orders_count': row[1],
                'revenue': row[2],
                'seed_cost': row[3],
                'profit': row[4],
                'seed_weight_kg': row[5],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(
            f"""SELECT
                    {group_expressions.get(period, group_expressions['month'])[0].replace('orders.date', 'expense_date')} AS label,
                    COALESCE(SUM(goods_total), 0) AS goods_total,
                    COALESCE(SUM(delivery_cost), 0) AS delivery_cost,
                    COALESCE(SUM(carsharing_cost), 0) AS carsharing_cost,
                    COALESCE(SUM(goods_total + delivery_cost + carsharing_cost), 0) AS total_expense,
                    COALESCE(SUM(weight_kg), 0) AS purchased_weight_kg
                FROM expense_entries
                {expense_where_clause}
                GROUP BY {group_expressions.get(period, group_expressions['month'])[1].replace('orders.date', 'expense_date')}
                ORDER BY MIN(expense_date) ASC""",
            tuple(expense_params),
        )
        expenses_by_period_map = {
            row[0]: {
                'goods_total': row[1],
                'delivery_cost': row[2],
                'carsharing_cost': row[3],
                'total_expense': row[4],
                'purchased_weight_kg': row[5],
            }
            for row in cursor.fetchall()
        }

        period_map = {item['label']: item for item in by_period}
        all_labels = []
        for label in list(period_map.keys()) + list(expenses_by_period_map.keys()):
            if label not in all_labels:
                all_labels.append(label)
        by_period = []
        for label in all_labels:
            order_part = period_map.get(label, {})
            expense_part = expenses_by_period_map.get(label, {})
            gross_profit = order_part.get('profit', 0) or 0
            total_expense = expense_part.get('total_expense', 0) or 0
            by_period.append({
                'label': label,
                'orders_count': order_part.get('orders_count', 0) or 0,
                'revenue': order_part.get('revenue', 0) or 0,
                'seed_cost': order_part.get('seed_cost', 0) or 0,
                'profit': gross_profit,
                'seed_weight_kg': order_part.get('seed_weight_kg', 0) or 0,
                'extra_expense': total_expense,
                'net_profit': gross_profit - total_expense,
                'purchased_weight_kg': expense_part.get('purchased_weight_kg', 0) or 0,
            })

        cursor.execute(
            f"""SELECT
                    order_details.oil_name,
                    COALESCE(SUM(order_details.seed_weight_kg * order_details.count), 0) AS seed_weight_kg,
                    COALESCE(SUM(order_details.revenue), 0) AS revenue,
                    COALESCE(SUM(order_details.profit), 0) AS profit
                FROM orders
                JOIN order_details ON orders.id = order_details.order_id
                {where_clause}
                GROUP BY order_details.oil_name
                ORDER BY seed_weight_kg DESC, revenue DESC""",
            tuple(params),
        )
        by_oil = [
            {
                'oil_name': row[0],
                'seed_weight_kg': row[1],
                'revenue': row[2],
                'profit': row[3],
            }
            for row in cursor.fetchall()
        ]

        return {
            'date_from': str(date_from) if isinstance(date_from, date) else date_from,
            'date_to': str(date_to) if isinstance(date_to, date) else date_to,
            'period': period,
            'totals': totals,
            'by_period': by_period,
            'by_oil': by_oil,
            'expense_totals': expense_totals,
            'expenses': list_expense_entries(date_from, date_to),
        }
