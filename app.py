import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, pytz
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="ระบบส่วนกลาง (Safe Mode)", page_icon="👮‍♂️", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None

def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# --- MODULE: INVESTIGATION (อ่านอย่างเดียว) ---
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("📂 ระบบงานสอบสวน")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อสำเร็จ (โหมดอ่านอย่างเดียว)")
        st.dataframe(df.tail(15), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ขัดข้อง: {str(e)}")

# --- MODULE: TRAFFIC (อ่านอย่างเดียว + ซ่อมชื่อคอลัมน์ในแอป) ---
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
        
        if st.button("🔄 ดึงข้อมูลทะเบียนรถ (ไม่มีการแก้ไขไฟล์ต้นฉบับ)"):
            # อ่านข้อมูลทั้งหมดมาเก็บใน RAM ของแอป
            data = sheet.get_all_values()
            if data:
                header = data[0]
                clean_header = []
                # วนลูปซ่อมชื่อคอลัมน์ "เฉพาะในแอปนี้เท่านั้น"
                for i, name in enumerate(header):
                    new_name = name.strip() or f"Column_{i}"
                    if new_name in clean_header:
                        new_name = f"{new_name}_dup_{i}"
                    clean_header.append(new_name)
                
                # สร้างตารางแสดงผลจากข้อมูลที่ซ่อมชื่อแล้ว
                df = pd.DataFrame(data[1:], columns=clean_header)
                st.success("✅ ดึงข้อมูลสำเร็จ")
                st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ ขัดข้อง: {str(e)}")

# --- GATEWAY ---
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
                    else: st.error("❌ รหัสผ่านไม่ถูกต้อง")
    else:
        user = st.session_state.user_info
        st.sidebar.markdown(f"### 👤 {user.get('name', 'เจ้าหน้าที่')}")
        if st.sidebar.button("🚪 ออกจากระบบ", width='stretch'):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🕵️ เข้าใช้งานสอบสวน", use_container_width=True):
                    st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                if st.button("🚦 เข้าใช้งานจราจร", use_container_width=True):
                    st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
