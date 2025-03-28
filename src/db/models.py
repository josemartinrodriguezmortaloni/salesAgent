from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, UUID4


class PurchaseType(BaseModel):
    id: Optional[UUID4] = None
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class Product(BaseModel):
    id: Optional[UUID4] = None
    name: str
    brand: str
    price: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PurchaseProduct(BaseModel):
    id: Optional[UUID4] = None
    purchase_id: UUID4
    product_id: UUID4
    quantity: int
    unit_price: float
    subtotal: float
    created_at: Optional[datetime] = None


class Purchase(BaseModel):
    id: Optional[UUID4] = None
    purchase_number: Optional[int] = None
    amount: float
    date: Optional[datetime] = None
    purchase_type_id: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    products: Optional[List[PurchaseProduct]] = None


# --- Models for Function Parameters --- #
class ProductInput(BaseModel):
    """Model for product creation input."""

    name: str
    brand: str
    price: float


class PurchaseTypeInput(BaseModel):
    """Model for purchase type creation input."""

    name: str
    description: Optional[str] = None


class PurchaseProductInput(BaseModel):
    """Model for products in a purchase input."""

    product_id: str
    quantity: int
    unit_price: float


class PurchaseInput(BaseModel):
    """Model for purchase creation input."""

    amount: float
    purchase_type_id: str
    products: List[PurchaseProductInput]


class SalesReportInput(BaseModel):
    """Model for sales report generation input."""

    start_date: str
    end_date: str
