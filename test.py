import streamlit as st
import requests
import csv
import io
import zipfile
import os
from datetime import date, timedelta
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK

# ==============================================================================
# CONFIGURATION & BRANDING
# ==============================================================================
st.set_page_config(page_title="WSFCS Menu Generator", layout="centered")

# --- CUSTOM CSS ---
custom_css = """
    <style>
    /* 1. Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}

    /* 2. Adjust Main Container Padding */
    .block-container {
        padding-top: 1rem;
        max-width: 800px;
    }

    /* 3. Style the Generate Button (Wide) */
    .stButton > button {
        width: 100%;
        margin-top: 1rem;
        font-size: 1.2rem !important;
    }

    /* 4. Mobile Responsiveness */
    @media (max-width: 640px) {
        h2 { font-size: 1.5rem !important; }
        div[data-testid="stImage"] > img {
            margin: 0 auto;
        }
    }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==============================================================================
# LOCAL FILES & CONSTANTS
# ==============================================================================
CSV_FILENAME = "Schools.csv"
WSFCS_LOGO_FILENAME = "wsfcs.png"
CHARTWELLS_LOGO_FILENAME = "Chartwells.png"

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

EXCLUDED_ITEMS = ["MAYONNAISE", "KETCHUP", "MUSTARD", "RANCH DRESSING", "BARBECUE SAUCE", "HOT SAUCE", "PACKET", "SYRUP", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

REPRESENTATIVE_BREAKFAST = {"Elementary": "ashley-magnet", "Middle": "clemmons-middle", "High": "east-forsyth"}
ELEMENTARY_LUNCH_SLUG = "ashley-magnet"
MIDDLE_LUNCH_SLUG = "hanes-magnet"

# --- HELPER FUNCTIONS ---
def fetch_menu_data(slug, target_date, menu_type):
    url = f"https://wsfcs.api.nutrislice.com/menu/api/weeks/school/{slug}/menu-type/{menu_type}/{target_date:%Y/%m/%d}/?format=json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200: return r.json()
    except: pass
    return {}

def extract_food_items(data, target_date):
    items = []
    date_str = target_date.strftime("%Y-%m-%d")
    for day in data.get("days", []):
        if day.get("date") == date_str:
            for item in day.get("menu_items", []):
                food = item.get("food")
                if food and food.get("name"):
                    name = food["name"]
                    if not any(x in name.upper() for x in EXCLUDED_ITEMS): items.append(name)
            break
    return items

def extract_station_data(data, target_date, is_middle_school=False):
    categorized = {}
    current_station = "General Menu"
    if not is_middle_school: categorized[current_station] = []
    date_str = target_date.strftime("%Y-%m-%d")
    MS_STATION_BLOCKLIST = ["MILK", "CONDIMENT", "CONDIMENTS"]
    for day in data.get("days", []):
        if day.get("date") == date_str:
            for item in day.get("menu_items", []):
                is_header = item.get('is_section_title') or (item.get('food') is None and item.get('text'))
                if is_header and item.get('text'):
                    clean_header = item.get('text').strip()
                    if len(clean_header) > 2:
                        current_station = clean_header
                        categorized.setdefault(current_station, [])
                    continue
                food = item.get("food")
                if food and isinstance(food, dict) and food.get("name"):
                    name = food["name"]
                    if not any
