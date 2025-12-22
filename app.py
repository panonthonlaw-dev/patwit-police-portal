import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, pytz
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# Initialize Session State
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# Helper functions
def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# --- MODULE: INVESTIGATION (สอบสวน) ---
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("📂 ระบบงานสอบสวน")
    try:
        # ใช้ระบบ st.connection ดึงจาก [connections.gsheets]
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df.tail(15), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {str(e)}")

# --- MODULE: TRAFFIC (จราจร) ---
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
        if st.button("🔄 ดึงข้อมูลทะเบียนรถ"):
            data = sheet.get_all_records()
            st.dataframe(pd.DataFrame(data), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {str(e)}")

# --- MAIN APP GATEWAY ---
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.header("🔐 Central Login")
                pwd_input = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_input in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd_input]
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        # Sidebar
        user = st.session_state.user_info
        st.sidebar.markdown(f"### 👤 {user.get('name', 'เจ้าหน้าที่')}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        # Department Selection
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
