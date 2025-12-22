import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, json, requests, re, textwrap, time
from PIL import Image

# PDF Libraries
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import plotly.express as px

# ==========================================
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบบริหารจัดการสถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# Initialize Session States
states = {
    'logged_in': False, 'current_user': None, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'reset_count': 0,
    'search_results_df': None, 'edit_data': None, 'last_active': time.time()
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

# ค้นหาไฟล์พื้นฐาน
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")

# ==========================================
# 2. SHARED HELPERS (ฟังก์ชันใช้ร่วมกัน)
# ==========================================
def get_now_th():
    return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    try:
        with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()
    except: return ""

def get_img_link_drive(url):
    """แปลงลิงก์ Google Drive เป็น Thumbnail"""
    if pd.isna(url) or str(url).strip() == "" or str(url) == "nan":
        return "https://via.placeholder.com/150?text=No+Image"
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else str(url)

# ==========================================
# 3. INVESTIGATION MODULE (ระบบสอบสวน)
# ==========================================
def investigation_module():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # --- ฟังก์ชันเฉพาะของสอบสวน ---
    def safe_ensure_columns_for_view(df):
        required = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Status', 'Victim', 'Accused', 'Statement']
        if df is None or df.empty: return pd.DataFrame(columns=required)
        for col in required:
            if col not in df.columns: df[col] = ""
        return df

    def create_investigation_pdf(row):
        # (ตัดโค้ด HTML/WeasyPrint เดิมของคุณมาใส่ตรงนี้ โดยใช้ตัวแปร row)
        rid = str(row.get('Report_ID', ''))
        html_content = f"<html><body><h1>รายงานเลขที่ {rid}</h1></body></html>" # ตัวอย่างย่อ
        font_config = FontConfiguration()
        return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=font_config)

    # UI สอบสวน
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", width='stretch', on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบงานสอบสวน")

    try:
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy())
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).strip()

        if st.session_state.view_mode == "list":
            # ส่วนแสดงรายการ (List View)
            st.info("รายการแจ้งเหตุทั้งหมด")
            st.dataframe(df_display[['Report_ID', 'Timestamp', 'Incident_Type', 'Status']], width='stretch')
            # ... เพิ่มโค้ด pagination และรายละเอียดตามต้นฉบับของคุณ ...
        
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 4. TRAFFIC MODULE (ระบบจราจร)
# ==========================================
def traffic_module():
    SHEET_NAME = "Motorcycle_DB"
    DRIVE_FOLDER_ID = "1WQGATGaGBoIjf44Yj_-DjuX8LZ8kbmBA"

    def connect_gsheet_traffic():
        key_content = st.secrets["textkey"]["json_content"]
        key_dict = json.loads(key_content.replace('\n', '\\n'), strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        return gspread.authorize(creds).open(SHEET_NAME).sheet1

    # UI จราจร
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", width='stretch', on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบงานจราจร")

    try:
        sheet = connect_gsheet_traffic()
        if st.button("🔄 โหลดข้อมูลใหม่"):
            vals = sheet.get_all_values()
            st.session_state.df_traffic = pd.DataFrame(vals[1:], columns=vals[0])
            st.success("อัปเดตข้อมูลแล้ว")
            
        if 'df_traffic' in st.session_state:
            st.dataframe(st.session_state.df_traffic.head(), width='stretch')
            # ... เพิ่มโค้ด ค้นหา / ตัดคะแนน ตามต้นฉบับของคุณ ...
            
    except Exception as e: st.error(f"การเชื่อมต่อจราจรขัดข้อง: {e}")

# ==========================================
# 5. MAIN GATEWAY & LOGIN
# ==========================================
def main():
    if not st.session_state.logged_in:
        # หน้า Login ส่วนกลาง
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.header("🔐 Central Login")
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("officer_accounts", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.current_user = accounts[pwd]
                        st.rerun()
                    else: st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # ส่วนเมนูข้างหลัง Login
        st.sidebar.write(f"👤 **{st.session_state.current_user['name']}**")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            # หน้าเลือกแผนก
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เลือกงานสอบสวน", width='stretch'):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เลือกงานจราจร", width='stretch'):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
