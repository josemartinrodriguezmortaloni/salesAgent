from typing import Any, Callable
from datetime import datetime
import time
import traceback
from .supabase_client import supabase
from .models import (
    Producto,
    Compra,
    TipoCompra,
    ProductoInput,
    CompraInput,
    ReporteVentasInput,
)
from rich.console import Console
from agents import function_tool, RunContextWrapper
from functools import wraps
from pydantic import BaseModel

console = Console()


# --- Pydantic Models for Function Parameters --- #
class ProductoCompra(BaseModel):
    """Modelo para los productos en una compra."""

    producto_id: str
    cantidad: int
    precio_unitario: float


def db_tracer(func):
    """Decorador que registra y visualiza operaciones de base de datos."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        operation_name = func.__name__
        start_time = time.time()

        # Mostrar inicio de operación
        console.print(f"\n[bold cyan]🗃️ DB OPERATION:[/] Iniciando {operation_name}")

        try:
            # Obtener parámetros relevantes para logging (sin exponer datos sensibles)
            params_str = ", ".join(
                [
                    f"{k}={v}"
                    for k, v in kwargs.items()
                    if k not in ["password", "token", "ctx"]
                ]
            )
            if params_str:
                console.print(f"[dim cyan]  └─ Parámetros: {params_str}[/dim cyan]")

            # Ejecutar la operación
            result = await func(*args, **kwargs)

            # Calcular tiempo transcurrido
            elapsed = time.time() - start_time

            # Mostrar éxito
            console.print(
                f"[bold green]✅ DB SUCCESS:[/] {operation_name} completado en {elapsed:.3f}s"
            )

            # Mostrar vista previa del resultado
            if result and isinstance(result, str):
                preview = result[:150] + "..." if len(result) > 150 else result
                console.print(f"[dim green]  └─ Resultado: {preview}[/dim green]")

            return result
        except Exception as e:
            # Calcular tiempo hasta el error
            elapsed = time.time() - start_time

            # Mostrar error
            console.print(
                f"[bold red]❌ DB ERROR:[/] {operation_name} falló en {elapsed:.3f}s: {str(e)}"
            )
            console.print(
                f"[dim red]  └─ {traceback.format_exc().splitlines()[-1]}[/dim red]"
            )

            # Re-lanzar la excepción
            raise

    return wrapper


def auto_schema(name_override: str):
    """Decorador que genera automáticamente el esquema JSON para las funciones de la base de datos."""

    def decorator(func: Callable):
        @wraps(func)
        @db_tracer  # Añadir el decorador de trazado de base de datos
        async def wrapper(ctx: RunContextWrapper[Any], *args, **kwargs):
            return await func(ctx, *args, **kwargs)

        return function_tool(name_override=name_override)(wrapper)

    return decorator


# --- Database Tools --- #
@auto_schema(name_override="obtener_productos")
async def get_productos(ctx: RunContextWrapper[Any]) -> str:
    """Obtener todos los productos disponibles en la base de datos."""
    try:
        console.print("[bold blue]📊 Consultando tabla productos...[/bold blue]")
        response = supabase.table("productos").select("*").execute()

        if not response.data:
            console.print("[bold yellow]⚠️ La consulta no retornó datos[/bold yellow]")
            return "[]"

        productos = [Producto(**producto) for producto in response.data]
        console.print(
            f"[bold green]✅ Encontrados {len(productos)} productos[/bold green]"
        )

        # Mostrar resumen de los productos encontrados
        for p in productos[:3]:  # Solo mostrar hasta 3 para no saturar
            console.print(f"[dim]  └─ {p.nombre}: ${p.precio} (ID: {p.id})[/dim]")

        if len(productos) > 3:
            console.print(f"[dim]  └─ ... y {len(productos) - 3} más[/dim]")

        return str(
            [
                {"nombre": p.nombre, "marca": p.marca, "precio": p.precio, "id": p.id}
                for p in productos
            ]
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error en consulta DB: {str(e)}[/bold red]")
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
            "monto": float(compra.monto),
            "tipo_compra_id": compra.tipo_compra_id,
            "fecha": datetime.now().isoformat(),
        }

        # Log para depuración
        console.print(
            f"[bold blue]📝 Creando compra:[/] Monto: ${compra.monto}, Tipo: {compra.tipo_compra_id}"
        )
        console.print(f"[dim blue]  └─ Datos a insertar: {compra_data}[/dim blue]")

        response_compra = supabase.table("compras").insert(compra_data).execute()

        if not response_compra.data:
            console.print(
                "[bold red]❌ Error:[/] No se recibieron datos de respuesta al crear la compra"
            )
            return "Error al crear la compra: No se recibieron datos de respuesta"

        compra_id = response_compra.data[0]["id"]
        console.print(f"[bold green]✅ Compra creada:[/] ID: {compra_id}")

        # Crear las relaciones con productos
        for producto in compra.productos:
            producto_data = {
                "compra_id": compra_id,
                "producto_id": producto.producto_id,
                "cantidad": producto.cantidad,
                "precio_unitario": float(producto.precio_unitario),
                "subtotal": float(producto.cantidad * producto.precio_unitario),
            }

            console.print(
                f"[bold blue]📝 Añadiendo producto a compra:[/] {producto.producto_id} x{producto.cantidad}"
            )
            producto_response = (
                supabase.table("compras_productos").insert(producto_data).execute()
            )

            if not producto_response.data:
                console.print(
                    f"[bold yellow]⚠️ Advertencia:[/] No se recibieron datos al añadir producto {producto.producto_id}"
                )

        return f"Compra creada exitosamente. ID: {compra_id}"
    except Exception as e:
        console.print(f"[bold red]❌ Error al crear compra:[/] {str(e)}")
        console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
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


@auto_schema(name_override="test_connection")
async def test_connection(ctx: RunContextWrapper[Any]) -> str:
    """Test the database connection by attempting to create and read a test product."""
    try:
        # Try to create a test product
        test_product = {
            "nombre": "Producto de Prueba",
            "marca": "Test",
            "precio": 0.01,
            "descripcion": "Este es un producto de prueba para verificar la conexión",
        }

        # Attempt to insert
        insert_response = supabase.table("productos").insert(test_product).execute()

        if not insert_response.data:
            return "❌ Error: No se pudo insertar el producto de prueba"

        # Get the inserted product ID
        product_id = insert_response.data[0]["id"]

        # Try to read the product back
        read_response = (
            supabase.table("productos").select("*").eq("id", product_id).execute()
        )

        if not read_response.data:
            return "❌ Error: No se pudo leer el producto de prueba"

        # Clean up - delete the test product
        supabase.table("productos").delete().eq("id", product_id).execute()

        return (
            "✅ Conexión exitosa: Se pudo crear, leer y eliminar un producto de prueba"
        )

    except Exception as e:
        return f"❌ Error de conexión: {str(e)}"
