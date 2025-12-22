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

# --- 1. CONFIG & SESSION SETUP ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD_FILE = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# Initialize Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list" # สำหรับงานสอบสวน
if 'traffic_page' not in st.session_state: st.session_state.traffic_page = 'teacher_main' # สำหรับงานจราจร
if 'search_results_df' not in st.session_state: st.session_state.search_results_df = None
if 'edit_data' not in st.session_state: st.session_state.edit_data = None

# --- 2. COMMON HELPERS ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

def get_img_link_drive(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

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
    st.subheader("🕵️ ระบบบริหารงานสืบสวนและรับแจ้งเหตุ")
    user = st.session_state.current_user_data
    
    try:
        df_raw = conn_inv.read(ttl="0")
        df_display = safe_ensure_inv_cols(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการเคส", "📊 สถิติ"])
            with tab_list:
                st.write("รายการเคสทั้งหมด...")
                st.dataframe(df_display[['Report_ID', 'Timestamp', 'Incident_Type', 'Status']], use_container_width=True)
            with tab_dash:
                st.write("สรุปยอดสถิติ...")
                # (Logic สถิติเดิม)
    except Exception as e: st.error(f"Error Inv: {e}")

# --- 4. [MODULE: TRAFFIC] งานจราจร (แก้ไข Error Header row) ---
def connect_gsheet_traffic():
    # ใช้รูปแบบใหม่ตามที่แนะนำ
    creds_dict = dict(st.secrets["traffic_creds"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Motorcycle_DB").sheet1

def load_traffic_data():
    try:
        sheet = connect_gsheet_traffic()
        vals = sheet.get_all_values() # ใช้ get_all_values แทนเพื่อเลี่ยงปัญหา Header ซ้ำ
        if len(vals) > 1:
            # กำหนดชื่อคอลัมน์เองเพื่อความปลอดภัย
            st.session_state.traffic_df = pd.DataFrame(vals[1:], columns=[f"C{i}" for i in range(len(vals[0]))])
            return True
    except Exception as e:
        st.error(f"โหลดข้อมูลจราจรไม่สำเร็จ: {e}")
    return False

def traffic_department():
    st.subheader("🚦 ระบบบริหารงานจราจรและวินัยนักเรียน")
    user = st.session_state.current_user_data
    
    if 'traffic_df' not in st.session_state: load_traffic_data()
    
    # 📊 Dashboard Cards (สถิติด้านบน)
    if 'traffic_df' in st.session_state:
        df = st.session_state.traffic_df
        total = len(df)
        # คำนวณ % ปัญหา (อิงจาก Index คอลัมน์เดิมในระบบจราจร)
        try:
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("รถทั้งหมด", f"{total} คัน")
            with m2: 
                lok = df[df.iloc[:,7].str.contains("มี", na=False)].shape[0]
                st.metric("มีใบขับขี่", f"{lok} คัน", f"{(lok/total*100):.1f}%")
            with m3:
                tok = df[df.iloc[:,8].str.contains("ปกติ|✅", na=False)].shape[0]
                st.metric("ภาษีปกติ", f"{tok} คัน", f"{(tok/total*100):.1f}%")
            with m4:
                hok = df[df.iloc[:,9].str.contains("มี", na=False)].shape[0]
                st.metric("สวมหมวก", f"{hok} คัน", f"{(hok/total*100):.1f}%")
        except: pass

    st.markdown("---")
    
    # 🔍 Search & Filters
    col_q, col_btn = st.columns([4, 1])
    query = col_q.text_input("🔍 ค้นหา (ชื่อ / รหัส / ทะเบียนรถ)", placeholder="พิมพ์ข้อมูลที่ต้องการหาที่นี่...")
    
    if col_btn.button("ค้นหา", use_container_width=True, type="primary") or query:
        df = st.session_state.traffic_df
        # กรองข้อมูล (Column 1=ชื่อ, 2=รหัส, 6=ทะเบียน)
        res = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(query, case=False).any(), axis=1)]
        st.session_state.search_results_df = res

    # แสดงผลการค้นหาแบบ Expander (เหมือนแอปจราจรเดิม)
    if st.session_state.search_results_df is not None:
        for i, row in st.session_state.search_results_df.iterrows():
            v = row.tolist()
            with st.expander(f"🏍️ {v[6]} | {v[1]} (แต้ม: {v[13]})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(get_img_link_drive(v[14]), caption="เจ้าของรถ", use_container_width=True)
                with c2:
                    st.write(f"**ชื่อ-นามสกุล:** {v[1]} | **ชั้น:** {v[3]}")
                    st.write(f"**ยี่ห้อ:** {v[4]} | **สี:** {v[5]}")
                    st.progress(int(v[13])/100, text=f"แต้มวินัยจราจร: {v[13]}")
                    # (เพิ่มปุ่มตัดแต้ม/แก้ไข ต่อจากนี้ได้เลย)

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
            if st.button("🔎 เข้าสู่ระบบงานสืบสวน (จัดการเคสรับแจ้งเหตุ)", use_container_width=True):
                st.session_state.current_dept = "inv"; st.rerun()
        with col2:
            if st.button("🚦 เข้าสู่ระบบงานจราจร (ทะเบียนรถนักเรียน)", use_container_width=True):
                st.session_state.current_dept = "traffic"; st.rerun()
    else:
        c_back, c_empty = st.columns([1, 4])
        if c_back.button("🔄 สลับแผนก", use_container_width=True):
            st.session_state.current_dept = None; st.rerun()
        
        st.markdown("---")
        if st.session_state.current_dept == "inv": investigation_department()
        else: traffic_department()

# --- 6. PUBLIC PAGE (LANDING) ---
def public_page():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ ศูนย์ปฏิบัติการสถานีตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📝 แจ้งเหตุ (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    
    with tab1:
        st.info("ใช้สำหรับแจ้งเหตุพฤติกรรมไม่เหมาะสม หรือเหตุด่วนภายในโรงเรียน")
        with st.form("student_inv_form"):
            name = st.text_input("ชื่อผู้แจ้ง (ระบุหรือไม่ก็ได้)")
            loc = st.selectbox("สถานที่เกิดเหตุ", ["โรงอาหาร", "อาคาร 1", "สนามบาส", "อื่นๆ"])
            det = st.text_area("รายละเอียดเหตุการณ์ *", placeholder="ตัวอย่างการกรอก เกิดเหตุอะไร ที่ใด ใครเป็นคนกระทำความผิด(ถ้าทราบ)")
            if st.form_submit_button("ส่งข้อมูลแจ้งเหตุ", use_container_width=True):
                st.success("ส่งข้อมูลสำเร็จ!")

    with tab2:
        st.info("ลงทะเบียนนำรถจักรยานยนต์เข้าโรงเรียน หรือ ตรวจสอบบัตรอนุญาตดิจิทัล")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📝 ลงทะเบียนรถใหม่", use_container_width=True): pass
        with c2:
            if st.button("🆔 โหลดบัตรอนุญาต (Student Portal)", use_container_width=True): pass

    st.markdown("---")
    with st.expander("🔐 สำหรับเจ้าหน้าที่ (Officer Login)"):
        pwd = st.text_input("รหัสผ่านประจำตัว", type="password")
        if st.button("เข้าสู่ระบบ"):
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
    public_page()
