from supabase import create_client, Client
from dotenv import load_dotenv
import os
import time
from rich.console import Console

load_dotenv()
console = Console()
MAX_RETRIES = 3


def initialize_supabase_client():
    """Initializes the Supabase client with reconnection capability"""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        console.print(
            "[bold red]Error: Environment variables SUPABASE_URL and SUPABASE_KEY required[/bold red]"
        )
        raise ValueError("Supabase URL and Key are required")

    retry_count = 0
    last_error = None

    while retry_count < MAX_RETRIES:
        try:
            client = create_client(url, key)
            client.table("productos").select("count", count="exact").limit(1).execute()
            console.print(
                f"[bold green]✅ Connection to Supabase established successfully[/bold green]"
            )
            return client
        except Exception as e:
            retry_count += 1
            last_error = e
            wait_time = 2**retry_count
            console.print(
                f"[bold yellow]⚠️ Attempt {retry_count}/{MAX_RETRIES} failed: {str(e)}[/bold yellow]"
            )
            console.print(f"[dim]Retrying in {wait_time}s...[/dim]")
            time.sleep(wait_time)

    console.print(
        f"[bold red]❌ Could not connect to Supabase after {MAX_RETRIES} attempts[/bold red]"
    )
    raise last_error


supabase = initialize_supabase_client()
