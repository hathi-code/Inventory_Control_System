from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import models
from pydantic import BaseModel
from database import SessionLocal, engine
from fastapi import WebSocket, WebSocketDisconnect, Request
from websocket_manager import manager
from typing import Literal
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
from auth import get_current_user
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from auth import hash_password, verify_password, create_access_token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from agents.scheduler import start_scheduler
from agents.coordinator import run_agent_pipeline
from notifications import notify_order_decision
import logging
logging.basicConfig(level=logging.INFO, force=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
models.Base.metadata.create_all(bind=engine)
start_scheduler()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# The Schema (Defines what the user should send)
class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    price: float
    quantity: int
    min_buffer: int = 10  # Default value for min_buffer


@app.get("/products")
def read_products(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    products = db.query(models.Product).all()
    return products


# NEW: single-product lookup — fixes "Could not load product" on the dashboard,
# which needs this route when a Purchase Order is clicked.
@app.get("/products/{sku}")
def get_product(
    sku: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


# The POST Route (Saves data to PostgreSQL)
@app.post("/products")
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # 1. Create a new instance of the Product model
    new_item = models.Product(
        name=product.name,
        sku=product.sku,
        category=product.category,
        price=product.price,
        quantity=product.quantity,
        min_buffer=product.min_buffer
    )

    # 2. Add it to the session
    db.add(new_item)

    # 3. Commit to save it permanently in Postgres
    db.commit()

    # 4. Refresh to get the auto-generated ID back
    db.refresh(new_item)

    return new_item


@app.put("/products/scan/{sku}")
async def scan_product(
    sku: str,
    quantity: int,
    direction: Literal["in", "out"],
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="SKU not found.")

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be a positive number.")

    if direction == "out":
        if product.quantity - quantity < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock. Only {product.quantity} units available."
            )
        product.quantity -= quantity
        change = -quantity
    else:
        product.quantity += quantity
        change = quantity

    # Log this transaction for forecasting later
    transaction = models.StockTransaction(
        product_id=product.id,
        quantity_change=change,
        direction=direction
    )
    db.add(transaction)

    db.commit()
    db.refresh(product)

    if product.quantity <= product.min_buffer:
        alert_message = f"Warning! {product.name} is low on stock! Only {product.quantity} units left."
        await manager.broadcast(alert_message)

    return product


@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/forecast/{sku}")
def forecast_demand(sku: str, db: Session = Depends(get_db)):
    # Step 1: Find the product by SKU
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="SKU not found.")

    # Step 2: Pull all "out" transactions for this product (sales/usage history)
    # This is our raw historical data — the (day, units sold) pairs
    transactions = (
        db.query(models.StockTransaction)
        .filter(models.StockTransaction.product_id == product.id)
        .filter(models.StockTransaction.direction == "out")
        .order_by(models.StockTransaction.transaction_date)
        .all()
    )

    # Step 3: Need a minimum amount of data for a meaningful trend line
    if len(transactions) < 5:
        raise HTTPException(
            status_code=400,
            detail="Not enough historical data to generate a forecast (need at least 5 transactions)."
        )

    # Step 4: Convert to a table of (day number, quantity sold)
    # "day" = how many days after the FIRST transaction this one happened
    data = pd.DataFrame([
        {
            "day": (t.transaction_date - transactions[0].transaction_date).days,
            "quantity_sold": abs(t.quantity_change)
        }
        for t in transactions
    ])

    X = data[["day"]]           # Input feature: day number
    y = data["quantity_sold"]   # Target: units sold that day

    # Step 5: Fit the Linear Regression line to this data
    model = LinearRegression()
    model.fit(X, y)

    # Step 6: Predict demand for each of the next 7 days
    last_day = data["day"].max()
    future_days = np.array([[last_day + i] for i in range(1, 8)])
    predictions = model.predict(future_days)

    # Step 7: Package predictions, clipping any negative values to 0
    # (a line can technically predict negative demand, which makes no real-world sense)
    forecast = [
        {"day_offset": i + 1, "predicted_demand": round(max(0, predictions[i]), 2)}
        for i in range(7)
    ]

    total_predicted_demand = round(sum(p["predicted_demand"] for p in forecast), 2)

    # Step 8: Return a business-friendly recommendation, not just raw numbers
    return {
        "sku": sku,
        "product_name": product.name,
        "current_quantity": product.quantity,
        "min_buffer": product.min_buffer,
        "forecast_next_7_days": forecast,
        "total_predicted_demand_7_days": total_predicted_demand,
        "recommendation": (
            "Reorder soon" if product.quantity < total_predicted_demand
            else "Stock sufficient for now"
        )
    }


@app.delete("/products/{sku}")
def delete_product(
    sku: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete products.")

    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="SKU not found.")

    db.delete(product)
    db.commit()
    return {"message": f"Product {sku} deleted successfully."}


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "staff"


@app.post("/register")
@limiter.limit("3/minute")
def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken.")

    new_user = models.User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully", "username": new_user.username}


@app.post("/login")
@limiter.limit("5/minute")  # Limit to 5 login attempts per minute
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/agent/run-now")
def trigger_agent_pipeline_manually(
    current_user: dict = Depends(get_current_user)
):
    """TEMPORARY testing route — lets you trigger the pipeline on
    demand instead of waiting for the 6-hour schedule. Useful while
    building/demoing. Remove or restrict before final submission."""
    run_agent_pipeline()
    return {"message": "Agent pipeline executed."}


@app.get("/recommendations")
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return db.query(models.ReorderRecommendation).order_by(
        models.ReorderRecommendation.generated_at.desc()
    ).limit(20).all()


@app.get("/purchase-orders")
def get_all_purchase_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return db.query(models.PurchaseOrder).order_by(
        models.PurchaseOrder.placed_at.desc()
    ).limit(30).all()


@app.get("/purchase-orders/pending")
def get_pending_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return db.query(models.PurchaseOrder).filter(
        models.PurchaseOrder.status == "pending_approval"
    ).order_by(models.PurchaseOrder.placed_at.desc()).all()


# FIXED: this used to be defined twice. FastAPI only ever ran the first
# definition (status change only — no stock update), leaving the second
# definition (the one that actually restocks the product) as dead code.
# This single version merges both: it updates stock, logs the transaction,
# broadcasts the websocket alert, AND sends the SMS/email notification.
@app.put("/purchase-orders/{order_id}/approve")
async def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can approve orders.")

    order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Order is not pending approval.")

    # Actually receive the stock — simulate the order arriving
    product = db.query(models.Product).filter(models.Product.id == order.product_id).first()
    if product:
        product.quantity += order.quantity_ordered
        db.add(models.StockTransaction(
            product_id=product.id,
            quantity_change=order.quantity_ordered,
            direction="in",
        ))

    order.status = "approved"
    order.reviewed_by = current_user["username"]
    order.reviewed_at = func.now()
    db.commit()
    db.refresh(order)
    if product:
        db.refresh(product)  # ensures the response reflects the new quantity immediately

    await manager.broadcast(f"Order approved: {order.sku} restocked with {order.quantity_ordered} units.")
    notify_order_decision(order, decision="approved")  # NEW: SMS/email
    return order


@app.put("/purchase-orders/{order_id}/reject")
def reject_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can reject orders.")
    order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Order is not pending approval.")

    order.status = "rejected"
    order.reviewed_by = current_user["username"]
    order.reviewed_at = func.now()
    db.commit()
    db.refresh(order)

    notify_order_decision(order, decision="rejected")  # NEW: SMS/email
    return order


# NEW: lets the dashboard delete a purchase order. Scoped to pending_approval
# only, so the audit trail for anything already decided (auto_placed,
# approved, rejected) is preserved. Widen this if you want unrestricted delete.
@app.delete("/purchase-orders/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete orders.")
    order = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail="Only pending orders can be deleted. Approved/rejected orders are kept for audit history."
        )
    db.delete(order)
    db.commit()
    return {"detail": f"Order {order_id} deleted."}