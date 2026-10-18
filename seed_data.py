import random
from datetime import datetime, timedelta
from database import SessionLocal
import models

db = SessionLocal()

# Change this to the SKU you want to simulate history for
SKU = "MGI-YIPPIE-4P"

product = db.query(models.Product).filter(models.Product.sku == SKU).first()

if not product:
    print(f"Product with SKU {SKU} not found. Update the SKU variable and try again.")
else:
    today = datetime.now()
    base_demand = 5  # average units sold per day

    for day in range(30, 0, -1):  # 30 days ago up to yesterday
        transaction_date = today - timedelta(days=day)

        # Add small random variation so the trend looks realistic
        quantity_sold = max(1, base_demand + random.randint(-2, 3))

        transaction = models.StockTransaction(
            product_id=product.id,
            quantity_change=-quantity_sold,
            direction="out",
            transaction_date=transaction_date
        )
        db.add(transaction)

    db.commit()
    print(f"Inserted 30 days of simulated transaction history for {SKU}.")

db.close()