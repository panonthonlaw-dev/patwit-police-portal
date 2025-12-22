import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, json, requests, re, textwrap, time
from PIL import Image

# PDF Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import plotly.express as px

# ==========================================
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# แก้ปัญหา AttributeError โดยการสร้างค่าเริ่มต้นทุกครั้งที่รันแอป
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = {} # กำหนดเป็น dict ว่างไว้ก่อน
if "current_dept" not in st.session_state:
    st.session_state.current_dept = None

# ฟังก์ชันล้างคีย์ขยะ (ป้องกัน Incorrect padding)
def fix_private_key(key):
    if not key: return ""
    return key.strip().replace("\\n", "\n")

# ==========================================
# 2. MODULE: INVESTIGATION (งานสอบสวน)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("📂 ระบบงานสอบสวน")
    
    try:
        # เชื่อมต่อ GSheets (จะดึงค่าจาก [connections.gsheets] ใน Secrets อัตโนมัติ)
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_inv = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        
        # แสดงตารางข้อมูลเบื้องต้น (คุณสามารถยกโค้ดแสดงผลเดิมมาใส่ตรงนี้ได้เลย)
        st.dataframe(df_inv.tail(10), use_container_width=True)
        
    except Exception as e:
        st.error(f"ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (งานจราจร)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("🚦 ระบบงานจราจร")

    def connect_traffic():
        raw_json = st.secrets["textkey"]["json_content"].strip()
        info = json.loads(raw_json)
        info["private_key"] = fix_private_key(info["private_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_traffic()
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        # ปุ่มโหลดข้อมูล (ตัวอย่างการใช้งาน)
        if st.button("🔄 ดึงข้อมูลทะเบียนรถ"):
            vals = sheet.get_all_records()
            st.session_state.df_traffic = pd.DataFrame(vals)
            st.rerun()
            
        if "df_traffic" in st.session_state:
            st.dataframe(st.session_state.df_traffic, use_container_width=True)
            
    except Exception as e:
        st.error(f"ระบบจราจรขัดข้อง: {e}")

# ==========================================
# 4. MAIN GATEWAY (หน้า Login & เลือกแผนก)
# ==========================================
def main():
    if not st.session_state.logged_in:
        # --- หน้า Login ---
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.header("🔐 Central Login")
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("officer_accounts", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        # --- หลัง Login สำเร็จ ---
        # การดึงชื่อแบบปลอดภัย (Defensive Programming)
        user = st.session_state.get('user_info', {})
        # เช็คว่าเป็น dictionary หรือไม่ และมี key 'name' หรือไม่
        if isinstance(user, dict):
            name = user.get('name', 'เจ้าหน้าที่')
        else:
            name = "เจ้าหน้าที่"
        
        st.sidebar.markdown(f"### 👤 {name}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear() # ล้างทุกอย่างรวมถึง logged_in
            st.rerun()

        if st.session_state.current_dept is None:
            # --- หน้าเลือกแผนก ---
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            st.write("ยินดีต้อนรับสู่ศูนย์รวมระบบบริหารจัดการ")
            
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    st.write("จัดการเคส, สรุปสำนวน และพิมพ์รายงาน PDF")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    st.write("ตรวจสอบทะเบียนรถ, ตัดแต้ม และดูสถิติจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            # --- เข้าสู่แต่ละแผนก ---
            if st.session_state.current_dept == "inv": 
                investigation_module()
            elif st.session_state.current_dept == "tra": 
                traffic_module()

if __name__ == "__main__":
    main()
