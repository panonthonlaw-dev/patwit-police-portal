import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import re
import requests
import time
import io
import os
import glob

# --- 1. CONFIG & INITIALIZATION ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

# ป้องกัน AttributeError โดยการเช็คและสร้าง Key ที่จำเป็นใน Session State
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = None
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'traffic_df' not in st.session_state: st.session_state.traffic_df = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# --- 2. ฟังก์ชันดึงรูปภาพ (Private Access) ---
def load_drive_image(url_input, creds):
    url = str(url_input).strip() if pd.notna(url_input) else ""
    if not url or url.lower() == "nan":
        return "https://via.placeholder.com/150"
    try:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', url)
        file_id = match.group(1) or match.group(2)
        if file_id:
            if not creds.access_token or creds.access_token_expired:
                creds.refresh(requests.Request())
            headers = {"Authorization": f"Bearer {creds.access_token}"}
            api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.content
    except: pass
    return "https://via.placeholder.com/150"

# --- 3. ส่วนเชื่อมต่อฐานข้อมูล ---
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
            return pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        st.error(f"โหลดข้อมูลจราจรไม่สำเร็จ: {e}")
    return None

# --- 4. [MODULE] งานจราจร (Traffic) ---
def traffic_module():
    st.header("🚦 ระบบบริหารงานจราจร")
    client, creds = get_traffic_client()
    if st.session_state.traffic_df is None:
        st.session_state.traffic_df = load_traffic_data()
    
    df = st.session_state.traffic_df
    if df is not None:
        search_q = st.text_input("🔍 ค้นหาทะเบียน/ชื่อ/รหัส", placeholder="พิมพ์เพื่อค้นหา...")
        if search_q:
            results = df[df.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
            for idx, row in results.iterrows():
                with st.expander(f"🏍️ {row.iloc[6]} | {row.iloc[1]}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        img_data = load_drive_image(row.iloc[14], creds)
                        st.image(img_data, use_container_width=True)
                    with c2:
                        st.write(f"**รหัส:** {row.iloc[2]} | **คะแนน:** {row.iloc[13]}")
                        # ส่วนหักแต้ม/เพิ่มแต้ม (ตาม Logic ที่เคยทำ)
                        with st.form(f"score_{idx}"):
                            pts = st.number_input("แต้ม", 1, 50, 5)
                            note = st.text_input("เหตุผล")
                            if st.form_submit_button("บันทึกแต้ม"):
                                sheet = client.open("Motorcycle_DB").sheet1
                                cell = sheet.find(str(row.iloc[2]))
                                new_score = max(0, int(row.iloc[13]) - pts)
                                sheet.update(f'N{cell.row}', [[str(new_score)]])
                                st.success("อัปเดตแล้ว!"); st.session_state.traffic_df = None; st.rerun()

# --- 5. [MODULE] งานสอบสวน (Investigation) ---
def investigation_module():
    st.header("🕵️ ระบบงานสอบสวน")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_inv = conn.read(ttl="0")
        st.dataframe(df_inv, use_container_width=True)
    except Exception as e:
        st.error(f"โหลดข้อมูลสอบสวนไม่สำเร็จ: {e}")

# --- 6. MAIN NAVIGATION & LOGIN ---
def main():
    if not st.session_state.logged_in:
        # หน้าแรก & Login
        if LOGO_PATH:
            c1, c2, c3 = st.columns([5, 1, 5])
            c2.image(LOGO_PATH, width=100)
        st.markdown("<h1 style='text-align: center;'>👮‍♂️ ศูนย์ปฏิบัติการสถานีตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.subheader("🔐 เข้าสู่ระบบเจ้าหน้าที่")
            pwd = st.text_input("รหัสผ่าน", type="password")
            if st.button("Login", use_container_width=True):
                accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                if pwd in accounts:
                    st.session_state.logged_in = True
                    st.session_state.user_info = accounts[pwd]
                    st.rerun()
                else: st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # ส่วนป้องกัน AttributeError: ตรวจสอบว่ามี user_info หรือไม่
        if st.session_state.user_info is None:
            st.session_state.logged_in = False
            st.rerun()

        # แสดง Sidebar
        st.sidebar.title(f"สวัสดี, {st.session_state.user_info['name']}")
        if st.sidebar.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.current_dept = None
            st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            if c1.button("🕵️ งานสอบสวน", use_container_width=True):
                st.session_state.current_dept = "inv"; st.rerun()
            if c2.button("🚦 งานจราจร", use_container_width=True):
                st.session_state.current_dept = "traffic"; st.rerun()
        else:
            if st.sidebar.button("🔄 สลับแผนก"):
                st.session_state.current_dept = None; st.rerun()
            
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
