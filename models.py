from sqlalchemy import Column,Integer,String,Numeric,TIMESTAMP
from database import Base
from sqlalchemy.sql import func
from sqlalchemy import ForeignKey
class Product(Base):
    __tablename__="products"
    id=Column(Integer,primary_key=True,index=True)
    sku=Column(String,unique=True,nullable=False)
    name=Column(String,nullable=False)
    category=Column(String)
    price=Column(Numeric(10,2))
    quantity=Column(Integer,default=0)
    created_at=Column(TIMESTAMP,server_default=func.now())
    updated_at=Column(TIMESTAMP,server_default=func.now(),onupdate=func.now())
    min_buffer=Column(Integer,default=10)

class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity_change = Column(Integer)          # positive for "in", negative for "out"
    direction = Column(String)                 # "in" or "out"
    transaction_date = Column(TIMESTAMP, server_default=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="staff")  # "staff" or "admin"

class ReorderRecommendation(Base):
    """Stores what the Forecasting + Procurement agents decided,
    for low-value items that don't need human approval."""
    __tablename__ = "reorder_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    sku = Column(String)
    predicted_demand = Column(Numeric(10, 2))
    current_quantity = Column(Integer)
    message = Column(String)
    generated_at = Column(TIMESTAMP, server_default=func.now())


class PurchaseOrder(Base):
    """Every order the Procurement Agent creates lands here —
    either auto_placed (low value) or pending_approval (high value)."""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    sku = Column(String)
    quantity_ordered = Column(Integer)
    order_value = Column(Numeric(10, 2))
    status = Column(String, default="auto_placed")  # auto_placed | pending_approval | approved | rejected
    reason = Column(String)
    placed_by = Column(String, default="ProcurementAgent")
    placed_at = Column(TIMESTAMP, server_default=func.now())
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(TIMESTAMP, nullable=True)