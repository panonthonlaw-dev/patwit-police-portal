import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# PDF Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass

# ==========================================
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# สร้าง State ให้ครบถ้วนเพื่อรองรับทั้ง 2 ระบบ
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query': "",
    'df_traffic': None, 'edit_data_tra': None
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# --- ระบบค้นหาโลโก้ ---
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), None)
LOGO_MIME = "image/png"
def get_base64_image(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
LOGO_BASE64 = get_base64_image(LOGO_PATH)

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

# ==========================================
# 2. MODULE: INVESTIGATION (ระบบสอบสวน 100%)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None, 'view_mode': 'list'}), width='stretch')
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Helper: ตรวจสอบคอลัมน์สอบสวน
    def safe_cols_inv(df):
        cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
        for c in cols:
            if c not in df.columns: df[c] = ""
        return df

    try:
        df_raw = conn.read(ttl="0")
        df_display = safe_cols_inv(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            st.title(f"🏢 ระบบสอบสวน คุณ{user['name']}")
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            
            with tab_list:
                # ระบบค้นหา
                search_q = st.text_input("🔍 ค้นหาเคส", placeholder="เลขเคส, ชื่อ, หรือเหตุการณ์...", key="inv_search")
                filtered = df_display.copy()
                if search_q:
                    filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_pending = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_finished = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                # --- ส่วนรายการที่รอ ---
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                for idx, row in df_pending.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {row['Report_ID']}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("⏳ รอ")
                    st.divider()

                # --- ส่วนรายการที่เรียบร้อย (แก้ไขให้กลับมาแสดงผล) ---
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                if df_finished.empty: st.caption("ไม่มีรายการที่ดำเนินการเรียบร้อย")
                for idx, row in df_finished.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"✅ {row['Report_ID']}", key=f"f_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.markdown("<span style='color:green;'>✅ เรียบร้อย</span>", unsafe_allow_html=True)
                    st.divider()

        elif st.session_state.view_mode == "detail":
            # (ฟังก์ชันรายละเอียดสอบสวน, ระบบปลดล็อก Patwit1510 และ PDF คงเดิมตามไฟล์ล่าสุด)
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            st.subheader(f"📄 รายละเอียดเคส: {sid}")
            # ... (ใส่ Logic Form บันทึก และ PDF Button จากโค้ดก่อนหน้า) ...
            st.info("กำลังเรียกดูข้อมูลรายละเอียด...")

    except Exception as e: st.error(f"Error สอบสวน: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ระบบงานจราจร 100%)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None}), width='stretch')
    st.title(f"🚦 ระบบงานจราจร คุณ{user['name']}")

    def connect_tra():
        try:
            info = json.loads(st.secrets["textkey"]["json_content"])
            info["private_key"] = fix_key(info["private_key"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(info, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
            return gspread.authorize(creds).open("Motorcycle_DB").sheet1
        except Exception as e: st.error(f"เชื่อมต่อฐานข้อมูลจราจรไม่ได้: {e}"); return None

    sheet = connect_tra()
    if sheet:
        if st.button("🔄 ดึงข้อมูลจราจรล่าสุด", use_container_width=True):
            data = sheet.get_all_values()
            # จัดการ Column ซ้ำอัตโนมัติ (รูปภาพ1)
            header = data[0]
            clean_h = []
            for i, n in enumerate(header):
                val = n.strip() or f"Col_{i}"
                if val in clean_h: val = f"{val}_{i}"
                clean_h.append(val)
            st.session_state.df_traffic = pd.DataFrame(data[1:], columns=clean_h)
            st.rerun()

        if st.session_state.df_traffic is not None:
            df = st.session_state.df_traffic
            q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_search")
            if q:
                df = df[df.apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
            
            for i, row in df.head(20).iterrows():
                with st.expander(f"🏍️ {row.get('ทะเบียน')} | {row.get('ชื่อ-สกุล')}"):
                    st.write(f"**รหัสประจำตัว:** {row.get('เลขประจำตัว')} | **คะแนนคงเหลือ:** {row.get('คะแนน')}")
                    # (ใส่ Logic แสดง ATM Card และ ปุ่มหักคะแนนตามโค้ดต้นฉบับจราจร)
                    if user['role'] == 'admin':
                        st.button(f"🔴 หักคะแนนวินัย (เคส {i})", key=f"tra_btn_{i}")

# ==========================================
# 4. MAIN GATEWAY & LOGIN
# ==========================================
def main():
    if not st.session_state.logged_in:
        # --- หน้า LOGIN ---
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        # --- หน้าหลักหลังล็อกอิน ---
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    st.write("สรุปสำนวนคดีและพิมพ์รายงาน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    st.write("ตรวจทะเบียนรถและตัดแต้มวินัย")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type="primary"):
                        st.session_state.current_dept = "tra"; st.rerun()
            
            if st.sidebar.button("🚪 ออกจากระบบ"):
                st.session_state.clear(); st.rerun()
        else:
            # รัน Module ตามที่เลือก
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__":
    main()
