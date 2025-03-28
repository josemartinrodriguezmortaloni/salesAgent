from typing import Any, Callable
from datetime import datetime
import time
import traceback
from .supabase_client import supabase
from .models import (
    Product,
    Purchase,
    PurchaseType,
    ProductInput,
    PurchaseInput,
    SalesReportInput,
)
from rich.console import Console
from agents import function_tool, RunContextWrapper
from functools import wraps
from pydantic import BaseModel
import json

console = Console()


# --- Pydantic Models for Function Parameters --- #
class PurchaseProduct(BaseModel):
    """Model for products in a purchase."""

    product_id: str
    quantity: int
    unit_price: float


def db_tracer(func):
    """Decorator that logs and visualizes database operations."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        operation_name = func.__name__
        start_time = time.time()

        console.print(f"\n[bold cyan]🗃️ DB OPERATION:[/] Starting {operation_name}")

        try:
            params_str = ", ".join(
                [
                    f"{k}={v}"
                    for k, v in kwargs.items()
                    if k not in ["password", "token", "ctx"]
                ]
            )
            if params_str:
                console.print(f"[dim cyan]  └─ Parameters: {params_str}[/dim cyan]")

            result = await func(*args, **kwargs)

            elapsed = time.time() - start_time

            console.print(
                f"[bold green]✅ DB SUCCESS:[/] {operation_name} completed in {elapsed:.3f}s"
            )

            if result and isinstance(result, str):
                preview = result[:150] + "..." if len(result) > 150 else result
                console.print(f"[dim green]  └─ Result: {preview}[/dim green]")

            return result
        except Exception as e:
            elapsed = time.time() - start_time

            console.print(
                f"[bold red]❌ DB ERROR:[/] {operation_name} failed in {elapsed:.3f}s: {str(e)}"
            )
            console.print(
                f"[dim red]  └─ {traceback.format_exc().splitlines()[-1]}[/dim red]"
            )

            raise

    return wrapper


def auto_schema(name_override: str):
    """Decorator that automatically generates JSON schema for database functions."""

    def decorator(func: Callable):
        @wraps(func)
        @db_tracer  # Add database tracing decorator
        async def wrapper(ctx: RunContextWrapper[Any], *args, **kwargs):
            return await func(ctx, *args, **kwargs)

        return function_tool(name_override=name_override)(wrapper)

    return decorator


# --- Database Tools --- #
@auto_schema(name_override="get_products")
async def get_products(ctx: RunContextWrapper[Any]) -> str:
    """Get all available products from the database."""
    try:
        console.print("[bold blue]📊 Querying products table...[/bold blue]")
        response = supabase.table("productos").select("*").execute()

        if not response.data:
            console.print("[bold yellow]⚠️ The query returned no data[/bold yellow]")
            return "[]"

        # Map Spanish field names to English field names required by the model
        products_mapped = []
        for p in response.data:
            # Transform the keys from Spanish to English
            product_mapped = {
                "id": p.get("id"),
                "name": p.get("nombre"),
                "brand": p.get("marca"),
                "price": p.get("precio"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
            }
            products_mapped.append(product_mapped)

        # Create product instances with the correctly mapped fields
        products = [Product(**product) for product in products_mapped]

        console.print(f"[bold green]✅ Found {len(products)} products[/bold green]")

        for p in products[:3]:
            console.print(f"[dim]  └─ {p.name}: ${p.price} (ID: {p.id})[/dim]")

        if len(products) > 3:
            console.print(f"[dim]  └─ ... and {len(products) - 3} more[/dim]")

        # Return products with English field names
        return str(
            [
                {"name": p.name, "brand": p.brand, "price": p.price, "id": p.id}
                for p in products
            ]
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error in DB query: {str(e)}[/bold red]")
        return f"Error getting products: {str(e)}"


@auto_schema(name_override="get_product")
async def get_product(ctx: RunContextWrapper[Any], product_id: str) -> str:
    """Get detailed information about a specific product.

    Args:
        product_id: The ID of the product to search for
    """
    try:
        response = (
            supabase.table("productos")
            .select("*")
            .eq("id", product_id)
            .single()
            .execute()
        )
        if response.data:
            # Map Spanish field names to English field names required by the model
            product_mapped = {
                "id": response.data.get("id"),
                "name": response.data.get("nombre"),
                "brand": response.data.get("marca"),
                "price": response.data.get("precio"),
                "created_at": response.data.get("created_at"),
                "updated_at": response.data.get("updated_at"),
            }

            # Create a product instance with the mapped fields
            product = Product(**product_mapped)

            return str(
                {
                    "name": product.name,
                    "brand": product.brand,
                    "price": product.price,
                }
            )
        return "Product not found"
    except Exception as e:
        return f"Error getting product: {str(e)}"


@auto_schema(name_override="create_product")
async def create_product(ctx: RunContextWrapper[Any], product: ProductInput) -> str:
    """Create a new product in the database.

    Args:
        product: Product data to create
    """
    try:
        # Map from English model fields to Spanish database fields
        product_data = {
            "nombre": product.name,
            "marca": product.brand,
            "precio": product.price,
        }

        response = supabase.table("productos").insert(product_data).execute()
        if response.data:
            return f"Product successfully created: {product.name} - {product.brand}"
        return "Error creating product"
    except Exception as e:
        return f"Error creating product: {str(e)}"


@auto_schema(name_override="create_purchase")
async def create_purchase(ctx: RunContextWrapper[Any], purchase: PurchaseInput) -> str:
    """Create a new purchase in the database.

    Args:
        purchase: Purchase data to create
    """
    try:
        purchase_data = {
            "monto": float(purchase.amount),
            "tipo_compra_id": purchase.purchase_type_id,
            "fecha": datetime.now().isoformat(),
        }

        console.print(
            f"[bold blue]📝 Creating purchase:[/] Amount: ${purchase.amount}, Type: {purchase.purchase_type_id}"
        )
        console.print(f"[dim blue]  └─ Data to insert: {purchase_data}[/dim blue]")

        response_purchase = supabase.table("compras").insert(purchase_data).execute()

        if not response_purchase.data:
            console.print(
                "[bold red]❌ Error:[/] No response data received when creating purchase"
            )
            return "Error creating purchase: No response data received"

        purchase_id = response_purchase.data[0]["id"]
        console.print(f"[bold green]✅ Purchase created:[/] ID: {purchase_id}")

        for product in purchase.products:
            product_data = {
                "compra_id": purchase_id,
                "producto_id": product.product_id,
                "cantidad": product.quantity,
                "precio_unitario": float(product.unit_price),
                "subtotal": float(product.quantity * product.unit_price),
            }

            console.print(
                f"[bold blue]📝 Adding product to purchase:[/] {product.product_id} x{product.quantity}"
            )
            product_response = (
                supabase.table("compras_productos").insert(product_data).execute()
            )

            if not product_response.data:
                console.print(
                    f"[bold red]❌ Error:[/] No data received when adding product {product.product_id}"
                )

        return f"Purchase created successfully. ID: {purchase_id}"
    except Exception as e:
        console.print(f"[bold red]❌ Error creating purchase:[/] {str(e)}")
        console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
        return f"Error creating purchase: {str(e)}"


@auto_schema(name_override="get_purchase_types")
async def get_purchase_types(ctx: RunContextWrapper[Any]) -> str:
    """Get all available purchase types."""
    try:
        response = supabase.table("tipo_compra").select("*").execute()

        # Map Spanish field names to English field names
        types_mapped = []
        for t in response.data:
            type_mapped = {
                "id": t.get("id"),
                "name": t.get("nombre", ""),
                "description": t.get("descripcion", ""),
                "created_at": t.get("created_at"),
            }
            types_mapped.append(type_mapped)

        types = [PurchaseType(**type_mapped) for type_mapped in types_mapped]
        types_list = [
            {"id": str(t.id), "name": t.name, "description": t.description or ""}
            for t in types
        ]

        mercado_pago_exists = any(
            t["name"].lower() == "mercado pago" for t in types_list
        )
        if not mercado_pago_exists:
            console.print("[bold yellow]⚠️ Type 'Mercado Pago' not found[/]")
            console.print(
                "[dim yellow]  └─ Will use the first available type or create a new one[/dim yellow]"
            )

            if types_list:
                console.print(
                    f"[dim yellow]  └─ Using type: {types_list[0]['name']} (ID: {types_list[0]['id']})[/dim yellow]"
                )

        formatted_output = json.dumps(types_list, ensure_ascii=False, indent=2)
        console.print(
            f"[bold green]✅ Payment types retrieved:[/] {len(types_list)} types"
        )
        return formatted_output

    except Exception as e:
        error_msg = f"Error getting payment types: {str(e)}"
        console.print(f"[bold red]❌ {error_msg}[/]")
        return error_msg


@auto_schema(name_override="generate_sales_report")
async def generate_sales_report(
    ctx: RunContextWrapper[Any], report: SalesReportInput
) -> str:
    """Generate a sales report for a specific period.

    Args:
        report: Data to generate the sales report
    """
    try:
        start_date_dt = datetime.fromisoformat(report.start_date)
        end_date_dt = datetime.fromisoformat(report.end_date)

        # Get purchases for the period
        query = (
            supabase.table("compras")
            .select("*")
            .gte("fecha", start_date_dt.isoformat())
            .lte("fecha", end_date_dt.isoformat())
        )

        response = query.execute()

        # Map Spanish field names to English field names
        purchases_mapped = []
        for p in response.data:
            purchase_mapped = {
                "id": p.get("id"),
                "purchase_number": p.get("numero_compra"),
                "amount": p.get("monto"),
                "date": p.get("fecha"),
                "purchase_type_id": p.get("tipo_compra_id"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
            }
            purchases_mapped.append(purchase_mapped)

        purchases = [Purchase(**purchase) for purchase in purchases_mapped]

        # Calculate statistics
        total_sales = sum(purchase.amount for purchase in purchases)
        purchase_count = len(purchases)
        average_purchase = total_sales / purchase_count if purchase_count > 0 else 0

        return str(
            {
                "total_sales": total_sales,
                "purchase_count": purchase_count,
                "average_purchase": average_purchase,
                "period": f"From {report.start_date} to {report.end_date}",
            }
        )
    except Exception as e:
        return f"Error generating report: {str(e)}"


@auto_schema(name_override="test_connection")
async def test_connection(ctx: RunContextWrapper[Any]) -> str:
    """Test the database connection by attempting to create and read a test product."""
    try:
        test_product = {
            "nombre": "Test Product",
            "marca": "Test",
            "precio": 0.01,
            "descripcion": "This is a test product to verify connection",
        }

        insert_response = supabase.table("productos").insert(test_product).execute()

        if not insert_response.data:
            return "❌ Error: Could not insert test product"

        product_id = insert_response.data[0]["id"]

        read_response = (
            supabase.table("productos").select("*").eq("id", product_id).execute()
        )

        if not read_response.data:
            return "❌ Error: Could not read test product"

        supabase.table("productos").delete().eq("id", product_id).execute()

        return "✅ Successful connection: Test product was created, read and deleted"

    except Exception as e:
        return f"❌ Connection error: {str(e)}"
