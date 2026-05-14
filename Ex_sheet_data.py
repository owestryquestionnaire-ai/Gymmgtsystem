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
    html, body, [class*="css"]  { font-size: 14px !important; }
    .cat-header { font-size: 15px; font-weight: 800; text-decoration: underline; background-color: #e1f5fe; color: #01579b; padding: 5px; border-radius: 4px; margin-bottom: 10px; margin-top: 10px; }
    .config-box { padding-left: 15px; border-left: 3px solid #1f77b4; background-color: #f0f2f6; margin-bottom: 15px; padding-top: 8px; padding-bottom: 8px; border-radius: 0 5px 5px 0; }
    .appt-box { background-color: #f1f8e9; padding: 12px; border-radius: 8px; border: 1px solid #c5e1a5; margin-top: 10px; }
    .grid-header { background-color: #424242; color: white; padding: 10px; text-align: center; font-weight: bold; border: 1px solid #ddd; font-size: 13px; }
    .time-slot-label { background-color: #f8f9fa; font-weight: bold; padding: 10px; text-align: center; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; }
    .grid-cell { min-height: 70px; padding: 4px; border: 1px solid #eee; background-color: #ffffff; font-size: 11px; overflow-y: auto; }
    .patient-tag { background-color: #e3f2fd; border-left: 3px solid #1976d2; padding: 2px 4px; margin-bottom: 2px; border-radius: 2px; color: #0d47a1; }
    .ex-list-condensed { max-height: 100px; overflow-y: auto; font-size: 12px; line-height: 1.4; background: #fdfdfd; border: 1px solid #eee; padding: 8px; border-radius: 4px; }
    .dash-header { font-weight: bold; font-size: 14px; border-bottom: 2px solid #333; padding-bottom: 5px; margin-bottom: 10px; color: #333; }
    .history-box { background: #fafafa; border-left: 4px solid #9c27b0; padding: 10px; margin-bottom: 10px; border-radius: 4px;}

    /* --- SIDEBAR NAVIGATION STYLING --- */
    [data-testid="stSidebar"] .stRadio > label {
        font-size: 24px !important;
        font-weight: 900 !important;
        color: #1976d2 !important;
        padding-bottom: 10px;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p {
        font-size: 16px !important;
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
    conn = sqlite3.connect(DB_FILE, timeout=10);
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

    conn.commit();
    conn.close()


def set_check_status(case_no, status):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("UPDATE history SET is_checked_in = ? WHERE case_no = ?", (status, case_no))
    conn.commit();
    conn.close()


def update_appt(case_no, n_date, n_time):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("UPDATE history SET next_appt_date = ?, next_appt_time = ? WHERE case_no = ?",
                 (n_date, n_time, case_no))
    conn.commit();
    conn.close()


def save_h(c_no, name, presc, op_text, o_date, p_class, p_pre, is_chk, n_date, n_time, assessment, therapist):
    conn = sqlite3.connect(DB_FILE, timeout=10);
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO history 
        (case_no, p_name, timestamp, op_details, op_date, p_class, p_precautions, prescription_json, is_checked_in, next_appt_date, next_appt_time, assessment_text, therapist) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (c_no, name, datetime.now().strftime('%Y-%m-%d %H:%M'), op_text, o_date, p_class, p_pre,
                    json.dumps(presc, ensure_ascii=False), is_chk, n_date, n_time, assessment, therapist))
    conn.commit();
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


init_db()

# --- Exercise Config ---
EXERCISE_DB = {
    "Electrotherapy": [{"id": "e1", "name": "Ice + Magnetopulse"}, {"id": "e2", "name": "Gameready"},
                       {"id": "e3", "name": "EMS"}, {"id": "e4", "name": "Lymphapress"},
                       {"id": "e5", "name": "Hot Pack"}],
    "Mobilization": [{"id": "s3", "name": "Knee to chest mob"}, {"id": "s4", "name": "Static bike"},
                     {"id": "s5", "name": "Nustep"}, {"id": "s9", "name": "RT300"},
                     {"id": "s10", "name": "Cybercycle"}],
    "Strengthening": [{"id": "st1", "name": "Quad exercise"}, {"id": "st2", "name": "Standing + Ham curl"},
                      {"id": "st3", "name": "Wall slides"}, {"id": "st4", "name": "企 Hip strengthening"},
                      {"id": "st7", "name": "Bridging"}, {"id": "st8", "name": "Minipress"}],
    "Functional": [{"id": "f4", "name": "Stepping on box"}, {"id": "f6", "name": "Hurdles"},
                   {"id": "f11", "name": "海棉單腳企"}, {"id": "f8", "name": "踩磅"},
                   {"id": "f10", "name": "Wall bar: 坐>企"}],
    "Others": [{"id": "o1", "name": "Massage roller"}, {"id": "o3", "name": "斜板"}]
}

# --- GLOBAL DATA VAULT & LOGIN STATE ---
if "logged_in" not in st.session_state:
    if "user" in st.query_params:
        st.session_state.current_therapist = st.query_params["user"]
        st.session_state.logged_in = True
        if "sidebar_radio" not in st.session_state:
            st.session_state.sidebar_radio = "🗒️ Active Cases" if st.session_state.current_therapist == "PCA" else "👥 Database"
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

if "sidebar_radio" not in st.session_state:
    st.session_state.sidebar_radio = "👥 Database"

ap = st.session_state.active_patient


def format_ex_details(item):
    eid, d = item['id'], []
    if eid in ["st1", "st2"]: d.append(f"{item.get(eid + '_weight')} lbs")
    detail_str = f" ({', '.join(filter(None, d))})" if d else ""
    return f"{item['name']}{detail_str}"


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
                    st.session_state.sidebar_radio = "🗒️ Active Cases"
                else:
                    st.session_state.sidebar_radio = "👥 Database"

                st.rerun()
            else:
                st.error("Input cannot be empty.")
    st.stop()

# --- ROLE-BASED NAVIGATION CONFIGURATION ---
if st.session_state.current_therapist == "PCA":
    pages = ["🗒️ Active Cases", "📊 Dashboard"]
else:
    pages = ["👥 Database", "📝 Assessment", "📋 Prescription", "🗒️ Active Cases", "📊 Dashboard", "📅 Schedule",
             "🗂️ Patient History"]


def nav_to(page_name):
    st.session_state.sidebar_radio = page_name


# --- APP LAYOUT ---
st.title("🏋️‍♂️ Gym Management System")

page = st.sidebar.radio("Navigation Panel", pages, key="sidebar_radio")

st.sidebar.divider()
st.sidebar.markdown(f"**🩺 Logged in as:** {st.session_state.current_therapist}")


def perform_logout():
    st.session_state.logged_in = False
    st.session_state.current_therapist = ""
    st.session_state.sidebar_radio = "👥 Database"
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

    h = st.columns([1.5, 0.8, 1.2, 0.8, 0.8, 0.6])
    h[0].markdown("**Case Number**")
    h[1].markdown("**Name**")
    h[2].markdown("**Appointment Date**")

    if db:
        for row in db:
            c = st.columns([1.5, 0.8, 1.2, 0.8, 0.8, 0.6])
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
                        if eid: ex_dict[eid] = str(item.get(f"{eid}_weight", ""))
                except Exception:
                    pass

                # Load patient identity, but intentionally clear operation details (No pre-fill)
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


            c[3].button("Assess", key=f"ld_{row[0]}", type="primary", use_container_width=True,
                        on_click=load_and_assess)
            c[4].button("History", key=f"hist_{row[0]}", use_container_width=True, on_click=quick_history)

            if c[5].button("View", key=f"sh_{row[0]}", use_container_width=True):
                with st.expander("Latest Prescription Details"):
                    for ex in json.loads(row[7]): st.write(f"• {format_ex_details(ex)}")
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
    st.divider()

    if ap["is_loaded"]:
        st.info(f"✏️ **Updating Prescription for {ap['p_name']}.**")

    l, r = st.columns([1.2, 3.5])
    with l:
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


        st.text_input("Case Number", value=ap["case_no"], key="rx_case", on_change=sync_form)
        st.text_input("Name", value=ap["p_name"], key="rx_name", on_change=sync_form)

        opts = ["Class I", "Class II", "Class III"]
        idx = opts.index(ap["p_class"]) if ap["p_class"] in opts else 0
        st.radio("Class", opts, index=idx, horizontal=True, key="rx_class", on_change=sync_form)

        st.markdown("**Precautions:**")
        st.checkbox("多注目", value=ap["p_att"], key="rx_att", on_change=sync_form)
        st.checkbox("夾手指做運動", value=ap["p_fing"], key="rx_fing", on_change=sync_form)

        # --- NEW DYNAMIC CHECKBOX UI FOR OPERATION DETAILS ---
        st.markdown("<br>**Operation Details:**", unsafe_allow_html=True)
        op_choices = ["TKR", "UKA", "HTO", "THR"]

        c_op1, c_op2, c_op3 = st.columns(3)
        with c_op1:
            if st.checkbox("Left", value=ap.get("op_left_chk", False), key="rx_op_l_chk", on_change=sync_form):
                st.selectbox("Op", op_choices, index=op_choices.index(ap.get("op_left_val", "TKR")), key="rx_op_l_val",
                             on_change=sync_form, label_visibility="collapsed")

        with c_op2:
            if st.checkbox("Right", value=ap.get("op_right_chk", False), key="rx_op_r_chk", on_change=sync_form):
                st.selectbox("Op", op_choices, index=op_choices.index(ap.get("op_right_val", "TKR")), key="rx_op_r_val",
                             on_change=sync_form, label_visibility="collapsed")

        with c_op3:
            if st.checkbox("Bilateral", value=ap.get("op_bi_chk", False), key="rx_op_b_chk", on_change=sync_form):
                st.selectbox("Op", op_choices, index=op_choices.index(ap.get("op_bi_val", "TKR")), key="rx_op_b_val",
                             on_change=sync_form, label_visibility="collapsed")

        st.date_input("Date of Operation", value=ap.get("op_date", datetime.now().date()), key="rx_op_d",
                      on_change=sync_form)
        st.text_area("Other Details / Complications", value=ap.get("op_notes", ""),
                     placeholder="e.g., bleeding, specific implants used...", key="rx_op_notes", on_change=sync_form)


        def check_in_patient():
            pre_list = []
            if ap["p_att"]: pre_list.append("多注目")
            if ap["p_fing"]: pre_list.append("夾手指做運動")
            final_pre = ", ".join(pre_list) if pre_list else "None"

            # Format Operation String based on checked boxes
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

            if not op_string.strip():
                op_string = "None recorded"

            sel = []
            for eid, weight in ap["exercises"].items():
                ex_name = next((x["name"] for cat in EXERCISE_DB.values() for x in cat if x["id"] == eid), "Unknown")
                ex_data = {"id": eid, "name": ex_name, "mins": "15"}
                if eid in ["st1", "st2"]: ex_data[f"{eid}_weight"] = weight
                sel.append(ex_data)

            save_h(
                ap["case_no"], ap["p_name"], sel, op_string,
                ap.get("op_date", datetime.now().date()).strftime("%Y-%m-%d"),
                ap["p_class"], final_pre, 1, ap["current_nd"], ap["current_nt"],
                ap["assessment"], st.session_state.current_therapist
            )
            ap["is_loaded"] = False
            nav_to("🗒️ Active Cases")


        btn_label = "💾 Finalize & Check In to Gym" if ap["is_loaded"] else "Generate & Check In"
        st.button(btn_label, type="primary", use_container_width=True, on_click=check_in_patient)

    with r:
        def toggle_ex(eid):
            if st.session_state[f"ui_{eid}"]:
                if eid not in ap["exercises"]: ap["exercises"][eid] = ""
            else:
                if eid in ap["exercises"]: del ap["exercises"][eid]


        def update_w(eid):
            ap["exercises"][eid] = st.session_state[f"ui_w_{eid}"]


        cols_r = st.columns(3)
        for idx, (cat, items) in enumerate(EXERCISE_DB.items()):
            with cols_r[idx % 3]:
                st.markdown(f'<div class="cat-header">{cat}</div>', unsafe_allow_html=True)
                for ex in items:
                    eid = ex["id"]
                    is_selected = eid in ap["exercises"]

                    st.checkbox(ex["name"], value=is_selected, key=f"ui_{eid}", on_change=toggle_ex, args=(eid,))

                    if is_selected and eid in ["st1", "st2"]:
                        st.markdown('<div class="config-box">', unsafe_allow_html=True)
                        st.text_input("lbs", value=ap["exercises"].get(eid, ""), key=f"ui_w_{eid}", on_change=update_w,
                                      args=(eid,))
                        st.markdown('</div>', unsafe_allow_html=True)

# --- PAGE 4: ACTIVE CASES ---
elif page == "🗒️ Active Cases":
    st.subheader("Step 4: Active Gym Floor")
    conn = sqlite3.connect(DB_FILE, timeout=10)

    rows = conn.execute(
        "SELECT id, case_no, p_name, prescription_json, next_appt_date, next_appt_time, assessment_text, p_precautions, therapist, op_details, op_date FROM history WHERE is_checked_in = 1 AND id IN (SELECT MAX(id) FROM history GROUP BY case_no) ORDER BY p_name ASC").fetchall()
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

                    # Show Operation details if present
                    if r[9] and r[9] != "None recorded":
                        st.info(f"**🔪 Operation:** {r[9]} \n\n**📅 Op Date:** {r[10]}")

                    precautions = r[7]
                    if precautions and precautions != "None":
                        st.error(f"**⚠️ Precautions:** {precautions}")

                    presc_list = json.loads(r[3])
                    for ex in presc_list:
                        is_done = ex.get('done', False)
                        st.checkbox(
                            format_ex_details(ex),
                            value=is_done,
                            key=f"done_{r[1]}_{ex['id']}",
                            on_change=toggle_exercise_db,
                            args=(r[0], r[1], ex['id'])
                        )
                    st.divider()

                    if st.checkbox("📅 Schedule Next Visit", key=f"show_appt_{r[1]}"):
                        st.markdown('<div class="appt-box">', unsafe_allow_html=True)
                        nd = st.date_input("Date", key=f"nd_{r[1]}");
                        nt = st.time_input("Time", value=time(9, 0), key=f"nt_{r[1]}")
                        if st.button("Save Appt & Checkout", key=f"u_{r[1]}", use_container_width=True):
                            update_appt(r[1], nd.strftime('%Y-%m-%d'), nt.strftime('%H:%M'))
                            set_check_status(r[1], 0)
                            st.success("Appt Saved and Checked Out!")
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

                    if st.button("Check Out (No Appt)", key=f"co_{r[0]}", use_container_width=True, type="primary"):
                        set_check_status(r[1], 0);
                        st.rerun()
    else:
        st.info("Gym is empty.")

# --- PAGE 5: DASHBOARD ---
elif page == "📊 Dashboard":
    st.subheader("Gym Real-time Monitoring")
    conn = sqlite3.connect(DB_FILE, timeout=10)
    active = conn.execute(
        "SELECT case_no, p_name, prescription_json, therapist FROM history WHERE is_checked_in = 1 AND id IN (SELECT MAX(id) FROM history GROUP BY case_no)").fetchall()
    conn.close()

    if active:
        h1, h2, h3, h4 = st.columns([1.2, 2.5, 2.5, 1.2])
        h1.markdown('<div class="dash-header">Patient</div>', unsafe_allow_html=True)
        h2.markdown('<div class="dash-header">✅ Completed</div>', unsafe_allow_html=True)
        h3.markdown('<div class="dash-header">⏳ Remaining</div>', unsafe_allow_html=True)
        h4.markdown('<div class="dash-header">Progress</div>', unsafe_allow_html=True)

        for p in active:
            c_no, name, presc, th_name = p[0], p[1], json.loads(p[2]), p[3]
            th_name = th_name if th_name else "Unassigned"
            t_color = get_therapist_color(th_name)

            done = [format_ex_details(ex) for ex in presc if ex.get('done', False)]
            todo = [format_ex_details(ex) for ex in presc if not ex.get('done', False)]

            r1, r2, r3, r4 = st.columns([1.2, 2.5, 2.5, 1.2])
            with r1:
                st.write(f"**{name}**")
                st.caption(f"{c_no}")
                st.markdown(
                    f"<span style='background-color: {t_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px;'>🩺 {th_name}</span>",
                    unsafe_allow_html=True)

            with r2:
                html_done = "<br>".join([f"✔️ {x}" for x in done]) if done else "---"
                st.markdown(f'<div class="ex-list-condensed">{html_done}</div>', unsafe_allow_html=True)

            with r3:
                html_todo = "<br>".join([f"🔹 {x}" for x in todo]) if todo else "<b>Clear</b>"
                st.markdown(f'<div class="ex-list-condensed">{html_todo}</div>', unsafe_allow_html=True)

            with r4:
                pct = len(done) / len(presc) if presc else 0
                st.progress(pct)
                st.caption(f"{int(pct * 100)}% complete")

            st.divider()
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