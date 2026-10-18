from agents.base import Agent


class ProcurementAgent(Agent):
    """Receives a forecast message and independently decides whether
    to reorder. Low-value orders: acts automatically. High-value
    orders: creates a PENDING order for a human admin to approve."""

    def __init__(
        self,
        safety_margin: float = 1.1,       # order a bit extra as buffer
        min_confidence: float = 0.5,       # CONFIDENCE TRIGGER — see note below
        approval_threshold_value: float = 5000.0,  # ₹ value above which a human must approve
    ):
        super().__init__(name="ProcurementAgent")
        self.safety_margin = safety_margin
        self.min_confidence = min_confidence
        self.approval_threshold_value = approval_threshold_value

    def run(self, forecast_message: dict, product_price: float):
        if forecast_message is None:
            return None

        # CONFIDENCE TRIGGER: if the Forecasting Agent wasn't confident
        # enough in its own prediction, Procurement Agent refuses to
        # act on it at all — protects against ordering based on noise.
        if forecast_message["confidence"] < self.min_confidence:
            return None

        predicted = forecast_message["predicted_demand_7d"]
        current = forecast_message["current_stock"]

        if predicted <= current:
            return None  # stock is sufficient, no action needed

        suggested_order_qty = round((predicted * self.safety_margin) - current, 0)
        order_value = round(suggested_order_qty * product_price, 2)

        reason = (
            f"{forecast_message['product_name']}: predicted demand {predicted} "
            f"vs {current} in stock (confidence {forecast_message['confidence']*100:.0f}%)"
        )

        # VALUE TRIGGER: cheap orders -> full autonomy.
        # Expensive orders -> require a human to approve.
        action = "requires_approval" if order_value > self.approval_threshold_value else "auto_reorder"

        return {
    "sku": forecast_message["sku"],
    "action": action,
    "quantity_to_order": float(suggested_order_qty),  # was: suggested_order_qty
    "order_value": float(order_value),                 # was: order_value
    "reason": reason,
}
