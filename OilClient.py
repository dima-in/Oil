from Product import Product


class OilClient(Product):

    def __init__(self, name, surname, phone, address, oil_types: str, volume: int, price: int):
        super().__init__(oil_types, volume, price)
        self.name = name
        self.surname = surname
        self.phone = phone
        self.address = address
