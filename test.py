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
st.set_page_config(page_title="WSFCS Menu Generator", layout="wide")

st.markdown(
    """
    <style>
    /* Hide Streamlit header/footer/menu for cleaner look */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .block-container { padding-top: 1rem; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- FILE PATHS (LOCAL SYSTEM) ---
# NOTE: These paths must exist on the machine running this script.
BASE_DIR = r"C:\Users\nthambidurai\OneDrive - Winston-Salem Forsyth County Schools\Line Menu App"
CSV_PATH = os.path.join(BASE_DIR, "Schools.csv")
WSFCS_LOGO = os.path.join(BASE_DIR, "wsfcs.png")
CHARTWELLS_LOGO = os.path.join(BASE_DIR, "Chartwells.png")

# ==============================================================================
# DISCLAIMERS & CONSTANTS
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

EXCLUDED_ITEMS = [
    "MAYONNAISE", "KETCHUP", "MUSTARD", "RANCH DRESSING", 
    "BARBECUE SAUCE", "HOT SAUCE", "PACKET", "SYRUP",
    "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"
]

# Representative Schools for Generic Menus
REPRESENTATIVE_BREAKFAST = {
    "Elementary": "ashley-magnet",
    "Middle":     "clemmons-middle",
    "High":       "east-forsyth" 
}

ELEMENTARY_LUNCH_SLUG = "ashley-magnet"
MIDDLE_LUNCH_SLUG = "hanes-magnet"

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def fetch_menu_data(slug, target_date, menu_type):
    """Fetches JSON data from Nutrislice API."""
    url = (
        f"https://wsfcs.api.nutrislice.com/menu/api/weeks/school/"
        f"{slug}/menu-type/{menu_type}/{target_date:%Y/%m/%d}/?format=json"
    )
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        return {}
    return {}

def extract_food_items(json_data, target_date):
    """Extracts simple list of food items (Entrees/sides) excluding blocklisted words."""
    items = []
    date_str = target_date.strftime("%Y-%m-%d")
    
    for day in json_data.get("days", []):
        if day.get("date") == date_str:
            for item in day.get("menu_items", []):
                food = item.get("food")
                if food and food.get("name"):
                    name = food["name"]
                    if any(bad in name.upper() for bad in EXCLUDED_ITEMS): 
                        continue
                    items.append(name)
            break
    return items

def extract_station_data(json_data, target_date):
    """Extracts food items categorized by station headers."""
    categorized = {}
    current_station = "General Menu"
    categorized[current_station] = []
    date_str = target_date.strftime("%Y-%m-%d")
    
    for day in json_data.get("days", []):
        if day.get("date") == date_str:
            for item in day.get("menu_items", []):
                # Check if item is a header/station title
                is_header = item.get('is_section_title') or (item.get('food') is None and item.get('text'))
                
                if is_header:
                    txt = item.get('text', '').strip()
                    if len(txt) > 2:
                        current_station = txt
                        if current_station not in categorized: 
                            categorized[current_station] = []
                    continue
                
                # Process food item
                food = item.get("food")
                if food and food.get("name"):
                    name = food["name"]
                    if any(bad in name.upper() for bad in EXCLUDED_ITEMS): 
                        continue
                    if name not in categorized[current_station]:
                        categorized[current_station].append(name)
            break
            
    # Remove empty stations
    return {k: v for k, v in categorized.items() if v}

def create_doc_bytes(content_data, disclaimer, is_station_mode=False):
    """Generates a Word Document in memory and returns bytes."""
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(2.8)
    section.bottom_margin = Inches(1.5)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.footer_distance = Inches(0.8)

    # Add Footer
    footer = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
    footer.text = disclaimer
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in footer.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(9)

    if is_station_mode:
        stations = list(content_data.keys())
        for idx, station in enumerate(stations):
            # Station Header
            p = doc.add_paragraph()
            r = p.add_run(station.upper())
            r.font.name = "Times New Roman"
            r.font.size = Pt(24)
            r.font.bold = True
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Spacing after header
            doc.add_paragraph().paragraph_format.space_after = Pt(12)

            # Food Items
            for item in content_data[station]:
                p = doc.add_paragraph()
                r = p.add_run(item.upper())
                r.font.name = "Times New Roman"
                r.font.size = Pt(18)
                r.font.bold = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Page Break between stations
            if idx < len(stations) - 1:
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    else:
        # Simple List Mode
        for item in content_data:
            p = doc.add_paragraph()
            r = p.add_run(item.upper())
            r.font.name = "Times New Roman"
            r.font.size = Pt(18)
            r.font.bold = True
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ==============================================================================
# WEBSITE INTERFACE
# ==============================================================================

# --- BRANDING HEADER ---
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if os.path.exists(WSFCS_LOGO):
        st.image(WSFCS_LOGO, width=150)
    else:
        st.write("Logo not found")
with col2:
    st.markdown("<h1 style='text-align: center;'>Line Menu Generator</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Select any date range.</p>", unsafe_allow_html=True)
with col3:
    if os.path.exists(CHARTWELLS_LOGO):
        st.image(CHARTWELLS_LOGO, width=200)
    else:
        st.write("Logo not found")

st.markdown("---")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("1. Select Date Range")
    start_d = st.date_input("Start Date", value=date.today())
    end_d = st.date_input("End Date", value=date.today())

    st.subheader("2. Menu Categories")
    run_breakfast = st.checkbox("All Schools - Breakfast", value=True)
    run_ele_lunch = st.checkbox("Elementary Lunch", value=True)
    run_mid_lunch = st.checkbox("Middle School Lunch", value=True)
    run_high_lunch = st.checkbox("High School Lunch", value=True)

# ==============================================================================
# MAIN LOGIC
# ==============================================================================
if st.button("🚀 Generate Menus", type="primary"):
    
    # Validation
    if not os.path.exists(CSV_PATH):
        st.error(f"Error: Could not find 'Schools.csv' at: {CSV_PATH}")
        st.stop()
    
    if start_d > end_d:
        st.error("Error: Start Date must be before End Date.")
        st.stop()

    # 1. Load CSV Data
    try:
        with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            all_schools_data = [row for row in reader]
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()

    # 2. Prepare Date List
    selected_dates = []
    curr = start_d
    while curr <= end_d:
        selected_dates.append(curr)
        curr += timedelta(days=1)

    # 3. Processing Setup
    zip_buffer = io.BytesIO()
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Calculate total tasks for progress bar
    total_tasks = len(selected_dates) * 4 
    completed_tasks = 0

    # 4. Generate Files
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for d in selected_dates:
            d_str = d.strftime("%Y-%m-%d")
            # Root folder per date
            parent_folder = f"Line Menu_{d_str}/" 
            
            # --- BREAKFAST ---
            if run_breakfast:
                status_text.text(f"Processing Breakfast: {d_str}")
                # Subfolder for Breakfast
                subfolder = parent_folder + f"All_School_Breakfast_Menus_{d_str}/"
                
                for level, slug in REPRESENTATIVE_BREAKFAST.items():
                    data = fetch_menu_data(slug, d, "breakfast")
                    items = extract_food_items(data, d)
                    if items:
                        doc = create_doc_bytes(items, BREAKFAST_DISCLAIMER)
                        zip_file.writestr(f"{subfolder}{level}_Breakfast_{d_str}.docx", doc.read())
            
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

            # --- ELEMENTARY LUNCH ---
            if run_ele_lunch:
                status_text.text(f"Processing Elementary Lunch: {d_str}")
                # Subfolder for Ele Lunch
                subfolder = parent_folder + f"Elementary_Lunch_{d_str}/"
                
                data = fetch_menu_data(ELEMENTARY_LUNCH_SLUG, d, "lunch")
                items = extract_food_items(data, d)
                if items:
                    doc = create_doc_bytes(items, LUNCH_DISCLAIMER)
                    zip_file.writestr(f"{subfolder}Elementary_Lunch_{d_str}.docx", doc.read())
            
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

            # --- MIDDLE SCHOOL LUNCH ---
            if run_mid_lunch:
                status_text.text(f"Processing Middle Lunch: {d_str}")
                # Subfolder for Middle Lunch
                subfolder = parent_folder + f"Middle_Lunch_{d_str}/"
                
                data = fetch_menu_data(MIDDLE_LUNCH_SLUG, d, "lunch")
                stations = extract_station_data(data, d)
                if stations:
                    doc = create_doc_bytes(stations, LUNCH_DISCLAIMER, is_station_mode=True)
                    zip_file.writestr(f"{subfolder}Middle_Lunch_{d_str}.docx", doc.read())
            
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

            # --- HIGH SCHOOL LUNCH ---
            if run_high_lunch:
                status_text.text(f"Processing High School Lunch: {d_str}")
                # Subfolder for High School
                subfolder = parent_folder + f"High_Lunch_{d_str}/"
                
                hs_schools = [row for row in all_schools_data if row.get('Type') == 'HS']
                for school in hs_schools:
                    slug = school.get("Url Name") or school.get("URL")
                    name = school.get("School Name")
                    
                    if not slug: continue
                    
                    data = fetch_menu_data(slug, d, "lunch")
                    stations = extract_station_data(data, d)
                    
                    if stations:
                        doc = create_doc_bytes(stations, LUNCH_DISCLAIMER, is_station_mode=True)
                        safe_name = str(name).replace(" ", "_").replace("/", "-")
                        zip_file.writestr(f"{subfolder}{safe_name}_Lunch.docx", doc.read())
            
            completed_tasks += 1
            progress_bar.progress(min(completed_tasks / total_tasks, 1.0))

    # 5. Finish & Download
    progress_bar.progress(1.0)
    status_text.text("✅ Done!")
    
    date_label = f"{start_d}_to_{end_d}"
    st.success("Menus Generated Successfully!")
    
    st.download_button(
        label="📥 Download ZIP",
        data=zip_buffer.getvalue(),
        file_name=f"Line_Menus_{date_label}.zip",
        mime="application/zip"
    )
