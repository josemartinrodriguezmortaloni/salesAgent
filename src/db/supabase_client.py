from supabase import create_client
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
