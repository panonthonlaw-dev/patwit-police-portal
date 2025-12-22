import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, re, pytz
from datetime import datetime

# --- 1. INITIAL SETTINGS ---
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", layout="wide")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# ฟังก์ชันทำความสะอาดคีย์ (ป้องกัน Incorrect padding)
def clean_key(key_string):
    if not key_string: return ""
    # ลบช่องว่างหน้า/หลัง และลบเครื่องหมาย \n ที่เป็นตัวอักษรให้เป็นขึ้นบรรทัดใหม่จริง
    cleaned = key_string.strip().replace("\\n", "\n")
    # ตรวจสอบว่าคีย์ต้องขึ้นต้นและลงท้ายด้วยมาตรฐาน PEM
    if "-----BEGIN PRIVATE KEY-----" not in cleaned:
        cleaned = "-----BEGIN PRIVATE KEY-----\n" + cleaned
    if "-----END PRIVATE KEY-----" not in cleaned:
        cleaned = cleaned + "\n-----END PRIVATE KEY-----"
    return cleaned

# --- 2. MODULE: INVESTIGATION (สอบสวน) ---
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("📂 ระบบงานสอบสวน")
    try:
        # สำหรับระบบสอบสวน ใช้ st.connection ซึ่งดึงค่าจาก [connections.gsheets]
        # ตัวไลบรารี st-gsheets จะอ่านค่าจาก secrets ให้อัตโนมัติ
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        st.dataframe(df.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {str(e)}")
        st.info("คำแนะนำ: ตรวจสอบหน้า Secrets ส่วน [connections.gsheets] ว่าคีย์อยู่ในเครื่องหมายฟันหนู 3 อัน \"\"\" หรือไม่")

# --- 3. MODULE: TRAFFIC (จราจร) ---
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
    st.title("🚦 ระบบงานจราจร")
    try:
        # ดึง JSON และทำความสะอาดคีย์ภายใน
        info = json.loads(st.secrets["textkey"]["json_content"])
        info["private_key"] = clean_key(info["private_key"])
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open("Motorcycle_DB").sheet1
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        if st.button("แสดงข้อมูลรถ"):
            st.dataframe(pd.DataFrame(sheet.get_all_records()), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {str(e)}")

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
                    st.session_state.current_user = accounts[pwd]
                    st.rerun()
                else: st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        user = st.session_state.current_user
        name = user['name'] if isinstance(user, dict) else "เจ้าหน้าที่"
        st.sidebar.write(f"👤 **{name}**")
        if st.sidebar.button("🚪 ออกจากระบบ"):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            st.header("🏢 เลือกฝ่ายปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🕵️ เข้าใช้งานงานสอบสวน", use_container_width=True):
                    st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                if st.button("🚦 เข้าใช้งานงานจราจร", use_container_width=True):
                    st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            else: traffic_module()

if __name__ == "__main__":
    main()
