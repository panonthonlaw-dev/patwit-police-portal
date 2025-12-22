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

# --- 1. ตั้งค่าพื้นฐานและตรวจสอบไฟล์ ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# ป้องกันจอขาวจากไฟล์ฟอนต์หาย
if not os.path.exists(FONT_FILE):
    st.error(f"❌ ไม่พบไฟล์ฟอนต์: {FONT_FILE} กรุณาอัปโหลดขึ้น GitHub")
    st.stop()

# Initialize Session State
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'traffic_page' not in st.session_state: st.session_state.traffic_page = 'search'

# --- 2. ฟังก์ชันช่วย (Common Helpers) ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

# --- 3. [Module: Investigation] ระบบงานสืบสวน ---
def investigation_module():
    st.markdown("### 🕵️ ระบบบริหารงานสืบสวนและรับแจ้งเหตุ")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสืบสวนสำเร็จ")
        
        # --- ท่านสามารถวาง Logic แสดงตารางรายการแจ้งเหตุเดิมของท่านตรงนี้ ---
        st.info("ใช้สำหรับ: ตรวจสอบรายการแจ้งเหตุ / บันทึกผลสอบสวน / พิมพ์รายงาน PDF")
        st.dataframe(df.tail(10), use_container_width=True) # ตัวอย่างการโชว์ข้อมูล
        
    except Exception as e:
        st.error(f"❌ การเชื่อมต่อสืบสวนผิดพลาด: {e}")

# --- 4. [Module: Traffic] ระบบงานจราจร ---
def traffic_module():
    st.markdown("### 🚦 ระบบบริหารงานจราจร (ทะเบียนรถนักเรียน)")
    try:
        # ดึง JSON จาก Secrets และล้างตัวอักษรควบคุม
        key_content = st.secrets["textkey"]["json_content"].strip()
        key_dict = json.loads(key_content, strict=False)
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        
        # เปิด Sheet จราจร
        sheet = client.open("Motorcycle_DB").sheet1
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        # --- ท่านสามารถวาง Logic ค้นหาทะเบียน / ตัดคะแนน เดิมของท่านตรงนี้ ---
        st.info("ใช้สำหรับ: ค้นหาทะเบียนรถ / ตรวจสอบแต้มวินัย / ออกบัตรอนุญาต")
        
    except Exception as e:
        st.error(f"❌ การเชื่อมต่อจราจรผิดพลาด: {e}")

# --- 5. OFFICER PORTAL (หน้าเลือกแผนก) ---
def officer_portal():
    user = st.session_state.current_user_data
    
    # Header ส่วนเจ้าหน้าที่
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
        st.markdown("<h2 style='text-align:center;'>กรุณาเลือกหมวดหมู่การปฏิบัติงาน</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔎 เข้าสู่งานสืบสวน (จัดการเคสรับแจ้งเหตุ)", use_container_width=True):
                st.session_state.current_dept = "inv"
                st.rerun()
        with col2:
            if st.button("🚦 เข้าสู่งานจราจร (ทะเบียนรถ/ตัดคะแนน)", use_container_width=True):
                st.session_state.current_dept = "traffic"
                st.rerun()
    else:
        # ปุ่มย้อนกลับมาหน้าเลือกแผนก
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
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    tab_inv, tab_traffic = st.tabs(["📝 แจ้งเหตุด่วน (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    
    with tab_inv:
        st.info("ระบบรับแจ้งเหตุด่วนเหตุร้ายภายในโรงเรียน")
        # (ท่านสามารถวางฟอร์มรับแจ้งเหตุที่มี Placeholder ของท่านตรงนี้)

    with tab_traffic:
        st.info("ระบบตรวจสอบทะเบียนรถและวินัยจราจร")
        # (ท่านสามารถวางปุ่ม Student Portal หรือ ลงทะเบียนรถ เดิมตรงนี้)

    st.markdown("---")
    with st.expander("🔐 สำหรับเจ้าหน้าที่ (Login)"):
        pwd = st.text_input("รหัสผ่านประจำตัวเจ้าหน้าที่", type="password")
        if st.button("เข้าสู่ระบบ"):
            accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
            if pwd in accounts:
                st.session_state.logged_in = True
                st.session_state.current_user_data = accounts[pwd]
                st.rerun()
            else:
                st.error("รหัสผ่านไม่ถูกต้อง")

# --- 7. RUN APP ---
if st.session_state.logged_in:
    officer_portal()
else:
    public_landing()
