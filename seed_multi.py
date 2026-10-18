import random
from datetime import datetime, timedelta
from database import SessionLocal
import models

PRODUCTS = [
    {"sku": "BLON-BLU-10P", "name": "Balloon (Blue, 10-pack)", "category": "Toys",
     "price": 149.00, "quantity": 19, "min_buffer": 15},
    {"sku": "MGI-YIPPIE-4P", "name": "Magic Yippie Kit (4-pack)", "category": "Grocery",
     "price": 399.00, "quantity": 42, "min_buffer": 10},
    {"sku": "STN-A4-500", "name": "A4 Notebook (500 sheets)", "category": "Stationery",
     "price": 89.00, "quantity": 120, "min_buffer": 30},
    {"sku": "ELC-USB-C1M", "name": "USB-C Cable (1m)", "category": "Electronics",
     "price": 199.00, "quantity": 8, "min_buffer": 20},
    {"sku": "KIT-BOWL-STL", "name": "Steel Mixing Bowl", "category": "Kitchen",
     "price": 299.00, "quantity": 35, "min_buffer": 10},
    {"sku": "GRC-RICE-5KG", "name": "Basmati Rice (5kg)", "category": "Grocery",
     "price": 649.00, "quantity": 60, "min_buffer": 25},
    {"sku": "APR-TSHIRT-M", "name": "Cotton T-Shirt (M)", "category": "Apparel",
     "price": 349.00, "quantity": 5, "min_buffer": 15},
]
 
# ---------------------------------------------------------------------------
# 2. Seeding logic
# ---------------------------------------------------------------------------
def seed():
    db = SessionLocal()
    today = datetime.now()
 
    try:
        for p in PRODUCTS:
            product = db.query(models.Product).filter(models.Product.sku == p["sku"]).first()
 
            if product:
                print(f"[skip]  {p['sku']} already exists (id={product.id}) — not duplicating.")
                continue
 
            product = models.Product(
                sku=p["sku"],
                name=p["name"],
                category=p["category"],
                price=p["price"],
                quantity=p["quantity"],
                min_buffer=p["min_buffer"],
            )
            db.add(product)
            db.commit()
            db.refresh(product)
            print(f"[create] {p['sku']} -> id={product.id}")
 
            # ---- 30 days of "out" transactions for demand history ----
            base_demand = max(1, p["quantity"] // 15)  # rough daily sell-through
            for day in range(30, 0, -1):
                transaction_date = today - timedelta(days=day)
                quantity_sold = max(1, base_demand + random.randint(-2, 3))
 
                db.add(models.StockTransaction(
                    product_id=product.id,
                    quantity_change=-quantity_sold,
                    direction="out",
                    transaction_date=transaction_date,
                ))
 
            db.commit()
            print(f"         + seeded 30 days of transaction history")
 
        print("\nDone. Run GET /products in Swagger to verify.")
 
    finally:
        db.close()
 
 
if __name__ == "__main__":
    seed()