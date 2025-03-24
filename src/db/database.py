from typing import List, Dict, Any, Callable, get_type_hints, Union
from datetime import datetime
from .supabase_client import supabase
from .models import (
    Producto,
    Compra,
    TipoCompra,
    ProductoInput,
    TipoCompraInput,
    ProductoCompraInput,
    CompraInput,
    ReporteVentasInput,
)
from rich.console import Console
from agents import function_tool, RunContextWrapper
from inspect import signature, Parameter
from functools import wraps
from pydantic import BaseModel

console = Console()


# --- Pydantic Models for Function Parameters --- #
class ProductoCompra(BaseModel):
    """Modelo para los productos en una compra."""

    producto_id: str
    cantidad: int
    precio_unitario: float


def auto_schema(name_override: str):
    """Decorador que genera automáticamente el esquema JSON para las funciones de la base de datos.

    Args:
        name_override: Nombre de la función para el agente
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(ctx: RunContextWrapper[Any], *args, **kwargs):
            return await func(ctx, *args, **kwargs)

        # Aplicar el decorador function_tool con el nombre personalizado
        return function_tool(name_override=name_override)(wrapper)

    return decorator


# --- Database Tools --- #
@auto_schema(name_override="obtener_productos")
async def get_productos(ctx: RunContextWrapper[Any]) -> str:
    """Obtener todos los productos disponibles en la base de datos."""
    try:
        response = supabase.table("productos").select("*").execute()
        productos = [Producto(**producto) for producto in response.data]
        return str(
            [
                {"nombre": p.nombre, "marca": p.marca, "precio": p.precio}
                for p in productos
            ]
        )
    except Exception as e:
        return f"Error al obtener productos: {str(e)}"


@auto_schema(name_override="obtener_producto")
async def get_producto(ctx: RunContextWrapper[Any], producto_id: str) -> str:
    """Obtener información detallada de un producto específico.

    Args:
        producto_id: El ID del producto a buscar
    """
    try:
        response = (
            supabase.table("productos")
            .select("*")
            .eq("id", producto_id)
            .single()
            .execute()
        )
        if response.data:
            producto = Producto(**response.data)
            return str(
                {
                    "nombre": producto.nombre,
                    "marca": producto.marca,
                    "precio": producto.precio,
                }
            )
        return "Producto no encontrado"
    except Exception as e:
        return f"Error al obtener producto: {str(e)}"


@auto_schema(name_override="crear_producto")
async def crear_producto(ctx: RunContextWrapper[Any], producto: ProductoInput) -> str:
    """Crear un nuevo producto en la base de datos.

    Args:
        producto: Datos del producto a crear
    """
    try:
        response = (
            supabase.table("productos")
            .insert(producto.model_dump(exclude_unset=True))
            .execute()
        )
        if response.data:
            return f"Producto creado exitosamente: {producto.nombre} - {producto.marca}"
        return "Error al crear el producto"
    except Exception as e:
        return f"Error al crear producto: {str(e)}"


@auto_schema(name_override="crear_compra")
async def crear_compra(ctx: RunContextWrapper[Any], compra: CompraInput) -> str:
    """Crear una nueva compra en la base de datos.

    Args:
        compra: Datos de la compra a crear
    """
    try:
        compra_data = {
            "monto": compra.monto,
            "tipo_compra_id": compra.tipo_compra_id,
            "fecha": datetime.now().isoformat(),
        }
        response_compra = supabase.table("compras").insert(compra_data).execute()

        if not response_compra.data:
            return "Error al crear la compra"

        compra_id = response_compra.data[0]["id"]

        # Crear las relaciones con productos
        for producto in compra.productos:
            producto_data = {
                "compra_id": compra_id,
                "producto_id": producto.producto_id,
                "cantidad": producto.cantidad,
                "precio_unitario": producto.precio_unitario,
                "subtotal": producto.cantidad * producto.precio_unitario,
            }
            supabase.table("compras_productos").insert(producto_data).execute()

        return f"Compra creada exitosamente. ID: {compra_id}"
    except Exception as e:
        return f"Error al crear compra: {str(e)}"


@auto_schema(name_override="obtener_tipos_compra")
async def get_tipos_compra(ctx: RunContextWrapper[Any]) -> str:
    """Obtener todos los tipos de compra disponibles."""
    try:
        response = supabase.table("tipo_compra").select("*").execute()
        tipos = [TipoCompra(**tipo) for tipo in response.data]
        return str(
            [
                {"id": str(t.id), "nombre": t.nombre, "descripcion": t.descripcion}
                for t in tipos
            ]
        )
    except Exception as e:
        return f"Error al obtener tipos de compra: {str(e)}"


@auto_schema(name_override="generar_reporte_ventas")
async def get_reporte_ventas(
    ctx: RunContextWrapper[Any], reporte: ReporteVentasInput
) -> str:
    """Generar un reporte de ventas para un período específico.

    Args:
        reporte: Datos para generar el reporte de ventas
    """
    try:
        fecha_inicio_dt = datetime.fromisoformat(reporte.fecha_inicio)
        fecha_fin_dt = datetime.fromisoformat(reporte.fecha_fin)

        # Obtener compras del período
        query = (
            supabase.table("compras")
            .select("*")
            .gte("fecha", fecha_inicio_dt.isoformat())
            .lte("fecha", fecha_fin_dt.isoformat())
        )

        response = query.execute()
        compras = [Compra(**compra) for compra in response.data]

        # Calcular estadísticas
        total_ventas = sum(compra.monto for compra in compras)
        cantidad_compras = len(compras)
        promedio_compra = total_ventas / cantidad_compras if cantidad_compras > 0 else 0

        return str(
            {
                "total_ventas": total_ventas,
                "cantidad_compras": cantidad_compras,
                "promedio_compra": promedio_compra,
                "periodo": f"Del {reporte.fecha_inicio} al {reporte.fecha_fin}",
            }
        )
    except Exception as e:
        return f"Error al generar reporte: {str(e)}"
