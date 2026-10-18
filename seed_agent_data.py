import random
from datetime import datetime, timedelta
from database import SessionLocal
import models

db = SessionLocal()

# sku -> (weekend_spike_multiplier, base_daily_qty, noise_range, starting_stock)
TARGET_SKUS = {
    "ELC-USB-C1M":       (1.3, 1.0, 0.5, 60),
    "APR-TSHIRT-M":      (1.4, 0.8, 0.4, 50),
    "BLON-BLU-10P":      (1.8, 0.7, 0.4, 40),
    "MGI-YIPPIE-4P":     (1.6, 1.2, 0.6, 60),
    "LPTP-HP-SILVR":     (1.0, 0.6, 0.4, 3),
    "HAIER-AIRFRR-BLCK": (1.1, 0.4, 0.3, 3),
    "GRC-RICE-5KG":      (1.15, 3.0, 1.0, 120),
    "MLK-500ML":         (1.05, 4.0, 0.8, 150),

    "IPHN-17-PRO":       (1.05, 0.5, 0.3, 2),
}

DAYS_OF_HISTORY = 35  # shorter, clean window -- less accumulated noise than 90 days
today = datetime.utcnow()
seeded_count = 0

for sku, (weekend_mult, base_qty, noise, starting_stock) in TARGET_SKUS.items():
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        print(f"SKIPPED {sku} -- not found in database")
        continue

    deleted = (
        db.query(models.StockTransaction)
        .filter(models.StockTransaction.product_id == product.id)
        .delete()
    )
    if deleted:
        print(f"  (cleared {deleted} existing transaction rows for {sku} before reseeding)")

    product.quantity = starting_stock

    for day_offset in range(DAYS_OF_HISTORY, 0, -1):
        txn_date = today - timedelta(days=day_offset)
        trend = base_qty + (DAYS_OF_HISTORY - day_offset) * (base_qty * 0.01)

        if txn_date.weekday() in (5, 6):
            trend *= weekend_mult

        qty = max(1, round(trend + random.uniform(-noise, noise)))

        transaction = models.StockTransaction(
            product_id=product.id,
            quantity_change=-qty,
            direction="out",
            transaction_date=txn_date,
        )
        db.add(transaction)

    seeded_count += 1
    print(f"Seeded {DAYS_OF_HISTORY} days for {sku} ({product.name}) -- current stock set to {product.quantity} units")

db.commit()
db.close()
print(f"\nDone. Seeded {seeded_count}/{len(TARGET_SKUS)} products.")
print("Next: open Swagger, POST /agent/run-now, then GET /purchase-orders/pending")