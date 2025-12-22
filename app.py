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
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD_FILE = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# ตรวจสอบไฟล์ฟอนต์ (กันจอขาวจาก FileNotFoundError)
if not os.path.exists(FONT_FILE):
    st.error(f"❌ ไม่พบไฟล์ฟอนต์: {FONT_FILE} กรุณาอัปโหลดขึ้น GitHub")
    st.stop()

# Initialize Session State
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None

# --- 2. ฟังก์ชันช่วย ---
def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

# --- 3. [Module] งานสืบสวน (ใส่โค้ดจัดการเดิมของคุณที่นี่) ---
def investigation_department():
    st.header("🕵️ ระบบบริหารงานสืบสวน")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("เชื่อมต่อฐานข้อมูลสืบสวนสำเร็จ")
        st.dataframe(df.head()) # โชว์ข้อมูล 5 แถวแรกเพื่อทดสอบ
    except Exception as e:
        st.error(f"การเชื่อมต่อสืบสวนผิดพลาด: {e}")

# --- 4. [Module] งานจราจร (ใส่โค้ดจราจรเดิมของคุณที่นี่) ---
def traffic_department():
    st.header("🚦 ระบบบริหารงานจราจร")
    try:
        key_content = st.secrets["textkey"]["json_content"]
        key_dict = json.loads(key_content)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Motorcycle_DB").sheet1
        st.success("เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        st.write(f"จำนวนรถในระบบ: {len(sheet.get_all_values()) - 1} คัน")
    except Exception as e:
        st.error(f"การเชื่อมต่อจราจรผิดพลาด: {e}")

# --- 5. OFFICER PORTAL ---
def officer_portal():
    user = st.session_state.current_user_data
    
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
            if st.button("🔎 เข้าสู่งานสืบสวน (จัดการเคส)", use_container_width=True):
                st.session_state.current_dept = "inv"; st.rerun()
        with col2:
            if st.button("🚦 เข้าสู่งานจราจร (ทะเบียนรถ)", use_container_width=True):
                st.session_state.current_dept = "traffic"; st.rerun()
    else:
        if st.button("🔄 สลับแผนกงาน", use_container_width=True):
            st.session_state.current_dept = None; st.rerun()
        
        st.markdown("---")
        if st.session_state.current_dept == "inv": investigation_department()
        else: traffic_department()

# --- 6. LANDING PAGE ---
def public_landing():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📝 แจ้งเหตุ (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    with t1:
        st.info("ระบบรับแจ้งเหตุออนไลน์")
    with t2:
        st.info("ระบบทะเบียนรถจักรยานยนต์")

    st.markdown("---")
    with st.expander("🔐 สำหรับเจ้าหน้าที่ (Login)"):
        pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
        if st.button("Login"):
            accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
            if pwd in accounts:
                st.session_state.logged_in = True
                st.session_state.current_user_data = accounts[pwd]
                st.rerun()
            else: st.error("รหัสผ่านไม่ถูกต้อง")

# --- 7. RUN ---
if st.session_state.logged_in:
    officer_portal()
else:
    public_landing()
