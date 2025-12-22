import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, time, json, requests, re, textwrap
from PIL import Image

# --- Libraries สำหรับระบบสอบสวน (WeasyPrint) ---
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# --- Libraries สำหรับระบบจราจร (GSpread, Plotly, ReportLab) ---
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
# 1. INITIAL SETTINGS & SHARED HELPERS
# ==========================================
st.set_page_config(page_title="ระบบบริหารจัดการสถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# ค้นหาไฟล์ฟอนต์และโลโก้
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

# ==========================================
# 2. ฟังก์ชันระบบสอบสวน (INVESTIGATION)
# ==========================================
def investigation_module():
    # --- ดึงรหัสผ่านที่ Login มาใช้ในโมดูล ---
    user = st.session_state.current_user
    
    st.sidebar.title("📁 เมนูสอบสวน")
    if st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", use_container_width=True):
        st.session_state.app_mode = "portal"
        st.rerun()
    
    st.markdown(f"### 🏢 ระบบสอบสวน (เจ้าหน้าที่: {user['name']})")
    
    # [ที่นี่คือจุดที่คุณ Copy โค้ดส่วน 'officer_dashboard' ของเดิมมาวาง]
    # ตัวอย่างย่อ:
    st.info("กำลังดึงข้อมูลจาก Google Sheets สอบสวน...")
    # ... (โค้ดสอบสวนเดิมทั้งหมด) ...

# ==========================================
# 3. ฟังก์ชันระบบจราจร (TRAFFIC)
# ==========================================
def traffic_module():
    # --- ดึงรหัสผ่านที่ Login มาใช้ในโมดูล ---
    user = st.session_state.current_user
    
    st.sidebar.title("🏍️ เมนูจราจร")
    if st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", use_container_width=True):
        st.session_state.app_mode = "portal"
        st.rerun()

    st.markdown(f"### 🏍️ ระบบจราจร (เจ้าหน้าที่: {user['name']})")
    
    # [ที่นี่คือจุดที่คุณ Copy โค้ดส่วน 'teacher' page ของเดิมมาวาง]
    # ตัวอย่างย่อ:
    st.info("กำลังดึงข้อมูลจาก Google Sheets จราจร...")
    # ... (โค้ดจราจรเดิมทั้งหมด) ...

# ==========================================
# 4. หน้าหลัก และระบบ LOGIN ส่วนกลาง
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'app_mode' not in st.session_state: st.session_state.app_mode = "login"

# --- [A] หน้า LOGIN ---
if st.session_state.app_mode == "login":
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center;'>ศูนย์รวมระบบงานสถานีตำรวจนักเรียน</p>", unsafe_allow_html=True)
            
            pwd_input = st.text_input("กรุณาใส่รหัสผ่านเจ้าหน้าที่", type="password")
            if st.button("เข้าสู่ระบบ", use_container_width=True, type="primary"):
                accounts = st.secrets.get("officer_accounts", {})
                if pwd_input in accounts:
                    st.session_state.logged_in = True
                    st.session_state.current_user = accounts[pwd_input]
                    st.session_state.current_user_pwd = pwd_input
                    st.session_state.app_mode = "portal"
                    st.rerun()
                else:
                    st.error("❌ รหัสผ่านไม่ถูกต้อง")
            
            st.divider()
            st.caption("หมายเหตุ: สำหรับนักเรียนที่ต้องการแจ้งเหตุหรือดูบัตรจราจร โปรดใช้แอปแยกตามลิงก์เดิม")

# --- [B] หน้าเลือกแผนก (PORTAL) ---
elif st.session_state.app_mode == "portal":
    st.markdown(f"<h2 style='text-align:center;'>สวัสดีคุณ {st.session_state.current_user['name']}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>กรุณาเลือกฝ่ายที่ต้องการดำเนินการ</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### 📁 ฝ่ายสอบสวน")
            st.write("จัดการเคสแจ้งเหตุ, สอบปากคำ และออกใบสรุปรายงาน PDF")
            if st.button("เข้าใช้งานระบบสอบสวน", use_container_width=True, type="primary"):
                st.session_state.app_mode = "investigation"
                st.rerun()
                
    with col2:
        with st.container(border=True):
            st.markdown("### 🏍️ ฝ่ายจราจร")
            st.write("ตรวจสอบทะเบียนรถ, ตัด/เพิ่มคะแนนวินัย และจัดการข้อมูลรถ")
            if st.button("เข้าใช้งานระบบจราจร", use_container_width=True, type="primary"):
                st.session_state.app_mode = "traffic"
                st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔴 ออกจากระบบ (Logout)", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- [C] เรียกใช้ Module ตามโหมด ---
elif st.session_state.app_mode == "investigation":
    investigation_module()

elif st.session_state.app_mode == "traffic":
    traffic_module()
