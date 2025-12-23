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

st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;} [data-testid="collapsedControl"] {display: none;}
    .metric-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 2.5rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 1rem; color: #64748b; }
</style>
""", unsafe_allow_html=True)

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

SHEET_NAME_TRAFFIC = "Motorcycle_DB"
DRIVE_FOLDER_ID = "1WQGATGaGBoIjf44Yj_-DjuX8LZ8kbmBA"
GAS_APP_URL = "https://script.google.com/macros/s/AKfycbxRf6z032SxMkiI4IxtUBvWLKeo1LmIQAUMByoXidy4crNEwHoO6h0B-3hT0X7Q5g/exec"
UPGRADE_PASSWORD = st.secrets.get("UPGRADE_PASSWORD", "Patwitsafe")
OFFICER_ACCOUNTS = st.secrets.get("OFFICER_ACCOUNTS", {})

LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: LOGO_BASE64 = base64.b64encode(f.read()).decode()

def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""

def get_img_link(url):
    if not url or pd.isna(url) or str(url).strip() == "": return None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

# ฟังก์ชันเชื่อมต่อหลัก (ใช้ร่วมกันทุกหน้า)
def connect_gsheet_universal():
    if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
        try:
            key_str = st.secrets["textkey"]["json_content"].strip()
            if key_str.startswith("'") and key_str.endswith("'"): key_str = key_str[1:-1]
            if key_str.startswith('"') and key_str.endswith('"'): key_str = key_str[1:-1]
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
    # ... (ส่วนนี้ใช้โค้ดเดิมของคุณทั้งหมด บรรทัดที่ 84 ถึง 208 ในข้อความล่าสุด)
    investigation_module_logic() # แทนค่าด้วยตรรกะเดิมของคุณ

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับ 100%)
# ==========================================
def traffic_module():
    # ... (ส่วนนี้ใช้โค้ดเดิมของคุณทั้งหมด บรรทัดที่ 213 ถึง 352 ในข้อความล่าสุด)
    traffic_module_logic() # แทนค่าด้วยตรรกะเดิมของคุณ

# ==========================================
# 4. MODULE: ANALYTICS (ฉบับแก้ไขการเชื่อมต่อ)
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
        st.write("")
        st.write("")
        b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="ana_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="ana_logout"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    with st.spinner("⏳ กำลังบูรณาการฐานข้อมูล..."):
        try:
            # 1. ดึงข้อมูลสอบสวน (ใช้ st.connection แบบเดิมที่คุณมี)
            conn_inv = st.connection("gsheets", type=GSheetsConnection)
            df_inv = conn_inv.read(ttl="0").fillna("")
            
            # 2. ดึงข้อมูลจราจร (ใช้ฟังก์ชัน universal ที่ย้ายออกมาข้างนอก)
            sheet_tra = connect_gsheet_universal()
            vals_tra = sheet_tra.get_all_values()
            df_tra = pd.DataFrame(vals_tra[1:], columns=vals_tra[0]) if len(vals_tra) > 1 else pd.DataFrame()

            if not df_tra.empty:
                st.markdown("### 🔍 ผลการวิเคราะห์ระดับความเสี่ยงรายชั้นเรียน")
                
                # วิเคราะห์จราจร
                if 'ชั้น/ห้อง' in df_tra.columns:
                    df_tra['Grade'] = df_tra['ชั้น/ห้อง'].apply(lambda x: str(x).split('/')[0] if x else "N/A")
                    tra_count = df_tra['Grade'].value_counts()
                    # วิเคราะห์สอบสวน (เลียนแบบข้อมูล)
                    inv_count = df_inv['Location'].value_counts() if not df_inv.empty else pd.Series()
                    
                    comb = pd.DataFrame({'งานจราจร': tra_count, 'งานสอบสวน': inv_count}).fillna(0).reset_index().rename(columns={'index': 'ชั้น'})
                    comb = comb[comb['ชั้น'].str.contains("ม.", na=False)].sort_values('ชั้น')
                    
                    st.plotly_chart(px.bar(comb, x='ชั้น', y=['งานจราจร', 'งานสอบสวน'], barmode='group', title="เปรียบเทียบสถิติพฤติกรรมผิดระเบียบ"), use_container_width=True)
                
                if not df_inv.empty and 'Incident_Type' in df_inv.columns:
                    top_risk = df_inv['Incident_Type'].value_counts().idxmax()
                    st.error(f"🚩 **ความเสี่ยงทางคดีสูงสุดในระบบสอบสวน:** {top_risk}")
            else:
                st.info("ℹ️ ระบบยังไม่มีข้อมูลรถจักรยานยนต์เพียงพอสำหรับการวิเคราะห์เชิงลึก")
                
        except Exception as e:
            st.warning(f"⚠️ ระบบกำลังปรับปรุงการเชื่อมต่อ Analytics: {str(e)[:50]}...")

# ==========================================
# 5. MAIN ENTRY (ปุ่ม 3 ปุ่ม)
# ==========================================
def main():
    # ... (ส่วนนี้ใช้โค้ดเดิมของคุณ โดยเพิ่มปุ่มที่ 3)
    if st.session_state.logged_in:
        if st.session_state.current_dept is None:
            # ... (แสดง Header)
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary'):
                        st.session_state.current_dept = "tra"; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าใช้งาน Analytics", use_container_width=True, type='primary'):
                        st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
