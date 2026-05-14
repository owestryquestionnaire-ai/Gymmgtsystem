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
    .cat-header {
        font-size: 15px; font-weight: 800; text-decoration: underline;
        background-color: #e1f5fe; color: #01579b; padding: 5px;
        border-radius: 4px; margin-bottom: 10px; margin-top: 10px;
    }
    .config-box {
        padding-left: 15px; border-left: 3px solid #1f77b4;
        background-color: #f0f2f6; margin-bottom: 15px;
        padding-top: 8px; padding-bottom: 8px; border-radius: 0 5px 5px 0;
    }
    .appt-box {
        background-color: #f1f8e9; padding: 12px; border-radius: 8px;
        border: 1px solid #c5e1a5; margin-top: 10px;
    }
    .grid-header {
        background-color: #424242; color: white; padding: 10px;
        text-align: center; font-weight: bold; border: 1px solid #ddd; font-size: 13px;
    }
    .time-slot-label {
        background-color: #f8f9fa; font-weight: bold; padding: 10px;
        text-align: center; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center;
    }
    .grid-cell {
        min-height: 70px; padding: 4px; border: 1px solid #eee;
        background-color: #ffffff; font-size: 11px; overflow-y: auto;
    }
    .patient-tag {
        background-color: #e3f2fd; border-left: 3px solid #1976d2;
        padding: 2px 4px; margin-bottom: 2px; border-radius: 2px; color: #0d47a1;
    }
    .ex-list-condensed {
        max-height: 80px; overflow-y: auto; font-size: 12px; line-height: 1.2;
        background: #fdfdfd; border: 1px solid #eee; padding: 5px; border-radius: 3px;
    }
    .dash-header { font-weight: bold; font-size: 14px; border-bottom: 2px solid #333; padding-bottom: 5px; margin-bottom: 10px; }
    .stProgress { margin-bottom: 0 !important; }
    hr { margin: 8px 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Database Setup ---
DB_FILE = "gym_system.db"


def init_db():
    conn = sqlite3.connect(DB_FILE);
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_no TEXT, p_name TEXT, timestamp TEXT,
        op_details TEXT, op_date TEXT, p_class TEXT, p_precautions TEXT, 
        prescription_json TEXT, is_checked_in INTEGER DEFAULT 0,
        next_appt_date TEXT, next_appt_time TEXT)''')
    conn.commit();
    conn.close()


def set_check_status(case_no, status):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE history SET is_checked_in = ? WHERE case_no = ?", (status, case_no))
    conn.commit();
    conn.close()


def update_appt(case_no, n_date, n_time):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE history SET next_appt_date = ?, next_appt_time = ? WHERE case_no = ?",
                 (n_date, n_time, case_no))
    conn.commit();
    conn.close()


def delete_patient(case_no):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM history WHERE case_no = ?", (case_no,))
    conn.commit();
    conn.close()


def save_h(c_no, name, presc, op_text, o_date, p_class, p_pre, is_chk, n_date, n_time):
    conn = sqlite3.connect(DB_FILE);
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO history 
        (case_no, p_name, timestamp, op_details, op_date, p_class, p_precautions, prescription_json, is_checked_in, next_appt_date, next_appt_time) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (c_no, name, datetime.now().strftime('%Y-%m-%d %H:%M'), op_text, o_date, p_class, p_pre,
                    json.dumps(presc, ensure_ascii=False), is_chk, n_date, n_time))
    conn.commit();
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

# --- THE ULTIMATE FIX: GLOBAL DICTIONARY ---
# Streamlit CANNOT garbage collect this dictionary. It is our absolute source of truth.
if "active_patient" not in st.session_state:
    st.session_state.active_patient = {
        "case_no": "", "p_name": "New Patient", "p_class": "",
        "p_att": False, "p_fing": False,
        "exercises": {},  # Format: {"e1": "", "st1": "15"}
        "current_chk": 1, "current_nd": "None", "current_nt": "None",
        "is_loaded": False, "show_sheet": False
    }


# --- Format Helper ---
def format_ex_details(item):
    eid, d = item['id'], []
    if eid in ["st1", "st2"]: d.append(f"{item.get(eid + '_weight')} lbs")
    detail_str = f" ({', '.join(filter(None, d))})" if d else ""
    return f"{item['name']}{detail_str}"


# --- APP ---
st.title("🏋️‍♂️ Gym Management System")

tabs = st.tabs(["📋 Selection", "👥 Database", "🗒️ Active Cases", "📊 Dashboard", "📅 Weekly Planner"])

ap = st.session_state.active_patient  # Short reference to our global dictionary

# --- TAB 1: SELECTION ---
with tabs[0]:
    c1, c2 = st.columns([4, 1])
    c1.subheader("Patient Entry")

    if c2.button("✨ Blank New Patient", type="primary", use_container_width=True):
        st.session_state.active_patient = {
            "case_no": "", "p_name": "New Patient", "p_class": "",
            "p_att": False, "p_fing": False, "exercises": {},
            "current_chk": 1, "current_nd": "None", "current_nt": "None",
            "is_loaded": False, "show_sheet": False
        }
        st.rerun()

    st.divider()

    if ap["is_loaded"]:
        st.info(
            "✏️ **Edit Mode Active:** You are modifying a loaded patient. Saving will keep their appointment schedule intact.")

    if not ap["show_sheet"]:
        l, r = st.columns([1.2, 3.5])
        with l:
            # Bind Text Inputs directly to our dictionary
            ap["case_no"] = st.text_input("Case No.", value=ap["case_no"])
            ap["p_name"] = st.text_input("Patient Name", value=ap["p_name"])

            opts = ["Class I", "Class II", "Class III"]
            idx = opts.index(ap["p_class"]) if ap["p_class"] in opts else None
            ap["p_class"] = st.radio("Class", opts, index=idx, horizontal=True)

            st.markdown("**Precautions:**")
            ap["p_att"] = st.checkbox("多注目", value=ap["p_att"])
            ap["p_fing"] = st.checkbox("夾手指做運動", value=ap["p_fing"])

            op_d = st.date_input("Date of Operation", value=datetime.now())

            btn_label = "💾 Update Prescription" if ap["is_loaded"] else "Generate & Check In"

            if st.button(btn_label, type="primary", use_container_width=True):
                # Format Precautions
                pre_list = []
                if ap["p_att"]: pre_list.append("多注目")
                if ap["p_fing"]: pre_list.append("夾手指做運動")
                final_pre = ", ".join(pre_list) if pre_list else "None"

                # Build JSON prescription purely from our dictionary
                sel = []
                for eid, weight in ap["exercises"].items():
                    # Find name from Database
                    ex_name = next((x["name"] for cat in EXERCISE_DB.values() for x in cat if x["id"] == eid),
                                   "Unknown")
                    ex_data = {"id": eid, "name": ex_name, "mins": "15"}
                    if eid in ["st1", "st2"]: ex_data[f"{eid}_weight"] = weight
                    sel.append(ex_data)

                # Save to Database
                save_h(
                    ap["case_no"], ap["p_name"], sel,
                    "Op Detail", op_d.strftime("%Y-%m-%d"),
                    ap["p_class"] if ap["p_class"] else "None", final_pre,
                    ap["current_chk"], ap["current_nd"], ap["current_nt"]
                )

                ap["is_loaded"] = False
                ap["show_sheet"] = True
                st.rerun()

        with r:
            cols_r = st.columns(3)
            for idx, (cat, items) in enumerate(EXERCISE_DB.items()):
                with cols_r[idx % 3]:
                    st.markdown(f'<div class="cat-header">{cat}</div>', unsafe_allow_html=True)
                    for ex in items:
                        eid = ex["id"]

                        # Data-Driven Checkbox: Streamlit CANNOT delete this memory!
                        is_selected = eid in ap["exercises"]
                        checked = st.checkbox(ex["name"], value=is_selected, key=f"ui_{eid}")

                        if checked:
                            # Add to dictionary if not present
                            if eid not in ap["exercises"]:
                                ap["exercises"][eid] = ""

                            # Show weight input if needed
                            if eid in ["st1", "st2"]:
                                st.markdown('<div class="config-box">', unsafe_allow_html=True)
                                w_val = ap["exercises"][eid]
                                new_w = st.text_input("lbs", value=w_val, key=f"ui_w_{eid}")
                                ap["exercises"][eid] = new_w
                                st.markdown('</div>', unsafe_allow_html=True)
                        else:
                            # Remove from dictionary instantly when unchecked
                            if eid in ap["exercises"]:
                                del ap["exercises"][eid]

    else:
        st.success("💾 Prescription Saved Successfully!")
        if st.button("Back to Editor"):
            ap["show_sheet"] = False
            st.rerun()

# --- TAB 2: DATABASE ---
with tabs[1]:
    st.subheader("Patient Records")
    col_f1, col_f2 = st.columns([1, 2])
    view_mode = col_f1.radio("View Options", ["All Patients", "Filter by Date"], horizontal=True)

    target_date = ""
    if view_mode == "Filter by Date":
        target_date = col_f2.date_input("Select Appointment Date").strftime('%Y-%m-%d')
    st.divider()

    conn = sqlite3.connect(DB_FILE)
    query = "SELECT id, case_no, p_name, next_appt_date, is_checked_in, p_class, p_precautions, prescription_json, op_details, next_appt_time FROM history WHERE id IN (SELECT MAX(id) FROM history GROUP BY case_no)"
    if view_mode == "Filter by Date": query += f" AND next_appt_date = '{target_date}'"
    query += " ORDER BY p_name ASC"
    db = conn.execute(query).fetchall()
    conn.close()

    if db:
        for row in db:
            c = st.columns([1, 1.2, 1.5, 0.8, 0.8, 0.8, 0.8])
            c[0].write(row[1]);
            c[1].write(row[2])
            appt_display = f"📅 {row[3]}" if row[3] != 'None' and row[3] else "No Appt"
            c[2].write(appt_display)

            # The Load Button overwrites the Global Dictionary Directly
            if c[3].button("Load", key=f"ld_{row[0]}"):

                # Safely parse JSON into our custom dictionary format
                ex_dict = {}
                try:
                    data = json.loads(row[7])
                    if isinstance(data, str): data = json.loads(data)
                    for item in data:
                        eid = item.get("id")
                        if eid: ex_dict[eid] = str(item.get(f"{eid}_weight", ""))
                except Exception:
                    pass

                # Overwrite the global dictionary
                st.session_state.active_patient = {
                    "case_no": row[1],
                    "p_name": row[2],
                    "p_class": row[5] if row[5] != "None" else "",
                    "p_att": "多注目" in (row[6] or ""),
                    "p_fing": "夾手指做運動" in (row[6] or ""),
                    "exercises": ex_dict,
                    "current_chk": row[4],
                    "current_nd": row[3],
                    "current_nt": row[9],
                    "is_loaded": True,
                    "show_sheet": False
                }
                st.toast(f"✅ Loaded {row[2]}! Check Tab 1.")
                st.rerun()

            if c[4].button("Show", key=f"sh_{row[0]}"):
                with st.expander("Exercises"):
                    for ex in json.loads(row[7]): st.write(f"• {format_ex_details(ex)}")
            if c[5].button("In/Out", key=f"io_{row[0]}"): set_check_status(row[1], 1 if not row[4] else 0); st.rerun()
            if c[6].button("Del", key=f"del_{row[0]}"): delete_patient(row[1]); st.rerun()
    else:
        st.info("No records found.")

# --- TAB 3: ACTIVE CASES ---
with tabs[2]:
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        "SELECT id, case_no, p_name, prescription_json, next_appt_date, next_appt_time FROM history WHERE is_checked_in = 1 AND id IN (SELECT MAX(id) FROM history GROUP BY case_no) ORDER BY p_name ASC").fetchall()
    conn.close()
    if rows:
        acols = st.columns(3)
        for i, r in enumerate(rows):
            with acols[i % 3]:
                with st.expander(f"👤 {r[2]} ({r[1]})", expanded=False):
                    for ex in json.loads(r[3]): st.checkbox(format_ex_details(ex), key=f"done_{r[1]}_{ex['id']}")
                    st.divider()
                    if st.checkbox("📅 Schedule Next Visit", key=f"show_appt_{r[1]}"):
                        st.markdown('<div class="appt-box">', unsafe_allow_html=True)
                        nd = st.date_input("Date", key=f"nd_{r[1]}");
                        nt = st.time_input("Time", value=time(9, 0), key=f"nt_{r[1]}")
                        if st.button("Save Appt", key=f"u_{r[1]}", use_container_width=True):
                            update_appt(r[1], nd.strftime('%Y-%m-%d'), nt.strftime('%H:%M'));
                            st.success("Updated!")
                        st.markdown('</div>', unsafe_allow_html=True)
                    if st.button("Check Out", key=f"co_{r[0]}", use_container_width=True, type="primary"):
                        set_check_status(r[1], 0);
                        st.rerun()

# --- TAB 4: DASHBOARD ---
with tabs[3]:
    conn = sqlite3.connect(DB_FILE)
    active = conn.execute(
        "SELECT case_no, p_name, prescription_json FROM history WHERE is_checked_in = 1 AND id IN (SELECT MAX(id) FROM history GROUP BY case_no)").fetchall()
    conn.close()
    if active:
        h1, h2, h3, h4 = st.columns([1, 2.5, 2.5, 1.2])
        h1.markdown('<div class="dash-header">Patient</div>', unsafe_allow_html=True)
        h2.markdown('<div class="dash-header">✅ Completed</div>', unsafe_allow_html=True)
        h3.markdown('<div class="dash-header">⏳ Remaining</div>', unsafe_allow_html=True)
        h4.markdown('<div class="dash-header">Progress</div>', unsafe_allow_html=True)
        for p in active:
            c_no, name, presc = p[0], p[1], json.loads(p[2])
            done = [format_ex_details(ex) for ex in presc if st.session_state.get(f"done_{c_no}_{ex['id']}", False)]
            todo = [format_ex_details(ex) for ex in presc if not st.session_state.get(f"done_{c_no}_{ex['id']}", False)]
            r1, r2, r3, r4 = st.columns([1, 2.5, 2.5, 1.2])
            r1.write(f"**{name}** ({c_no})")
            with r2: st.markdown(
                f'<div class="ex-list-condensed">{"<br>".join(["✔️ " + x for x in done]) if done else "---"}</div>',
                unsafe_allow_html=True)
            with r3: st.markdown(
                f'<div class="ex-list-condensed">{"<br>".join(["🔹 " + x for x in todo]) if todo else "<b>Clear</b>"}</div>',
                unsafe_allow_html=True)
            with r4: pct = len(done) / len(presc) if presc else 0; st.progress(pct); st.caption(f"{int(pct * 100)}%")
            st.divider()

# --- TAB 5: WEEKLY PLANNER GRID ---
with tabs[4]:
    st.subheader("📅 Gym Weekly Planner Grid")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "13:30", "14:00", "14:30", "15:00"]
    now = datetime.now();
    monday = now - timedelta(days=now.weekday())
    week_dates = [(monday + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

    conn = sqlite3.connect(DB_FILE)
    sched_df = pd.read_sql_query(
        "SELECT next_appt_date, next_appt_time, p_name FROM history WHERE next_appt_date IN ({})".format(
            ','.join(['?'] * 7)), conn, params=week_dates)
    conn.close()

    cols = st.columns([0.8] + [1] * 7)
    cols[0].markdown('<div class="grid-header">Time</div>', unsafe_allow_html=True)
    for i, day in enumerate(days):
        cols[i + 1].markdown(f'<div class="grid-header">{day}<br><small>{week_dates[i]}</small></div>',
                             unsafe_allow_html=True)

    for slot in slots:
        row_cols = st.columns([0.8] + [1] * 7)
        row_cols[0].markdown(f'<div class="time-slot-label">{slot}</div>', unsafe_allow_html=True)
        for i, date_str in enumerate(week_dates):
            matches = sched_df[(sched_df['next_appt_date'] == date_str) & (sched_df['next_appt_time'] == slot)]
            cell_content = "".join([f'<div class="patient-tag">👤 {r["p_name"]}</div>' for _, r in matches.iterrows()])
            row_cols[i + 1].markdown(f'<div class="grid-cell">{cell_content if cell_content else "-"}</div>',
                                     unsafe_allow_html=True)