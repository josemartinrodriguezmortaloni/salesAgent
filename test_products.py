from dotenv import load_dotenv
import os
import asyncio
from src.db.supabase_client import supabase
from rich.console import Console
from rich.table import Table
import sys

console = Console()

# Cargar variables de entorno
load_dotenv()


async def search_products(search_term=None):
    """Busca productos en la base de datos y muestra los resultados"""
    console.print(f"\n[bold blue]🔍 BUSCANDO PRODUCTOS EN LA BASE DE DATOS[/]")

    try:
        # Obtener todos los productos
        response = supabase.table("productos").select("*").execute()

        if not response.data:
            console.print(
                "[bold yellow]⚠️ No se encontraron productos en la base de datos[/]"
            )
            return

        all_products = response.data
        console.print(
            f"[bold green]✅ Se encontraron {len(all_products)} productos en total[/]"
        )

        # Si hay un término de búsqueda, filtrar los resultados
        filtered_products = all_products
        if search_term:
            search_term = search_term.lower()
            filtered_products = [
                p
                for p in all_products
                if search_term in p["nombre"].lower()
                or search_term in p["marca"].lower()
            ]

            console.print(
                f"[bold blue]🔍 Filtrando por término de búsqueda: '{search_term}'[/]"
            )
            console.print(
                f"[bold blue]🔍 Se encontraron {len(filtered_products)} productos que coinciden[/]"
            )

        # Crear tabla para mostrar productos
        table = Table(title="PRODUCTOS ENCONTRADOS")
        table.add_column("Nombre", style="cyan")
        table.add_column("Precio", style="green")
        table.add_column("Marca", style="yellow")
        table.add_column("ID", style="dim")

        for p in filtered_products:
            table.add_row(p["nombre"], f"${p['precio']}", p["marca"], str(p["id"]))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]❌ Error al buscar productos: {str(e)}[/]")


if __name__ == "__main__":
    # Si hay argumentos, usar el primero como término de búsqueda
    search_term = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(search_products(search_term))
