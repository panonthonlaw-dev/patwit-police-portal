import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, re, pytz
from datetime import datetime

# --- INITIAL SETTINGS ---
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# --- MODULE: INVESTIGATION ---
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบงานสอบสวน")
    try:
        # ใช้ค่าเริ่มต้นจาก Secrets โดยตรง
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df.tail(10))
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {str(e)}")
        st.info("ตรวจสอบว่าใน Secrets มีบรรทัด token_uri หรือยัง?")

# --- MODULE: TRAFFIC ---
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบงานจราจร")
    try:
        # แก้ไขการอ่าน JSON Content
        raw_json = st.secrets["textkey"]["json_content"].strip()
        key_dict = json.loads(raw_json)
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Motorcycle_DB").sheet1
        
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        if st.button("แสดงข้อมูลรถทั้งหมด"):
            data = sheet.get_all_records()
            st.dataframe(pd.DataFrame(data))
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {str(e)}")
        st.info("ตรวจสอบว่า json_content ใน Secrets ขึ้นต้นด้วย { และลงท้ายด้วย } หรือไม่?")

# --- MAIN GATEWAY ---
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🔐 Central Login")
            pwd = st.text_input("รหัสผ่าน", type="password")
            if st.button("เข้าสู่ระบบ", use_container_width=True):
                accounts = st.secrets.get("officer_accounts", {})
                if pwd in accounts:
                    st.session_state.logged_in = True
                    st.session_state.current_user = accounts[pwd]
                    st.rerun()
                else:
                    st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # Sidebar แสดงชื่อ
        user = st.session_state.current_user
        st.sidebar.write(f"👤 **{user['name']}**")
        if st.sidebar.button("🚪 ออกจากระบบ"):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.header("🏢 กรุณาเลือกแผนก")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🕵️ เข้าสู่งานสอบสวน", use_container_width=True):
                    st.session_state.current_dept = "inv"
                    st.rerun()
            with c2:
                if st.button("🚦 เข้าสู่งานจราจร", use_container_width=True):
                    st.session_state.current_dept = "tra"
                    st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
