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

# --- PDF Libraries ---
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image

# --- 1. ตั้งค่าพื้นฐานและ Session ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD_FILE = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# ตัวแปรระบบ
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'traffic_page' not in st.session_state: st.session_state.traffic_page = 'search'

# --- 2. ฟังก์ชันช่วย (Helpers) ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def sanitize_input(text):
    if text: return str(text).replace("=", "").replace('"', "").replace("'", "").strip()
    return text

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

# ฟังก์ชันย่อรูปภาพ (กัน Error 50,000 chars)
def process_image_inv(img_file):
    if img_file is None: return ""
    try:
        img = Image.open(img_file)
        if img.mode in ('RGBA', 'LA', 'P'): img = img.convert('RGB')
        max_size, quality = 800, 65
        while True:
            img_copy = img.copy(); img_copy.thumbnail((max_size, max_size))
            buf = io.BytesIO(); img_copy.save(buf, format="JPEG", quality=quality, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            if len(b64) < 49000 or max_size < 200: return b64
            max_size = int(max_size * 0.7); quality -= 5
    except: return ""

# --- 3. [Module: Investigation] งานสืบสวน ---
conn_inv = st.connection("gsheets", type=GSheetsConnection)

def safe_ensure_inv_cols(df):
    cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    if df is None or df.empty: return pd.DataFrame(columns=cols)
    df.columns = df.columns.str.strip()
    for c in cols:
        if c not in df.columns: df[c] = ""
    return df

def investigation_department():
    st.subheader("🕵️ ระบบบริหารงานสืบสวนและรับแจ้งเหตุ")
    user = st.session_state.current_user_data
    try:
        df_raw = conn_inv.read(ttl="0")
        df_display = safe_ensure_inv_cols(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_l, tab_s = st.tabs(["📋 รายการเคส", "📊 สถิติ"])
            with tab_l:
                # ส่วนแสดงรายการเคสสืบสวน (ยกมาจากโค้ดเก่า)
                st.write("รายการรับแจ้งเหตุ...")
                # (แทรก Logic แสดงตาราง p_index เดิมตรงนี้)
            with tab_s:
                # แดชบอร์ดสถิติที่มี % สีแดง
                st.write("สรุปสถิติงานสืบสวน...")
    except Exception as e: st.error(f"Error Investigation: {e}")

# --- 4. [Module: Traffic] งานจราจร ---
def connect_traffic_sheet():
    key_dict = json.loads(st.secrets["textkey"]["json_content"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open("Motorcycle_DB").sheet1

def traffic_department():
    st.subheader("🚦 ระบบบริหารงานจราจร")
    # ส่วนค้นหาทะเบียนรถและตัดคะแนน (ยกมาจากโค้ดจราจรเดิม)
    st.info("ค้นหาทะเบียนรถ / ปรับแต้มวินัยจราจร")
    # (แทรก Logic งานจราจรเดิมทั้งหมดตรงนี้)

# --- 5. [Portal] หน้าเจ้าหน้าที่ (Department Selector) ---
def officer_portal():
    user = st.session_state.current_user_data
    h1, h2, h3 = st.columns([1, 5, 1])
    with h1: 
        if LOGO_PATH: st.image(LOGO_PATH, width=80)
    with h2:
        st.markdown(f"#### 🏢 ศูนย์ปฏิบัติการตำรวจโรงเรียนโพนทองพัฒนาวิทยา\n**เจ้าหน้าที่:** {user['name']} | **บทบาท:** {user['role']}")
    with h3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False; st.session_state.current_dept = None; st.rerun()

    st.markdown("---")
    if st.session_state.current_dept is None:
        st.markdown("<h3 style='text-align:center;'>กรุณาเลือกหมวดหมู่การปฏิบัติงาน</h3>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("🕵️ งานสืบสวน / แจ้งเหตุ", use_container_width=True, height=150):
            st.session_state.current_dept = "inv"; st.rerun()
        if c2.button("🚦 งานจราจร / ทะเบียนรถ", use_container_width=True, height=150):
            st.session_state.current_dept = "traffic"; st.rerun()
    else:
        if st.button("🔄 สลับแผนก"): st.session_state.current_dept = None; st.rerun()
        if st.session_state.current_dept == "inv": investigation_department()
        else: traffic_department()

# --- 6. หน้าหลักนักเรียน (Public Page) ---
def public_page():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📝 แจ้งเหตุด่วน (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    
    with t1:
        # ฟอร์มแจ้งเหตุงานสืบสวน
        with st.form("inv_form"):
            st.write("แบบแจ้งเหตุการณ์ไม่พึงประสงค์")
            rep = st.text_input("ชื่อผู้แจ้ง")
            loc = st.text_input("สถานที่")
            det = st.text_area("รายละเอียด *", placeholder="ตัวอย่างการกรอก เกิดเหตุอะไร ที่ใด ใครเป็นคนกระทำความผิด(ถ้าทราบ)")
            if st.form_submit_button("ส่งข้อมูลแจ้งเหตุ"):
                st.success("บันทึกข้อมูลแล้ว (ตัวอย่าง)")

    with t2:
        # ส่วนงานจราจรสำหรับนักเรียน
        st.write("ลงทะเบียนรถและโหลดบัตรอนุญาต")
        if st.button("🆔 โหลดบัตรอนุญาต (Student Portal)"): pass
        if st.button("📝 ลงทะเบียนรถใหม่"): pass

    st.markdown("---")
    with st.expander("🔐 สำหรับเจ้าหน้าที่ (Login)"):
        pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
        if st.button("เข้าสู่ระบบ"):
            accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
            if pwd in accounts:
                st.session_state.logged_in = True
                st.session_state.current_user_data = accounts[pwd]
                st.rerun()
            else: st.error("รหัสผ่านไม่ถูกต้อง")

# --- 7. รันระบบ ---
if st.session_state.logged_in:
    officer_portal()
else:
    public_page()
