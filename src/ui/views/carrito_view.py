from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


class CarritoView:
    @staticmethod
    def mostrar_carrito(carrito, clear_screen=True):
        """Muestra el contenido del carrito"""
        if clear_screen:
            console.clear()

        # Verificar si el carrito está vacío
        if not carrito:
            mensaje = Text("🛒 Tu carrito está vacío", style="bold yellow")
            panel = Panel(mensaje, title="Carrito", border_style="yellow")
            console.print(panel)
            return

        # Crear una tabla para mostrar los items del carrito
        table = Table(title="🛒 Tu Carrito")

        # Añadir columnas
        table.add_column("Producto", style="cyan")
        table.add_column("Cantidad", style="green", justify="right")
        table.add_column("Precio Unit.", style="yellow", justify="right")
        table.add_column("Subtotal", style="yellow", justify="right")

        # Calcular el total
        total = 0

        # Añadir filas para cada producto
        for item_key, item_data in carrito.items():
            producto = item_data.producto
            cantidad = item_data.cantidad
            precio = (
                item_data.precio_unitario
                if item_data.precio_unitario is not None
                else 0
            )

            # Calcular el subtotal
            subtotal = cantidad * precio
            total += subtotal

            # Formatear los precios como cadenas
            precio_str = f"${precio:.2f}" if precio is not None else "Pendiente"
            subtotal_str = f"${subtotal:.2f}" if precio is not None else "Pendiente"

            # Añadir la fila
            table.add_row(producto, str(cantidad), precio_str, subtotal_str)

        # Añadir una fila para el total
        table.add_row("TOTAL", "", "", f"${total:.2f}", style="bold")

        # Mostrar la tabla
        console.print(table)

    @staticmethod
    def mostrar_resumen_pago(carrito, metodo_pago=None, link_pago=None):
        """Muestra el resumen del pago"""
        # Crear una tabla para el resumen
        table = Table(title="📝 Resumen de tu Compra")

        # Añadir columnas
        table.add_column("Detalle", style="cyan")
        table.add_column("Información", style="green")

        # Calcular el total
        total = sum(
            item.cantidad
            * (item.precio_unitario if item.precio_unitario is not None else 0)
            for item in carrito.values()
        )

        # Añadir información del pedido
        table.add_row("Número de productos:", str(len(carrito)))
        table.add_row(
            "Productos:",
            ", ".join(
                [f"{item.cantidad} {item.producto}" for item in carrito.values()]
            ),
        )
        table.add_row("Total a pagar:", f"${total:.2f}")

        if metodo_pago:
            table.add_row("Método de pago:", metodo_pago)

        if link_pago:
            table.add_row("Link de pago:", link_pago)

        # Mostrar la tabla
        console.print(table)

    @staticmethod
    def mostrar_metodos_pago():
        """Muestra los métodos de pago disponibles"""
        metodos = [
            "💳 Tarjeta de crédito/débito",
            "💸 Transferencia bancaria",
            "💰 Efectivo",
            "📱 MercadoPago",
        ]

        # Crear una tabla para los métodos de pago
        table = Table(title="💰 Métodos de Pago Disponibles")

        # Añadir columnas
        table.add_column("Opción", style="cyan", justify="center")
        table.add_column("Método", style="green")

        # Añadir filas para cada método
        for i, metodo in enumerate(metodos, 1):
            table.add_row(str(i), metodo)

        # Mostrar la tabla
        console.print(table)
