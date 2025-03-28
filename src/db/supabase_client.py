from supabase import create_client, Client
from dotenv import load_dotenv
import os
import time
from rich.console import Console

load_dotenv()
console = Console()
MAX_RETRIES = 3


def initialize_supabase_client():
    """Inicializa el cliente Supabase con capacidad de reconexión"""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        console.print(
            "[bold red]Error: Variables de entorno SUPABASE_URL y SUPABASE_KEY requeridas[/bold red]"
        )
        raise ValueError("Supabase URL y Key son requeridas")

    retry_count = 0
    last_error = None

    while retry_count < MAX_RETRIES:
        try:
            client = create_client(url, key)
            # Hacer una pequeña prueba para verificar que funciona
            client.table("productos").select("count", count="exact").limit(1).execute()
            console.print(
                f"[bold green]✅ Conexión a Supabase establecida exitosamente[/bold green]"
            )
            return client
        except Exception as e:
            retry_count += 1
            last_error = e
            wait_time = 2**retry_count  # Backoff exponencial
            console.print(
                f"[bold yellow]⚠️ Intento {retry_count}/{MAX_RETRIES} fallido: {str(e)}[/bold yellow]"
            )
            console.print(f"[dim]Reintentando en {wait_time}s...[/dim]")
            time.sleep(wait_time)

    console.print(
        f"[bold red]❌ No se pudo conectar a Supabase después de {MAX_RETRIES} intentos[/bold red]"
    )
    raise last_error


# Inicializar el cliente
supabase = initialize_supabase_client()


def get_supabase() -> Client:
    """Get a configured Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("Missing Supabase credentials in environment variables")

    return create_client(url, key)


# Initialize Supabase client
supabase = get_supabase()
