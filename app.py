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

# --- 1. การตั้งค่าหน้าจอและไฟล์ ---
st.set_page_config(page_title="ศูนย์ปฏิบัติการตำรวจพัทวิทย์", page_icon="👮‍♂️", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if f.lower().endswith(('.png','.jpg','.jpeg'))), None)

# Initialize Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'traffic_df' not in st.session_state: st.session_state.traffic_df = None

# --- 2. ฟังก์ชันดึงรูปภาพ (FIXED: แก้ Error ValueError) ---
def load_drive_image(url_input, creds):
    # ตรวจสอบค่าว่างแบบปลอดภัยสำหรับ Pandas
    url = str(url_input).strip() if pd.notna(url_input) else ""
    if not url or url.lower() == "nan" or url == "":
        return "https://via.placeholder.com/150"
    
    try:
        file_id = None
        match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1) or match.group(2)
        
        if file_id:
            if not creds.access_token or creds.access_token_expired:
                creds.refresh(requests.Request())
            
            headers = {"Authorization": f"Bearer {creds.access_token}"}
            api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            res = requests.get(api_url, headers=headers, timeout=10)
            
            if res.status_code == 200:
                return res.content
    except:
        pass
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

# --- 4. [MODULE] งานสอบสวน (Investigation) ---
def investigation_module():
    st.header("🕵️ ระบบบริหารงานสืบสวนและรับแจ้งเหตุ")
    # เชื่อมต่อผ่าน GSheetsConnection (พารามิเตอร์จาก Secrets [connections.gsheets])
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_inv = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสืบสวนสำเร็จ")
        
        # แสดงรายการแจ้งเหตุล่าสุด
        st.subheader("📋 รายการแจ้งเหตุล่าสุด")
        st.dataframe(df_inv.tail(10), use_container_width=True)
        
        # (เพิ่มปุ่มดูรายละเอียดเคสได้ที่นี่)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดงานสอบสวน: {e}")

# --- 5. [MODULE] งานจราจร (Traffic) ---
def traffic_module():
    st.header("🚦 ระบบบริหารงานจราจร (ทะเบียนรถ)")
    client, creds = get_traffic_client()
    
    if st.session_state.traffic_df is None:
        st.session_state.traffic_df = load_traffic_data()
    
    df = st.session_state.traffic_df
    if df is not None:
        search_q = st.text_input("🔍 ค้นหา (ชื่อ / รหัส / ทะเบียน)", placeholder="พิมพ์ข้อมูลที่ต้องการหา...")
        
        if search_q:
            results = df[df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)]
            if not results.empty:
                for idx, row in results.iterrows():
                    with st.expander(f"🏍️ {row['ทะเบียน']} | {row['ชื่อ-สกุล']}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            # ดึงรูปเจ้าของรถ (คอลัมน์ชื่อ 'รูปภาพ1' หรือปรับตามจริง)
                            img_col = 'รูปภาพ1' if 'รูปภาพ1' in row else df.columns[14]
                            img_data = load_drive_image(row[img_col], creds)
                            st.image(img_data, use_container_width=True)
                        with c2:
                            st.write(f"**รหัส:** {row.iloc[2]} | **ชั้น:** {row.iloc[3]}")
                            st.write(f"**คะแนนคงเหลือ:** {row.iloc[13]}")
                            # (ปุ่มหักแต้ม/เพิ่มแต้ม ใส่ตาม Logic เดิม)
            else:
                st.warning("ไม่พบข้อมูล")

# --- 6. หน้าหลักและการเข้าสู่ระบบ ---
def main():
    if not st.session_state.logged_in:
        # --- หน้าแรกสำหรับนักเรียนและ Login ---
        if LOGO_PATH:
            c1, c2, c3 = st.columns([5, 1, 5])
            c2.image(LOGO_PATH, width=100)
        st.markdown("<h1 style='text-align: center;'>👮‍♂️ ศูนย์ปฏิบัติการตำรวจโรงเรียนโพนทองพัฒนาวิทยา</h1>", unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["📝 สำหรับนักเรียน", "🔐 สำหรับเจ้าหน้าที่"])
        with t1:
            st.info("นักเรียนสามารถแจ้งเหตุหรือตรวจสอบทะเบียนรถได้ที่นี่ (กำลังพัฒนาฟอร์ม)")
        with t2:
            with st.form("login_form"):
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.form_submit_button("เข้าสู่ระบบ"):
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else: st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # --- หน้าปฏิบัติการเจ้าหน้าที่ ---
        st.sidebar.title(f"สวัสดี, {st.session_state.user_info['name']}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
        
        if st.session_state.current_dept is None:
            st.title("🏢 กรุณาเลือกแผนกที่ต้องการปฏิบัติงาน")
            c1, c2 = st.columns(2)
            if c1.button("🕵️ งานสอบสวน/แจ้งเหตุ", use_container_width=True):
                st.session_state.current_dept = "inv"; st.rerun()
            if c2.button("🚦 งานจราจร/ทะเบียนรถ", use_container_width=True):
                st.session_state.current_dept = "traffic"; st.rerun()
        else:
            if st.sidebar.button("🔄 สลับแผนกงาน"):
                st.session_state.current_dept = None; st.rerun()
            
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_department_module = traffic_module()

if __name__ == "__main__":
    main()
