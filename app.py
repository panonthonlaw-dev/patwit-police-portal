import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, re, pytz, base64
from datetime import datetime

# --- 1. INITIAL SETTINGS ---
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# ฟังก์ชันช่วยซ่อม Padding ของคีย์ (ป้องกัน Error: Incorrect padding)
def fix_private_key(key):
    if not key: return ""
    # ลบช่องว่างและขึ้นบรรทัดใหม่ที่อาจเกินมา
    return key.strip().replace("\\n", "\n")

# --- 2. MODULE: INVESTIGATION (งานสอบสวน) ---
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบงานสอบสวน")
    try:
        # ระบบ Streamlit Connection จะจัดการคีย์จาก [connections.gsheets] อัตโนมัติ
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.subheader("รายการแจ้งเหตุล่าสุด")
        st.dataframe(df.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {str(e)}")
        st.info("คำแนะนำ: ตรวจสอบว่าใน Secrets ของสอบสวน คัดลอกมาครบทุกบรรทัดหรือไม่")

# --- 3. MODULE: TRAFFIC (งานจราจร) ---
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบงานจราจร")
    try:
        # ดึงข้อมูล JSON และซ่อมแซมคีย์ภายใน
        raw_json = st.secrets["textkey"]["json_content"].strip()
        key_dict = json.loads(raw_json)
        
        # ซ่อม Private Key ของจราจรก่อนนำไปใช้
        key_dict["private_key"] = fix_private_key(key_dict["private_key"])
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open("Motorcycle_DB").sheet1
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        if st.button("ดึงข้อมูลรถทั้งหมด"):
            data = sheet.get_all_records()
            st.dataframe(pd.DataFrame(data), use_container_width=True)
            
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {str(e)}")

# --- 4. MAIN GATEWAY ---
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.header("🔐 Central Login")
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", use_container_width=True, type="primary"):
                    accounts = st.secrets.get("officer_accounts", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.current_user = accounts[pwd]
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        user = st.session_state.current_user
        display_name = user['name'] if isinstance(user, dict) and 'name' in user else "เจ้าหน้าที่"
        
        st.sidebar.markdown(f"### 👤 {display_name}")
        if st.sidebar.button("🚪 ออกจากระบบ", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.header("🏢 เลือกฝ่ายปฏิบัติงาน")
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานฝ่ายสอบสวน", use_container_width=True):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานฝ่ายจราจร", use_container_width=True):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__":
    main()
