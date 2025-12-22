import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, re, pytz
from datetime import datetime

# --- 1. INITIAL SETTINGS ---
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", layout="wide")

# ป้องกัน Error Session State หาย
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# --- 2. MODULE: INVESTIGATION (สอบสวน) ---
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบงานสอบสวน")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {str(e)}")
        st.info("คำแนะนำ: ตรวจสอบข้อมูล [connections.gsheets] ใน Secrets ว่ามี token_uri หรือไม่")

# --- 3. MODULE: TRAFFIC (จราจร) ---
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบงานจราจร")
    try:
        raw_json = st.secrets["textkey"]["json_content"].strip()
        key_dict = json.loads(raw_json)
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        # ตรวจสอบชื่อ Spreadsheet ใน Drive ให้ตรงกับคำว่า Motorcycle_DB
        sheet = client.open("Motorcycle_DB").sheet1
        
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        if st.button("ดึงข้อมูลรถทั้งหมด"):
            data = sheet.get_all_records()
            st.dataframe(pd.DataFrame(data), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {str(e)}")
        st.info("คำแนะนำ: ตรวจสอบ json_content ใน Secrets ว่ารูปแบบถูกต้องหรือไม่")

# --- 4. MAIN GATEWAY ---
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🔐 Central Login")
            pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
            if st.button("เข้าสู่ระบบ", use_container_width=True):
                accounts = st.secrets.get("officer_accounts", {})
                if pwd in accounts:
                    st.session_state.logged_in = True
                    # ดึงข้อมูล user มาเก็บไว้
                    st.session_state.current_user = accounts[pwd]
                    st.rerun()
                else:
                    st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        # --- ส่วนการแสดงชื่อใน Sidebar (ดัก Error TypeError) ---
        user = st.session_state.current_user
        
        # ถ้า user เป็น Dictionary และมี key 'name' ให้แสดงชื่อ
        if isinstance(user, dict) and 'name' in user:
            display_name = user['name']
        else:
            display_name = "เจ้าหน้าที่ (ไม่มีชื่อ)"
            
        st.sidebar.markdown(f"### 👤 {display_name}")
        
        if st.sidebar.button("🚪 ออกจากระบบ", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        # หน้าเลือกแผนก
        if st.session_state.current_dept is None:
            st.header("🏢 กรุณาเลือกแผนกปฏิบัติงาน")
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าสู่ระบบสอบสวน", use_container_width=True):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าสู่ระบบจราจร", use_container_width=True):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
