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

# ป้องกัน AttributeError
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None

def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# ==========================================
# 2. MODULE: INVESTIGATION (งานสอบสวน)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("📂 ระบบงานสอบสวน")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (งานจราจร)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("🚦 ระบบงานจราจร")
    try:
        raw_json = st.secrets["textkey"]["json_content"].strip()
        info = json.loads(raw_json)
        info["private_key"] = fix_key(info["private_key"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Motorcycle_DB").sheet1
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        if st.button("🔄 โหลดข้อมูลจราจร"):
            st.dataframe(pd.DataFrame(sheet.get_all_records()), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {e}")

# ==========================================
# 4. MAIN GATEWAY & LOGIN (แก้ไขระบบดึงบัญชี)
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
                    # ดึงข้อมูลบัญชี (รองรับทั้งชื่อตัวเล็กและตัวใหญ่)
                    # พยายามหา OFFICER_ACCOUNTS ก่อน ถ้าไม่มีหา officer_accounts
                    accounts = st.secrets.get("OFFICER_ACCOUNTS") or st.secrets.get("officer_accounts")
                    
                    if accounts:
                        if pwd_input in accounts:
                            st.session_state.logged_in = True
                            st.session_state.user_info = accounts[pwd_input]
                            st.rerun()
                        else:
                            st.error("❌ รหัสผ่านไม่ถูกต้อง")
                    else:
                        st.error("❌ ไม่พบการตั้งค่าบัญชีในระบบ (Secrets)")
                        st.info("กรุณาตรวจสอบว่าในหน้า Secrets มีหัวข้อ [OFFICER_ACCOUNTS] แล้วหรือยัง")
    else:
        # แสดงชื่อ Sidebar
        user = st.session_state.user_info
        name = user.get('name', 'เจ้าหน้าที่') if isinstance(user, dict) else "เจ้าหน้าที่"
        st.sidebar.markdown(f"### 👤 {name}")
        
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
