from agents.base import Agent
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np


class ForecastingAgent(Agent):
    """ONLY job: look at a product's transaction history, predict the
    next 7 days of demand, and report how confident it is. Knows
    nothing about procurement, orders, or business rules."""

    def __init__(self):
        super().__init__(name="ForecastingAgent")

    def run(self, product, transactions):
        if len(transactions) < 5:
            return None  # not enough history — refuses to guess

        data = pd.DataFrame([
            {
                "day": (t.transaction_date - transactions[0].transaction_date).days,
                "quantity_sold": abs(t.quantity_change)
            }
            for t in transactions
        ])

        model = LinearRegression()
        model.fit(data[["day"]], data["quantity_sold"])

        # CONFIDENCE = R² score. Measures how well the line actually
        # fits the historical dots. 1.0 = perfect fit, 0.0 = the line
        # explains nothing (data too noisy/random to trust).
        confidence = round(max(0, model.score(data[["day"]], data["quantity_sold"])), 3)

        last_day = data["day"].max()
        future_days = np.array([[last_day + i] for i in range(1, 8)])
        predictions = model.predict(future_days)
        total_predicted = round(sum(max(0, p) for p in predictions), 2)

        # This dict IS the message handed to the next agent.
        return {
    "sku": product.sku,
    "product_name": product.name,
    "predicted_demand_7d": float(total_predicted),   # was: total_predicted
    "current_stock": product.quantity,
    "confidence": float(confidence),                  # was: confidence
}