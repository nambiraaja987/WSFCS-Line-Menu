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

# --- MOBILE CSS (ONLY FOR HEADER & LOGOS) ---
# We removed the global centering so inputs look normal again.
mobile_css = """
    <style>
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}

    /* Mobile Tweaks for Logos */
    @media (max-width: 640px) {
        h2 { font-size: 1.5rem !important; }
        div[data-testid="stImage"] > img {
            margin: 0 auto;
        }
    }
    
    /* Add top padding */
    .block-container {
        padding-top: 1rem;
        max-width: 800px;
    }
    
    /* Make the Generate Button nice and wide */
    .stButton > button {
        width: 100%;
        margin-top: 1rem;
        font-size: 1.2rem !important;
    }
    </style>
"""
st.markdown(mobile_css, unsafe_allow_html=True)

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
                    if not any(x in name.upper() for x in EXCLUDED_ITEMS):
                        categorized.setdefault(current_station, []).append(name)
            break
    final_menu = {k: v for k, v in categorized.items() if v}
    if is_middle_school:
        return {k: v for k, v in final_menu.items() if not any(b in k.upper() for b in MS_STATION_BLOCKLIST)}
    return final_menu

def create_simple_doc(content, disclaimer, margin_top=2.8):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Inches(margin_top), Inches(1.5)
    footer = sec.footer.paragraphs[0]
    footer.text, footer.alignment = disclaimer, WD_ALIGN_PARAGRAPH.CENTER
    for r in footer.runs: r.font.name, r.font.size = "Times New Roman", Pt(9)
    for item in content:
        p = doc.add_paragraph()
        r = p.add_run(item.upper())
        r.font.name, r.font.size, r.font.bold = "Times New Roman", Pt(18), True
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def create_middle_school_doc(data, disclaimer):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Inches(2.5), Inches(1.0)
    footer = sec.footer.paragraphs[0]
    footer.text, footer.alignment = disclaimer, WD_ALIGN_PARAGRAPH.CENTER
    for r in footer.runs: r.font.name, r.font.size = "Times New Roman", Pt(9)
    for i, station in enumerate(data):
        p = doc.add_paragraph()
        if i > 0: p.paragraph_format.space_before = Pt(18)
        r = p.add_run(station.upper())
        r.font.name, r.font.size, r.font.bold, r.font.underline = "Times New Roman", Pt(16), True, True
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for item in data[station]:
            p = doc.add_paragraph()
            r = p.add_run(item.upper())
            r.font.name, r.font.size, r.font.bold = "Times New Roman", Pt(12), True
            p.alignment, p.paragraph_format.space_after = WD_ALIGN_PARAGRAPH.CENTER, Pt(2)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def create_high_school_doc(data, disclaimer):
    doc = Document()
    sec = doc.sections
