class OrderItem:

    def __init__(
        self,
        oil_name: str,
        volume: int,
        count: int,
        price: float,
        seed_weight_kg: float = 0.0,
        seed_price_per_kg: float = 0.0,
    ):
        self.oil_name = oil_name
        self.volume = volume
        self.count = count
        self.price = price
        self.seed_weight_kg = seed_weight_kg
        self.seed_price_per_kg = seed_price_per_kg

    def total_revenue(self) -> float:
        return float(self.price * self.count)

    def total_seed_weight_kg(self) -> float:
        return float(self.seed_weight_kg * self.count)

    def total_seed_cost(self) -> float:
        return float(self.total_seed_weight_kg() * self.seed_price_per_kg)

    def total_profit(self) -> float:
        return float(self.total_revenue() - self.total_seed_cost())
