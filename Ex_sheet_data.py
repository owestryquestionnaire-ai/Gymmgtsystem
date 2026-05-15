import streamlit as st
from datetime import datetime, time, timedelta
import json
import sqlite3
import pandas as pd

# --- Page Config ---
st.set_page_config(page_title="Gym Management System", layout="wide")

# --- Custom CSS ---
st.markdown(
    """
    <style>
    /* --- REDUCE TOP PADDING --- */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }

    /* Global Base Font Size */
    html, body, [class*="css"]  { font-size: 16px !important; }

    /* --- GYM FLOOR EXERCISES: LARGER FONT & NARROWER SPACING --- */
    div[data-testid="stCheckbox"] label p {
        font-size: 19px !important; 
        font-weight: 600 !important;
        line-height: 1.2 !important;
    }
    div[data-testid="stCheckbox"] {
        margin-bottom: -14px !important; 
        padding-bottom: 0px !important;
    }

    /* Custom Element Sizes */
    .cat-header { font-size: 17px; font-weight: 800; text-decoration: underline; background-color: #e1f5fe; color: #01579b; padding: 5px; border-radius: 4px; margin-bottom: 10px; margin-top: 10px; }
    .config-box { padding-left: 15px; border-left: 3px solid #1f77b4; background-color: #f0f2f6; margin-bottom: 15px; padding-top: 8px; padding-bottom: 8px; border-radius: 0 5px 5px 0; }
    .appt-box { background-color: #f1f8e9; padding: 12px; border-radius: 8px; border: 1px solid #c5e1a5; margin-top: 10px; }
    .grid-header { background-color: #424242; color: white; padding: 10px; text-align: center; font-weight: bold; border: 1px solid #ddd; font-size: 15px; }
    .time-slot-label { background-color: #f8f9fa; font-weight: bold; padding: 10px; text-align: center; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; }
    .grid-cell { min-height: 70px; padding: 4px; border: 1px solid #eee; background-color: #ffffff; font-size: 13px; overflow-y: auto; }
    .patient-tag { background-color: #e3f2fd; border-left: 3px solid #1976d2; padding: 2px 4px; margin-bottom: 2px; border-radius: 2px; color: #0d47a1; }
    .history-box { background: #fafafa; border-left: 4px solid #9c27b0; padding: 10px; margin-bottom: 10px; border-radius: 4px;}

    /* --- DASHBOARD CONDENSING CSS --- */
    .ex-list-condensed { max-height: 75px; overflow-y: auto; font-size: 14px; line-height: 1.2; background: #fdfdfd; border: 1px solid #eee; padding: 4px 6px; border-radius: 4px; margin-bottom: 0px; }
    .dash-header { font-weight: bold; font-size: 16px; border-bottom: 2px solid #333; padding-bottom: 2px; margin-bottom: 4px; color: #333; }

    /* Queue Styles */
    .queue-card { background-color: white; border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid #ffa000; }
    .queue-active { border-left: 5px solid #43a047; background-color: #f1f8e9; }
    .wait-time { font-size: 24px; font-weight: bold; color: #d32f2f; }

    /* --- SIDEBAR NAVIGATION STYLING --- */
    [data-testid="stSidebar"] .stRadio > label {
        font-size: 26px !important;
        font-weight: 900 !important;
        color: #1976d2 !important;
        padding-bottom: 10px;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p {
        font-size: 18px !important;
        font-weight: 500 !important;
        padding-top: 4px;
        padding-bottom: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Database ---
DB_FILE = "gym_system.db"


def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_no TEXT, p_name TEXT, timestamp TEXT,
        op_details TEXT, op_date TEXT, p_class TEXT, p_precautions TEXT, 
        prescription_json TEXT, is_checked_in INTEGER DEFAULT 0,
        next_appt_date TEXT, next_appt_time TEXT)''')

    try:
        cursor.execute("ALTER TABLE history ADD COLUMN assessment_text TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE history ADD COLUMN therapist TEXT")
    except sqlite3.OperationalError:
        pass

    # New Table for Queueing
    cursor.execute('''CREATE TABLE IF NOT EXISTS queues (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_no TEXT, p_name TEXT, 
        item_id TEXT, item_name TEXT, prescribed_mins INTEGER, 
        status TEXT DEFAULT 'waiting', joined_at TEXT)''')

    conn.commit()
    conn.close()


def add_to_queue(case_no, p_name, item_id, item_name, mins):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    exists = cursor.execute("SELECT id FROM queues WHERE case_no = ? AND item_id = ?", (case_no, item_id)).fetchone()
    if not exists:
        cursor.execute(
            "INSERT INTO queues (case_no, p_name, item_id, item_name, prescribed_mins, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_no, p_name, item_id, item_name, int(mins if mins else 10), datetime.now().strftime('%H:%M:%S')))
    conn.commit()
    conn.close()


def update_queue_status(qid, status, case_no=None, item_id=None):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    if status == "finished":
        conn.execute("DELETE FROM queues WHERE id = ?", (qid,))
    else:
        conn.execute("UPDATE queues SET status = ? WHERE id = ?", (status, qid))

        if status == "active" and case_no and item_id:
            row = conn.execute(
                "SELECT id, prescription_json FROM history WHERE case_no = ? AND is_checked_in = 1 ORDER BY id DESC LIMIT 1",
                (case_no,)).fetchone()
            if row:
                hist_id, presc_str = row
                presc = json.loads(presc_str)
                for ex in presc:
                    if ex['id'] == item_id:
                        ex['done'] = True
                conn.execute("UPDATE history SET prescription_json = ? WHERE id = ?",
                             (json.dumps(presc, ensure_ascii=False), hist_id))
                state_key = f"done_{case_no}_{item_id}"
                st.session_state[state_key] = True

    conn.commit()
    conn.close()


def set_check_status(case_no, status):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("UPDATE history SET is_checked_in = ? WHERE case_no = ?", (status, case_no))
    if status == 0:
        conn.execute("DELETE FROM queues WHERE case_no = ?", (case_no,))
    conn.commit()
    conn.close()


def update_appt(case_no, n_date, n_time):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("UPDATE history SET next_appt_date = ?, next_appt_time = ? WHERE case_no = ?",
                 (n_date, n_time, case_no))
    conn.commit()
    conn.close()


def save_h(c_no, name, presc, op_text, o_date, p_class, p_pre, is_chk, n_date, n_time, assessment, therapist):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO history 
        (case_no, p_name, timestamp, op_details, op_date, p_class, p_precautions, prescription_json, is_checked_in, next_appt_date, next_appt_time, assessment_text, therapist) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (c_no, name, datetime.now().strftime('%Y-%m-%d %H:%M'), op_text, o_date, p_class, p_pre,
                    json.dumps(presc, ensure_ascii=False), is_chk, n_date, n_time, assessment, therapist))
    conn.commit()
    conn.close()


def toggle_exercise_db(history_id, case_no, ex_id):
    state_key = f"done_{case_no}_{ex_id}"
    if state_key in st.session_state:
        is_done = st.session_state[state_key]
        conn = sqlite3.connect(DB_FILE, timeout=10)
        row = conn.execute("SELECT prescription_json FROM history WHERE id = ?", (history_id,)).fetchone()
        if row:
            presc = json.loads(row[0])
            for ex in presc:
                if ex['id'] == ex_id:
                    ex['done'] = is_done
            conn.execute("UPDATE history SET prescription_json = ? WHERE id = ?",
                         (json.dumps(presc, ensure_ascii=False), history_id))
            conn.commit()
        conn.close()


def delete_patient(case_no):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("DELETE FROM history WHERE case_no = ?", (case_no,))
    conn.commit()
    conn.close()


@st.dialog("⚠️ Confirm Deletion")
def confirm_delete_dialog(case_no, p_name):
    st.write(f"Are you sure you want to permanently delete all records for **{p_name}** ({case_no})?")
    st.write("This action cannot be undone.")

    col1, col2 = st.columns(2)
    if col1.button("Cancel", use_container_width=True):
        st.rerun()
    if col2.button("Yes, Delete", type="primary", use_container_width=True):
        delete_patient(case_no)
        st.rerun()


init_db()

# --- Exercise Config ---
EXERCISE_DB = {
    "Electrotherapy": [{"id": "e1", "name": "Ice + Magnetopulse"}, {"id": "e2", "name": "Gameready"},
                       {"id": "e3", "name": "EMS"}, {"id": "e4", "name": "Lymphapress"},
                       {"id": "e5", "name": "Hot Pack"}],
    "Mobilization": [{"id": "s3", "name": "Knee to chest mob"}, {"id": "s4", "name": "Static bike"},
                     {"id": "s5", "name": "Nustep"}, {"id": "s9", "name": "RT300"}, {"id": "s10", "name": "Cybercycle"},
                     {"id": "s11", "name": "Sling suspension"}, {"id": "s12", "name": "Reciprocal Pulley"}],
    "Strengthening": [{"id": "st1", "name": "Quad exercise"}, {"id": "st2", "name": "企 ＋ 屈腳"},
                      {"id": "st3", "name": "Wall slides"}, {"id": "st4", "name": "企 Hip strengthening"},
                      {"id": "st7", "name": "Bridging"}, {"id": "st8", "name": "Minipress"}],
    "Functional": [{"id": "f4", "name": "Stepping on box"}, {"id": "f6", "name": "跨欄"},
                   {"id": "f13", "name": "Stepping on foam"}, {"id": "f8", "name": "PWB踩磅"},
                   {"id": "f10", "name": "Wall bar: 坐>企"}, {"id": "f14", "name": "Arjo"},
                   {"id": "f11", "name": "Foam 單腳企"}],
    "Walking Exercise": [{"id": "w1", "name": "Stick walking"}, {"id": "w2", "name": "Quad walking"},
                         {"id": "w3", "name": "Stairs"}],
    "Others": [{"id": "o1", "name": "Massage roller"}, {"id": "o4", "name": "網球"}, {"id": "o3", "name": "斜板"}],
    "Assessment": [{"id": "a1", "name": "KOOS"}, {"id": "a2", "name": "考試"}]
}

# Items requiring queue
QUEUEABLE_IDS = {"e1": "Magnetopulse", "e2": "Gameready", "s5": "Nustep"}


def get_ex_info(target_eid):
    for cat, items in EXERCISE_DB.items():
        for ex in items:
            if ex["id"] == target_eid:
                return ex["name"], cat
    return "Unknown", "Unknown"


# --- GLOBAL DATA VAULT & LOGIN STATE ---
if "logged_in" not in st.session_state:
    if "user" in st.query_params:
        st.session_state.current_therapist = st.query_params["user"]
        st.session_state.logged_in = True
        if "nav_radio_key" not in st.session_state:
            st.session_state.nav_radio_key = "🗒️ Active Cases" if st.session_state.current_therapist == "PCA" else "👥 Database"
    else:
        st.session_state.logged_in = False
        st.session_state.current_therapist = ""

if "active_patient" not in st.session_state:
    st.session_state.active_patient = {
        "case_no": "", "p_name": "New Patient", "p_class": "Class I",
        "p_att": False, "p_fing": False, "exercises": {}, "assessment": "",
        "current_chk": 1, "current_nd": "None", "current_nt": "None", "is_loaded": False,
        "op_left_chk": False, "op_left_val": "TKR",
        "op_right_chk": False, "op_right_val": "TKR",
        "op_bi_chk": False, "op_bi_val": "TKR",
        "op_notes": "", "op_date": datetime.now().date()
    }

if "nav_radio_key" not in st.session_state:
    st.session_state.nav_radio_key = "👥 Database"

ap = st.session_state.active_patient


# --- ADVANCED FORMATTER FOR ALL PARAMETERS ---
def format_ex_details(item):
    name = item.get('name', 'Unknown')
    eid = item.get('id', '')
    details = []

    if eid == "st4":
        dirs = [("rf", "Right Flex前"), ("ra", "Right Abd側"), ("re", "Right Ext後"),
                ("lf", "Left Flex前"), ("la", "Left Abd側"), ("le", "Left Ext後")]
        st4_details = []
        for d_id, d_label in dirs:
            if item.get(f"{d_id}_chk"):
                m = item.get(f"{d_id}_mins", "10")
                g = "腳踩地" if item.get(f"{d_id}_gnd") else ""
                band = item.get(f"{d_id}_band_color", "") if item.get(f"{d_id}_band_chk") else ""

                parts = [f"{m} mins"]
                if g: parts.append(g)
                if band: parts.append(band)

                st4_details.append(f"{d_label} ({', '.join(parts)})")

        if st4_details:
            details.append("; ".join(st4_details))

    else:
        if 'mins' in item: details.append(f"{item['mins']} mins")
        if 'side' in item: details.append(item['side'])
        if 'pressure' in item: details.append(f"{item['pressure']} pressure")
        if 'degree' in item: details.append(f"{item['degree']}°")
        if 'mode' in item: details.append(item['mode'])
        if 'region' in item: details.append(item['region'])

        if 'weight' in item and str(item['weight']).strip():
            if eid in ["st1", "st2", "e3"]:
                details.append(f"Sandbag: {item['weight']} lbs")
            else:
                details.append(f"{item['weight']} lbs")

        if 'ball' in item and item['ball'] != 'None': details.append(item['ball'])
        if 'circle' in item: details.append(item['circle'])
        if 'res' in item and item['res']: details.append(f"Level {item['res']}")
        if 'seat' in item and item['seat']: details.append(f"Seat {item['seat']}")
        if item.get('hands'): details.append("用手")
        if item.get('lseat'): details.append("Long seat")
        if 'rt_res' in item and item['rt_res']: details.append(f"{item['rt_res']} Nm")

        if item.get('sling_abd'):
            tb = f" ({item.get('sabd_color', '')})" if item.get('sabd_tb') else ""
            details.append(f"平訓＋左右{tb}")
        if item.get('sling_flex'):
            tb = f" ({item.get('sflx_color', '')})" if item.get('sflx_tb') else ""
            details.append(f"側訓+前後{tb}")
        if item.get('towel'): details.append("毛巾於膝下")

        if eid == "st8":
            cords = []
            b = item.get('black_cord', '')
            r = item.get('red_cord', '')
            if b: cords.append(f"{b} black")
            if r: cords.append(f"{r} red")
            if cords: details.append(f"{' + '.join(cords)} cord")

        if 'box_height' in item: details.append(item['box_height'])
        if item.get('downstairs'): details.append("Downstairs training")
        if 'hurdle_height' in item: details.append(item['hurdle_height'])
        if item.get('pbar'): details.append("平衡架內")
        if item.get('family'): details.append("家人陪")
        if 'target_wt' in item and item['target_wt']: details.append(f"Target: {item['target_wt']}")
        if 'target_sec' in item and item['target_sec']: details.append(f"Target: {item['target_sec']} secs")

        if 'roller_region' in item: details.append(item['roller_region'])
        if 'slant_level' in item: details.append(item['slant_level'])

    detail_str = f" ({', '.join(filter(None, details))})" if details else ""
    return f"{name}{detail_str}"


def get_therapist_color(name):
    if not name or name == "Unassigned": return "#757575"
    if name.upper() == "MC": return "#1976D2"
    if name.upper() == "TY": return "#388E3C"
    colors = ["#D32F2F", "#7B1FA2", "#C2185B", "#0097A7", "#F57C00", "#E64A19"]
    return colors[sum(ord(c) for c in name) % len(colors)]


# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.title("🏋️‍♂️ Gym Management System")
    st.subheader("Secure Staff Login")
    st.divider()

    col1, col2 = st.columns([1, 2])
    with col1:
        st.info("Please enter your Staff Initials (e.g., MC, TY) or role (e.g., PCA) to continue.")
        therapist_input = st.text_input("Initials / Role")
        if st.button("Login", type="primary", use_container_width=True):
            if therapist_input.strip() != "":
                user = therapist_input.strip().upper()
                st.session_state.current_therapist = user
                st.session_state.logged_in = True

                st.query_params["user"] = user

                if st.session_state.current_therapist == "PCA":
                    st.session_state.nav_radio_key = "🗒️ Active Cases"
                else:
                    st.session_state.nav_radio_key = "👥 Database"

                st.rerun()
            else:
                st.error("Input cannot be empty.")
    st.stop()

# --- ROLE-BASED NAVIGATION CONFIGURATION ---
if st.session_state.current_therapist == "PCA":
    pages = ["🗒️ Active Cases", "📊 Dashboard", "🚦 Queue Status"]
else:
    pages = ["👥 Database", "📝 Assessment", "📋 Prescription", "🗒️ Active Cases", "🚦 Queue Status", "📊 Dashboard",
             "📅 Schedule", "🗂️ Patient History"]

def nav_to(page_name):
    st.session_state.nav_radio_key = page_name

# --- APP LAYOUT ---
st.title("🏋️‍♂️ Gym Management System")

page = st.sidebar.radio("Navigation Panel", pages, key="nav_radio_key")

st.sidebar.divider()
st.sidebar.markdown(f"**🩺 Logged in as:** {st.session_state.current_therapist}")


def perform_logout():
    st.session_state.logged_in = False
    st.session_state.current_therapist = ""
    st.session_state.nav_radio_key = "👥 Database"
    st.query_params.clear()

st.sidebar.button("Log Out", use_container_width=True, on_click=perform_logout)

# --- PAGE 1: DATABASE ---
if page == "👥 Database":
    st.subheader("Step 1: Patient Database")
    col_f1, col_f2 = st.columns([1, 2])
    view_mode = col_f1.radio("View Options", ["All Patients", "Filter by Date"], horizontal=True)
    target_date = ""
    if view_mode == "Filter by Date": target_date = col_f2.date_input("Select Appointment Date").strftime('%Y-%m-%d')
    st.divider()

    conn = sqlite3.connect(DB_FILE, timeout=10)
    query = "SELECT id, case_no, p_name, next_appt_date, is_checked_in, p_class, p_precautions, prescription_json, op_details, next_appt_time, assessment_text, op_date FROM history WHERE id IN (SELECT MAX(id) FROM history GROUP BY case_no)"
    if view_mode == "Filter by Date": query += f" AND next_appt_date = '{target_date}'"
    query += " ORDER BY p_name ASC"
    db = conn.execute(query).fetchall()
    conn.close()

    h = st.columns([1.5, 0.8, 1.2, 0.8, 0.8, 0.6, 0.5])
    h[0].markdown("**Case Number**")
    h[1].markdown("**Name**")
    h[2].markdown("**Appointment Date**")

    if db:
        for row in db:
            c = st.columns([1.5, 0.8, 1.2, 0.8, 0.8, 0.6, 0.5])
            c[0].write(row[1])
            c[1].write(row[2])
            c[2].write(f"📅 {row[3]}" if row[3] != 'None' and row[3] else "No Appt")

            def load_and_assess(r=row):
                ex_dict = {}
                try:
                    data = json.loads(r[7])
                    if isinstance(data, str): data = json.loads(data)
                    for item in data:
                        eid = item.get("id")
                        if eid:
                            parsed_data = {k: v for k, v in item.items() if k not in ["id", "name", "done"]}
                            if f"{eid}_weight" in parsed_data: parsed_data["weight"] = parsed_data.pop(f"{eid}_weight")
                            ex_dict[eid] = parsed_data
                except Exception:
                    pass

                st.session_state.active_patient = {
                    "case_no": r[1], "p_name": r[2],
                    "p_class": r[5] if r[5] != "None" else "Class I",
                    "p_att": "多注目" in (r[6] or ""), "p_fing": "夾手指做運動" in (r[6] or ""),
                    "exercises": ex_dict, "assessment": r[10] if r[10] else "",
                    "current_chk": r[4], "current_nd": r[3], "current_nt": r[9], "is_loaded": True,
                    "op_left_chk": False, "op_left_val": "TKR",
                    "op_right_chk": False, "op_right_val": "TKR",
                    "op_bi_chk": False, "op_bi_val": "TKR",
                    "op_notes": "", "op_date": datetime.now().date()
                }
                nav_to("📝 Assessment")

            def quick_history(c_no=row[1]):
                st.session_state.active_patient["case_no"] = c_no
                nav_to("🗂️ Patient History")

            c[3].button("Assess", key=f"ld_{row[0]}", type="primary", use_container_width=True, on_click=load_and_assess)
            c[4].button("History", key=f"hist_{row[0]}", use_container_width=True, on_click=quick_history)

            if c[5].button("View", key=f"sh_{row[0]}", use_container_width=True):
                with st.expander("Latest Prescription Details"):
                    for ex in json.loads(row[7]): st.write(f"• {format_ex_details(ex)}")

            if c[6].button("❌", key=f"del_{row[0]}", help="Delete Patient Record"):
                confirm_delete_dialog(row[1], row[2])
    else:
        st.info("No records found.")

# --- PAGE 2: ASSESSMENT ---
elif page == "📝 Assessment":
    st.subheader("Step 2: Clinical Assessment")

    if not ap["case_no"]:
        st.warning("⚠️ No patient selected. Please select a patient from the Database first.")
    else:
        st.markdown(f"### Assessing: **{ap['p_name']}** ({ap['case_no']})")

        def sync_assess():
            ap["assessment"] = st.session_state.assess_input

        def save_notes_and_proceed():
            ap["assessment"] = st.session_state.assess_input
            nav_to("📋 Prescription")

        st.text_area(
            "Today's Clinical Notes / Assessment Result",
            value=ap["assessment"],
            key="assess_input",
            height=200,
            on_change=sync_assess,
            placeholder="Type subjective/objective findings, pain scores, or progression notes here..."
        )

        st.button("Save Notes & Proceed to Prescription ➡️", type="primary", on_click=save_notes_and_proceed)

# --- PAGE 3: PRESCRIPTION ---
elif page == "📋 Prescription":

    c1, c2 = st.columns([4, 1])
    c1.subheader("Step 3: Update Exercise Prescription")

    def blank_patient():
        st.session_state.active_patient = {
            "case_no": "", "p_name": "New Patient", "p_class": "Class I",
            "p_att": False, "p_fing": False, "exercises": {}, "assessment": "",
            "current_chk": 1, "current_nd": "None", "current_nt": "None", "is_loaded": False,
            "op_left_chk": False, "op_left_val": "TKR",
            "op_right_chk": False, "op_right_val": "TKR",
            "op_bi_chk": False, "op_bi_val": "TKR",
            "op_notes": "", "op_date": datetime.now().date()
        }

    c2.button("✨ Blank New Patient", type="primary", use_container_width=True, on_click=blank_patient)
    if ap["is_loaded"]: st.info(f"✏️ **Updating Prescription for {ap['p_name']}.**")

    def sync_form():
        ap["case_no"] = st.session_state.rx_case
        ap["p_name"] = st.session_state.rx_name
        ap["p_class"] = st.session_state.rx_class
        ap["p_att"] = st.session_state.rx_att
        ap["p_fing"] = st.session_state.rx_fing
        ap["op_left_chk"] = st.session_state.rx_op_l_chk
        if "rx_op_l_val" in st.session_state: ap["op_left_val"] = st.session_state.rx_op_l_val
        ap["op_right_chk"] = st.session_state.rx_op_r_chk
        if "rx_op_r_val" in st.session_state: ap["op_right_val"] = st.session_state.rx_op_r_val
        ap["op_bi_chk"] = st.session_state.rx_op_b_chk
        if "rx_op_b_val" in st.session_state: ap["op_bi_val"] = st.session_state.rx_op_b_val
        ap["op_notes"] = st.session_state.rx_op_notes
        ap["op_date"] = st.session_state.rx_op_d

    def toggle_ex(eid):
        if st.session_state[f"ui_{eid}"]:
            if eid not in ap["exercises"]:
                _, cat = get_ex_info(eid)
                if cat == "Electrotherapy":
                    ap["exercises"][eid] = {"mins": "15"}
                elif cat in ["Walking Exercise", "Assessment"]:
                    ap["exercises"][eid] = {}
                else:
                    ap["exercises"][eid] = {"mins": "10"}
        else:
            if eid in ap["exercises"]: del ap["exercises"][eid]

    def update_dict(eid, key, val_key):
        if eid not in ap["exercises"]: ap["exercises"][eid] = {}
        ap["exercises"][eid][key] = st.session_state[val_key]

    def remove_cart_item(item_eid):
        if item_eid in ap["exercises"]:
            del ap["exercises"][item_eid]
        if f"ui_{item_eid}" in st.session_state:
            st.session_state[f"ui_{item_eid}"] = False

    def check_in_patient():
        pre_list = []
        if ap["p_att"]: pre_list.append("多注目")
        if ap["p_fing"]: pre_list.append("夾手指做運動")
        final_pre = ", ".join(pre_list) if pre_list else "None"

        op_list = []
        if ap.get("op_left_chk"): op_list.append(f"Left {ap.get('op_left_val', 'TKR')}")
        if ap.get("op_right_chk"): op_list.append(f"Right {ap.get('op_right_val', 'TKR')}")
        if ap.get("op_bi_chk"): op_list.append(f"Bilateral {ap.get('op_bi_val', 'TKR')}")

        op_string = ", ".join(op_list)
        if ap.get("op_notes", "").strip():
            if op_string:
                op_string += f" | Notes: {ap['op_notes']}"
            else:
                op_string = f"Notes: {ap['op_notes']}"
        if not op_string.strip(): op_string = "None recorded"

        sel = []
        for eid, data in ap["exercises"].items():
            ex_name = next((x["name"] for cat in EXERCISE_DB.values() for x in cat if x["id"] == eid), "Unknown")
            ex_data = {"id": eid, "name": ex_name}

            if isinstance(data, dict):
                ex_data.update(data)
                if ex_data.get('region') == 'Other (Type below)' and 'other_region' in ex_data:
                    ex_data['region'] = ex_data['other_region']
                if ex_data.get('roller_region') == 'Other (Type below)' and 'custom_roller_region' in ex_data:
                    ex_data['roller_region'] = ex_data['custom_roller_region']
            sel.append(ex_data)

        save_h(ap["case_no"], ap["p_name"], sel, op_string,
               ap.get("op_date", datetime.now().date()).strftime("%Y-%m-%d"), ap["p_class"], final_pre, 1,
               ap["current_nd"], ap["current_nt"], ap["assessment"], st.session_state.current_therapist)
        ap["is_loaded"] = False
        nav_to("🗒️ Active Cases")

    # --- TOP SECTION: Patient Data Container ---
    st.markdown('<div class="dash-header">👤 Patient Data & Operation Details</div>', unsafe_allow_html=True)
    with st.container(border=True):
        p_c1, p_c2, p_c3 = st.columns([1.2, 1, 1.8])

        with p_c1:
            st.text_input("Case Number", value=ap["case_no"], key="rx_case", on_change=sync_form)
            st.text_input("Name", value=ap["p_name"], key="rx_name", on_change=sync_form)
            opts = ["Class I", "Class II", "Class III"]
            idx = opts.index(ap["p_class"]) if ap["p_class"] in opts else 0
            st.radio("Class", opts, index=idx, horizontal=True, key="rx_class", on_change=sync_form)

        with p_c2:
            st.markdown("**Precautions:**")
            st.checkbox("多注目", value=ap["p_att"], key="rx_att", on_change=sync_form)
            st.checkbox("夾手指做運動", value=ap["p_fing"], key="rx_fing", on_change=sync_form)
            st.date_input("Date of Operation", value=ap.get("op_date", datetime.now().date()), key="rx_op_d",
                          on_change=sync_form)

        with p_c3:
            st.markdown("**Operation Details:**")
            op_choices = ["TKR", "UKA", "HTO", "THR"]

            c_op1, c_op2, c_op3 = st.columns(3)
            with c_op1:
                if st.checkbox("Left", value=ap.get("op_left_chk", False), key="rx_op_l_chk", on_change=sync_form):
                    st.selectbox("Op", op_choices, index=op_choices.index(ap.get("op_left_val", "TKR")),
                                 key="rx_op_l_val", on_change=sync_form, label_visibility="collapsed")
            with c_op2:
                if st.checkbox("Right", value=ap.get("op_right_chk", False), key="rx_op_r_chk", on_change=sync_form):
                    st.selectbox("Op", op_choices, index=op_choices.index(ap.get("op_right_val", "TKR")),
                                 key="rx_op_r_val", on_change=sync_form, label_visibility="collapsed")
            with c_op3:
                if st.checkbox("Bilateral", value=ap.get("op_bi_chk", False), key="rx_op_b_chk", on_change=sync_form):
                    st.selectbox("Op", op_choices, index=op_choices.index(ap.get("op_bi_val", "TKR")),
                                 key="rx_op_b_val", on_change=sync_form, label_visibility="collapsed")

            st.text_area("Other Details / Complications", value=ap.get("op_notes", ""), placeholder="e.g., bleeding...",
                         key="rx_op_notes", on_change=sync_form, height=68)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- BOTTOM SECTION: Cart (Left) and Select (Right) ---
    col_cart, col_select = st.columns([1.0, 1.6])

    with col_cart:
        st.markdown('<div class="dash-header">🛒 Exercise Cart (Configure Details)</div>', unsafe_allow_html=True)
        if not ap["exercises"]:
            st.info("👈 Select exercises from the right panel to add them to your cart.")
        else:
            for eid, data in list(ap["exercises"].items()):
                ex_name, ex_cat = get_ex_info(eid)

                with st.container(border=True):
                    c_title, c_del = st.columns([0.9, 0.1])
                    with c_title:
                        st.markdown(f"**{ex_name}**")
                    with c_del:
                        st.button("🗑️", key=f"del_cart_{eid}", help="Remove from Cart", on_click=remove_cart_item,
                                  args=(eid,))

                    if ex_cat == "Electrotherapy":
                        if eid == "e1":  # Ice + Magneto
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "15"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["Right knee", "Left knee", "Bilateral knee"]
                                current = data.get("side", "Right knee")
                                st.selectbox("Side", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_side_{eid}", on_change=update_dict,
                                             args=(eid, "side", f"ui_side_{eid}"))

                        elif eid == "e2":  # Gameready
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "15"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts_s = ["Right", "Left"]
                                current_s = data.get("side", "Right")
                                st.selectbox("Side", opts_s,
                                             index=opts_s.index(current_s) if current_s in opts_s else 0,
                                             key=f"ui_side_{eid}", on_change=update_dict,
                                             args=(eid, "side", f"ui_side_{eid}"))
                            c3, c4 = st.columns(2)
                            with c3:
                                opts_p = ["Low", "Medium"]
                                current_p = data.get("pressure", "Low")
                                st.selectbox("Pressure", opts_p,
                                             index=opts_p.index(current_p) if current_p in opts_p else 0,
                                             key=f"ui_pres_{eid}", on_change=update_dict,
                                             args=(eid, "pressure", f"ui_pres_{eid}"))
                            with c4:
                                st.text_input("Degree", value=data.get("degree", ""), placeholder="e.g. 10",
                                              key=f"ui_deg_{eid}", on_change=update_dict,
                                              args=(eid, "degree", f"ui_deg_{eid}"))

                        elif eid == "e3":  # EMS
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "15"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts_s = ["Right Quad", "Left Quad", "Bilateral Quad"]
                                current_s = data.get("side", "Right Quad")
                                st.selectbox("Side", opts_s,
                                             index=opts_s.index(current_s) if current_s in opts_s else 0,
                                             key=f"ui_side_{eid}", on_change=update_dict,
                                             args=(eid, "side", f"ui_side_{eid}"))
                            c3, c4 = st.columns(2)
                            with c3:
                                opts_m = ["Static Quad", "Quad board 踢腳", "沙包壓腳"]
                                current_m = data.get("mode", "Static Quad")
                                st.selectbox("Mode", opts_m,
                                             index=opts_m.index(current_m) if current_m in opts_m else 0,
                                             key=f"ui_mode_{eid}", on_change=update_dict,
                                             args=(eid, "mode", f"ui_mode_{eid}"))
                            if data.get("mode", "Static Quad") == "沙包壓腳":
                                with c4:
                                    st.text_input("Weight (lbs)", value=data.get("weight", ""), key=f"ui_w_{eid}",
                                                  on_change=update_dict, args=(eid, "weight", f"ui_w_{eid}"))

                        elif eid == "e4":  # Lymphapress
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "15"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts_s = ["Right", "Left", "Alternate bilateral"]
                                current_s = data.get("side", "Right")
                                st.selectbox("Side", opts_s,
                                             index=opts_s.index(current_s) if current_s in opts_s else 0,
                                             key=f"ui_side_{eid}", on_change=update_dict,
                                             args=(eid, "side", f"ui_side_{eid}"))
                            c3, _ = st.columns(2)
                            with c3:
                                opts_p = ["40", "50", "60"]
                                current_p = data.get("pressure", "40")
                                st.selectbox("Pressure", opts_p,
                                             index=opts_p.index(current_p) if current_p in opts_p else 0,
                                             key=f"ui_pres_{eid}", on_change=update_dict,
                                             args=(eid, "pressure", f"ui_pres_{eid}"))

                        elif eid == "e5":  # Hot pack
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "15"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts_s = ["Left", "Right", "Bilateral"]
                                current_s = data.get("side", "Left")
                                st.selectbox("Side", opts_s,
                                             index=opts_s.index(current_s) if current_s in opts_s else 0,
                                             key=f"ui_side_{eid}", on_change=update_dict,
                                             args=(eid, "side", f"ui_side_{eid}"))
                            c3, c4 = st.columns(2)
                            with c3:
                                opts_r = ["Quad", "Hamstring", "Calf", "ITB", "Other (Type below)"]
                                current_r = data.get("region", "Quad")
                                st.selectbox("Region", opts_r,
                                             index=opts_r.index(current_r) if current_r in opts_r else 0,
                                             key=f"ui_reg_{eid}", on_change=update_dict,
                                             args=(eid, "region", f"ui_reg_{eid}"))
                            with c4:
                                st.text_input("Custom Region", value=data.get("custom_region", ""),
                                              placeholder="Type here...", key=f"ui_creg_{eid}", on_change=update_dict,
                                              args=(eid, "custom_region", f"ui_creg_{eid}"))

                    elif ex_cat == "Mobilization":
                        if eid == "s3":  # Knee to chest
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["None", "紅波", "藍波"]
                                current = data.get("ball", "None")
                                st.selectbox("Option", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_ball_{eid}", on_change=update_dict,
                                             args=(eid, "ball", f"ui_ball_{eid}"))

                        elif eid == "s4":  # Static bike
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["半圈", "全圈"]
                                current = data.get("circle", "半圈")
                                st.selectbox("Option", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_circ_{eid}", on_change=update_dict,
                                             args=(eid, "circle", f"ui_circ_{eid}"))

                        elif eid == "s5":  # Nustep
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.text_input("Resistance", value=data.get("res", ""), key=f"ui_res_{eid}",
                                              on_change=update_dict, args=(eid, "res", f"ui_res_{eid}"))
                            with c3:
                                st.text_input("Seat", value=data.get("seat", ""), key=f"ui_seat_{eid}",
                                              on_change=update_dict, args=(eid, "seat", f"ui_seat_{eid}"))
                            c4, c5 = st.columns(2)
                            with c4:
                                st.checkbox("用手", value=data.get("hands", False), key=f"ui_hnds_{eid}",
                                            on_change=update_dict, args=(eid, "hands", f"ui_hnds_{eid}"))
                            with c5:
                                st.checkbox("Long Seat", value=data.get("lseat", False), key=f"ui_lseat_{eid}",
                                            on_change=update_dict, args=(eid, "lseat", f"ui_lseat_{eid}"))

                        elif eid == "s9":  # RT300
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.text_input("Resistance (Nm)", value=data.get("rt_res", ""), key=f"ui_rtres_{eid}",
                                              on_change=update_dict, args=(eid, "rt_res", f"ui_rtres_{eid}"))

                        elif eid == "s10":  # Cybercycle
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["easy", "medium"]
                                current = data.get("mode", "easy")
                                st.selectbox("Mode", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_mode_{eid}", on_change=update_dict,
                                             args=(eid, "mode", f"ui_mode_{eid}"))

                        elif eid == "s11":  # Sling suspension
                            c1, _ = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))

                            st.checkbox("平訓 ＋左右 (Abduction)", value=data.get("sling_abd", False),
                                        key=f"ui_sabd_{eid}", on_change=update_dict,
                                        args=(eid, "sling_abd", f"ui_sabd_{eid}"))
                            if data.get("sling_abd", False):
                                cb1, cb2 = st.columns(2)
                                with cb1:
                                    st.checkbox("加橡根", value=data.get("sabd_tb", False), key=f"ui_sabdtb_{eid}",
                                                on_change=update_dict, args=(eid, "sabd_tb", f"ui_sabdtb_{eid}"))
                                if data.get("sabd_tb", False):
                                    with cb2:
                                        opts = ["紅橡根", "綠橡根"]
                                        curr = data.get("sabd_color", "紅橡根")
                                        st.selectbox("Color", opts, index=opts.index(curr) if curr in opts else 0,
                                                     key=f"ui_sabdcol_{eid}", on_change=update_dict,
                                                     args=(eid, "sabd_color", f"ui_sabdcol_{eid}"),
                                                     label_visibility="collapsed")

                            st.checkbox("側訓 + 前後 (Flexion/ Extension)", value=data.get("sling_flex", False),
                                        key=f"ui_sflx_{eid}", on_change=update_dict,
                                        args=(eid, "sling_flex", f"ui_sflx_{eid}"))
                            if data.get("sling_flex", False):
                                cf1, cf2 = st.columns(2)
                                with cf1:
                                    st.checkbox("加橡根", value=data.get("sflx_tb", False), key=f"ui_sflxtb_{eid}",
                                                on_change=update_dict, args=(eid, "sflx_tb", f"ui_sflxtb_{eid}"))
                                if data.get("sflx_tb", False):
                                    with cf2:
                                        opts = ["紅橡根", "綠橡根"]
                                        curr = data.get("sflx_color", "紅橡根")
                                        st.selectbox("Color", opts, index=opts.index(curr) if curr in opts else 0,
                                                     key=f"ui_sflxcol_{eid}", on_change=update_dict,
                                                     args=(eid, "sflx_color", f"ui_sflxcol_{eid}"),
                                                     label_visibility="collapsed")

                        elif eid == "s12":  # Reciprocal Pulley
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
                                st.checkbox("毛巾於膝下", value=data.get("towel", False), key=f"ui_twl_{eid}",
                                            on_change=update_dict, args=(eid, "towel", f"ui_twl_{eid}"))

                    elif ex_cat == "Strengthening":
                        if eid in ["st1", "st2"]:  # Quad exercise / 企 ＋ 屈腳
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.text_input("Sandbag (lbs)", value=data.get("weight", ""), key=f"ui_w_{eid}",
                                              on_change=update_dict, args=(eid, "weight", f"ui_w_{eid}"))

                        elif eid in ["st3", "st7"]:  # Wall slides / Bridging
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["None", "紅波", "藍波"]
                                current = data.get("ball", "None")
                                st.selectbox("Option", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_ball_{eid}", on_change=update_dict,
                                             args=(eid, "ball", f"ui_ball_{eid}"))

                        elif eid == "st8":  # Minipress
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts_s = ["Right", "Left", "Bilateral"]
                                current_s = data.get("side", "Right")
                                st.selectbox("Side", opts_s,
                                             index=opts_s.index(current_s) if current_s in opts_s else 0,
                                             key=f"ui_side_{eid}", on_change=update_dict,
                                             args=(eid, "side", f"ui_side_{eid}"))
                            c3, c4 = st.columns(2)
                            with c3:
                                st.text_input("Black cord", value=data.get("black_cord", ""), placeholder="e.g. 2",
                                              key=f"ui_blk_{eid}", on_change=update_dict,
                                              args=(eid, "black_cord", f"ui_blk_{eid}"))
                            with c4:
                                st.text_input("Red cord", value=data.get("red_cord", ""), placeholder="e.g. 1",
                                              key=f"ui_red_{eid}", on_change=update_dict,
                                              args=(eid, "red_cord", f"ui_red_{eid}"))

                        elif eid == "st4":  # 企 Hip strengthening (Multi-direction)
                            st.caption("Select Leg:")
                            st.checkbox("Right Leg", value=data.get("right_leg", False), key=f"ui_{eid}_rleg",
                                        on_change=update_dict, args=(eid, "right_leg", f"ui_{eid}_rleg"))
                            if data.get("right_leg", False):
                                with st.container(border=True):
                                    r_dirs = [("rf", "Flex前"), ("ra", "Abd側"), ("re", "Ext後")]
                                    for d_id, d_label in r_dirs:
                                        chk_key = f"{d_id}_chk"
                                        st.checkbox(f"Right {d_label}", value=data.get(chk_key, False),
                                                    key=f"ui_{eid}_{chk_key}", on_change=update_dict,
                                                    args=(eid, chk_key, f"ui_{eid}_{chk_key}"))
                                        if data.get(chk_key, False):
                                            c1, c2, c3 = st.columns(3)
                                            with c1:
                                                st.text_input("Mins", value=data.get(f"{d_id}_mins", "10"),
                                                              key=f"ui_min_{eid}_{d_id}", on_change=update_dict,
                                                              args=(eid, f"{d_id}_mins", f"ui_min_{eid}_{d_id}"))
                                            with c2:
                                                st.markdown("<div style='margin-top: 35px;'></div>",
                                                            unsafe_allow_html=True)
                                                st.checkbox("腳踩地", value=data.get(f"{d_id}_gnd", False),
                                                            key=f"ui_gnd_{eid}_{d_id}", on_change=update_dict,
                                                            args=(eid, f"{d_id}_gnd", f"ui_gnd_{eid}_{d_id}"))
                                            with c3:
                                                st.checkbox("加橡根", value=data.get(f"{d_id}_band_chk", False),
                                                            key=f"ui_bnd_{eid}_{d_id}", on_change=update_dict,
                                                            args=(eid, f"{d_id}_band_chk", f"ui_bnd_{eid}_{d_id}"))
                                                if data.get(f"{d_id}_band_chk", False):
                                                    opts = ["紅橡根", "綠橡根"]
                                                    curr = data.get(f"{d_id}_band_color", "紅橡根")
                                                    st.selectbox("Color", opts,
                                                                 index=opts.index(curr) if curr in opts else 0,
                                                                 key=f"ui_bcol_{eid}_{d_id}", on_change=update_dict,
                                                                 args=(eid, f"{d_id}_band_color",
                                                                       f"ui_bcol_{eid}_{d_id}"),
                                                                 label_visibility="collapsed")

                            st.checkbox("Left Leg", value=data.get("left_leg", False), key=f"ui_{eid}_lleg",
                                        on_change=update_dict, args=(eid, "left_leg", f"ui_{eid}_lleg"))
                            if data.get("left_leg", False):
                                with st.container(border=True):
                                    l_dirs = [("lf", "Flex前"), ("la", "Abd側"), ("le", "Ext後")]
                                    for d_id, d_label in l_dirs:
                                        chk_key = f"{d_id}_chk"
                                        st.checkbox(f"Left {d_label}", value=data.get(chk_key, False),
                                                    key=f"ui_{eid}_{chk_key}", on_change=update_dict,
                                                    args=(eid, chk_key, f"ui_{eid}_{chk_key}"))
                                        if data.get(chk_key, False):
                                            c1, c2, c3 = st.columns(3)
                                            with c1:
                                                st.text_input("Mins", value=data.get(f"{d_id}_mins", "10"),
                                                              key=f"ui_min_{eid}_{d_id}", on_change=update_dict,
                                                              args=(eid, f"{d_id}_mins", f"ui_min_{eid}_{d_id}"))
                                            with c2:
                                                st.markdown("<div style='margin-top: 35px;'></div>",
                                                            unsafe_allow_html=True)
                                                st.checkbox("腳踩地", value=data.get(f"{d_id}_gnd", False),
                                                            key=f"ui_gnd_{eid}_{d_id}", on_change=update_dict,
                                                            args=(eid, f"{d_id}_gnd", f"ui_gnd_{eid}_{d_id}"))
                                            with c3:
                                                st.checkbox("加橡根", value=data.get(f"{d_id}_band_chk", False),
                                                            key=f"ui_bnd_{eid}_{d_id}", on_change=update_dict,
                                                            args=(eid, f"{d_id}_band_chk", f"ui_bnd_{eid}_{d_id}"))
                                                if data.get(f"{d_id}_band_chk", False):
                                                    opts = ["紅橡根", "綠橡根"]
                                                    curr = data.get(f"{d_id}_band_color", "紅橡根")
                                                    st.selectbox("Color", opts,
                                                                 index=opts.index(curr) if curr in opts else 0,
                                                                 key=f"ui_bcol_{eid}_{d_id}", on_change=update_dict,
                                                                 args=(eid, f"{d_id}_band_color",
                                                                       f"ui_bcol_{eid}_{d_id}"),
                                                                 label_visibility="collapsed")

                    elif ex_cat == "Functional":
                        if eid == "f4":  # Stepping on box
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["4\"", "6\"", "8\""]
                                current = data.get("box_height", "4\"")
                                st.selectbox("Height", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_hgt_{eid}", on_change=update_dict,
                                             args=(eid, "box_height", f"ui_hgt_{eid}"))
                            with c3:
                                st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
                                st.checkbox("Downstairs training", value=data.get("downstairs", False),
                                            key=f"ui_dwst_{eid}", on_change=update_dict,
                                            args=(eid, "downstairs", f"ui_dwst_{eid}"))

                        elif eid == "f6":  # 跨欄
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["4\"", "6\""]
                                current = data.get("hurdle_height", "4\"")
                                st.selectbox("Height", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_hgt_{eid}", on_change=update_dict,
                                             args=(eid, "hurdle_height", f"ui_hgt_{eid}"))

                        elif eid == "f13":  # Stepping on foam
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
                                st.checkbox("平衡架內", value=data.get("pbar", False), key=f"ui_pbar_{eid}",
                                            on_change=update_dict, args=(eid, "pbar", f"ui_pbar_{eid}"))
                            with c3:
                                st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
                                st.checkbox("家人陪", value=data.get("family", False), key=f"ui_fam_{eid}",
                                            on_change=update_dict, args=(eid, "family", f"ui_fam_{eid}"))

                        elif eid == "f8":  # PWB踩磅
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.text_input("Target weight", value=data.get("target_wt", ""), key=f"ui_twt_{eid}",
                                              on_change=update_dict, args=(eid, "target_wt", f"ui_twt_{eid}"))

                        elif eid == "f11":  # Foam 單腳企
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                st.text_input("Target (seconds)", value=data.get("target_sec", ""),
                                              key=f"ui_tsec_{eid}", on_change=update_dict,
                                              args=(eid, "target_sec", f"ui_tsec_{eid}"))

                        else:
                            c1, _ = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))

                    elif ex_cat == "Others":
                        if eid in ["o1", "o4"]:  # Massage roller / 網球
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["Quad", "ITB", "Calf", "Hamstring", "Other (Type below)"]
                                current = data.get("roller_region", "Quad")
                                st.selectbox("Region", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_rreg_{eid}", on_change=update_dict,
                                             args=(eid, "roller_region", f"ui_rreg_{eid}"))
                            with c3:
                                if data.get("roller_region", "Quad") == "Other (Type below)":
                                    st.text_input("Custom Region", value=data.get("custom_roller_region", ""),
                                                  placeholder="Type here...", key=f"ui_crreg_{eid}",
                                                  on_change=update_dict,
                                                  args=(eid, "custom_roller_region", f"ui_crreg_{eid}"))
                        elif eid == "o3":  # 斜板
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))
                            with c2:
                                opts = ["1格", "2格", "3格", "4格"]
                                current = data.get("slant_level", "1格")
                                st.selectbox("Level", opts, index=opts.index(current) if current in opts else 0,
                                             key=f"ui_slant_{eid}", on_change=update_dict,
                                             args=(eid, "slant_level", f"ui_slant_{eid}"))
                        else:
                            c1, _ = st.columns(2)
                            with c1:
                                st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                              on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))

                    elif ex_cat in ["Walking Exercise", "Assessment"]:
                        st.caption("Standard item. No additional parameters required.")

                    else:
                        c1, _ = st.columns(2)
                        with c1:
                            st.text_input("Mins", value=data.get("mins", "10"), key=f"ui_min_{eid}",
                                          on_change=update_dict, args=(eid, "mins", f"ui_min_{eid}"))

            st.markdown("<br>", unsafe_allow_html=True)
            btn_label = "💾 Finalize & Check In to Gym" if ap["is_loaded"] else "🚀 Generate & Check In"
            st.button(btn_label, type="primary", use_container_width=True, on_click=check_in_patient)

    with col_select:
        st.markdown('<div class="dash-header">✔️ Select Exercises</div>', unsafe_allow_html=True)
        with st.container(border=True):
            s_c1, s_c2 = st.columns(2)

            for cat, items in EXERCISE_DB.items():
                if cat in ["Electrotherapy", "Mobilization", "Strengthening"]:
                    col_to_use = s_c1
                else:
                    col_to_use = s_c2

                with col_to_use:
                    st.markdown(f'<div class="cat-header">{cat}</div>', unsafe_allow_html=True)
                    for ex in items:
                        eid = ex["id"]
                        is_selected = eid in ap["exercises"]
                        st.checkbox(ex["name"], value=is_selected, key=f"ui_{eid}", on_change=toggle_ex, args=(eid,))

# --- PAGE 4: ACTIVE CASES ---
elif page == "🗒️ Active Cases":
    st.subheader("Step 4: Active Gym Floor")
    conn = sqlite3.connect(DB_FILE, timeout=10)

    rows = conn.execute(
        "SELECT id, case_no, p_name, prescription_json, next_appt_date, next_appt_time, assessment_text, p_precautions, therapist, op_details, op_date FROM history WHERE is_checked_in = 1 AND id IN (SELECT MAX(id) FROM history GROUP BY case_no) ORDER BY p_name ASC").fetchall()

    queued_cases = [r[0] for r in conn.execute("SELECT case_no FROM queues").fetchall()]
    conn.close()

    if rows:
        acols = st.columns(3)
        for i, r in enumerate(rows):
            with acols[i % 3]:

                therapist_name = r[8] if r[8] else "Unassigned"
                t_color = get_therapist_color(therapist_name)

                with st.expander(f"👤 {r[2]} ({r[1]})", expanded=False):

                    st.markdown(
                        f"<div style='background-color: {t_color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-bottom: 10px; text-align: center;'>Therapist: {therapist_name}</div>",
                        unsafe_allow_html=True)

                    if r[9] and r[9] != "None recorded":
                        st.info(f"**🔪 Operation:** {r[9]} \n\n**📅 Op Date:** {r[10]}")

                    precautions = r[7]
                    if precautions and precautions != "None":
                        st.error(f"**⚠️ Precautions:** {precautions}")

                    presc_list = json.loads(r[3])
                    for ex in presc_list:
                        c1, c2 = st.columns([0.7, 0.3])
                        is_done = ex.get('done', False)

                        checkbox_key = f"done_{r[1]}_{ex['id']}"
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = is_done

                        c1.checkbox(
                            format_ex_details(ex),
                            value=st.session_state[checkbox_key],
                            key=checkbox_key,
                            on_change=toggle_exercise_db,
                            args=(r[0], r[1], ex['id'])
                        )

                        if ex['id'] in QUEUEABLE_IDS:
                            q_label = "✅ 排隊中" if r[1] in queued_cases else "🚦 排隊"
                            if c2.button(q_label, key=f"q_{r[1]}_{ex['id']}", disabled=r[1] in queued_cases):
                                add_to_queue(r[1], r[2], ex['id'], QUEUEABLE_IDS[ex['id']], ex.get('mins', 15))
                                st.rerun()

                    st.divider()

                    if st.checkbox("📅 Schedule Next Visit", key=f"show_appt_{r[1]}"):
                        st.markdown('<div class="appt-box">', unsafe_allow_html=True)

                        col_d, col_t = st.columns(2)
                        with col_d:
                            nd = st.date_input("Date", key=f"nd_{r[1]}")
                        with col_t:
                            nt = st.time_input("Time", value=time(9, 0), key=f"nt_{r[1]}")

                        if st.button("💾 Save Appointment Only", key=f"save_appt_{r[1]}", use_container_width=True):
                            update_appt(r[1], nd.strftime('%Y-%m-%d'), nt.strftime('%H:%M'))
                            st.success(f"Appointment saved for {nd.strftime('%b %d')} at {nt.strftime('%H:%M')}!")

                        st.markdown('</div>', unsafe_allow_html=True)

                    if st.button("🚪 Check Out Patient", key=f"co_{r[0]}", use_container_width=True, type="primary"):
                        set_check_status(r[1], 0)
                        st.rerun()
    else:
        st.info("Gym is empty.")


# --- PAGE: QUEUE STATUS ---
elif page == "🚦 Queue Status":
    st.subheader("🚦 Equipment Real-time Queue List")

    conn = sqlite3.connect(DB_FILE, timeout=10)
    q_data = pd.read_sql_query("SELECT * FROM queues ORDER BY id ASC", conn)
    conn.close()

    cols = st.columns(3)
    for i, (item_id, item_label) in enumerate(QUEUEABLE_IDS.items()):
        with cols[i]:
            st.markdown(f"### ⚙️ {item_label}")
            item_q = q_data[q_data['item_id'] == item_id]

            active_and_waiting = item_q[item_q['status'].isin(['waiting', 'active'])]
            total_wait = active_and_waiting['prescribed_mins'].sum()
            st.markdown(f"Estimated Wait: <span class='wait-time'>{total_wait} mins</span>", unsafe_allow_html=True)
            st.divider()

            if item_q.empty:
                st.caption("No one in queue.")
            else:
                for _, p in item_q.iterrows():
                    is_active = p['status'] == 'active'
                    status_cls = "queue-active" if is_active else ""
                    st.markdown(f"""
                    <div class='queue-card {status_cls}'>
                        <b>{p['p_name']}</b> ({p['case_no']})<br>
                        Time: {p['prescribed_mins']} mins | Joined: {p['joined_at']}<br>
                        Status: <b>{p['status'].upper()}</b>
                    </div>
                    """, unsafe_allow_html=True)

                    b1, b2 = st.columns(2)
                    if not is_active:
                        if b1.button("▶️ Start", key=f"start_{p['id']}"):
                            update_queue_status(p['id'], "active", p['case_no'], p['item_id'])
                            st.rerun()
                    if b2.button("✅ Finish", key=f"fin_{p['id']}"):
                        update_queue_status(p['id'], "finished")
                        st.rerun()


# --- PAGE 5: DASHBOARD ---
elif page == "📊 Dashboard":
    st.subheader("Gym Real-time Monitoring")
    conn = sqlite3.connect(DB_FILE, timeout=10)
    active = conn.execute(
        "SELECT case_no, p_name, prescription_json, therapist FROM history WHERE is_checked_in = 1 AND id IN (SELECT MAX(id) FROM history GROUP BY case_no)").fetchall()
    conn.close()

    if active:
        h1, h2, h3, h4 = st.columns([1.5, 2.2, 2.2, 1.1])
        h1.markdown('<div class="dash-header">Patient Details</div>', unsafe_allow_html=True)
        h2.markdown('<div class="dash-header">✅ Completed</div>', unsafe_allow_html=True)
        h3.markdown('<div class="dash-header">⏳ Remaining</div>', unsafe_allow_html=True)
        h4.markdown('<div class="dash-header">Progress</div>', unsafe_allow_html=True)

        for p in active:
            c_no, name, presc, th_name = p[0], p[1], json.loads(p[2]), p[3]
            th_name = th_name if th_name else "Unassigned"
            t_color = get_therapist_color(th_name)

            done = [ex['name'] for ex in presc if ex.get('done', False)]
            todo = [ex['name'] for ex in presc if not ex.get('done', False)]

            r1, r2, r3, r4 = st.columns([1.5, 2.2, 2.2, 1.1])
            with r1:
                st.markdown(
                    f"<div style='line-height: 1.2; padding-top: 5px;'>"
                    f"<span style='font-size: 18px; font-weight: 800; color: #1976d2;'>{name}</span> "
                    f"<span style='background-color: {t_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; vertical-align: middle;'>🩺 {th_name}</span><br>"
                    f"<span style='font-size: 12px; font-weight: 600; color: #757575;'>Case: {c_no}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with r2:
                html_done = "<br>".join([f"✔️ {x}" for x in done]) if done else "---"
                st.markdown(f'<div class="ex-list-condensed">{html_done}</div>', unsafe_allow_html=True)

            with r3:
                html_todo = "<br>".join([f"🔹 {x}" for x in todo]) if todo else "<b>Clear</b>"
                st.markdown(f'<div class="ex-list-condensed">{html_todo}</div>', unsafe_allow_html=True)

            with r4:
                pct = len(done) / len(presc) if presc else 0
                st.progress(pct)
                st.markdown(
                    f"<div style='font-size:12px; font-weight: bold; color:#666; margin-top:-10px;'>{int(pct * 100)}%</div>",
                    unsafe_allow_html=True)

            st.markdown("<hr style='margin: 8px 0px; padding: 0px;'>", unsafe_allow_html=True)
    else:
        st.info("No active cases currently being monitored on the gym floor.")

# --- PAGE 6: SCHEDULE ---
elif page == "📅 Schedule":
    st.subheader("📅 Gym Schedule")

    if "week_offset" not in st.session_state: st.session_state.week_offset = 0

    col_w1, col_w2, col_w3 = st.columns([1, 2, 1])
    with col_w1:
        if st.button("⬅️ Previous Week", use_container_width=True): st.session_state.week_offset -= 1; st.rerun()
    with col_w2:
        if st.button("🔄 Current Week", use_container_width=True): st.session_state.week_offset = 0; st.rerun()
    with col_w3:
        if st.button("Next Week ➡️", use_container_width=True): st.session_state.week_offset += 1; st.rerun()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "13:30", "14:00", "14:30", "15:00"]

    now = datetime.now()
    target_monday = (now - timedelta(days=now.weekday())) + timedelta(weeks=st.session_state.week_offset)
    week_dates = [(target_monday + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

    st.markdown(
        f"<h5 style='text-align: center; color: #1976d2;'>Viewing Week: {week_dates[0]} to {week_dates[-1]}</h5>",
        unsafe_allow_html=True)

    conn = sqlite3.connect(DB_FILE, timeout=10)

    query = f"""
        SELECT next_appt_date, next_appt_time, p_name 
        FROM history 
        WHERE id IN (SELECT MAX(id) FROM history GROUP BY case_no) 
        AND next_appt_date IN ({','.join(['?'] * 7)})
    """
    sched_df = pd.read_sql_query(query, conn, params=week_dates)
    conn.close()

    cols = st.columns([0.8] + [1] * 7)
    cols[0].markdown('<div class="grid-header">Time</div>', unsafe_allow_html=True)
    for i, day in enumerate(days): cols[i + 1].markdown(
        f'<div class="grid-header">{day}<br><small>{week_dates[i]}</small></div>', unsafe_allow_html=True)

    for slot in slots:
        row_cols = st.columns([0.8] + [1] * 7)
        row_cols[0].markdown(f'<div class="time-slot-label">{slot}</div>', unsafe_allow_html=True)
        for i, date_str in enumerate(week_dates):
            matches = sched_df[(sched_df['next_appt_date'] == date_str) & (sched_df['next_appt_time'] == slot)]
            cell_content = "".join([f'<div class="patient-tag">👤 {r["p_name"]}</div>' for _, r in matches.iterrows()])
            row_cols[i + 1].markdown(f'<div class="grid-cell">{cell_content if cell_content else "-"}</div>',
                                     unsafe_allow_html=True)

# --- PAGE 7: PATIENT HISTORY ---
elif page == "🗂️ Patient History":
    st.subheader("🗂️ Patient Historical Records")

    search_query = st.text_input("🔍 Search Database by Case Number",
                                 placeholder="Enter Patient Case No. (e.g., C12345)", value=ap["case_no"])
    st.divider()

    if not search_query:
        st.info("👆 Enter a Case Number above to pull up a patient's history.")
    else:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        patient_info = conn.execute("SELECT p_name FROM history WHERE case_no = ? LIMIT 1", (search_query,)).fetchone()

        if patient_info:
            p_name = patient_info[0]
            st.markdown(f"### History for: **{p_name}** ({search_query})")

            hist_records = conn.execute(
                "SELECT timestamp, assessment_text, prescription_json, therapist, op_details, op_date FROM history WHERE case_no = ? ORDER BY timestamp DESC",
                (search_query,)).fetchall()
            conn.close()

            if hist_records:
                filter_date = st.date_input("Filter by Specific Date (Optional)", value=None)
                count = 0
                for record in hist_records:
                    rec_date = record[0].split(" ")[0]
                    if filter_date and rec_date != filter_date.strftime('%Y-%m-%d'): continue

                    count += 1
                    th_name = record[3] if record[3] else "Unassigned"
                    with st.expander(f"📅 Record Date: {record[0]} (🩺 Assessed by: {th_name})"):

                        if record[4] and record[4] != "None recorded":
                            st.info(f"**🔪 Operation:** {record[4]} *(Date: {record[5]})*")

                        st.markdown("**📝 Notes:**")
                        if record[1] and record[1].strip() != "":
                            st.info(record[1])
                        else:
                            st.caption("No notes recorded on this date.")

                        st.markdown("**🏋️ Exercises:**")
                        try:
                            ex_list = json.loads(record[2])
                            if isinstance(ex_list, str): ex_list = json.loads(ex_list)
                            if ex_list:
                                for ex in ex_list: st.write(f"- {format_ex_details(ex)}")
                            else:
                                st.caption("No exercises recorded.")
                        except:
                            st.caption("No exercises recorded.")
                if count == 0: st.info("No records found for the selected date.")
            else:
                st.info("No historical records found for this patient.")
        else:
            conn.close()
            st.error("❌ Patient not found. Please check the Case Number and try again.")
