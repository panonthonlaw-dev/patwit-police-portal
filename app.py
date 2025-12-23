import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time, ast
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# PDF & Chart Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import plotly.express as px

# ==========================================
# 1. INITIAL SETTINGS & SESSION MANAGEMENT
# ==========================================
st.set_page_config(page_title="ศูนย์ปฏิบัติการกลางฯ", page_icon="👮‍♂️", layout="wide", initial_sidebar_state="collapsed")

# --- 1.1 CSS ปรับแต่งเพื่อลดภาระเครื่อง (NO ANIMATION / MAX SPEED) ---
st.markdown("""
<style>
    /* ปิด Animation ทั้งหมดเพื่อความเร็วสูงสุด */
    * {
        animation: none !important;
        transition: none !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    
    .metric-card { 
        background: white; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #e2e8f0; 
        text-align: center; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
    }
    .metric-value { font-size: 2.5rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 1rem; color: #64748b; }
    img { opacity: 1 !important; }
</style>
""", unsafe_allow_html=True)

# --- 1.2 Session & Timeout Logic (15 นาที) ---
TIMEOUT_SECONDS = 15 * 60 

def check_inactivity():
    if 'last_active' not in st.session_state:
        st.session_state.last_active = time.time()
        return
    if time.time() - st.session_state.last_active > TIMEOUT_SECONDS:
        st.session_state.clear()
        st.session_state.timeout_msg = "⏳ หมดเวลาการเชื่อมต่อ (15 นาที) กรุณาเข้าสู่ระบบใหม่"
        st.rerun()
    else:
        st.session_state.last_active = time.time()

check_inactivity()

# Session States
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None, 'current_user': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query_main': "",
    'traffic_page': 'teacher', 'df_tra': None, 'search_results_df': None, 
    'current_user_pwd': "", 'edit_data': None, 'reset_count': 0,
    'preserve_search': False
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")

# Configs
SHEET_NAME_TRAFFIC = "Motorcycle_DB"
DRIVE_FOLDER_ID = "1WQGATGaGBoIjf44Yj_-DjuX8LZ8kbmBA"
GAS_APP_URL = "https://script.google.com/macros/s/AKfycbxRf6z032SxMkiI4IxtUBvWLKeo1LmIQAUMByoXidy4crNEwHoO6h0B-3hT0X7Q5g/exec"
UPGRADE_PASSWORD = st.secrets.get("UPGRADE_PASSWORD", "Patwitsafe")
OFFICER_ACCOUNTS = st.secrets.get("OFFICER_ACCOUNTS", {})

# Logo
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), 
                 next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: LOGO_BASE64 = base64.b64encode(f.read()).decode()

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""
def process_image(img_file):
    if not img_file: return ""
    try:
        img = Image.open(img_file).convert('RGB'); img.thumbnail((800, 800))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=65); return base64.b64encode(buf.getvalue()).decode()
    except: return ""

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    start_idx = (st.session_state[key] - 1) * limit
    end_idx = start_idx + limit
    return start_idx, end_idx, st.session_state[key], total_pages

def get_img_link(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

def connect_gsheet_universal():
    if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
        try:
            key_str = st.secrets["textkey"]["json_content"]
            key_str = key_str.strip()
            if key_str.startswith("'") and key_str.endswith("'"): key_str = key_str[1:-1]
            if key_str.startswith('"') and key_str.endswith('"'): key_str = key_str[1:-1]
            try: creds_dict = json.loads(key_str, strict=False)
            except: creds_dict = json.loads(key_str.replace('\n', '\\n'), strict=False)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds).open(SHEET_NAME_TRAFFIC).sheet1
        except: pass
    if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open(SHEET_NAME_TRAFFIC).sheet1
    raise Exception("Credential Error")

# ==========================================
# 2. MODULE: INVESTIGATION (ต้นฉบับ 100% ห้ามแก้)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">🕵️ ระบบงานสอบสวน</span> | ผู้เข้าใช้: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write("")
        st.write("")
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", use_container_width=True, key="inv_home_btn"):
            setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="inv_logout_btn", use_container_width=True):
            st.session_state.clear(); st.rerun()
    st.markdown("---")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = df_raw.copy().fillna("")
        for c in ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']:
            if c not in df_display.columns: df_display[c] = ""
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหา", placeholder="เลขเคส, ชื่อ...", key="search_query_main", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา", use_container_width=True)
                if c_btn_clear.button("❌ ล้าง", use_container_width=True): st.rerun()
                filtered = df_display.copy()
                if search_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                df_p = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_f = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start_p, end_p, cur_p, tot_p = calculate_pagination('page_pending', len(df_p), 5)
                h1, h2, h3, h4 = st.columns([2.5, 2, 3, 1.5]); h1.markdown("**เลขที่รับแจ้ง**"); h2.markdown("**วันเวลา**"); h3.markdown("**ประเภทเหตุ**"); h4.markdown("**สถานะ**")
                st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
                if df_p.empty: st.caption("ไม่มีรายการ")
                for i, row in df_p.iloc[start_p:end_p].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {row['Report_ID']}", key=f"p_{i}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.markdown(f"<span style='color:orange;font-weight:bold'>⏳ {row['Status']}</span>", unsafe_allow_html=True); st.divider()
                if tot_p > 1:
                    cp1, cp2, cp3 = st.columns([1, 2, 1])
                    if cp1.button("⬅️ ย้อนกลับ", disabled=st.session_state.page_pending==1, key="pp"): st.session_state.page_pending-=1; st.rerun()
                    cp2.markdown(f"<div style='text-align:center;'>{st.session_state.page_pending} / {tot_p}</div>", unsafe_allow_html=True)
                    if cp3.button("ถัดไป ➡️", disabled=st.session_state.page_pending==tot_p, key="pn"): st.session_state.page_pending+=1; st.rerun()
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, cur_f, tot_f = calculate_pagination('page_finished', len(df_f), 5)
                for i, row in df_f.iloc[start_f:end_f].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {row['Report_ID']}", key=f"f_{i}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.markdown("<span style='color:green;font-weight:bold'>✅ เรียบร้อย</span>", unsafe_allow_html=True); st.divider()
            with tab_dash:
                tc = len(df_display)
                if tc > 0:
                    m1, m2, m3 = st.columns(3); m1.metric("แจ้งเหตุทั้งหมด", f"{tc} ครั้ง"); m2.metric("สถานที่เกิดเหตุบ่อยสุด", df_display['Location'].mode()[0] if not df_display.empty else "-"); m3.metric("เหตุที่เกิดบ่อยสุด", df_display['Incident_Type'].mode()[0] if not df_display.empty else "-")
                    st.divider(); col1, col2 = st.columns(2)
                    with col1: st.markdown("**🔹 ประเภทเหตุ**"); st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2: st.markdown("**🔹 สถานที่เกิดเหตุ**"); st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")
        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list'}), use_container_width=True)
            sid = st.session_state.selected_case_id; sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx_raw = sel.index[0]; row = sel.iloc[0]; st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}"); st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']): st.image(base64.b64decode(row['Image_Data']), width=500, caption="หลักฐานจากผู้แจ้ง")
                cur_sta = clean_val(row['Status']); is_lock = (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510")
                if user.get('role') != 'admin': is_lock = True
                if is_lock and cur_sta == "ดำเนินการเรียบร้อย" and user.get('role') == 'admin':
                    pwd = st.text_input("รหัสปลดล็อค", type="password")
                    if st.button("ยืนยันปลดล็อค"):
                        if pwd == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()
                with st.form("full_inv_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_lock); v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_lock); v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_lock); v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_lock); v_stu = c1.text_input("ตำรวจนักเรียนผู้สอบสวน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_lock); v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"].index(cur_sta) if cur_sta in ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"] else 0, disabled=is_lock); v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_lock); ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่ม", type=['jpg','png'], disabled=is_lock)
                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_lock:
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc; df_raw.at[idx_raw, 'Witness'] = v_wit; df_raw.at[idx_raw, 'Teacher_Investigator'] = v_tea; df_raw.at[idx_raw, 'Student_Police_Investigator'] = v_stu; df_raw.at[idx_raw, 'Statement'] = v_stmt; df_raw.at[idx_raw, 'Status'] = v_sta
                        if ev_img: df_raw.at[idx_raw, 'Evidence_Image'] = process_image(ev_img)
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกเรียบร้อย!"); time.sleep(1); st.rerun()
                if clean_val(row['Audit_Log']):
                    with st.expander("📜 ประวัติการบันทึก (Audit Log)"): st.code(row['Audit_Log'])
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับ 100% ห้ามแก้)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.session_state.officer_name = user.get('name', 'N/A')
    st.session_state.officer_role = user.get('role', 'teacher')
    st.session_state.current_user_pwd = st.session_state.current_user_pwd 
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">🚦 ระบบงานจราจร</span> | ผู้เข้าใช้: {st.session_state.officer_name}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); st.write(""); b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", key="tra_home_btn", use_container_width=True): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="tra_logout_btn", use_container_width=True): st.session_state.clear(); st.rerun()
    st.markdown("---")
    if st.session_state.df_tra is None:
        try:
            sheet = connect_gsheet_universal(); vals = sheet.get_all_values()
            if len(vals) > 1: st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])])
        except: pass
    if st.session_state.traffic_page == 'teacher':
        c1, c2 = st.columns(2)
        if c1.button("🔄 ดึงข้อมูลล่าสุด"): st.session_state.df_tra = None; st.session_state.search_results_df = None; st.rerun()
        if c2.button("📊 รายงานสถิติ"): st.session_state.traffic_page = 'dash'; st.rerun()
        q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_search_input")
        c_s, c_c = st.columns([4, 1])
        do_s = c_s.button("ค้นหา", type="primary", use_container_width=True); do_cl = c_c.button("ล้างค่า", use_container_width=True)
        if do_cl: st.session_state.search_results_df = None; st.rerun()
        st.caption("▼ ตัวกรองข้อมูล")
        col_f1, col_f2, col_f3 = st.columns(3)
        u_lv, u_br = [], []
        if st.session_state.df_tra is not None:
            u_lv = sorted(list(set([str(x).split('/')[0] for x in st.session_state.df_tra.iloc[:, 3].unique()])))
            u_br = sorted(list(set(st.session_state.df_tra.iloc[:, 4].unique())))
        f_risk = col_f1.selectbox("🚨 กลุ่มปัญหา:", ["ทั้งหมด", "❌ ไม่มีใบขับขี่", "❌ ภาษีขาด", "❌ ไม่สวมหมวก"]); f_lv = col_f2.selectbox("📚 ระดับชั้น:", ["ทั้งหมด"] + u_lv); f_br = col_f3.selectbox("🏍️ ยี่ห้อรถ:", ["ทั้งหมด"] + u_br)
        if st.button("⚡ กรองข้อมูลตามเงื่อนไข", use_container_width=True) or do_s:
            if not q.strip() and f_risk == "ทั้งหมด" and f_lv == "ทั้งหมด" and f_br == "ทั้งหมด": st.error("⚠️ กรุณากรอกข้อมูล")
            elif st.session_state.df_tra is not None:
                df = st.session_state.df_tra.copy()
                if q.strip(): df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
                if f_risk != "ทั้งหมด": idx = 7 if "ใบขับขี่" in f_risk else (8 if "ภาษี" in f_risk else 9); df = df[df.iloc[:, idx].astype(str).str.contains("ไม่มี|ขาด")]
                if f_lv != "ทั้งหมด": df = df[df.iloc[:, 3].astype(str).str.contains(f_lv)]
                if f_br != "ทั้งหมด": df = df[df.iloc[:, 4] == f_br]
                st.session_state.search_results_df = df
        if st.session_state.search_results_df is not None:
            tdf = st.session_state.search_results_df
            if tdf.empty: st.warning("❌ ไม่พบข้อมูล")
            else:
                for i, row in tdf.iterrows():
                    v = row.tolist(); sc = int(v[13]) if len(v)>13 and str(v[13]).isdigit() else 100
                    with st.expander(f"📍 {v[6]} | {v[1]}"):
                        st.write(f"คะแนน: {sc}"); st.image(get_img_link(v[14]), width=200)
                        if st.session_state.officer_role == "admin":
                            with st.form(key=f"sc_form_{i}"):
                                pts = st.number_input("แต้ม", 1, 50, 5); nt = st.text_area("เหตุผล"); pwd = st.text_input("รหัสยืนยัน", type="password")
                                if st.form_submit_button("🔴 หักแต้ม") and nt and pwd == st.session_state.current_user_pwd:
                                    s = connect_gsheet_universal(); cell = s.find(str(v[2])); ns = max(0, sc-pts); tn = get_now_th().strftime('%d/%m/%Y %H:%M'); old = str(v[12]).strip() if str(v[12]).lower()!="nan" else ""; s.update(f'M{cell.row}:N{cell.row}', [[f"{old}\n[{tn}] หัก {pts}: {nt}", str(ns)]]); st.success("บันทึกแล้ว"); st.session_state.df_tra = None; st.rerun()
        if st.session_state.current_user_pwd == "Patwit1510":
            with st.expander("⚙️ ระบบจัดการเลื่อนชั้นเรียน (Patwitnext)"):
                up_pwd = st.text_input("รหัสเลื่อนชั้น", type="password", key="prom_pwd")
                if st.button("ยืนยันเลื่อนชั้น", use_container_width=True) and up_pwd == UPGRADE_PASSWORD:
                    s = connect_gsheet_universal(); d = s.get_all_values(); h = d[0]; r = d[1:]; nr = []
                    for row in r:
                        ol = str(row[3]); nl = ol
                        if "ม.1" in ol: nl=ol.replace("ม.1","ม.2")
                        elif "ม.6" in ol: nl="จบการศึกษา 🎓"
                        row[3] = nl; nr.append(row)
                    s.clear(); s.update('A1', [h] + nr); st.success("สำเร็จ!"); st.session_state.df_tra = None; st.rerun()
    elif st.session_state.traffic_page == 'dash':
        if st.button("⬅️ กลับ"): st.session_state.traffic_page = 'teacher'; st.rerun()
        if st.session_state.df_tra is not None:
            df = st.session_state.df_tra.copy(); df.columns = [f"Col_{i}" for i in range(len(df.columns))] 
            c1, c2, c3 = st.columns(3)
            with c1: st.plotly_chart(px.pie(df, names='Col_7', title="ใบขับขี่", hole=0.3), use_container_width=True)
            with c2: st.plotly_chart(px.pie(df, names='Col_8', title="ภาษี", hole=0.3), use_container_width=True)
            with c3: st.plotly_chart(px.pie(df, names='Col_9', title="หมวก", hole=0.3), use_container_width=True)

# ==========================================
# 4. MODULE: ANALYTICS (ส่วนเพิ่มใหม่ - Read Only)
# ==========================================
def analytics_module():
    user = st.session_state.user_info
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์วิเคราะห์พฤติกรรมและมาตรการเชิงป้องกัน</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">📊 ระบบวิเคราะห์พฤติกรรมศาสตร์ (Analytics)</span> | ผู้เชี่ยวชาญ: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="ana_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="ana_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    with st.spinner("⏳ กำลังวิเคราะห์ข้อมูล Big Data พฤติกรรมศาสตร์..."):
        try:
            # 1. ดึงข้อมูลสอบสวน (Investigation)
            conn_inv = st.connection("gsheets", type=GSheetsConnection)
            df_inv = conn_inv.read(ttl="0").fillna("")
            
            # 2. ดึงข้อมูลจราจร (Traffic)
            sheet_tra = connect_gsheet_universal()
            vals_tra = sheet_tra.get_all_values()
            df_tra = pd.DataFrame(vals_tra[1:], columns=[f"C{i}" for i in range(len(vals_tra[0]))])

            st.markdown("### 🔍 ผลการวิเคราะห์ระดับความเสี่ยงรายชั้นเรียน")
            
            # วิเคราะห์เปรียบเทียบระดับชั้น (Traffic = C3, Investigation = Location หรือ Grade ถ้ามี)
            if not df_tra.empty:
                df_tra['Grade_Only'] = df_tra['C3'].apply(lambda x: str(x).split('/')[0] if x else "N/A")
                tra_stats = df_tra['Grade_Only'].value_counts()
                inv_stats = df_inv['Location'].value_counts() if not df_inv.empty else pd.Series()
                
                comb = pd.DataFrame({'งานจราจร': tra_stats, 'งานสอบสวน': inv_stats}).fillna(0).reset_index().rename(columns={'index': 'ชั้น'})
                comb = comb[comb['ชั้น'].str.contains("ม.", na=False)].sort_values('ชั้น')
                
                fig = px.bar(comb, x='ชั้น', y=['งานจราจร', 'งานสอบสวน'], barmode='group', title="เปรียบเทียบสถิติพฤติกรรมผิดระเบียบ")
                st.plotly_chart(fig, use_container_width=True)
                
                top_risk = df_inv['Incident_Type'].value_counts().idxmax() if not df_inv.empty else "N/A"
                st.error(f"🚩 **ความเสี่ยงทางคดีสูงสุด:** เรื่อง **{top_risk}** (จำเป็นต้องมีการรณรงค์เชิงป้องกัน)")
        except Exception as e:
            st.warning(f"⚠️ ระบบกำลังรวบรวมข้อมูล: {str(e)[:50]}...")

# ==========================================
# 5. MAIN ENTRY (แก้ไขเพื่อรองรับ 3 ปุ่ม)
# ==========================================
def main():
    if 'timeout_msg' in st.session_state and st.session_state.timeout_msg: st.error(st.session_state.timeout_msg); del st.session_state.timeout_msg
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                if LOGO_PATH: st.image(LOGO_PATH, width=120)
                st.markdown("<h3 style='text-align:center;'>ศูนย์ปฏิบัติการกลาง<br>สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h3>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    if pwd_in in st.secrets.get("OFFICER_ACCOUNTS", {}):
                        st.session_state.logged_in = True; st.session_state.user_info = st.secrets["OFFICER_ACCOUNTS"][pwd_in]; st.session_state.current_user_pwd = pwd_in; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            c_brand, c_nav = st.columns([7, 2.5])
            with c_brand:
                c_logo, c_text = st.columns([1, 6])
                with c_logo: 
                    if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
                with c_text: st.markdown('<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;">🏢 เลือกแผนกปฏิบัติงาน</div></div>', unsafe_allow_html=True)
            with c_nav:
                st.write(""); st.write("")
                if st.button("🚪 ออกจากระบบ", key="main_logout", use_container_width=True): st.session_state.clear(); st.rerun()
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary', key="btn_inv"): st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary', key="btn_tra"): st.session_state.current_dept = "tra"; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าสู่ระบบ Analytics", use_container_width=True, type='primary', key="btn_ana"): st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
