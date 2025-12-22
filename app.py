import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, json, requests, re, textwrap, time
from PIL import Image

# PDF Libraries
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

# ป้องกัน Error: Initialize Session State
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None
if "view_mode" not in st.session_state: st.session_state.view_mode = "list"
if "selected_case_id" not in st.session_state: st.session_state.selected_case_id = None
if "page_pending" not in st.session_state: st.session_state.page_pending = 1
if "page_finished" not in st.session_state: st.session_state.page_finished = 1

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
# 3. INVESTIGATION MODULE (งานสอบสวน)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", width='stretch', on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบบริหารจัดการงานสอบสวน")
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # ดึงโค้ด Logic สอบสวนเดิมของคุณมาใส่ที่นี่
    try:
        df_raw = conn.read(ttl="0")
        st.success("เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df_raw.head(), width='stretch')
        # ... (ใส่ส่วนแสดงรายการเคสเดิมของคุณ) ...
    except Exception as e:
        st.error(f"ไม่สามารถโหลดข้อมูลสอบสวนได้: {e}")

# ==========================================
# 4. TRAFFIC MODULE (งานจราจร)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", width='stretch', on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบบริหารจัดการงานจราจร")
    
    def connect_traffic():
        key_content = st.secrets["textkey"]["json_content"]
        key_dict = json.loads(key_content.replace('\n', '\\n'), strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_traffic()
        st.success("เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        # ... (ใส่ส่วนค้นหาทะเบียน/ตัดคะแนนเดิมของคุณ) ...
    except Exception as e:
        st.error(f"ไม่สามารถโหลดข้อมูลจราจรได้: {e}")

# ==========================================
# 5. MAIN GATEWAY (หน้า LOGIN & PORTAL)
# ==========================================
def main():
    if not st.session_state.logged_in:
        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            with st.container(border=True):
                st.header("🔐 Central Login")
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("officer_accounts", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.current_user = accounts[pwd]
                        st.rerun()
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # Sidebar หลัง Login
        user_info = st.session_state.current_user
        name = user_info['name'] if isinstance(user_info, dict) else str(user_info)
        st.sidebar.write(f"👤 **{name}**")
        
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            st.write("กรุณาเลือกฝ่ายที่ต้องการเข้าปฏิบัติงาน")
            
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch'):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch'):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
