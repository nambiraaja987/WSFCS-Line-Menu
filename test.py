import streamlit as st
import requests
import csv
import io
import zipfile
from datetime import date, timedelta
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK

# ==============================================================================
# CONFIGURATION
# ==============================================================================
st.set_page_config(page_title="WSFCS Menu Generator", layout="wide")

# ==============================================================================
# GITHUB RAW FILES
# ==============================================================================
BASE_URL = "https://raw.githubusercontent.com/nambiraaja987/WSFCS-Line-Menu/main"

CSV_URL = f"{BASE_URL}/Schools.csv"
WSFCS_LOGO_URL = f"{BASE_URL}/wsfcs.png"
CHARTWELLS_LOGO_URL = f"{BASE_URL}/Chartwells.png"

# ==============================================================================
# DISCLAIMERS
# ==============================================================================
LUNCH_DISCLAIMER = (
    "A full student lunch includes a choice of one (1) entrée supplying protein and grain, "
    "two (2) vegetable side dishes, one (1) fruit side dish, and one (1) milk. "
    "Milk choices include skim white, 1% white and skim chocolate. In order to qualify as a "
    "reimbursable meal, students must choose a minimum of three (3) components and the meal "
    "must contain ½ cup of fruit or vegetable."
)

BREAKFAST_DISCLAIMER = (
    "All students must select at least 1/2 cup of fruit with their reimbursable meal. "
    "A full student breakfast includes a choice of one (1) entrée supplying protein "
    "and/or grain, up to two (2) fruit side dishes (one (1) can be a fruit juice, "
    "and one (1) milk. Milk choices include skim white, 1% white, and skim chocolate"
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
EXCLUDED_ITEMS = [
    "MAYONNAISE", "KETCHUP", "MUSTARD", "RANCH DRESSING",
    "BARBECUE SAUCE", "HOT SAUCE", "PACKET", "SYRUP",
    "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"
]

REPRESENTATIVE_BREAKFAST = {
    "Elementary": "ashley-magnet",
    "Middle": "clemmons-middle",
    "High": "east-forsyth"
}

ELEMENTARY_LUNCH_SLUG = "ashley-magnet"
MIDDLE_LUNCH_SLUG = "hanes-magnet"

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def fetch_menu_data(slug, target_date, menu_type):
    url = f"https://wsfcs.api.nutrislice.com/menu/api/weeks/schoo
