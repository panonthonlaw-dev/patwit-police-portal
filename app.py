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

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD_FILE = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# Initialize Session State
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'traffic_page' not in st.session_state: st.session_state.traffic_page = 'search'

# --- 2. COMMON HELPERS ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

def sanitize_input(text):
    if text: return str(text).replace("=", "").replace('"', "").replace("'", "").strip()
    return text

# --- 3. [MODULE: INVESTIGATION] งานสืบสวน ---
conn_inv = st.connection("gsheets", type=GSheetsConnection)

def safe_ensure_inv_cols(df):
    required = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    if df is None or df.empty: return pd.DataFrame(columns=required)
    df.columns = df.columns.str.strip()
    for col in required:
        if col not in df.columns: df[col] = ""
    return df

def investigation_department():
    st.markdown("### 🕵️ งานสืบสวนและรับแจ้งเหตุ")
    # --- ส่วนของ Logic งานสืบสวนเดิมของคุณ (เรียกดูเคส / จัดการสถานะ) ---
    try:
        df_raw = conn_inv.read(ttl="0")
        df_display = safe_ensure_inv_cols(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        # แสดงรายการเคส
        st.write("จัดการเคสรับแจ้งเหตุ...")
        # (ท่านสามารถยก Code แสดงตาราง List จากแอปสืบสวนเดิมมาวางตรงนี้ได้เลย)
    except Exception as e: st.error(f"Error Inv: {e}")

# --- 4. [MODULE: TRAFFIC] งานจราจร ---
def connect_gsheet_traffic():
    key_content = st.secrets["textkey"]["json_content"]
    key_dict = json.loads(key_content)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    return gspread.authorize(creds).open("Motorcycle_DB").sheet1

def traffic_department():
    st.markdown("### 🚦 งานจราจรและวินัยจราจร")
    # --- ส่วนของ Logic งานจราจรเดิมของคุณ (ค้นหาทะเบียน / ตัดคะแนน) ---
    st.info("ค้นหาทะเบียนประวัติรถจักรยานยนต์")
    # (ท่านสามารถยก Code ค้นหาทะเบียนจากแอปจราจรเดิมมาวางตรงนี้ได้เลย)

# --- 5. OFFICER PORTAL (หน้าเข้าสู่ระบบ & เลือกแผนก) ---
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

    # ส่วนเลือกแผนก (Department Selection)
    if st.session_state.current_dept is None:
        st.markdown("<h2 style='text-align:center;'>เลือกหมวดหมู่การปฏิบัติงาน</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔎 เข้าสู่งานสืบสวน\n(จัดการเคสรับแจ้งเหตุ)", use_container_width=True, height=200):
                st.session_state.current_dept = "inv"; st.rerun()
        with col2:
            if st.button("🚦 เข้าสู่งานจราจร\n(ทะเบียนรถ/วินัยจราจร)", use_container_width=True, height=200):
                st.session_state.current_dept = "traffic"; st.rerun()
    else:
        # ปุ่มสลับแผนก
        if st.button("🔄 สลับแผนกงาน"):
            st.session_state.current_dept = None
            st.rerun()
        
        # เข้าสู่หน้างานแต่ละแผนก
        if st.session_state.current_dept == "inv":
            investigation_department()
        elif st.session_state.current_dept == "traffic":
            traffic_department()

# --- 6. PUBLIC PAGE (สำหรับนักเรียน) ---
def public_page():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📝 แจ้งเหตุ (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    
    with tab1:
        st.info("กรุณากรอกข้อมูลตามความเป็นจริง")
        with st.form("inv_form"):
            # ฟอร์มรับแจ้งเหตุที่มี Placeholder
            st.text_input("ชื่อผู้แจ้ง")
            st.text_area("รายละเอียดเหตุการณ์ *", placeholder="ตัวอย่างการกรอก เกิดเหตุอะไร ที่ใด ใครเป็นคนกระทำความผิด(ถ้าทราบ)")
            st.form_submit_button("ส่งข้อมูล")

    with tab2:
        # ส่วนงานจราจรสำหรับนักเรียน
        st.write("โหลดบัตรอนุญาตดิจิทัล หรือ ลงทะเบียนรถ")
        if st.button("🆔 โหลดบัตรอนุญาต (Student Portal)"): pass
        if st.button("📝 ลงทะเบียนรถใหม่"): pass

    st.markdown("---")
    with st.expander("🔐 สำหรับเจ้าหน้าที่ (เข้าสู่ระบบ)"):
        pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
        if st.button("Login"):
            accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
            if pwd in accounts:
                st.session_state.logged_in = True
                st.session_state.current_user_data = accounts[pwd]
                st.rerun()
            else: st.error("รหัสผ่านไม่ถูกต้อง")

# --- 7. RUN APP ---
if st.session_state.logged_in:
    officer_portal()
else:
    public_page()
