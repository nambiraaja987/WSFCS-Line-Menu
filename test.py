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
# CONFIGURATION & BRANDING
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
    url = (
        f"https://wsfcs.api.nutrislice.com/menu/api/weeks/school/"
        f"{slug}/menu-type/{menu_type}/{target_date:%Y/%m/%d}/?format=json"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
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
                    if not any(x in name.upper() for x in EXCLUDED_ITEMS):
                        items.append(name)
            break
    return items

def extract_station_data(data, target_date):
    categorized = {"General Menu": []}
    current_station = "General Menu"
    date_str = target_date.strftime("%Y-%m-%d")

    for day in data.get("days", []):
        if day.get("date") == date_str:
            for item in day.get("menu_items", []):
                if item.get("is_section_title"):
                    current_station = item.get("text", current_station)
                    categorized.setdefault(current_station, [])
                    continue
                food = item.get("food")
                if food and food.get("name"):
                    name = food["name"]
                    if not any(x in name.upper() for x in EXCLUDED_ITEMS):
                        categorized[current_station].append(name)
            break

    return {k: v for k, v in categorized.items() if v}

def create_doc_bytes(content, disclaimer, station_mode=False):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(2.8)
    sec.bottom_margin = Inches(1.5)
    sec.left_margin = Inches(1)
    sec.right_margin = Inches(1)

    footer = sec.footer.paragraphs[0]
    footer.text = disclaimer
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in footer.runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(9)

    if station_mode:
        for i, station in enumerate(content):
            p = doc.add_paragraph(station.upper())
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].font.size = Pt(24)
            p.runs[0].font.bold = True

            for item in content[station]:
                p = doc.add_paragraph(item.upper())
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].font.size = Pt(18)
                p.runs[0].font.bold = True

            if i < len(content) - 1:
                doc.add_page_break()
    else:
        for item in content:
            p = doc.add_paragraph(item.upper())
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].font.size = Pt(18)
            p.runs[0].font.bold = True

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ==============================================================================
# WEBSITE INTERFACE (UNCHANGED UI)
# ==============================================================================
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.image(WSFCS_LOGO_URL, width=150)
with col2:
    st.markdown("<h1 style='text-align: center;'>Line Menu Generator</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Select any date range.</p>", unsafe_allow_html=True)
with col3:
    st.image(CHARTWELLS_LOGO_URL, width=200)

st.markdown("---")

# ==============================================================================
# SIDEBAR (UNCHANGED)
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Settings")

    st.subheader("1. Select Date Range")
    start_d = st.date_input("Start Date", date.today())
    end_d = st.date_input("End Date", date.today())

    st.subheader("2. Menu Categories")
    run_breakfast = st.checkbox("All Schools - Breakfast", True)
    run_ele_lunch = st.checkbox("Elementary Lunch", True)
    run_mid_lunch = st.checkbox("Middle School Lunch", True)
    run_high_lunch = st.checkbox("High School Lunch", True)

# ==============================================================================
# MAIN LOGIC
# ==============================================================================
if st.button("🚀 Generate Menus", type="primary"):

    if start_d > end_d:
        st.error("Start Date must be before End Date.")
        st.stop()

    try:
        r = requests.get(CSV_URL, timeout=10)
        r.raise_for_status()
        schools = list(csv.DictReader(io.StringIO(r.text)))
    except Exception as e:
        st.error(f"Error loading Schools.csv: {e}")
        st.stop()

    zip_buffer = io.BytesIO()
    progress = st.progress(0)
    status = st.empty()

    dates = []
    d = start_d
    while d <= end_d:
        dates.append(d)
        d += timedelta(days=1)

    total = len(dates) * 4
    done = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for d in dates:
            d_str = d.strftime("%Y-%m-%d")
            parent = f"Line Menu_{d_str}/"

            if run_breakfast:
                status.text(f"Processing Breakfast: {d_str}")
                for level, slug in REPRESENTATIVE_BREAKFAST.items():
                    data = fetch_menu_data(slug, d, "breakfast")
                    items = extract_food_items(data, d)
                    if items:
                        doc = create_doc_bytes(items, BREAKFAST_DISCLAIMER)
                        zipf.writestr(f"{parent}{level}_Breakfast_{d_str}.docx", doc.read())
                done += 1
                progress.progress(done / total)

            if run_ele_lunch:
                status.text(f"Processing Elementary Lunch: {d_str}")
                data = fetch_menu_data(ELEMENTARY_LUNCH_SLUG, d, "lunch")
                items = extract_food_items(data, d)
                if items:
                    doc = create_doc_bytes(items, LUNCH_DISCLAIMER)
                    zipf.writestr(f"{parent}Elementary_Lunch_{d_str}.docx", doc.read())
                done += 1
                progress.progress(done / total)

            if run_mid_lunch:
                status.text(f"Processing Middle Lunch: {d_str}")
                data = fetch_menu_data(MIDDLE_LUNCH_SLUG, d, "lunch")
                stations = extract_station_data(data, d)
                if stations:
                    doc = create_doc_bytes(stations, LUNCH_DISCLAIMER, True)
                    zipf.writestr(f"{parent}Middle_Lunch_{d_str}.docx", doc.read())
                done += 1
                progress.progress(done / total)

            if run_high_lunch:
                status.text(f"Processing High School Lunch: {d_str}")
                for s in schools:
                    if s.get("Type") == "HS":
                        slug = s.get("Url Name")
                        name = s.get("School Name", "HighSchool").replace(" ", "_")
                        data = fetch_menu_data(slug, d, "lunch")
                        stations = extract_station_data(data, d)
                        if stations:
                            doc = create_doc_bytes(stations, LUNCH_DISCLAIMER, True)
                            zipf.writestr(f"{parent}{name}_Lunch.docx", doc.read())
                done += 1
                progress.progress(done / total)

    st.success("Menus Generated Successfully!")
    st.download_button(
        "📥 Download ZIP",
        zip_buffer.getvalue(),
        f"Line_Menus_{start_d}_to_{end_d}.zip",
        "application/zip"
    )
