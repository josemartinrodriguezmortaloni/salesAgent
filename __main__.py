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

console = Console()

load_dotenv()


async def show_database_status():
    """Muestra el estado de la base de datos al iniciar la aplicación"""
    try:
        console.print("\n" + "─" * 80)
        console.print("[bold cyan]🗃️ COMPROBANDO ESTADO DE LA BASE DE DATOS[/bold cyan]")

        # Implementación básica temporal
        try:
            # Intenta importar y usar el cliente de Supabase
            from src.db.supabase_client import supabase

            start_time = datetime.now().timestamp()
            response = (
                supabase.table("productos").select("count", count="exact").execute()
            )
            elapsed = datetime.now().timestamp() - start_time

            count = response.count if hasattr(response, "count") else len(response.data)

            console.print(
                Panel(
                    f"[bold green]✅ Conectado correctamente[/bold green]\n"
                    + f"[dim]Latencia: {elapsed * 1000:.2f}ms[/dim]\n"
                    + f"[dim]Registros: {count} productos[/dim]",
                    title="ESTADO DE LA BASE DE DATOS",
                    border_style="green",
                    expand=False,
                )
            )
        except Exception as e:
            console.print(
                Panel(
                    f"[bold yellow]⚠️ No se pudo verificar la base de datos[/bold yellow]\n"
                    + f"[dim]Error: {str(e)}[/dim]",
                    title="ESTADO DE LA BASE DE DATOS",
                    border_style="yellow",
                    expand=False,
                )
            )

        console.print("─" * 80 + "\n")
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]Error al comprobar estado: {str(e)}[/bold red]\n{traceback.format_exc()}",
                title="ERROR DE BASE DE DATOS",
                border_style="red",
                expand=False,
            )
        )


async def main():
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
