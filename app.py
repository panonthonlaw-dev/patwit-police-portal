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
# 1. INITIAL SETTINGS
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# Shared Helpers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# ==========================================
# 2. MODULE: INVESTIGATION (ต้นฉบับสอบสวน)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # --- [สอบสวน] Helper Functions จากต้นฉบับ ---
    def safe_ensure_columns_for_view(df):
        required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
        if df is None or df.empty: return pd.DataFrame(columns=required_cols)
        for col in required_cols:
            if col not in df.columns: df[col] = ""
        return df

    def clean_val(val):
        if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
        return str(val).strip()

    # --- [สอบสวน] Main Module Logic ---
    st.markdown(f"### 🏢 ระบบสอบสวน (เจ้าหน้าที่: {user['name']})")
    
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy())
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
        
        with tab_list:
            st.subheader("รายการแจ้งเหตุล่าสุด")
            st.dataframe(df_display.tail(20), use_container_width=True)
            st.info("💡 ท่านสามารถคลิกดูรายละเอียดและพิมพ์ PDF ได้จากระบบเดิม (ย้าย Logic มาแล้ว)")

        with tab_dash:
            st.write("สถิติภาพรวมการแจ้งเหตุ")
            st.bar_chart(df_display['Incident_Type'].value_counts())

    except Exception as e:
        st.error(f"ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับจราจร)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # --- [จราจร] Helper Functions จากต้นฉบับ ---
    def connect_traffic_db():
        raw_json = st.secrets["textkey"]["json_content"].strip()
        info = json.loads(raw_json)
        info["private_key"] = fix_key(info["private_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    # --- [จราจร] Main Module Logic ---
    st.title("🚦 ระบบบริหารงานจราจร")
    
    try:
        sheet = connect_traffic_db()
        st.success(f"เชื่อมต่อฐานข้อมูลจราจรสำเร็จ (โดย: {user['name']})")
        
        c1, c2 = st.columns(2)
        if c1.button("🔄 อัปเดตข้อมูลล่าสุด", width='stretch'):
            vals = sheet.get_all_records()
            st.session_state.df_tra = pd.DataFrame(vals)
            st.rerun()

        if "df_tra" in st.session_state:
            st.subheader("🔍 ค้นหาข้อมูลทะเบียนรถ")
            q = st.text_input("กรอกชื่อ หรือ ทะเบียนรถ")
            if q:
                df = st.session_state.df_tra
                res = df[df.apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
                st.dataframe(res, use_container_width=True)
            else:
                st.dataframe(st.session_state.df_tra.head(10), use_container_width=True)

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
                pwd_input = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("OFFICER_ACCOUNTS") or st.secrets.get("officer_accounts")
                    if accounts and pwd_input in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd_input]
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง หรือ ไม่พบข้อมูลในระบบ")
    else:
        # Sidebar แสดงชื่อผู้ใช้
        user = st.session_state.user_info
        name = user.get('name', 'เจ้าหน้าที่') if isinstance(user, dict) else "เจ้าหน้าที่"
        st.sidebar.markdown(f"### 👤 {name}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        # หน้าเลือกแผนก
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    st.write("บันทึกคดี / พิมพ์รายงาน / ดูสถิติเหตุการณ์")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    st.write("ค้นหารถ / ตัดแต้มวินัย / สถิติจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            # รันระบบตามแผนกที่เลือก
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
