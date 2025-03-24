from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, UUID4


class TipoCompra(BaseModel):
    id: Optional[UUID4] = None
    nombre: str
    descripcion: Optional[str] = None
    created_at: Optional[datetime] = None


class Producto(BaseModel):
    id: Optional[UUID4] = None
    nombre: str
    marca: str
    precio: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CompraProducto(BaseModel):
    id: Optional[UUID4] = None
    compra_id: UUID4
    producto_id: UUID4
    cantidad: int
    precio_unitario: float
    subtotal: float
    created_at: Optional[datetime] = None


class Compra(BaseModel):
    id: Optional[UUID4] = None
    numero_compra: Optional[int] = None
    monto: float
    fecha: Optional[datetime] = None
    tipo_compra_id: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    productos: Optional[List[CompraProducto]] = None


# --- Models for Function Parameters --- #
class ProductoInput(BaseModel):
    """Modelo para la entrada de creación de producto."""

    nombre: str
    marca: str
    precio: float


class TipoCompraInput(BaseModel):
    """Modelo para la entrada de creación de tipo de compra."""

    nombre: str
    descripcion: Optional[str] = None


class ProductoCompraInput(BaseModel):
    """Modelo para la entrada de productos en una compra."""

    producto_id: str
    cantidad: int
    precio_unitario: float


class CompraInput(BaseModel):
    """Modelo para la entrada de creación de compra."""

    monto: float
    tipo_compra_id: str
    productos: List[ProductoCompraInput]


class ReporteVentasInput(BaseModel):
    """Modelo para la entrada de generación de reporte de ventas."""

    fecha_inicio: str
    fecha_fin: str
