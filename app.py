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
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# ป้องกัน AttributeError โดยการสร้างค่าเริ่มต้นทุกตัวที่จำเป็น
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None
# State สำหรับงานสอบสวน
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'page_pending' not in st.session_state: st.session_state.page_pending = 1
if 'page_finished' not in st.session_state: st.session_state.page_finished = 1
if 'selected_case_id' not in st.session_state: st.session_state.selected_case_id = None
if 'unlock_password' not in st.session_state: st.session_state.unlock_password = ""
# State สำหรับงานจราจร
if 'reset_count' not in st.session_state: st.session_state['reset_count'] = 0
if 'search_results_df' not in st.session_state: st.session_state['search_results_df'] = None
if 'edit_data' not in st.session_state: st.session_state['edit_data'] = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# ฟังก์ชันส่วนกลาง
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# ==========================================
# 2. MODULE: INVESTIGATION (งานสอบสวน)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # --- ดึงฟังก์ชันช่วย (Helper Functions) จากโค้ดสอบสวนเดิม ---
    def safe_ensure_columns_for_view(df):
        required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
        if df is None or df.empty: return pd.DataFrame(columns=required_cols)
        for col in required_cols:
            if col not in df.columns: df[col] = ""
        return df

    def clean_val(val):
        if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
        return str(val).strip()

    def view_case(rid):
        st.session_state.selected_case_id = rid
        st.session_state.view_mode = "detail"
        st.session_state.unlock_password = ""

    # --- ส่วนแสดงผล Dashboard สอบสวน ---
    st.title("📂 ระบบงานสอบสวน")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy())
        df_display = df_display.fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            st.info(f"เจ้าหน้าที่ปฏิบัติการ: {user['name']}")
            st.subheader("📋 รายการแจ้งเหตุ")
            st.dataframe(df_display.tail(10), use_container_width=True)
            # สามารถเพิ่ม Logic Pagination และ Detail View ตามโค้ดเดิมได้ที่นี่
        
        elif st.session_state.view_mode == "detail":
            if st.button("⬅️ กลับหน้ารายการ"): st.session_state.view_mode = "list"; st.rerun()
            st.write(f"รายละเอียดเคส: {st.session_state.selected_case_id}")

    except Exception as e:
        st.error(f"ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (งานจราจร)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    def connect_gsheet_tra():
        key_content = st.secrets["textkey"]["json_content"]
        key_dict = json.loads(key_content.replace('\n', '\\n'), strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    st.title("🚦 ระบบงานจราจร")
    try:
        sheet = connect_gsheet_tra()
        st.success(f"เชื่อมต่อฐานข้อมูลจราจรสำเร็จ (เจ้าหน้าที่: {user['name']})")
        
        if st.button("🔄 โหลดข้อมูลทะเบียนรถ"):
            vals = sheet.get_all_values()
            st.session_state.df_tra = pd.DataFrame(vals[1:], columns=vals[0])
            st.rerun()
            
        if "df_tra" in st.session_state:
            st.dataframe(st.session_state.df_tra, use_container_width=True)
            # สามารถเพิ่ม Logic ค้นหา/ตัดแต้ม ตามโค้ดเดิมได้ที่นี่

    except Exception as e:
        st.error(f"ระบบจราจรขัดข้อง: {e}")

# ==========================================
# 4. MAIN GATEWAY & LOGIN
# ==========================================
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    # ดึงรายชื่อจาก [OFFICER_ACCOUNTS] ตาม TOML
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else: st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        # Sidebar หลัง Login
        user = st.session_state.user_info
        display_name = user.get('name', 'เจ้าหน้าที่')
        st.sidebar.markdown(f"### 👤 {display_name}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    st.write("บันทึกเหตุการณ์และรายงานคดี")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    st.write("ตรวจสอบรถและวินัยจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
