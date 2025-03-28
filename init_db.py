from dotenv import load_dotenv
import os
import asyncio
from src.db.supabase_client import supabase
from rich.console import Console

console = Console()

load_dotenv()


async def init_database():
    """Initialize the database with basic data necessary for operation"""
    console.print("\n[bold blue]📦 INITIALIZING DATABASE[/]")

    try:
        response = (
            supabase.table("tipo_compra")
            .select("*")
            .eq("nombre", "Mercado Pago")
            .execute()
        )

        if response.data and len(response.data) > 0:
            console.print(
                "[bold green]✅ Payment type 'Mercado Pago' already exists[/]"
            )
            console.print(f"[dim green]  └─ ID: {response.data[0]['id']}[/dim green]")
            return

        console.print("[yellow]⚠️ Payment type 'Mercado Pago' not found, creating...[/]")

        new_tipo = {
            "nombre": "Mercado Pago",
            "descripcion": "Payments processed through Mercado Pago",
        }

        insert_response = supabase.table("tipo_compra").insert(new_tipo).execute()

        if insert_response.data and len(insert_response.data) > 0:
            console.print(
                "[bold green]✅ Payment type 'Mercado Pago' created successfully[/]"
            )
            console.print(
                f"[dim green]  └─ ID: {insert_response.data[0]['id']}[/dim green]"
            )
        else:
            console.print("[bold red]❌ Error creating payment type 'Mercado Pago'[/]")

    except Exception as e:
        console.print(f"[bold red]❌ Error initializing database: {str(e)}[/]")


if __name__ == "__main__":
    asyncio.run(init_database())
