import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json, os, re, pytz, base64
from datetime import datetime

# ==========================================
# 1. การตั้งค่าหน้าจอและ SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบงานสถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# ป้องกัน Error ทุกจุดด้วยการประกาศค่าเริ่มต้น
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# ฟังก์ชันทำความสะอาดคีย์อัตโนมัติ (แก้ปัญหา Incorrect padding)
def get_clean_key(key_str):
    if not key_str: return ""
    return key_str.strip().replace("\\n", "\n")

# ==========================================
# 2. โมดูลงานสอบสวน (INVESTIGATION)
# ==========================================
def investigation_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("📂 ระบบบริหารจัดการงานสอบสวน")
    
    try:
        # เชื่อมต่ออัตโนมัติผ่านพารามิเตอร์ที่ตั้งไว้ใน Secrets
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl="0")
        st.success("✅ เชื่อมต่อฐานข้อมูลสอบสวนสำเร็จ")
        
        st.subheader("รายการแจ้งเหตุล่าสุด")
        st.dataframe(df.tail(10), use_container_width=True)
        st.info("💡 ท่านสามารถจัดการข้อมูลสอบสวนได้เต็มรูปแบบในส่วนนี้")
    except Exception as e:
        st.error(f"❌ ระบบสอบสวนขัดข้อง: {str(e)}")

# ==========================================
# 3. โมดูลงานจราจร (TRAFFIC)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเมนูหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    st.title("🚦 ระบบบริหารจัดการงานจราจร")
    
    try:
        # ดึงข้อมูลจากส่วน [textkey]
        raw_info = json.loads(st.secrets["textkey"]["json_content"])
        raw_info["private_key"] = get_clean_key(raw_info["private_key"])
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(raw_info, scope)
        client = gspread.authorize(creds)
        
        # เชื่อมต่อ Motorcycle_DB
        sheet = client.open("Motorcycle_DB").sheet1
        st.success("✅ เชื่อมต่อฐานข้อมูลจราจรสำเร็จ")
        
        if st.button("🔄 โหลดข้อมูลรถจักรยานยนต์ทั้งหมด"):
            data = sheet.get_all_records()
            st.dataframe(pd.DataFrame(data), use_container_width=True)
    except Exception as e:
        st.error(f"❌ ระบบจราจรขัดข้อง: {str(e)}")

# ==========================================
# 4. ระบบ LOGIN และหน้าหลัก (GATEWAY)
# ==========================================
def main():
    if not st.session_state.logged_in:
        # --- หน้า LOGIN ---
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align:center;'>ระบบบริหารจัดการส่วนกลาง</p>", unsafe_allow_html=True)
                
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
        # --- หลัง LOGIN สำเร็จ ---
        user = st.session_state.current_user
        name = user['name'] if isinstance(user, dict) and 'name' in user else "เจ้าหน้าที่"
        
        st.sidebar.markdown(f"### 👤 {name}")
        if st.sidebar.button("🚪 ออกจากระบบ", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        if st.session_state.current_dept is None:
            # --- หน้าเลือกแผนก ---
            st.header("🏢 เลือกแผนกปฏิบัติงาน")
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ ฝ่ายสอบสวน")
                    st.write("บันทึกเหตุการณ์และรายงานคดี")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True):
                        st.session_state.current_dept = "inv"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 ฝ่ายจราจร")
                    st.write("ตรวจสอบรถและวินัยจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True):
                        st.session_state.current_dept = "tra"
                        st.rerun()
        else:
            # --- เข้าสู่แต่ละฝ่าย ---
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__":
    main()
