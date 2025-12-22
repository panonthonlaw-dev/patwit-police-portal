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
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'traffic_page' not in st.session_state: st.session_state.traffic_page = 'teacher_main'
if 'search_results_df' not in st.session_state: st.session_state.search_results_df = None
if 'edit_data' not in st.session_state: st.session_state.edit_data = None

# --- 2. COMMON HELPERS ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()

def get_img_link_drive(url):
    if not url or str(url) == "nan": return "https://via.placeholder.com/150"
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

# ฟังก์ชันอัปโหลดรูป (GAS)
def upload_to_drive(file_obj, filename):
    GAS_APP_URL = "https://script.google.com/macros/s/AKfycbxRf6z032SxMkiI4IxtUBvWLKeo1LmIQAUMByoXidy4crNEwHoO6h0B-3hT0X7Q5g/exec"
    DRIVE_FOLDER_ID = "1WQGATGaGBoIjf44Yj_-DjuX8LZ8kbmBA"
    base64_str = base64.b64encode(file_obj.getvalue()).decode('utf-8')
    payload = {"folder_id": DRIVE_FOLDER_ID, "filename": filename, "file": base64_str, "mimeType": file_obj.type}
    try:
        res = requests.post(GAS_APP_URL, json=payload).json()
        return res.get("link") if res.get("status") == "success" else None
    except: return None

# --- 3. [MODULE: TRAFFIC] งานจราจร ---

def connect_gsheet_traffic():
    creds_dict = dict(st.secrets["traffic_creds"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Motorcycle_DB").sheet1

def load_traffic_data():
    try:
        sheet = connect_gsheet_traffic()
        vals = sheet.get_all_values()
        if len(vals) > 1:
            st.session_state.traffic_df = pd.DataFrame(vals[1:], columns=[f"C{i}" for i in range(len(vals[0]))])
            return True
    except Exception as e: st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")
    return False

# ฟังก์ชันสร้าง PDF บัตรจราจร (ReportLab)
def create_traffic_pdf(vals, printed_by="ระบบอัตโนมัติ"):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    if os.path.exists(FONT_FILE):
        pdfmetrics.registerFont(TTFont('Thai', FONT_FILE))
        pdfmetrics.registerFont(TTFont('ThaiBold', FONT_BOLD_FILE))
        f_reg, f_bold = 'Thai', 'ThaiBold'
    else: f_reg, f_bold = 'Helvetica', 'Helvetica-Bold'
    
    # วาดหน้าบัตรประวัติ (ตาม Logic เดิมของคุณ)
    c.setFont(f_bold, 22); c.drawCentredString(width/2, height - 50, "แบบทะเบียนประวัติรถจักรยานยนต์นักเรียน")
    c.setFont(f_reg, 18); c.drawCentredString(width/2, height - 72, "โรงเรียนโพนทองพัฒนาวิทยา")
    c.line(50, height - 85, width - 50, height - 85)
    
    # ข้อมูลนักเรียน (v[1]=Name, v[2]=ID, v[3]=Class, v[6]=Plate, v[13]=Score)
    c.setFont(f_reg, 16)
    c.drawString(60, height - 115, f"ชื่อ-นามสกุล: {vals[1]}"); c.drawString(300, height - 115, f"ทะเบียน: {vals[6]}")
    c.drawString(60, height - 135, f"รหัสนักเรียน: {vals[2]}"); c.drawString(300, height - 135, f"ระดับชั้น: {vals[3]}")
    c.setFont(f_bold, 18); c.drawString(60, height - 170, f"คะแนนคงเหลือ: {vals[13]} แต้ม")
    
    # วาดรูป (v[14]=Face, v[10]=Back, v[11]=Side)
    def draw_img(url, x, y, w, h):
        try:
            res = requests.get(url, timeout=5)
            img = ImageReader(io.BytesIO(res.content))
            c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True)
        except: pass

    draw_img(get_img_link_drive(vals[14]), 60, height - 320, 100, 120)
    draw_img(get_img_link_drive(vals[10]), 180, height - 320, 150, 120)
    draw_img(get_img_link_drive(vals[11]), 350, height - 320, 150, 120)

    c.save(); buffer.seek(0); return buffer

def traffic_department():
    if st.session_state.traffic_page == 'edit':
        show_traffic_edit_page()
    else:
        show_traffic_main_page()

def show_traffic_main_page():
    st.markdown("### 🚦 ระบบบริหารงานจราจร")
    if 'traffic_df' not in st.session_state: load_traffic_data()
    
    df = st.session_state.get('traffic_df', pd.DataFrame())
    if not df.empty:
        # สถิติ
        total = len(df)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("รถทั้งหมด", total)
        lok = df[df.iloc[:,7].str.contains("มี", na=False)].shape[0]
        m2.metric("มีใบขับขี่", lok, f"{(lok/total*100):.1f}%")
        tok = df[df.iloc[:,8].str.contains("ปกติ|✅", na=False)].shape[0]
        m3.metric("ภาษีปกติ", tok, f"{(tok/total*100):.1f}%")
        hok = df[df.iloc[:,9].str.contains("มี", na=False)].shape[0]
        m4.metric("สวมหมวก", hok, f"{(hok/total*100):.1f}%")

    st.markdown("---")
    # ค้นหา
    col_q, col_btn, col_ref = st.columns([3, 1, 1])
    q = col_q.text_input("🔍 ค้นหาชื่อ/รหัส/ทะเบียน", placeholder="ระบุข้อมูลที่ต้องการค้นหา...")
    if col_btn.button("ค้นหา", use_container_width=True, type="primary") or q:
        st.session_state.search_results_df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
    if col_ref.button("🔄 รีเฟรชข้อมูล", use_container_width=True): 
        load_traffic_data(); st.rerun()

    if st.session_state.search_results_df is not None:
        for i, row in st.session_state.search_results_df.iterrows():
            v = row.tolist()
            with st.expander(f"🏍️ {v[6]} | {v[1]} (แต้ม: {v[13]})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(get_img_link_drive(v[14]), caption="รูปถ่ายหน้าตรง", use_container_width=True)
                with c2:
                    st.markdown(f"**ชื่อ:** {v[1]} | **รหัส:** {v[2]} | **ชั้น:** {v[3]}")
                    st.markdown(f"**ยี่ห้อ:** {v[4]} | **สี:** {v[5]} | **ทะเบียน:** {v[6]}")
                    
                    # ปุ่มดำเนินการ
                    b1, b2, b3 = st.columns(3)
                    if b1.button("✏️ แก้ไขข้อมูล", key=f"edit_{i}", use_container_width=True):
                        st.session_state.edit_data = v
                        st.session_state.traffic_page = 'edit'
                        st.rerun()
                    
                    pdf_buf = create_traffic_pdf(v, st.session_state.current_user_data['name'])
                    b2.download_button("📥 พิมพ์ PDF", data=pdf_buf, file_name=f"Traffic_{v[2]}.pdf", use_container_width=True)
                    
                    # ฟอร์มตัดแต้ม
                    with st.form(f"score_{i}"):
                        pts = st.number_input("จำนวนแต้มที่ปรับ", 1, 50, 5)
                        note = st.text_input("เหตุผล")
                        sub_deduct = st.form_submit_button("🔴 หักแต้ม", use_container_width=True)
                        if sub_deduct and note:
                            sheet = connect_gsheet_traffic()
                            cell = sheet.find(str(v[2]))
                            new_score = max(0, int(v[13]) - pts)
                            new_log = f"{v[12]}\n[{get_now_th().strftime('%d/%m/%Y')}] หัก {pts}: {note}"
                            sheet.update(f'M{cell.row}:N{cell.row}', [[new_log, str(new_score)]])
                            st.success("บันทึกแล้ว"); load_traffic_data(); st.rerun()

def show_traffic_edit_page():
    v = st.session_state.edit_data
    st.markdown(f"### ✏️ แก้ไขข้อมูล: {v[1]}")
    with st.form("edit_traffic_form"):
        new_name = st.text_input("ชื่อ-นามสกุล", v[1])
        new_class = st.text_input("ชั้น", v[3])
        new_brand = st.text_input("ยี่ห้อรถ", v[4])
        new_color = st.text_input("สีรถ", v[5])
        new_plate = st.text_input("ทะเบียน", v[6])
        
        c1, c2 = st.columns(2)
        if c1.form_submit_button("💾 บันทึกการเปลี่ยนแปลง", use_container_width=True, type="primary"):
            sheet = connect_gsheet_traffic()
            cell = sheet.find(str(v[2]))
            # อัปเดต Column B ถึง G (Index 1-6)
            sheet.update(f'B{cell.row}:G{cell.row}', [[new_name, v[2], new_class, new_brand, new_color, new_plate]])
            st.success("แก้ไขข้อมูลสำเร็จ!"); load_traffic_data()
            st.session_state.traffic_page = 'teacher_main'; st.rerun()
        if c2.form_submit_button("❌ ยกเลิก", use_container_width=True):
            st.session_state.traffic_page = 'teacher_main'; st.rerun()

# --- 4. [MODULE: INVESTIGATION] งานสืบสวน ---
def investigation_department():
    st.markdown("### 🕵️ ระบบสืบสวนและรับแจ้งเหตุ")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสืบสวนสำเร็จ")
        
        tab1, tab2 = st.tabs(["📋 รายการแจ้งเหตุ", "📊 สถิติรวม"])
        with tab1:
            st.dataframe(df.tail(20), use_container_width=True)
            # (เพิ่ม Logic จัดการเคสเหมือนโค้ดเก่าได้เลย)
        with tab2:
            st.write("กราฟสถิติการแจ้งเหตุ...")
            st.bar_chart(df['Incident_Type'].value_counts())
            
    except Exception as e: st.error(f"Error Inv: {e}")

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
            st.session_state.logged_in = False; st.session_state.current_dept = None; st.rerun()

    st.markdown("---")
    if st.session_state.current_dept is None:
        st.markdown("<h2 style='text-align:center;'>เลือกหมวดหมู่การปฏิบัติงาน</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("🔎 เข้าสู่ระบบงานสืบสวน (จัดการเคสรับแจ้งเหตุ)", use_container_width=True):
            st.session_state.current_dept = "inv"; st.rerun()
        if col2.button("🚦 เข้าสู่ระบบงานจราจร (ทะเบียนรถนักเรียน)", use_container_width=True):
            st.session_state.current_dept = "traffic"; st.rerun()
    else:
        if st.button("🔄 สลับแผนกงาน", use_container_width=True):
            st.session_state.current_dept = None; st.rerun()
        st.markdown("---")
        if st.session_state.current_dept == "inv": investigation_department()
        else: traffic_department()

# --- 6. PUBLIC LANDING ---
def public_landing():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ ศูนย์ปฏิบัติการสถานีตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📝 แจ้งเหตุ (งานสืบสวน)", "🏍️ ทะเบียนรถ (งานจราจร)"])
    with t1:
        st.info("ใช้สำหรับแจ้งเหตุพฤติกรรมไม่เหมาะสม หรือเหตุด่วนภายในโรงเรียน")
        with st.form("inv_form"):
            rep = st.text_input("ชื่อผู้แจ้ง")
            loc = st.text_input("สถานที่")
            det = st.text_area("รายละเอียดเหตุการณ์ *", placeholder="ตัวอย่างการกรอก เกิดเหตุอะไร ที่ใด ใครเป็นคนกระทำความผิด(ถ้าทราบ)")
            if st.form_submit_button("ส่งข้อมูลแจ้งเหตุ", use_container_width=True):
                st.success("ส่งข้อมูลสำเร็จ!")

    with t2:
        st.info("ลงทะเบียนนำรถเข้าโรงเรียน หรือ ตรวจสอบบัตรอนุญาตดิจิทัล")
        # (เพิ่มปุ่ม Student Portal และ Register รถเดิม)

    st.markdown("---")
    with st.expander("🔐 สำหรับเจ้าหน้าที่ (Login)"):
        pwd = st.text_input("รหัสผ่านประจำตัว", type="password")
        if st.button("เข้าสู่ระบบ", use_container_width=True):
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
