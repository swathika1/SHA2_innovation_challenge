import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== MeriLion API Configuration ==========
# Load credentials from environment variables (set in .env file)
MERILION_USERNAME = os.environ.get("MERILION_USERNAME", "Sai Ashwin Kumar Chandramouli")
MERILION_API_KEY = os.environ.get("MERILION_API_KEY", "oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE")

# MeriLion API base URL (cr8lab is the official MERaLiON host)
MERILION_BASE_URL = os.environ.get("MERILION_BASE_URL", "https://api.cr8lab.com")

