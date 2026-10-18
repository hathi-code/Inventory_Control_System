import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from database import SessionLocal
import models

MIN_TRANSACTIONS = 15   # need enough data for a meaningful split
TEST_FRACTION = 0.25    # last 25% of days used as held-out test set

db = SessionLocal()
products = db.query(models.Product).all()

results = []

for product in products:
    transactions = (
        db.query(models.StockTransaction)
        .filter(models.StockTransaction.product_id == product.id)
        .filter(models.StockTransaction.direction == "out")
        .order_by(models.StockTransaction.transaction_date)
        .all()
    )

    if len(transactions) < MIN_TRANSACTIONS:
        continue

    data = pd.DataFrame([
        {
            "day": (t.transaction_date - transactions[0].transaction_date).days,
            "quantity_sold": abs(t.quantity_change),
        }
        for t in transactions
    ])

    # Chronological split — NOT random. This preserves the time-series
    # structure and avoids leaking future data into training.
    split_idx = int(len(data) * (1 - TEST_FRACTION))
    train, test = data.iloc[:split_idx], data.iloc[split_idx:]

    if len(test) < 2:
        continue  # too little held-out data to evaluate meaningfully

    X_train, y_train = train[["day"]], train["quantity_sold"]
    X_test, y_test = test[["day"]], test["quantity_sold"]

    # ---- Linear Regression ----
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    lr_pred = lr.predict(X_test)

    # ---- Random Forest ----
    rf = RandomForestRegressor(n_estimators=100, max_depth=4, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    def metrics(y_true, y_pred):
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        # MAPE guards against divide-by-zero on days with 0 actual sales
        mape = np.mean([
            abs(t - p) / t if t != 0 else 0
            for t, p in zip(y_true, y_pred)
        ]) * 100
        return round(mae, 3), round(rmse, 3), round(mape, 2)

    lr_mae, lr_rmse, lr_mape = metrics(y_test.values, lr_pred)
    rf_mae, rf_rmse, rf_mape = metrics(y_test.values, rf_pred)

    results.append({
        "sku": product.sku,
        "name": product.name,
        "train_size": len(train),
        "test_size": len(test),
        "lr_mae": lr_mae, "lr_rmse": lr_rmse, "lr_mape": lr_mape,
        "rf_mae": rf_mae, "rf_rmse": rf_rmse, "rf_mape": rf_mape,
    })

db.close()

# ---- Print results table ----
if not results:
    print(f"No products had >= {MIN_TRANSACTIONS} transactions. "
          f"Run seed_agent_data_viva.py first, or lower MIN_TRANSACTIONS.")
else:
    print(f"\n{'SKU':<20}{'Train':>7}{'Test':>6}   "
          f"{'LR MAE':>8}{'LR RMSE':>9}{'LR MAPE%':>10}   "
          f"{'RF MAE':>8}{'RF RMSE':>9}{'RF MAPE%':>10}")
    print("-" * 100)
    for r in results:
        print(f"{r['sku']:<20}{r['train_size']:>7}{r['test_size']:>6}   "
              f"{r['lr_mae']:>8}{r['lr_rmse']:>9}{r['lr_mape']:>10}   "
              f"{r['rf_mae']:>8}{r['rf_rmse']:>9}{r['rf_mape']:>10}")

    avg_lr_mae = round(np.mean([r["lr_mae"] for r in results]), 3)
    avg_rf_mae = round(np.mean([r["rf_mae"] for r in results]), 3)
    avg_lr_rmse = round(np.mean([r["lr_rmse"] for r in results]), 3)
    avg_rf_rmse = round(np.mean([r["rf_rmse"] for r in results]), 3)
    avg_lr_mape = round(np.mean([r["lr_mape"] for r in results]), 2)
    avg_rf_mape = round(np.mean([r["rf_mape"] for r in results]), 2)

    print("-" * 100)
    print(f"{'AVERAGE':<20}{'':>7}{'':>6}   "
          f"{avg_lr_mae:>8}{avg_lr_rmse:>9}{avg_lr_mape:>10}   "
          f"{avg_rf_mae:>8}{avg_rf_rmse:>9}{avg_rf_mape:>10}")

    print(f"\nProducts evaluated: {len(results)}")
    print(f"Lower MAE/RMSE/MAPE = better. Whichever model wins here is what goes in the paper.")