import asyncio
import os
from dotenv import load_dotenv
from db.supabase_client import supabase

# Load environment variables
load_dotenv()


def verify_env():
    """Verify that all required environment variables are set."""
    print("\nVerificando variables de entorno:")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    print(
        f"SUPABASE_URL: {supabase_url[:30]}..." if supabase_url else "❌ No configurada"
    )
    print(
        f"SUPABASE_KEY: {supabase_key[:15]}..." if supabase_key else "❌ No configurada"
    )

    if supabase_url and supabase_key:
        print("\nLongitud de las claves:")
        print(f"URL length: {len(supabase_url)} caracteres")
        print(f"KEY length: {len(supabase_key)} caracteres")
        return True
    return False


async def test_connection():
    """Test the database connection by attempting to read products."""
    try:
        # Try to read products
        response = supabase.table("productos").select("*").limit(1).execute()

        if response.data is not None:
            return "✅ Conexión exitosa: Se pudo leer la tabla de productos"
        return "❌ Error: No se pudo leer la tabla de productos"

    except Exception as e:
        return f"❌ Error de conexión: {str(e)}"


async def main():
    if not verify_env():
        print("\n❌ Error: Faltan variables de entorno necesarias")
        return

    result = await test_connection()
    print("\nResultado de la prueba de conexión:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
