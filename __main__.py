#!/usr/bin/env python
"""
Main entry point for the agent application.
Initializes the agent system with Supabase and handles user interactions.
"""

from src.agents.agents import Agents, ChatContext
import asyncio
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
import traceback
from datetime import datetime
from rich.table import Table
from src.db.supabase_client import supabase
from init_db import init_database

console = Console()

load_dotenv()


async def show_menu():
    """Muestra el menú de productos disponibles como carta de restaurante"""
    console.print("\n" + "━" * 80)
    console.print("[bold cyan]🍕 NUESTRO MENÚ DE PIZZAS[/]")

    try:
        response = supabase.table("productos").select("*").execute()
        products = response.data

        # Crear tabla para el menú
        table = Table(title="CARTA DEL RESTAURANTE")
        table.add_column("🍕 Variedad", style="cyan")
        table.add_column("💲 Precio", style="green")
        table.add_column("🏷️ Marca", style="yellow")

        # Ordenar productos por precio
        products = sorted(products, key=lambda x: x["precio"])

        # Agregar los productos al menú
        for p in products:
            table.add_row(p["nombre"], f"${p['precio']}", p["marca"])

        console.print(table)
        console.print(
            "\n[bold cyan]¡Haz tu pedido ahora! Simplemente escribe qué pizza deseas ordenar.[/]"
        )
        console.print("━" * 80 + "\n")

    except Exception as e:
        console.print(f"[bold red]❌ Error al cargar el menú: {str(e)}[/]")


async def show_database_status():
    """Muestra el estado actual de la conexión a la base de datos y los productos disponibles"""
    console.print("\n" + "━" * 80)
    console.print("🔍 COMPROBANDO ESTADO DE LA BASE DE DATOS")

    try:
        response = supabase.table("productos").select("*").execute()
        products = response.data

        # Crear tabla para el estado
        table = Table(title="ESTADO DE LA BASE DE DATOS")
        table.add_column("Estado", style="green")
        table.add_column("Valor", style="cyan")

        # Añadir información a la tabla
        table.add_row("Conectado correctamente", "✅")
        table.add_row("Latencia", "No disponible")
        table.add_row("Registros", f"{len(products)} productos")

        console.print(table)

        # Mostrar información detallada de los productos si hay pocos
        if len(products) <= 5:
            for p in products:
                console.print(
                    f"  └─ {p['nombre']}: ${p['precio']} (ID: {p['id']})",
                    style="dim",
                )

    except Exception as e:
        console.print(f"[bold red]❌ Error al conectar con Supabase: {str(e)}[/]")


async def main():
    # Inicializar la base de datos con datos necesarios
    await init_database()

    console.print(
        Panel(
            "Sistema de ordenamiento y pagos con agentes de IA",
            title="SISTEMA INICIADO",
            border_style="green",
            expand=False,
        )
    )

    await show_database_status()

    # Mostrar el menú de productos
    await show_menu()

    agents = Agents()
    # Opciones:
    # 1. context = None - Usará el nuevo formato de diccionario
    # 2. context = ChatContext() - Usará el formato original de objeto
    # Elegimos usar el formato original para compatibilidad
    context = ChatContext()

    while True:
        query = input("\nTu pedido 🍕 > ")

        if query.lower() == "exit":
            break

        if query.lower() == "debug":
            # Comando especial para mostrar estado actual
            if hasattr(context, "get_messages"):
                console.print(
                    Panel(
                        f"Mensajes en contexto: {len(context.get_messages())}\n"
                        + f"Items en orden: {list(context.current_order.keys()) if context.current_order else 'Ninguno'}",
                        title="ESTADO DEL CONTEXTO",
                        border_style="yellow",
                        expand=False,
                    )
                )
            elif context and "messages" in context:
                console.print(
                    Panel(
                        f"Mensajes en contexto: {len(context['messages'])}",
                        title="ESTADO DEL CONTEXTO",
                        border_style="yellow",
                        expand=False,
                    )
                )
            else:
                console.print("[yellow]No hay contexto activo todavía[/]")
            continue

        if query.lower() == "db-status":
            # Comando especial para verificar estado de la base de datos
            await show_database_status()
            continue

        if query.lower() == "menu":
            await show_menu()
            continue

        # Procesar la consulta normal
        try:
            response = await agents.run(query, context=context)
        except Exception as e:
            console.print(
                f"[bold red]Error al procesar la consulta: {str(e)}[/]", highlight=False
            )
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
