#!/usr/bin/env python
"""
Test file for new functionalities and features.
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

async def test_agent_logging():
    """Test the agent logging functionality"""
    console.print("\n" + "━" * 80)
    console.print("[bold cyan] TESTING AGENT LOGGING[/]")

    try:
        agents = Agents()
        context = ChatContext()

        # Test different types of interactions
        test_queries = [
            "I want a pizza",
            "What's the price?",
            "I want to pay"
        ]

        for query in test_queries:
            console.print(f"\n[bold blue]Testing query:[/] {query}")
            try:
                response = await agents.run(query, context=context)
                console.print(f"[green]Response:[/] {response}")
            except Exception as e:
                console.print(f"[red]Error:[/] {str(e)}")

        # Verify logs in database
        logs = supabase.table("agent_logs")\
            .select("*")\
            .order("timestamp", desc=True)\
            .limit(5)\
            .execute()

        console.print("\n[bold green]Latest logs:[/]")
        for log in logs.data:
            console.print(f"  └─ {log['agent_name']}: {log['activity_type']} - {log['details']}")

    except Exception as e:
        console.print(f"[bold red]❌ Error in test: {str(e)}[/]")
        traceback.print_exc()

async def test_api_endpoints():
    """Test the API endpoints"""
    console.print("\n" + "━" * 80)
    console.print("[bold cyan]🧪 TESTING API ENDPOINTS[/]")

    try:
        # Test products endpoint
        products = supabase.table("productos").select("*").execute()
        console.print(f"\n[bold green]Products count:[/] {len(products.data)}")

        # Test payment types
        payment_types = supabase.table("tipo_compra").select("*").execute()
        console.print(f"[bold green]Payment types count:[/] {len(payment_types.data)}")

        # Test agent logs
        logs = supabase.table("agent_logs").select("*").execute()
        console.print(f"[bold green]Agent logs count:[/] {len(logs.data)}")

    except Exception as e:
        console.print(f"[bold red]❌ Error in API test: {str(e)}[/]")
        traceback.print_exc()

async def main():
    await init_database()

    console.print(
        Panel(
            "Testing new functionalities",
            title="TEST MODE",
            border_style="yellow",
            expand=False,
        )
    )

    # Run tests
    await test_agent_logging()
    await test_api_endpoints()

if __name__ == "__main__":
    asyncio.run(main())
