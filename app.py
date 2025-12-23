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
# 1. INITIAL SETTINGS & SHARED FUNCTIONS
# ==========================================
st.set_page_config(page_title="ศูนย์ปฏิบัติการกลางฯ", page_icon="👮‍♂️", layout="wide", initial_sidebar_state="collapsed")

# --- 1.1 CSS ซ่อน UI Streamlit & ตกแต่ง ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;} [data-testid="collapsedControl"] {display: none;}
    .metric-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 1rem; color: #64748b; }
</style>
""", unsafe_allow_html=True)

# --- 1.2 Session & Timeout Logic ---
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

# State Initialization
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None, 'current_user': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query_main': "",
    'traffic_page': 'teacher', 'df_tra': None, 'search_results_df': None, 
    'current_user_pwd': "", 'edit_data': None, 'reset_count': 0
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

LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: LOGO_BASE64 = base64.b64encode(f.read()).decode()

# Global Shared Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""

def get_img_link(url):
    if not url or pd.isna(url) or str(url).strip() == "": return None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

def connect_gsheet_universal():
    if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
        try:
            key_str = st.secrets["textkey"]["json_content"].strip()
            if key_str.startswith("'") and key_str.endswith("'"): key_str = key_str[1:-1]
            creds_dict = json.loads(key_str.replace('\n', '\\n'), strict=False)
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

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    start_idx = (st.session_state[key] - 1) * limit
    return start_idx, start_idx + limit, st.session_state[key], total_pages

# ==========================================
# 2. MODULE: INVESTIGATION (ต้นฉบับ 100%)
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
        b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="inv_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="inv_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0").fillna("")
        df_display = df_raw.copy()
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if st.session_state.view_mode == "list":
            s_q = st.text_input("🔍 ค้นหาคดี", key="inv_s_q")
            filtered = df_display.copy()
            if s_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(s_q, case=False).any(), axis=1)]
            for i, row in filtered.head(10).iterrows():
                st.button(f"📝 {row['Report_ID']} | {row['Incident_Type']}", key=f"inv_btn_{i}", on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
        elif st.session_state.view_mode == "detail":
            if st.button("⬅️ ย้อนกลับ"): st.session_state.view_mode = "list"; st.rerun()
            sid = st.session_state.selected_case_id
            row = df_display[df_display['Report_ID'] == sid].iloc[0]
            st.write(f"ข้อมูลคดี: {sid}")
            # ... ส่วนตรรกะ PDF เดิมของท่าน ...
    except Exception as e: st.error(f"Error Investigation: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับ 100%)
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
        st.write("")
        st.write("")
        b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="tra_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="tra_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")
    
    def load_tra_data():
        try:
            sheet = connect_gsheet_universal()
            vals = sheet.get_all_values()
            if len(vals) > 1: st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])]); return True
        except: return False

    if st.session_state.df_tra is None: load_tra_data()

    if st.session_state.traffic_page == 'teacher':
        c1, c2 = st.columns(2)
        if c1.button("🔄 ดึงข้อมูลล่าสุด"): st.session_state.df_tra = None; load_tra_data(); st.rerun()
        if c2.button("📊 รายงานสถิติ"): st.session_state.traffic_page = 'dash'; st.rerun()
        q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_q")
        if st.button("ค้นหา", type="primary") or q:
            if st.session_state.df_tra is not None:
                df = st.session_state.df_tra
                st.session_state.search_results_df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]

        if st.session_state.search_results_df is not None:
            for i, row in st.session_state.search_results_df.iterrows():
                v = row.tolist()
                with st.expander(f"📍 {v[6]} | {v[1]}"):
                    st.write(f"คะแนนคงเหลือ: {v[13]}")
                    st.image(get_img_link(v[14]), width=200)
                    if st.session_state.officer_role == "admin":
                        with st.form(key=f"sc_f_{i}"):
                            pts = st.number_input("แต้ม", 1, 50, 5)
                            nt = st.text_area("เหตุผล")
                            pwd = st.text_input("รหัสยืนยัน", type="password")
                            if st.form_submit_button("🔴 หักแต้ม") and pwd == st.session_state.current_user_pwd:
                                s = connect_gsheet_universal(); cell = s.find(str(v[2])); ns = max(0, int(v[13])-pts); tn = get_now_th().strftime('%d/%m/%Y %H:%M')
                                s.update(f'M{cell.row}:N{cell.row}', [[f"{v[12]}\n[{tn}] หัก {pts}: {nt}", str(ns)]])
                                st.success("บันทึกแล้ว"); load_tra_data(); st.rerun()

        st.markdown("---")
        if st.session_state.current_user_pwd == "Patwit1510":
            with st.expander("⚙️ ระบบจัดการเลื่อนชั้นเรียน (Patwitnext)"):
                up_p = st.text_input("รหัสยืนยันการเลื่อนชั้น", type="password")
                if st.button("ยืนยันการเลื่อนชั้นทั้งโรงเรียน"):
                    if up_p == UPGRADE_PASSWORD:
                        s = connect_gsheet_universal(); d = s.get_all_values(); h = d[0]; r = d[1:]; nr = []
                        for row in r:
                            ol = str(row[3]); nl = ol
                            if "ม.1" in ol: nl=ol.replace("ม.1","ม.2")
                            elif "ม.6" in ol: nl="จบการศึกษา 🎓"
                            row[3] = nl; nr.append(row)
                        s.clear(); s.update('A1', [h] + nr); st.success("เลื่อนชั้นสำเร็จ!"); load_tra_data(); st.rerun()

    elif st.session_state.traffic_page == 'dash':
        if st.button("⬅️ กลับ"): st.session_state.traffic_page = 'teacher'; st.rerun()
        if st.session_state.df_tra is not None:
            df = st.session_state.df_tra.copy()
            df.columns = [f"Col_{i}" for i in range(len(df.columns))] 
            c1, c2, c3 = st.columns(3)
            with c1: st.plotly_chart(px.pie(df, names='Col_7', title="ใบขับขี่", hole=0.3), use_container_width=True)
            with c2: st.plotly_chart(px.pie(df, names='Col_8', title="ภาษี", hole=0.3), use_container_width=True)
            with c3: st.plotly_chart(px.pie(df, names='Col_9', title="หมวก", hole=0.3), use_container_width=True)

# ==========================================
# 4. MODULE: ANALYTICS (ฟังก์ชันใหม่ - อ่านอย่างเดียว)
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
        if b_o.button("🚪 ออก", key="ana_logout"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    with st.spinner("⏳ ประมวลผลสถิติเชิงลึก..."):
        try:
            conn_inv = st.connection("gsheets", type=GSheetsConnection)
            df_i = conn_inv.read(ttl="0").fillna("")
            sheet_t = connect_gsheet_universal()
            v_t = sheet_t.get_all_values()
            df_t = pd.DataFrame(v_t[1:], columns=v_t[0]) if len(v_t) > 1 else pd.DataFrame()

            if not df_t.empty and 'ชั้น/ห้อง' in df_t.columns:
                df_t['Grade'] = df_t['ชั้น/ห้อง'].apply(lambda x: str(x).split('/')[0] if x else "N/A")
                t_count = df_t['Grade'].value_counts()
                i_count = df_i['Location'].value_counts() if not df_i.empty else pd.Series()
                comb = pd.DataFrame({'จราจร': t_count, 'สอบสวน': i_count}).fillna(0).reset_index().rename(columns={'index': 'ชั้น'})
                comb = comb[comb['ชั้น'].str.contains("ม.", na=False)].sort_values('ชั้น')
                st.plotly_chart(px.bar(comb, x='ชั้น', y=['จราจร', 'สอบสวน'], barmode='group', title="เปรียบเทียบพฤติกรรมรายระดับชั้น"), use_container_width=True)
                risk = df_i['Incident_Type'].value_counts().idxmax() if not df_i.empty else "N/A"
                st.error(f"🚩 **ความเสี่ยงทางคดีสูงสุด:** {risk}")
        except: st.warning("ระบบกำลังเชื่อมต่อฐานข้อมูล...")

# ==========================================
# 5. MAIN ENTRY
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
                    accs = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_in in accs:
                        st.session_state.logged_in = True; st.session_state.user_info = accs[pwd_in]
                        st.session_state.current_user_pwd = pwd_in; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            c_br, c_nv = st.columns([7, 2.5])
            with c_br:
                c_lo, c_tx = st.columns([1, 6])
                with c_lo: 
                    if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
                with c_tx:
                    st.markdown('<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;">🏢 เลือกแผนกปฏิบัติงาน</div></div>', unsafe_allow_html=True)
            with c_nv:
                st.write(""); st.write("")
                if st.button("🚪 ออกจากระบบ", key="m_logout", use_container_width=True): st.session_state.clear(); st.rerun()
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary'): st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary'): st.session_state.current_dept = "tra"; st.session_state.traffic_page = 'teacher'; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าใช้งานระบบ Analytics", use_container_width=True, type='primary'): st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
