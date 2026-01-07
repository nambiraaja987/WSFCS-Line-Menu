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

# --- CUSTOM CSS (LIGHT MODE, LAYOUT & MOBILE FIXES) ---
custom_css = """
    <style>
    /* 1. Force Light Mode */
    .stApp {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    h1, h2, h3, h4, h5, h6, p, label, span, .stMarkdown {
        color: #000000 !important;
    }

    /* 2. Hide Streamlit Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}

    /* 3. Main Container Padding */
    .block-container {
        padding-top: 1rem;
        max-width: 800px;
    }

    /* 4. Button Styles */
    .stButton > button {
        width: 100%;
        margin-top: 1rem;
        font-size: 1.2rem !important;
    }

    /* 5. Download Button Hover Fix */
    .stDownloadButton > button:hover {
        background-color: #f0f2f6 !important;
        color: #000000 !important;
        border: 1px solid #333333 !important;
    }
    .stDownloadButton > button {
        background-color: #ffffff;
        color: #000000;
        border: 1px solid #cccccc;
    }

    /* 6. MOBILE RESPONSIVENESS FIXES */
    @media (max-width: 640px) {
        h2 { font-size: 1.5rem !important; }
        
        /* FORCE CENTER ALL IMAGES ON MOBILE */
        div[data-testid="stImage"] {
            display: flex;
            justify-content: center;
            width: 100%;
        }
        
        div[data-testid="stImage"] > img {
            margin-left: auto !important;
            margin-right: auto !important;
            display: block !important;
        }
        
        /* Force columns to align items to center on mobile */
        [data-testid="column"] {
            align-items: center;
            text-align: center;
        }
    }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

st.markdown(
    """
    <style>
    /* Hide Streamlit header */
    header {visibility: hidden;}

    /* Hide Streamlit footer */
    footer {visibility: hidden;}

    /* Hide hamburger menu */
    #MainMenu {visibility: hidden;}

    /* Remove top padding */
    .block-container {
        padding-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Inches(2.8), Inches(1.5)
    footer = sec.footer.paragraphs[0]
    footer.text, footer.alignment = disclaimer, WD_ALIGN_PARAGRAPH.CENTER
    for r in footer.runs: r.font.name, r.font.size = "Times New Roman", Pt(9)
    stations = list(data.keys())
    for i, station in enumerate(stations):
        p = doc.add_paragraph()
        r = p.add_run(station.upper())
        r.font.name, r.font.size, r.font.bold = "Times New Roman", Pt(24), True
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph().paragraph_format.space_after = Pt(12)
        for item in data[station]:
            p = doc.add_paragraph()
            r = p.add_run(item.upper())
            r.font.name, r.font.size, r.font.bold = "Times New Roman", Pt(18), True
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if i < len(stations) - 1: doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ==============================================================================
# UI HEADER: CENTERED LOGO & TITLE
# ==============================================================================
col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    if os.path.exists(WSFCS_LOGO_FILENAME):
        st.image(WSFCS_LOGO_FILENAME, width=150)

st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>Line Menu Generator</h2>", unsafe_allow_html=True)
st.markdown("---")

# ==============================================================================
# UI BODY: LEFT ALIGNED INPUTS
# ==============================================================================
st.subheader("🗓️ 1. Select Date Range")
c1, c2 = st.columns(2)
with c1: start_d = st.date_input("Start Date", date.today())
with c2: end_d = st.date_input("End Date", date.today())

st.markdown("<br>", unsafe_allow_html=True)

st.subheader("🍴 2. Select Menus")
mc1, mc2 = st.columns(2)
with mc1:
    run_breakfast = st.checkbox("All Schools - Breakfast", True)
    run_ele_lunch = st.checkbox("Elementary Lunch", True)
with mc2:
    run_mid_lunch = st.checkbox("Middle School Lunch", True)
    run_high_lunch = st.checkbox("High School Lunch", True)

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# LOGIC
# ==============================================================================
if st.button("🚀 Generate Menus", type="primary"):
    
    if start_d > end_d:
        st.error("Start Date must be before End Date.")
        st.stop()
    if not os.path.exists(CSV_FILENAME):
        st.error(f"Missing {CSV_FILENAME}")
        st.stop()

    with open(CSV_FILENAME, mode='r', encoding='utf-8-sig') as f:
        schools_raw = list(csv.DictReader(f))

    zip_buffer = io.BytesIO()
    dates = [start_d + timedelta(days=x) for x in range((end_d - start_d).days + 1)]
    
    # --- PROGRESS BAR LOGIC ---
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_tasks = len(dates) * 4 
    completed_tasks = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for d in dates:
            d_str = d.strftime("%Y-%m-%d")
            parent = f"Line Menu_{d_str}/"
            
            # 1. BREAKFAST
            if run_breakfast:
                status_text.text(f"Processing Breakfast: {d_str}")
                sub = f"{parent}All_School_Breakfast_Menus_{d_str}/"
                for lvl, slug in REPRESENTATIVE_BREAKFAST.items():
                    data = fetch_menu_data(slug, d, "breakfast")
                    items = extract_food_items(data, d)
                    if items: zipf.writestr(f"{sub}{lvl}_Breakfast_{d_str}.docx", create_simple_doc(items, BREAKFAST_DISCLAIMER).read())
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

            # 2. ELE LUNCH
            if run_ele_lunch:
                status_text.text(f"Processing Elementary Lunch: {d_str}")
                sub = f"{parent}Elementary_Lunch_{d_str}/"
                data = fetch_menu_data(ELEMENTARY_LUNCH_SLUG, d, "lunch")
                items = extract_food_items(data, d)
                if items: zipf.writestr(f"{sub}Elementary_Lunch_{d_str}.docx", create_simple_doc(items, LUNCH_DISCLAIMER).read())
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

            # 3. MID LUNCH
            if run_mid_lunch:
                status_text.text(f"Processing Middle Lunch: {d_str}")
                sub = f"{parent}Middle_School_Lunch_{d_str}/"
                data = fetch_menu_data(MIDDLE_LUNCH_SLUG, d, "lunch")
                stations = extract_station_data(data, d, True)
                if stations: zipf.writestr(f"{sub}Middle_Lunch_{d_str}.docx", create_middle_school_doc(stations, LUNCH_DISCLAIMER).read())
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

            # 4. HIGH LUNCH
            if run_high_lunch:
                status_text.text(f"Processing High School Lunch: {d_str}")
                sub = f"{parent}High_Lunch_{d_str}/"
                for row in schools_raw:
                    clean = {k.strip(): v for k, v in row.items() if k}
                    if clean.get("Type") == "HS":
                        data = fetch_menu_data(clean.get("Url Name"), d, "lunch")
                        stations = extract_station_data(data, d, False)
                        if stations:
                            safe_name = str(clean.get("School Name")).replace(" ", "_").replace("/", "-").replace(".", "")
                            zipf.writestr(f"{sub}{safe_name}_Lunch.docx", create_high_school_doc(stations, LUNCH_DISCLAIMER).read())
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

    progress_bar.progress(1.0)
    status_text.text("✅ Done!")
    st.success("✅ Menus Generated Successfully!")
    st.download_button("📥 Download ZIP", zip_buffer.getvalue(), f"Line_Menus_{start_d}_{end_d}.zip", "application/zip")

# ==============================================================================
# FOOTER: CHARTWELLS LOGO (BOTTOM RIGHT)
# ==============================================================================
st.markdown("<br><br>", unsafe_allow_html=True)
if os.path.exists(CHARTWELLS_LOGO_FILENAME):
    # Use columns to push logo to the right
    fc1, fc2 = st.columns([2, 1]) 
    with fc2:
        st.image(CHARTWELLS_LOGO_FILENAME, width=200)




