import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz
import random
import os
import base64
import io
import qrcode
import glob
import math
import time
import re
import json
import textwrap
import requests
import plotly.express as px

# PDF Libraries
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image

# --- 1. ตั้งค่าพื้นฐานและตรวจสอบไฟล์ ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD_FILE = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

if not os.path.exists(FONT_FILE):
    st.error("❌ ไม่พบไฟล์ฟอนต์บน GitHub")
    st.stop()

# Initialize Session State
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None # แผนก (inv / traffic)
if 'page' not in st.session_state: st.session_state.page = 'main' # หน้าภายในแผนกจราจร
if 'search_results_df' not in st.session_state: st.session_state.search_results_df = None

# --- 2. ฟังก์ชันช่วยส่วนกลาง ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

def get_img_link_drive(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

# --- 3. [MODULE: INVESTIGATION] งานสืบสวน (WeasyPrint) ---
def investigation_module():
    st.markdown("## 🕵️ ระบบบริหารงานสืบสวนและรับแจ้งเหตุ")
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        df = conn.read(ttl="0")
        # --- วาง Logic แสดงตารางรายการแจ้งเหตุเดิมของท่านตรงนี้ ---
        st.success("เชื่อมต่อฐานข้อมูลสืบสวนสำเร็จ")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error Inv: {e}")

# --- 4. [MODULE: TRAFFIC] งานจราจร (ReportLab + gspread) ---
def traffic_module():
    st.markdown("## 🚦 ระบบบริหารงานจราจรและวินัยจราจร")
    
    def connect_traffic():
        creds_dict = dict(st.secrets["traffic_creds"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_traffic()
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        # --- วาง Logic ค้นหาทะเบียน/ตัดคะแนน เดิมของท่านตรงนี้ ---
        q = st.text_input("🔍 ค้นหาทะเบียนรถ/ชื่อนักเรียน")
        if q:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            res = df[df.apply(lambda row: row.astype(str).str.contains(q).any(), axis=1)]
            st.write(res)
            
    except Exception as e:
        st.error(f"Error Traffic: {e}")

# --- 5. OFFICER PORTAL (หน้าเลือกแผนก) ---
def officer_portal():
    user = st.session_state.current_user_data
    
    # Header
    h1, h2, h3 = st.columns([1, 5, 1])
    with h1: 
        if LOGO_PATH: st.image(LOGO_PATH, width=80)
    with h2:
        st.markdown(f"#### 🏢 ศูนย์ปฏิบัติการตำรวจโรงเรียนโพนทองพัฒนาวิทยา\n**เจ้าหน้าที่:** {user['name']} | **บทบาท:** {user['role']}")
    with h3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_dept = None
            st.rerun()

    st.markdown("---")

    if st.session_state.current_dept is None:
        st.markdown("<h2 style='text-align:center;'>กรุณาเลือกหมวดหมู่การปฏิบัติงาน</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔎 งานสืบสวน (จัดการเคสรับแจ้งเหตุ)", use_container_width=True):
                st.session_state.current_dept = "inv"; st.rerun()
        with col2:
            if st.button("🚦 งานจราจร (ทะเบียนรถ/วินัยจราจร)", use_container_width=True):
                st.session_state.current_dept = "traffic"; st.rerun()
    else:
        if st.button("🔄 สลับแผนกงาน", use_container_width=True):
            st.session_state.current_dept = None
            st.rerun()
        
        st.markdown("---")
        if st.session_state.current_dept == "inv":
            investigation_module()
        elif st.session_state.current_dept == "traffic":
            traffic_module()

# --- 6. PUBLIC LANDING (หน้าแรกสำหรับนักเรียน) ---
def public_landing():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ ศูนย์ปฏิบัติการสถานีตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📝 แจ้งเหตุใหม่ (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    
    with tab1:
        st.info("ใช้สำหรับแจ้งเหตุด่วน เหตุร้าย หรือพฤติกรรมไม่เหมาะสม")
        with st.form("inv_student_form"):
            st.text_input("ชื่อผู้แจ้ง")
            st.text_area("รายละเอียดเหตุการณ์", placeholder="ตัวอย่างการกรอก เกิดเหตุอะไร ที่ใด ใครเป็นคนกระทำความผิด(ถ้าทราบ)")
            st.form_submit_button("ส่งข้อมูล")

    with tab2:
        st.info("ลงทะเบียนนำรถเข้าโรงเรียน หรือ ตรวจสอบบัตรอนุญาตดิจิทัล")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📝 ลงทะเบียนรถใหม่", use_container_width=True): pass
        with c2:
            if st.button("🆔 โหลดบัตรอนุญาต (Student Portal)", use_container_width=True): pass

    st.markdown("---")
    with st.expander("🔐 ส่วนเจ้าหน้าที่ (Officer Login)"):
        pwd = st.text_input("รหัสผ่านประจำตัว", type="password")
        if st.button("เข้าสู่ระบบ"):
            accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
            if pwd in accounts:
                st.session_state.logged_in = True
                st.session_state.current_user_data = accounts[pwd]
                st.rerun()
            else:
                st.error("รหัสผ่านไม่ถูกต้อง")

# --- 7. RUN ---
if st.session_state.logged_in:
    officer_portal()
else:
    public_landing()
