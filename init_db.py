from dotenv import load_dotenv
import os
import asyncio
from src.db.supabase_client import supabase
from rich.console import Console

console = Console()

# Cargar variables de entorno
load_dotenv()


async def init_database():
    """Inicializar la base de datos con datos básicos necesarios para el funcionamiento"""
    console.print("\n[bold blue]📦 INICIALIZANDO BASE DE DATOS[/]")

    # Verificar si ya existe el tipo de compra Mercado Pago
    try:
        response = (
            supabase.table("tipo_compra")
            .select("*")
            .eq("nombre", "Mercado Pago")
            .execute()
        )

        if response.data and len(response.data) > 0:
            console.print("[bold green]✅ Tipo de compra 'Mercado Pago' ya existe[/]")
            console.print(f"[dim green]  └─ ID: {response.data[0]['id']}[/dim green]")
            return

        # Si no existe, crearlo
        console.print(
            "[yellow]⚠️ No se encontró tipo de compra 'Mercado Pago', creando...[/]"
        )

        new_tipo = {
            "nombre": "Mercado Pago",
            "descripcion": "Pagos procesados a través de Mercado Pago",
        }

        insert_response = supabase.table("tipo_compra").insert(new_tipo).execute()

        if insert_response.data and len(insert_response.data) > 0:
            console.print(
                "[bold green]✅ Tipo de compra 'Mercado Pago' creado exitosamente[/]"
            )
            console.print(
                f"[dim green]  └─ ID: {insert_response.data[0]['id']}[/dim green]"
            )
        else:
            console.print(
                "[bold red]❌ Error al crear tipo de compra 'Mercado Pago'[/]"
            )

    except Exception as e:
        console.print(f"[bold red]❌ Error al inicializar base de datos: {str(e)}[/]")


if __name__ == "__main__":
    asyncio.run(init_database())
