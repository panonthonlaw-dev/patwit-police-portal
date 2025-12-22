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
LOGO_PATH = next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None)

# Initialize Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'traffic_df' not in st.session_state: st.session_state.traffic_df = None
if 'search_results_df' not in st.session_state: st.session_state.search_results_df = None

# --- 2. COMMON HELPERS ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_img_link_drive(url):
    if not url or str(url) == "nan": return "https://via.placeholder.com/150"
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

# --- 3. [MODULE: TRAFFIC] ระบบงานจราจร ---

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
    except Exception as e:
        st.error(f"โหลดข้อมูลจราจรไม่สำเร็จ: {e}")
        return False

# ฟังก์ชันสร้าง PDF (ReportLab)
def create_traffic_pdf(vals, printed_by):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    if os.path.exists(FONT_FILE):
        pdfmetrics.registerFont(TTFont('Thai', FONT_FILE))
        pdfmetrics.registerFont(TTFont('ThaiBold', FONT_BOLD_FILE))
        f_reg, f_bold = 'Thai', 'ThaiBold'
    else: f_reg, f_bold = 'Helvetica', 'Helvetica-Bold'
    
    # Header
    if LOGO_PATH: c.drawImage(LOGO_PATH, 50, height - 85, width=50, height=50, mask='auto')
    c.setFont(f_bold, 22); c.drawCentredString(width/2, height - 50, "แบบทะเบียนประวัติรถจักรยานยนต์นักเรียน")
    c.setFont(f_reg, 18); c.drawCentredString(width/2, height - 72, "โรงเรียนโพนทองพัฒนาวิทยา")
    c.line(50, height - 85, width - 50, height - 85)
    
    # Data (v1=Name, v2=ID, v3=Class, v6=Plate, v13=Score)
    c.setFont(f_reg, 16)
    c.drawString(60, height - 115, f"ชื่อ-นามสกุล: {vals[1]}")
    c.drawString(300, height - 115, f"รหัสนักเรียน: {vals[2]}")
    c.drawString(60, height - 135, f"ระดับชั้น: {vals[3]}")
    c.drawString(300, height - 135, f"ทะเบียนรถ: {vals[6]}")
    
    c.setFont(f_bold, 18); c.drawString(60, height - 170, f"คะแนนคงเหลือ: {vals[13]} คะแนน")
    
    # Images (v14=Face, v10=Back, v11=Side)
    def draw_drive_img(url, x, y, w, h):
        try:
            res = requests.get(get_img_link_drive(url), timeout=5)
            img = ImageReader(io.BytesIO(res.content))
            c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True)
            c.rect(x, y, w, h)
        except: pass

    draw_drive_img(vals[14], 70, height - 350, 120, 150)
    draw_drive_img(vals[10], 210, height - 350, 150, 150)
    draw_drive_img(vals[11], 380, height - 350, 150, 150)

    c.save(); buffer.seek(0); return buffer

def traffic_module():
    st.markdown("### 🚦 ระบบบริหารงานจราจรและวินัยนักเรียน")
    if st.session_state.traffic_df is None: load_traffic_data()
    
    df = st.session_state.traffic_df
    if df is not None:
        # สถิติด้านบน
        total = len(df)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("รถทั้งหมด", f"{total} คัน")
        lok = df[df.iloc[:,7].str.contains("มี", na=False)].shape[0]
        m2.metric("ใบขับขี่", f"{lok} คน", f"{(lok/total*100):.1f}%")
        tok = df[df.iloc[:,8].str.contains("ปกติ|✅", na=False)].shape[0]
        m3.metric("ภาษีปกติ", f"{tok} คัน", f"{(tok/total*100):.1f}%")
        hok = df[df.iloc[:,9].str.contains("มี", na=False)].shape[0]
        m4.metric("สวมหมวก", f"{hok} คน", f"{(hok/total*100):.1f}%")

        st.markdown("---")
        # ระบบค้นหา
        col_q, col_btn = st.columns([4, 1])
        q = col_q.text_input("🔍 ค้นหา (ชื่อ / รหัส / ทะเบียน)", placeholder="ระบุข้อมูลที่ต้องการค้นหา...")
        if col_btn.button("ค้นหา", use_container_width=True, type="primary") or q:
            st.session_state.search_results_df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]

        # แสดงผลการค้นหา
        if st.session_state.search_results_df is not None:
            for i, row in st.session_state.search_results_df.iterrows():
                v = row.tolist()
                with st.expander(f"🏍️ {v[6]} | {v[1]} (คะแนน: {v[13]})", expanded=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.image(get_img_link_drive(v[14]), caption="รูปเจ้าของรถ", use_container_width=True)
                    with c2:
                        st.markdown(f"**ชื่อ:** {v[1]} | **รหัส:** {v[2]} | **ชั้น:** {v[3]}")
                        st.markdown(f"**ยี่ห้อ:** {v[4]} | **สี:** {v[5]} | **ทะเบียน:** {v[6]}")
                        
                        # --- ระบบจัดการแต้ม (หัก/เพิ่ม) ---
                        st.markdown("#### 🛠️ จัดการคะแนนความประพฤติ")
                        with st.form(f"score_form_{i}"):
                            pts = st.number_input("จำนวนแต้ม", 1, 100, 5)
                            note = st.text_input("เหตุผลการปรับคะแนน", placeholder="ระบุสาเหตุ เช่น ไม่สวมหมวกกันน็อค")
                            col_sub1, col_sub2 = st.columns(2)
                            sub_deduct = col_sub1.form_submit_button("🔴 หักแต้ม", use_container_width=True)
                            sub_add = col_sub2.form_submit_button("🟢 เพิ่มแต้ม", use_container_width=True)
                            
                            if (sub_deduct or sub_add) and note:
                                sheet = connect_gsheet_traffic()
                                cell = sheet.find(str(v[2]))
                                current_score = int(v[13])
                                new_score = current_score - pts if sub_deduct else current_score + pts
                                new_score = max(0, min(100, new_score))
                                
                                timestamp = get_now_th().strftime('%d/%m/%Y %H:%M')
                                old_log = str(v[12]).strip() if str(v[12]).lower() != "nan" else ""
                                action = "หัก" if sub_deduct else "เพิ่ม"
                                new_log = f"{old_log}\n[{timestamp}] {action} {pts} แต้ม: {note} (โดย: {st.session_state.current_user_data['name']})"
                                
                                sheet.update(f'M{cell.row}:N{cell.row}', [[new_log, str(new_score)]])
                                st.success("✅ บันทึกคะแนนเรียบร้อยแล้ว!"); time.sleep(1); load_traffic_data(); st.rerun()

                        # --- ปุ่มพิมพ์รายงาน ---
                        pdf_data = create_traffic_pdf(v, st.session_state.current_user_data['name'])
                        st.download_button("🖨️ พิมพ์ใบประวัติ (PDF)", data=pdf_data, file_name=f"Report_{v[2]}.pdf", use_container_width=True)

# --- 4. [MODULE: INVESTIGATION] งานสืบสวน ---
def investigation_module():
    st.markdown("### 🕵️ ระบบบริหารงานสืบสวนและรับแจ้งเหตุ")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสืบสวนสำเร็จ")
        st.dataframe(df.tail(10), use_container_width=True)
        # (เพิ่ม Logic จัดการเคสแบบ WeasyPrint ของท่านต่อจากนี้ได้เลย)
    except Exception as e: st.error(f"Error Inv: {e}")

# --- 5. OFFICER PORTAL (หน้าเลือกแผนก) ---
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
        st.markdown("<h2 style='text-align:center;'>กรุณาเลือกหมวดหมู่การปฏิบัติงาน</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("🔎 เข้าสู่ระบบงานสืบสวน (จัดการเคสรับแจ้งเหตุ)", use_container_width=True):
            st.session_state.current_dept = "inv"; st.rerun()
        if col2.button("🚦 เข้าสู่ระบบงานจราจร (ทะเบียนรถนักเรียน)", use_container_width=True):
            st.session_state.current_dept = "traffic"; st.rerun()
    else:
        if st.button("🔄 สลับแผนกงาน", use_container_width=True):
            st.session_state.current_dept = None; st.rerun()
        st.markdown("---")
        if st.session_state.current_dept == "inv": investigation_module()
        else: traffic_module()

# --- 6. PUBLIC LANDING ---
def public_landing():
    if LOGO_PATH:
        c1, c2, c3 = st.columns([5, 1, 5])
        c2.image(LOGO_PATH, width=100)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>👮‍♂️ ศูนย์ปฏิบัติการสถานีตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📝 แจ้งเหตุใหม่", "🏍️ ตรวจสอบทะเบียนรถ"])
    with t1:
        st.info("ระบุรายละเอียดเหตุการณ์เพื่อแจ้งเจ้าหน้าที่ตำรวจนักเรียน")
        with st.form("inv_student"):
            st.text_input("ชื่อผู้แจ้ง")
            st.text_area("รายละเอียดเหตุการณ์ *", placeholder="เกิดเหตุอะไร ที่ใด ใครเป็นคนทำ (ข้อมูลจะถูกเก็บเป็นความลับ)")
            st.form_submit_button("ส่งข้อมูล")
    with t2:
        st.info("ตรวจสอบสถานะรถจักรยานยนต์")
        # (ส่วน Student Portal เดิม)

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
