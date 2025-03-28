from dotenv import load_dotenv
import os
import asyncio
from src.db.supabase_client import supabase
from rich.console import Console
from rich.table import Table

console = Console()

# Cargar variables de entorno
load_dotenv()

# Nuevas pizzas a agregar sin el campo descripcion (que no existe en la tabla)
NUEVAS_PIZZAS = [
    {"nombre": "Pizza Napolitana", "marca": "Pizzería Italiana", "precio": 12.50},
    {"nombre": "Pizza Cuatro Quesos", "marca": "Pizzería Gourmet", "precio": 15.00},
    {"nombre": "Pizza Pepperoni", "marca": "American Style", "precio": 13.00},
    {"nombre": "Pizza Vegetariana", "marca": "Healthy Pizza", "precio": 13.50},
    {"nombre": "Pizza Hawaiana", "marca": "Tropical Taste", "precio": 12.00},
    {"nombre": "Pizza BBQ", "marca": "American Style", "precio": 14.50},
    {"nombre": "Pizza Margarita", "marca": "Pizzería Clásica", "precio": 11.00},
]


async def add_pizzas():
    """Añade nuevas pizzas a la base de datos"""
    console.print("\n[bold blue]🍕 AÑADIENDO NUEVAS PIZZAS A LA BASE DE DATOS[/]")

    # Primero verificar productos existentes para evitar duplicados
    try:
        response = supabase.table("productos").select("*").execute()
        existing_products = {p["nombre"].lower(): p for p in response.data}

        # Crear tabla para visualizar productos existentes
        table = Table(title="PRODUCTOS EXISTENTES")
        table.add_column("Nombre", style="cyan")
        table.add_column("Precio", style="green")
        table.add_column("Marca", style="yellow")

        for p in response.data:
            table.add_row(p["nombre"], f"${p['precio']}", p["marca"])

        console.print(table)
        console.print(f"[bold blue]Total productos existentes:[/] {len(response.data)}")

        # Añadir nuevas pizzas
        pizzas_added = 0
        pizza_errors = 0

        for pizza in NUEVAS_PIZZAS:
            # Verificar si ya existe
            if pizza["nombre"].lower() in existing_products:
                console.print(
                    f"[yellow]⚠️ La pizza '{pizza['nombre']}' ya existe en la base de datos, omitiendo...[/]"
                )
                continue

            try:
                # Insertar nueva pizza
                insert_response = supabase.table("productos").insert(pizza).execute()

                if insert_response.data and len(insert_response.data) > 0:
                    new_id = insert_response.data[0]["id"]
                    console.print(
                        f"[bold green]✅ Pizza añadida: {pizza['nombre']} (${pizza['precio']})[/]"
                    )
                    console.print(f"[dim green]  └─ ID: {new_id}[/dim green]")
                    pizzas_added += 1
                else:
                    console.print(
                        f"[bold red]❌ Error al añadir pizza '{pizza['nombre']}'[/]"
                    )
                    pizza_errors += 1

            except Exception as e:
                console.print(
                    f"[bold red]❌ Error al añadir pizza '{pizza['nombre']}': {str(e)}[/]"
                )
                pizza_errors += 1

        # Mostrar resumen final
        console.print("\n[bold blue]📊 RESUMEN DE OPERACIÓN[/]")
        console.print(f"[green]✅ Pizzas añadidas correctamente: {pizzas_added}[/]")

        if pizza_errors > 0:
            console.print(f"[red]❌ Errores al añadir pizzas: {pizza_errors}[/]")

        # Mostrar lista actualizada de productos
        response = supabase.table("productos").select("*").execute()

        table = Table(title="PRODUCTOS ACTUALIZADOS")
        table.add_column("Nombre", style="cyan")
        table.add_column("Precio", style="green")
        table.add_column("Marca", style="yellow")

        for p in response.data:
            table.add_row(p["nombre"], f"${p['precio']}", p["marca"])

        console.print(table)
        console.print(
            f"[bold blue]Total productos en base de datos:[/] {len(response.data)}"
        )

    except Exception as e:
        console.print(f"[bold red]❌ Error al acceder a la base de datos: {str(e)}[/]")


if __name__ == "__main__":
    asyncio.run(add_pizzas())
