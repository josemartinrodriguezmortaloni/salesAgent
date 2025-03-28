from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class CarritoView:
    @staticmethod
    def mostrar_carrito(carrito, clear_screen=True):
        if clear_screen:
            console.clear()

        if not carrito:
            mensaje = Text("🛒 Your cart is empty", style="bold yellow")
            panel = Panel(mensaje, title="Cart", border_style="yellow")
            console.print(panel)
            return

        table = Table(title="🛒 Your Cart")

        table.add_column("Product", style="cyan")
        table.add_column("Quantity", style="green", justify="right")
        table.add_column("Unit Price", style="yellow", justify="right")
        table.add_column("Subtotal", style="yellow", justify="right")

        total = 0

        for item_key, item_data in carrito.items():
            producto = item_data.producto
            cantidad = item_data.cantidad
            precio = (
                item_data.precio_unitario
                if item_data.precio_unitario is not None
                else 0
            )

            subtotal = cantidad * precio
            total += subtotal

            precio_str = f"${precio:.2f}" if precio is not None else "Pending"
            subtotal_str = f"${subtotal:.2f}" if precio is not None else "Pending"

            table.add_row(producto, str(cantidad), precio_str, subtotal_str)

        table.add_row("TOTAL", "", "", f"${total:.2f}", style="bold")

        console.print(table)

    @staticmethod
    def mostrar_resumen_pago(carrito, metodo_pago=None, link_pago=None):
        table = Table(title="📝 Purchase Summary")

        table.add_column("Detail", style="cyan")
        table.add_column("Information", style="green")

        total = sum(
            item.cantidad
            * (item.precio_unitario if item.precio_unitario is not None else 0)
            for item in carrito.values()
        )

        table.add_row("Number of products:", str(len(carrito)))
        table.add_row(
            "Products:",
            ", ".join(
                [f"{item.cantidad} {item.producto}" for item in carrito.values()]
            ),
        )
        table.add_row("Total to pay:", f"${total:.2f}")

        if metodo_pago:
            table.add_row("Payment method:", metodo_pago)

        if link_pago:
            table.add_row("Payment link:", link_pago)

        console.print(table)

    @staticmethod
    def mostrar_metodos_pago():
        metodos = [
            "💳 Credit/debit card",
            "💸 Bank transfer",
            "💰 Cash",
            "📱 MercadoPago",
        ]

        table = Table(title="💰 Available Payment Methods")

        table.add_column("Option", style="cyan", justify="center")
        table.add_column("Method", style="green")

        for i, metodo in enumerate(metodos, 1):
            table.add_row(str(i), metodo)

        console.print(table)
