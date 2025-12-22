import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
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
# 1. INITIAL CONFIG & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# ป้องกัน Error Session State: Initialize ทุกตัวที่โค้ดเก่าต้องใช้
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'page' not in st.session_state: st.session_state.page = 'teacher'
if 'search_results_df' not in st.session_state: st.session_state['search_results_df'] = None

# เส้นทางไฟล์พื้นฐาน
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# ==========================================
# 2. MODULE: INVESTIGATION (งานสอบสวน)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    st.markdown(f"### 🏢 ระบบสอบสวน (เจ้าหน้าที่: {user.get('name', 'ไม่ระบุ')})")
    
    try:
        # เชื่อมต่อผ่าน GSheetsConnection (สอบสวน)
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        
        # --- Logic แสดงผลสอบสวน ---
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df_raw.tail(20), use_container_width=True)
        # (หมายเหตุ: logic การแก้ข้อมูลและ PDF จะทำงานต่อจากจุดนี้)
        
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {e}")
        st.info("ตรวจสอบว่าใน Secrets มี [connections.gsheets] และ token_uri หรือไม่")

# ==========================================
# 3. MODULE: TRAFFIC (งานจราจร)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    st.markdown(f"### 🚦 ระบบจราจร (เจ้าหน้าที่: {user.get('name', 'ไม่ระบุ')})")

    def connect_gs_tra():
        raw_json = st.secrets["textkey"]["json_content"].strip()
        info = json.loads(raw_json)
        info["private_key"] = fix_key(info["private_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_gs_tra()
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        if st.button("🔄 โหลด/อัปเดต ข้อมูลทะเบียนรถ", width='stretch'):
            vals = sheet.get_all_records()
            st.session_state.search_results_df = pd.DataFrame(vals)
            st.rerun()

        if st.session_state.search_results_df is not None:
            st.dataframe(st.session_state.search_results_df, use_container_width=True)

    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {e}")
        st.info("ตรวจสอบว่า json_content ใน Secrets [textkey] ถูกต้องหรือไม่")

# ==========================================
# 4. MAIN GATEWAY & LOGIN
# ==========================================
def main():
    if not st.session_state.logged_in:
        # --- หน้า LOGIN ---
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    # ดึงจาก [OFFICER_ACCOUNTS] ตาม TOML
                    accounts = st.secrets.get("OFFICER_ACCOUNTS")
                    if accounts and pwd_in in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd_in]
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง หรือ ไม่พบการตั้งค่าบัญชี")
    else:
        # --- หลัง LOGIN ---
        user = st.session_state.user_info
        name = user.get('name', 'เจ้าหน้าที่')
        st.sidebar.markdown(f"### 👤 {name}")
        
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            # --- หน้าเลือกแผนก ---
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("📁 ฝ่ายสอบสวน")
                    st.write("จัดการรายงานเหตุการณ์ และพิมพ์รายงาน PDF")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🏍️ ฝ่ายจราจร")
                    st.write("ตรวจสอบรถ และจัดการคะแนนวินัยจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            # --- รัน Module ---
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
