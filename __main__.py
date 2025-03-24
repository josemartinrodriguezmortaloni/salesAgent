#!/usr/bin/env python
"""
Main entry point for the agent application.
Initializes the agent system with Supabase and handles user interactions.
"""

from src.agents.agents import Agents, ChatContext
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Initialize Rich console
console = Console()


async def display_agent_response(result: str):
    """Display the agent's response in a nicely formatted panel."""
    console.print(
        Panel(
            result,
            title="[bold blue]Assistant[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    )


async def display_user_message(message: str):
    """Display the user's message in a nicely formatted panel."""
    console.print(
        Panel(
            message,
            title="[bold green]User[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


async def main():
    # Display welcome message
    console.print(
        Panel(
            "[bold green]¡Bienvenido a nuestro sistema de ventas![/bold green]\n"
            "Escribe 'exit' para salir.",
            title="[bold blue]Sistema de Ventas[/bold blue]",
            border_style="blue",
        )
    )

    agents = Agents()
    context = ChatContext(uid=1)  # Initialize chat context

    while True:
        try:
            # Get user input
            prompt = Prompt.ask("\n[bold blue]Tú[/bold blue]")

            # Check for exit command
            if prompt.lower() == "exit":
                console.print(
                    Panel(
                        "[bold green]¡Gracias por usar nuestro servicio! ¡Que tengas un excelente día![/bold green]",
                        border_style="green",
                    )
                )
                break

            # Display user message
            await display_user_message(prompt)

            # Show processing message with spinner
            with console.status(
                "[bold blue]Procesando tu solicitud...[/bold blue]", spinner="dots"
            ):
                result = await agents.run(prompt, context)

            # Display agent response
            await display_agent_response(result)

        except KeyboardInterrupt:
            console.print(
                "\n[bold red]Interrumpido por el usuario. Saliendo...[/bold red]"
            )
            break
        except Exception as e:
            console.print(
                Panel(
                    f"[bold red]Error: {str(e)}[/bold red]",
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
