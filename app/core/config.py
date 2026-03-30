import os


SBI_BANK_ID = "sbi"
SBI_BANK_NAME = "State Bank of India"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BANKS_DIR = os.path.join(BASE_DIR, "banks")
SBI_BANK_DIR = os.path.join(BANKS_DIR, SBI_BANK_ID)
SBI_SOP_FILE = "SBI_SOP.pdf"
