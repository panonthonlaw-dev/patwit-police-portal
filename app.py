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
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# ป้องกัน AttributeError ด้วยการสร้าง State เริ่มต้นให้ครบตามโค้ดเดิมทั้ง 2 แผนก
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'search_results_df' not in st.session_state: st.session_state.search_results_df = None
if 'selected_case_id' not in st.session_state: st.session_state.selected_case_id = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""
def get_img_link(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

# ==========================================
# 2. MODULE: INVESTIGATION (งานสอบสวน)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    user = st.session_state.user_info
    st.title("📂 ระบบงานสอบสวน")
    
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        
        # แสดง Metric สรุปเหมือน Dashboard เดิม
        m1, m2, m3 = st.columns(3)
        m1.metric("แจ้งเหตุทั้งหมด", len(df_raw))
        m2.metric("รอดำเนินการ", len(df_raw[df_raw['Status'] == "รอดำเนินการ"]))
        m3.metric("เสร็จสิ้น", len(df_raw[df_raw['Status'] == "ดำเนินการเรียบร้อย"]))
        
        st.subheader("📋 รายการแจ้งเหตุล่าสุด")
        st.dataframe(df_raw.tail(20), use_container_width=True)
        
        # เพิ่มเติม: ส่วนรายละเอียดเคส (Copy Logic แสดงรายละเอียดเดิมมาวางที่นี่ได้)
    except Exception as e:
        st.error(f"ระบบสอบสวนขัดข้อง: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (งานจราจร)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    user = st.session_state.user_info
    st.title("🚦 ระบบงานจราจร")

    def connect_traffic():
        raw_json = st.secrets["textkey"]["json_content"].strip()
        info = json.loads(raw_json)
        info["private_key"] = fix_key(info["private_key"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Motorcycle_DB").sheet1

    try:
        sheet = connect_traffic()
        if st.button("🔄 อัปเดตข้อมูลทะเบียนรถ", use_container_width=True):
            data = sheet.get_all_values()
            header = data[0]
            # จัดการชื่อคอลัมน์ซ้ำในแอป (เช่น รูปภาพ1)
            clean_header = []
            for i, name in enumerate(header):
                n = name.strip() or f"Col_{i}"
                if n in clean_header: n = f"{n}_{i}"
                clean_header.append(n)
            st.session_state.search_results_df = pd.DataFrame(data[1:], columns=clean_header)
            st.rerun()

        if st.session_state.search_results_df is not None:
            df = st.session_state.search_results_df
            q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)")
            if q:
                df = df[df.apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
            
            st.write(f"พบข้อมูล {len(df)} รายการ")
            for i, row in df.iterrows():
                with st.expander(f"🏍️ {row.get('ทะเบียน', 'ไม่ระบุ')} | {row.get('ชื่อ-สกุล', 'ไม่ระบุ')}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"**รหัสประจำตัว:** {row.get('เลขประจำตัว')}")
                    c1.write(f"**ยี่ห้อ/สี:** {row.get('ยี่ห้อ')} - {row.get('สี')}")
                    c2.write(f"**แต้มวินัยคงเหลือ:** {row.get('คะแนน')}")
                    
                    # Logic หักแต้ม (ปุ่มกดหักแต้มจะอยู่ตรงนี้)
                    if user['role'] == 'admin':
                        st.button("🔴 หักคะแนนวินัย", key=f"btn_{i}")

    except Exception as e:
        st.error(f"ระบบจราจรขัดข้อง: {e}")

# ==========================================
# 4. MAIN LOGIN & GATEWAY
# ==========================================
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_in in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd_in]
                        st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        # ส่วนแสดงชื่อเจ้าหน้าที่และปุ่ม Logout ใน Sidebar
        user = st.session_state.user_info
        st.sidebar.markdown(f"### 👤 {user.get('name')}")
        st.sidebar.caption(f"ตำแหน่ง: {user.get('role')}")
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
                    st.subheader("🕵️ ฝ่ายสอบสวน")
                    if st.button("เข้าสู่ระบบสอบสวน", use_container_width=True, type="primary"):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 ฝ่ายจราจร")
                    if st.button("เข้าสู่ระบบจราจร", use_container_width=True, type="primary"):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
