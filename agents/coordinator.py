from agents.forecasting_agent import ForecastingAgent
from agents.procurement_agent import ProcurementAgent
from database import SessionLocal
import models
import logging
from notifications import notify_admin_of_pending_order  

logger = logging.getLogger("agent_pipeline")

forecasting_agent = ForecastingAgent()
procurement_agent = ProcurementAgent(min_confidence=0.3)


def run_agent_pipeline():
    """Runs every time the scheduler TRIGGERS it (see main.py).
    Loops through every product, passes it through both agents,
    and records whatever they decide. One bad product can't crash
    the whole run — errors are isolated per product."""
    db = SessionLocal()
    try:
        products = db.query(models.Product).all()

        for product in products:
            try:
                # Skip products that already have an unresolved order —
                # prevents duplicate orders (and duplicate email notifications)
                # every time the pipeline reruns before the existing one is
                # approved or rejected.
                existing_open_order = (
                    db.query(models.PurchaseOrder)
                    .filter(
                        models.PurchaseOrder.product_id == product.id,
                        models.PurchaseOrder.status.in_(["auto_placed", "pending_approval"]),
                    )
                    .first()
                )
                if existing_open_order:
                    logger.info(
                        f"Skipping {product.sku} — open order #{existing_open_order.id} "
                        f"already exists (status: {existing_open_order.status})"
                    )
                    continue

                transactions = (
                    db.query(models.StockTransaction)
                    .filter(models.StockTransaction.product_id == product.id)
                    .filter(models.StockTransaction.direction == "out")
                    .order_by(models.StockTransaction.transaction_date)
                    .all()
                )

                # Step 1: Forecasting Agent predicts demand + confidence
                forecast_message = forecasting_agent.run(product, transactions)

                # Step 2: message handed to Procurement Agent, which decides
                decision = procurement_agent.run(forecast_message, float(product.price))

                if decision:
                    order = models.PurchaseOrder(
                        product_id=product.id,
                        sku=decision["sku"],
                        quantity_ordered=int(decision["quantity_to_order"]),
                        order_value=decision["order_value"],
                        reason=decision["reason"],
                        status="auto_placed" if decision["action"] == "auto_reorder" else "pending_approval",
                    )
                    db.add(order)

                    if decision["action"] == "auto_reorder":
                        product.quantity += int(decision["quantity_to_order"])
                        transaction = models.StockTransaction(
                            product_id=product.id,
                            quantity_change=int(decision["quantity_to_order"]),
                            direction="in",
                        )
                        db.add(transaction)

                    if order.status == "pending_approval":
                        notify_admin_of_pending_order(order)

                    logger.info(f"[{order.status}] {decision['reason']}")
                else:
                    logger.info(f"No action for {product.sku} — forecast: {forecast_message}")

            except Exception as e:
                logger.error(f"Agent pipeline failed for SKU {product.sku}: {e}")
                continue

        db.commit()
    finally:
        db.close()