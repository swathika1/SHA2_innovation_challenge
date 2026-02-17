import os

# ========== MeriLion API Configuration ==========
# Paste your credentials directly here
MERILION_USERNAME = "Sai Ashwin Kumar Chandramouli"
MERILION_API_KEY = "oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE"

# Or set via environment variables (overrides the above)
if os.environ.get("MERILION_USERNAME"):
    MERILION_USERNAME = os.environ["MERILION_USERNAME"]
if os.environ.get("MERILION_API_KEY"):
    MERILION_API_KEY = os.environ["MERILION_API_KEY"]

# MeriLion API base URL (cr8lab is the official MERaLiON host)
MERILION_BASE_URL = os.environ.get("MERILION_BASE_URL", "https://api.cr8lab.com")
