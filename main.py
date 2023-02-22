from datetime import datetime
from OilOrder import OilOrder
from flask import Flask, render_template, request, escape

app = Flask(__name__)


def make_order():
    name = request.form['name']
    surname = request.form['surname']
    phone = request.form['phone']
    address = request.form['address']
    oil = request.form['oil']
    vol = int(request.form['volume'])
    count = int(request.form['count'])
    price = 900
    tot = price * count

    order = OilOrder(datetime.now().replace(microsecond=0), name, surname, phone, address, oil, vol, price, tot)
    save_order(order)


def save_order(order):
    with open('заказы.txt', 'a')  as orders:
        print(order.data, order.name, order.surname,
              order.phone, order.address, order.oil_type,
              order.volume, order.price, order.total_price, file=orders, sep='|')


@app.route('/entryorder')
@app.route('/')
def enrty_page() -> 'html':
    return render_template('entryorder.html', the_title='Выжимальня приветствует тебя!',
                           the_invitation='Введите данные заказа:',
                           the_clickbutton='Когда будете готовы, нажмите эту кнопку:')


@app.route('/showorder', methods=['POST'])
def show_order_list() -> 'html':
    make_order()
    with open('заказы.txt') as orders:
        list_order = []
        for line in orders:
            list_order.append(line.split('|'))
    titles = ('Клиент', 'Масло', 'Стоимость', 'Дата')
    return render_template('showorder.html', the_row_order=titles, the_data=list_order, )


# **********************************************************************************************



if __name__ == '__main__':
    app.run()
