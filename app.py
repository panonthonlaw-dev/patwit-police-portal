import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, json, requests, re, textwrap, time
from PIL import Image

# PDF & Visualization Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except:
    pass
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import plotly.express as px

# ==========================================
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# Initialize Session States เพื่อป้องกัน AttributeError
init_states = {
    'logged_in': False, 'user_info': None, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'search_results_df': None,
    'page_pending': 1, 'page_finished': 1, 'reset_count': 0
}
for key, val in init_states.items():
    if key not in st.session_state:
        st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# ==========================================
# 2. SHARED HELPERS (ฟังก์ชันส่วนกลาง)
# ==========================================
def get_now_th():
    return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_img_link_drive(url):
    """แก้ไข Error: The truth value of a Series is ambiguous"""
    if pd.isna(url) or str(url).strip() == "" or str(url) == "nan":
        return "https://via.placeholder.com/150?text=No+Image"
    url_str = str(url)
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', url_str)
    if match:
        file_id = match.group(1) or match.group(2)
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800"
    return url_str

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

# ==========================================
# 3. INVESTIGATION MODULE (ระบบสอบสวน)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", width='stretch', on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบงานสอบสวน")
    
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        
        # แสดงข้อมูลตัวอย่าง
        st.success("เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.write("รายการแจ้งเหตุล่าสุด:")
        st.dataframe(df_raw.tail(10), width='stretch')
        
        # --- คุณสามารถนำ Logic การจัดการเคส (List/Detail) มาวางต่อที่นี่ ---
        
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในระบบสอบสวน: {str(e)}")

# ==========================================
# 4. TRAFFIC MODULE (ระบบจราจร)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", width='stretch', on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบงานจราจร")
    
    def connect_traffic():
        # แก้ไข Error: JSON Decoding
        key_content = st.secrets["textkey"]["json_content"]
        key_dict = json.loads(key_content.replace('\n', '\\n'), strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_traffic()
        st.success("เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        if st.button("🔄 โหลดข้อมูลรถทั้งหมด"):
            vals = sheet.get_all_values()
            st.session_state.search_results_df = pd.DataFrame(vals[1:], columns=vals[0])
            st.rerun()
            
        if st.session_state.search_results_df is not None:
            st.dataframe(st.session_state.search_results_df, width='stretch')
            
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในระบบจราจร: {str(e)}")

# ==========================================
# 5. MAIN GATEWAY (หน้า LOGIN & PORTAL)
# ==========================================
def main():
    if not st.session_state.logged_in:
        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Portal</h2>", unsafe_allow_html=True)
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("Login", width='stretch', type='primary'):
                    accounts = st.secrets.get("officer_accounts", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # Sidebar Management
        user = st.session_state.user_info
        name = user['name'] if isinstance(user, dict) else str(user)
        st.sidebar.write(f"👤 **{name}**")
        
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกฝ่ายปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    st.write("จัดการเคสและสรุปสำนวน")
                    if st.button("เลือกงานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    st.write("ตรวจสอบรถและวินัยจราจร")
                    if st.button("เลือกงานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            if st.session_state.current_dept == "inv": 
                investigation_module()
            else: 
                traffic_module()

if __name__ == "__main__":
    main()
