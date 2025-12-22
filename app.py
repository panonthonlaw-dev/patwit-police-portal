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
# 1. INITIAL CONFIG & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# ป้องกัน Error Session State
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# ฟังก์ชันทำความสะอาดคีย์เพื่อแก้ Incorrect padding
def fix_private_key(key):
    if not key: return ""
    return key.strip().replace("\\n", "\n")

# ==========================================
# 2. MODULE: INVESTIGATION (ยกโค้ดสอบสวนมาทั้งหมด)
# ==========================================
def investigation_module():
    # Helper functions ของสอบสวน
    def safe_ensure_columns_for_view(df):
        required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
        if df is None or df.empty: return pd.DataFrame(columns=required_cols)
        for col in required_cols:
            if col not in df.columns: df[col] = ""
        return df

    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # --- เริ่มต้นดึงข้อมูลสอบสวน ---
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy())
        
        st.title("📂 ระบบงานสอบสวน")
        st.success("เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        
        # แสดงรายการเหมือนโค้ดต้นฉบับของคุณ
        st.subheader("รายการแจ้งเหตุ")
        st.dataframe(df_display.tail(10), width='stretch')
        # (หมายเหตุ: คุณสามารถเอา Logic Dashboard/PDF ของสอบสวนมาใส่ต่อตรงนี้ได้เลย)
        
    except Exception as e:
        st.error(f"ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ยกโค้ดจราจรมาทั้งหมด)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    def connect_traffic():
        raw_json = st.secrets["textkey"]["json_content"].strip()
        info = json.loads(raw_json)
        info["private_key"] = fix_private_key(info["private_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    st.title("🚦 ระบบงานจราจร")
    try:
        sheet = connect_traffic()
        st.success("เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        # ส่วนแสดงผลงานจราจร
        if st.button("🔄 โหลดข้อมูลรถจักรยานยนต์"):
            vals = sheet.get_all_records()
            st.dataframe(pd.DataFrame(vals), width='stretch')
            
    except Exception as e:
        st.error(f"ระบบจราจรขัดข้อง: {e}")

# ==========================================
# 4. MAIN GATEWAY
# ==========================================
def main():
    if not st.session_state.logged_in:
        # หน้า Login
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
                    else: st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # แสดงชื่อ Sidebar
        name = st.session_state.user_info.get('name', 'เจ้าหน้าที่')
        st.sidebar.write(f"👤 **{name}**")
        if st.sidebar.button("🚪 ออกจากระบบ"):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            # หน้าเลือกแผนก
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เลือกงานสอบสวน", width='stretch'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เลือกงานจราจร", width='stretch'):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
