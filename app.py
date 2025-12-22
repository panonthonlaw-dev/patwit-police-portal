import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz
import re
import requests
import time
import io
import os
import glob
import textwrap
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# --- 1. การตั้งค่าเบื้องต้นและ Session ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'traffic_df' not in st.session_state: st.session_state.traffic_df = None
if 'search_results' not in st.session_state: st.session_state.search_results = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD_FILE = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# --- 2. ฟังก์ชันช่วย (Helpers) ---
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def get_img_link_drive(url):
    if not url or str(url) == "nan": return "https://via.placeholder.com/150"
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

# --- 3. การเชื่อมต่อฐานข้อมูลจราจร ---
def get_traffic_client():
    creds_dict = dict(st.secrets["traffic_creds"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds), creds

def load_traffic_data():
    try:
        client, _ = get_traffic_client()
        sheet = client.open("Motorcycle_DB").sheet1
        data = sheet.get_all_values()
        if len(data) > 1:
            # ใช้ Header จริงจาก Sheet เพื่อความถูกต้อง
            return pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        st.error(f"โหลดข้อมูลจราจรไม่สำเร็จ: {e}")
    return None

# --- 4. ฟังก์ชัน PDF จราจร ---
def create_traffic_pdf(row, printed_by):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    if os.path.exists(FONT_FILE):
        pdfmetrics.registerFont(TTFont('Thai', FONT_FILE))
        pdfmetrics.registerFont(TTFont('ThaiBold', FONT_BOLD_FILE))
        f_reg, f_bold = 'Thai', 'ThaiBold'
    else: f_reg, f_bold = 'Helvetica', 'Helvetica-Bold'
    
    # วาดข้อมูล PDF
    c.setFont(f_bold, 22); c.drawCentredString(width/2, height - 50, "แบบทะเบียนประวัติรถจักรยานยนต์นักเรียน")
    c.setFont(f_reg, 18); c.drawCentredString(width/2, height - 70, "โรงเรียนโพนทองพัฒนาวิทยา")
    
    c.setFont(f_reg, 16)
    c.drawString(60, height - 120, f"ชื่อ-นามสกุล: {row['ชื่อ-สกุล']}")
    c.drawString(300, height - 120, f"รหัสนักเรียน: {row['เลขประจำตัว']}")
    c.drawString(60, height - 140, f"ระดับชั้น: {row['ชั้น']}")
    c.drawString(300, height - 140, f"ทะเบียนรถ: {row['ทะเบียน']}")
    c.drawString(60, height - 170, f"แต้มวินัยจราจรคงเหลือ: {row['คะแนน']} คะแนน")
    
    # ประวัติบันทึก
    c.drawString(60, height - 200, "ประวัติการทำผิดวินัย:")
    text_obj = c.beginText(70, height - 220)
    text_obj.setFont(f_reg, 14)
    for line in str(row['ประวัติ']).split('\n'):
        for wrap_line in textwrap.wrap(line, width=80): text_obj.textLine(wrap_line)
    c.drawText(text_obj)
    
    c.save(); buffer.seek(0); return buffer

# --- 5. [MODULE] งานจราจร (Traffic) ---
def traffic_module():
    st.header("🚦 ระบบบริหารงานจราจรและวินัยนักเรียน")
    client, creds = get_traffic_client()
    
    if st.session_state.traffic_df is None:
        st.session_state.traffic_df = load_traffic_data()
    
    df = st.session_state.traffic_df
    if df is not None:
        q = st.text_input("🔍 ค้นหา (ชื่อ / รหัส / ทะเบียน)", placeholder="พิมพ์ข้อมูลที่ต้องการหา...")
        if q:
            st.session_state.search_results = df[df.apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]

        if st.session_state.search_results is not None:
            for idx, row in st.session_state.search_results.iterrows():
                with st.expander(f"🏍️ {row['ทะเบียน']} | {row['ชื่อ-สกุล']} (แต้ม: {row['คะแนน']})", expanded=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        # แสดงภาพจาก Google Drive
                        st.image(get_img_link_drive(row['รูปภาพ1']), caption="รูปเจ้าของรถ", use_container_width=True)
                    with c2:
                        st.markdown(f"**รหัส:** {row['เลขประจำตัว']} | **ชั้น:** {row['ชั้น']}")
                        st.markdown(f"**สถานะ:** ใบขับขี่: {row['ใบขับขี่']} | ภาษี: {row['พรบ_ภาษี']}")
                        
                        # --- ระบบแก้ไข/จัดการแต้ม ---
                        with st.form(f"action_{idx}"):
                            pts = st.number_input("จำนวนแต้มที่ปรับ", 1, 50, 5)
                            note = st.text_input("เหตุผลการปรับคะแนน")
                            col_b1, col_b2 = st.columns(2)
                            deduct = col_b1.form_submit_button("🔴 หักแต้ม", use_container_width=True)
                            add = col_b2.form_submit_button("🟢 เพิ่มแต้ม", use_container_width=True)
                            
                            if (deduct or add) and note:
                                sheet = client.open("Motorcycle_DB").sheet1
                                cell = sheet.find(str(row['เลขประจำตัว']))
                                old_score = int(row['คะแนน'])
                                new_score = max(0, min(100, old_score - pts if deduct else old_score + pts))
                                
                                log_time = get_now_th().strftime('%d/%m/%Y %H:%M')
                                action = "หัก" if deduct else "เพิ่ม"
                                new_history = f"{row['ประวัติ']}\n[{log_time}] {action} {pts} แต้ม: {note}"
                                
                                # อัปเดตลง Sheet (M=ประวัติ, N=คะแนน)
                                sheet.update(f'M{cell.row}:N{cell.row}', [[new_history, str(new_score)]])
                                st.success("อัปเดตข้อมูลสำเร็จ!"); st.session_state.traffic_df = None; time.sleep(1); st.rerun()

                        # --- ปุ่มพิมพ์ PDF ---
                        pdf_data = create_traffic_pdf(row, st.session_state.user_info['name'])
                        st.download_button("🖨️ ดาวน์โหลดไฟล์ PDF", data=pdf_data, file_name=f"Report_{row['เลขประจำตัว']}.pdf", use_container_width=True)

# --- 6. [MODULE] งานสอบสวน (Investigation) ---
def investigation_module():
    st.header("🕵️ ระบบบริหารงานสืบสวน")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_inv = conn.read(ttl="0")
        st.dataframe(df_inv.tail(10), use_container_width=True)
    except Exception as e: st.error(f"Error: {e}")

# --- 7. MAIN NAVIGATION ---
def main():
    if not st.session_state.logged_in:
        if LOGO_PATH:
            c1, c2, c3 = st.columns([5, 1, 5])
            c2.image(LOGO_PATH, width=100)
        st.markdown("<h1 style='text-align: center;'>👮‍♂️ ศูนย์ปฏิบัติการตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.subheader("🔐 เข้าสู่ระบบเจ้าหน้าที่")
            pwd = st.text_input("รหัสผ่านประจำตัว", type="password")
            if st.button("Login", use_container_width=True):
                accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                if pwd in accounts:
                    st.session_state.logged_in = True
                    st.session_state.user_info = accounts[pwd]
                    st.rerun()
                else: st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        if st.session_state.user_info is None:
            st.session_state.logged_in = False; st.rerun()

        st.sidebar.title(f"👤 {st.session_state.user_info['name']}")
        if st.sidebar.button("🚪 Logout"):
            st.session_state.logged_in = False; st.session_state.current_dept = None; st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            col1, col2 = st.columns(2)
            if col1.button("🕵️ งานสอบสวน", use_container_width=True, height=100):
                st.session_state.current_dept = "inv"; st.rerun()
            if col2.button("🚦 งานจราจร", use_container_width=True, height=100):
                st.session_state.current_dept = "traffic"; st.rerun()
        else:
            if st.sidebar.button("🔄 สลับแผนก"):
                st.session_state.current_dept = None; st.rerun()
            
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
