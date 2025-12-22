import streamlit as st
import pandas as pd
from datetime import datetime
import pytz, random, os, base64, io, qrcode, re, time
from PIL import Image

# --- Libraries สำหรับ PDF & Visualization ---
try:
    from weasyprint import HTML, CSS
except ImportError:
    pass # ระบบจะยังทำงานได้ยกเว้นตอนพิมพ์ PDF สอบสวน

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# ป้องกัน Error: AttributeError: st.session_state has no attribute...
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "current_dept" not in st.session_state:
    st.session_state.current_dept = None
if "search_results" not in st.session_state:
    st.session_state.search_results = None

# ==========================================
# 2. SHARED HELPERS (ฟังก์ชันส่วนกลาง)
# ==========================================
def get_now_th():
    return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_img_link_drive(url):
    """แก้ไข Error ValueError: The truth value of a Series is ambiguous"""
    if pd.isna(url) or str(url).strip() == "" or str(url) == "nan":
        return "https://via.placeholder.com/150?text=No+Image"
    
    url_str = str(url)
    # ค้นหา File ID จาก Link Google Drive
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', url_str)
    if match:
        file_id = match.group(1) or match.group(2)
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800"
    return url_str

# ==========================================
# 3. INVESTIGATION MODULE (ฝ่ายสอบสวน)
# ==========================================
def investigation_module():
    st.sidebar.markdown("### 📁 เมนูสอบสวน")
    if st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", width='stretch'):
        st.session_state.current_dept = None
        st.rerun()
    
    st.title("🕵️ ระบบงานสอบสวน")
    user = st.session_state.user_info
    st.write(f"เจ้าหน้าที่ปฏิบัติการ: **{user['name']}**")
    
    # --- ใส่ Code สอบสวนเดิมของคุณที่นี่ ---
    st.info("ระบบกำลังเชื่อมต่อฐานข้อมูลสอบสวน...")
    # (Copy โค้ดส่วน Dashboard สอบสวนมาวาง)

# ==========================================
# 4. TRAFFIC MODULE (ฝ่ายจราจร)
# ==========================================
def traffic_module():
    st.sidebar.markdown("### 🚦 เมนูจราจร")
    if st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", width='stretch'):
        st.session_state.current_dept = None
        st.rerun()
        
    st.title("🏍️ ระบบงานจราจร")
    
    # ตัวอย่างการดึงข้อมูลแบบปลอดภัย
    try:
        # เชื่อมต่อ GSheet (ใช้ความลับจาก secrets[textkey])
        # ... (โค้ดดึงข้อมูลจราจรเดิม) ...
        st.success("เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลได้: {e}")

# ==========================================
# 5. MAIN GATEWAY (หน้า Login & เลือกแผนก)
# ==========================================
def main():
    # ตรวจสอบว่าล็อกอินหรือยัง
    if not st.session_state.logged_in:
        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            with st.container(border=True):
                st.header("🔐 เจ้าหน้าที่เข้าสู่ระบบ")
                pwd = st.text_input("รหัสผ่านประจำตัว", type="password")
                if st.button("Login", width='stretch', type='primary'):
                    accounts = st.secrets.get("officer_accounts", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else:
                        st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # ส่วนหน้าจัดการหลัง Login
        st.sidebar.title(f"👤 {st.session_state.user_info['name']}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        # กรณีล็อกอินแล้วแต่ยังไม่ได้เลือกแผนก
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            st.write("ยินดีต้อนรับสู่ระบบบริหารจัดการส่วนกลาง")
            
            c1, c2 = st.columns(2)
            # แก้ไข Error: ลบ height=100 และใช้ width='stretch'
            if c1.button("🕵️ เข้าใช้งานงานสอบสวน", width='stretch'):
                st.session_state.current_dept = "investigation"
                st.rerun()
            
            if c2.button("🚦 เข้าใช้งานงานจราจร", width='stretch'):
                st.session_state.current_dept = "traffic"
                st.rerun()
        else:
            # เข้าสู่แผนกที่เลือก
            if st.session_state.current_dept == "investigation":
                investigation_module()
            else:
                traffic_module()

if __name__ == "__main__":
    main()
