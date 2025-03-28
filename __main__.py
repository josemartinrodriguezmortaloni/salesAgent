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
from rich.table import Table
from src.db.supabase_client import supabase
from init_db import init_database

console = Console()

load_dotenv()


async def show_menu():
    """Displays the menu of available products as a restaurant menu"""
    console.print("\n" + "━" * 80)
    console.print("[bold cyan]🍕 OUR PIZZA MENU[/]")

    try:
        response = supabase.table("productos").select("*").execute()
        products = response.data

        table = Table(title="RESTAURANT MENU")
        table.add_column("🍕 Variety", style="cyan")
        table.add_column("💲 Price", style="green")
        table.add_column("🏷️ Brand", style="yellow")

        products = sorted(products, key=lambda x: x["precio"])

        for p in products:
            table.add_row(p["nombre"], f"${p['precio']}", p["marca"])

        console.print(table)
        console.print(
            "\n[bold cyan]Place your order now! Simply type which pizza you'd like to order.[/]"
        )
        console.print("━" * 80 + "\n")

    except Exception as e:
        console.print(f"[bold red]❌ Error loading menu: {str(e)}[/]")


async def show_database_status():
    """Shows the current status of the database connection and available products"""
    console.print("\n" + "━" * 80)
    console.print("🔍 CHECKING DATABASE STATUS")

    try:
        response = supabase.table("productos").select("*").execute()
        products = response.data

        table = Table(title="DATABASE STATUS")
        table.add_column("Status", style="green")
        table.add_column("Value", style="cyan")

        table.add_row("Connected correctly", "✅")
        table.add_row("Latency", "Not available")
        table.add_row("Records", f"{len(products)} products")

        console.print(table)

        if len(products) <= 5:
            for p in products:
                console.print(
                    f"  └─ {p['nombre']}: ${p['precio']} (ID: {p['id']})",
                    style="dim",
                )

    except Exception as e:
        console.print(f"[bold red]❌ Error connecting to Supabase: {str(e)}[/]")


async def main():
    await init_database()

    console.print(
        Panel(
            "AI agent ordering and payment system",
            title="SYSTEM STARTED",
            border_style="green",
            expand=False,
        )
    )

    await show_database_status()

    await show_menu()

    agents = Agents()
    context = ChatContext()

    while True:
        query = input("\nYour order 🍕 > ")

        if query.lower() == "exit":
            break

        if query.lower() == "debug":
            if hasattr(context, "get_messages"):
                console.print(
                    Panel(
                        f"Messages in context: {len(context.get_messages())}\n"
                        + f"Items in order: {list(context.current_order.keys()) if context.current_order else 'None'}",
                        title="CONTEXT STATUS",
                        border_style="yellow",
                        expand=False,
                    )
                )
            elif context and "messages" in context:
                console.print(
                    Panel(
                        f"Messages in context: {len(context['messages'])}",
                        title="CONTEXT STATUS",
                        border_style="yellow",
                        expand=False,
                    )
                )
            else:
                console.print("[yellow]No active context yet[/]")
            continue

        if query.lower() == "db-status":
            await show_database_status()
            continue

        if query.lower() == "menu":
            await show_menu()
            continue

        try:
            response = await agents.run(query, context=context)
        except Exception as e:
            console.print(
                f"[bold red]Error processing query: {str(e)}[/]", highlight=False
            )
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
