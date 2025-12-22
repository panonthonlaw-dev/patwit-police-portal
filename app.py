import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, json, requests, re, time
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
# 1. การตั้งค่าเบื้องต้น (INITIAL SETTINGS)
# ==========================================
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# แก้ปัญหา AttributeError: ตรวจสอบและสร้าง Session State ทุกตัวที่จำเป็น
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None
if "view_mode" not in st.session_state: st.session_state.view_mode = "list"
if "selected_case_id" not in st.session_state: st.session_state.selected_case_id = None

# เส้นทางไฟล์
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

def get_now_th():
    return datetime.now(pytz.timezone('Asia/Bangkok'))

# ==========================================
# 2. ฟังก์ชันระบบสอบสวน (INVESTIGATION)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("📂 งานสอบสวน")
    
    try:
        # เชื่อมต่อ GSheets ผ่าน [connections.gsheets] อัตโนมัติ
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        
        # แสดงรายการล่าสุด (ยกมาจากโค้ดสอบสวนเดิม)
        st.subheader("รายการแจ้งเหตุ")
        st.dataframe(df.tail(10), use_container_width=True)
        
        # ใส่ Logic จัดการเคส/PDF ของสอบสวนต่อที่นี่...
        
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. ฟังก์ชันระบบจราจร (TRAFFIC)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("🚦 งานจราจร")

    def connect_traffic():
        # ดึงจาก [textkey]
        raw_json = st.secrets["textkey"]["json_content"].strip()
        key_dict = json.loads(raw_json)
        # ซ่อมแซมคีย์ป้องกัน Incorrect padding
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_traffic()
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        if st.button("🔄 ดึงข้อมูลทะเบียนรถ"):
            vals = sheet.get_all_records()
            st.session_state.df_tra = pd.DataFrame(vals)
            st.rerun()
            
        if "df_tra" in st.session_state:
            st.dataframe(st.session_state.df_tra, use_container_width=True)
            
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {e}")

# ==========================================
# 4. หน้าหลัก และระบบ LOGIN ส่วนกลาง
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
                    # ตรวจสอบจาก [OFFICER_ACCOUNTS] (อิงตาม toml ที่ส่งมา)
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        # --- หลัง Login สำเร็จ ---
        user = st.session_state.user_info
        # ดึงชื่อแบบปลอดภัย (ป้องกัน AttributeError)
        name = user.get('name', 'เจ้าหน้าที่') if isinstance(user, dict) else "เจ้าหน้าที่"
        
        st.sidebar.markdown(f"### 👤 {name}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            # --- หน้าเลือกแผนก ---
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            # --- เข้าสู่แต่ละแผนก ---
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__":
    main()
