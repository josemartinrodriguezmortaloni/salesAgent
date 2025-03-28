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
        table.add_row("Latencia", f"{response.execution_time_client:.2f}ms")
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

    agents = Agents()
    context = ChatContext()
    console.print(f"[bold blue]Contexto creado con ID:[/] {context.uid}")

    while True:
        query = input("Your: ")

        if query.lower() == "exit":
            break

        if query.lower() == "debug":
            # Comando especial para mostrar estado actual
            console.print(
                Panel(
                    f"Mensajes en contexto: {len(context.get_messages())}\n"
                    + f"Items en orden: {list(context.current_order.keys()) if context.current_order else 'Ninguno'}",
                    title="ESTADO DEL CONTEXTO",
                    border_style="yellow",
                    expand=False,
                )
            )
            continue

        if query.lower() == "db-status":
            # Comando especial para verificar estado de la base de datos
            await show_database_status()
            continue

        # Procesar la consulta normal
        response = await agents.run(query, context=context)
        print(f"\nAgent: {response}")


if __name__ == "__main__":
    asyncio.run(main())
