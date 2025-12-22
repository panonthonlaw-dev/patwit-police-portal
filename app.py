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

states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query': "",
    'df_traffic': None
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def fix_key(key): return key.strip().replace("\\n", "\n") if key else ""

def process_image(img_file):
    if img_file is None: return ""
    try:
        img = Image.open(img_file)
        if img.mode in ('RGBA', 'LA', 'P'): img = img.convert('RGB')
        img.thumbnail((800, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=65, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode()
    except: return ""

def clean_val(val):
    if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
    return str(val).strip()

# ==========================================
# 2. MODULE: INVESTIGATION (แก้ไขจุดดึงรายละเอียด)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None, 'view_mode': 'list'}), width='stretch')
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    
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
                search_q = st.text_input("🔍 ค้นหาเคส", key="inv_search")
                filtered = df_display.copy()
                if search_q:
                    filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_pending = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_finished = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                for idx, row in df_pending.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {row['Report_ID']}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("⏳ รอ")
                    st.divider()

                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                for idx, row in df_finished.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"✅ {row['Report_ID']}", key=f"f_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("✅ จบ")
                    st.divider()

        elif st.session_state.view_mode == "detail":
            # --- แก้ไขจุดนี้: ดึงรายละเอียดจาก df_display ตาม selected_case_id ---
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx_in_raw = sel.index[0]
                row = sel.iloc[0]
                
                # ระบบป้องกันแก้ไข
                current_status = clean_val(row['Status'])
                is_admin = user.get('role') == 'admin'
                is_finished = (current_status == "ดำเนินการเรียบร้อย")
                is_locked = True if (is_finished and st.session_state.unlock_password != "Patwit1510") else False
                if not is_admin: is_locked = True

                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียดเหตุการณ์:** {row['Details']}")
                    if clean_val(row['Image_Data']):
                        st.image(base64.b64decode(row['Image_Data']), width=400, caption="หลักฐานจากผู้แจ้ง")

                if is_locked and is_finished and is_admin:
                    st.warning("🔒 เคสนี้ดำเนินการเรียบร้อยแล้ว กรุณาใส่รหัส Patwit1510 เพื่อปลดล็อคการแก้ไข")
                    pwd_in = st.text_input("รหัสปลดล็อค", type="password")
                    if st.button("ยืนยันปลดล็อค"):
                        if pwd_in == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("edit_case_form"):
                    col1, col2 = st.columns(2)
                    v_vic = col1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_locked)
                    v_acc = col2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_locked)
                    v_wit = col1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_locked)
                    v_tea = col2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_locked)
                    v_stu = col1.text_input("ตำรวจนักเรียนผู้สอบสวน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_locked)
                    v_sta = col2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], 
                                         index=["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"].index(current_status) if current_status in ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"] else 0,
                                         disabled=is_locked)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_locked)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่มเติม", type=['jpg','png'], disabled=is_locked)

                    if st.form_submit_button("💾 บันทึกข้อมูล", use_container_width=True) and not is_locked:
                        final_img = process_image(ev_img) if ev_img else row['Evidence_Image']
                        df_raw.at[idx_in_raw, 'Victim'] = v_vic
                        df_raw.at[idx_in_raw, 'Accused'] = v_acc
                        df_raw.at[idx_in_raw, 'Witness'] = v_wit
                        df_raw.at[idx_in_raw, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx_in_raw, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx_in_raw, 'Statement'] = v_stmt
                        df_raw.at[idx_in_raw, 'Status'] = v_sta
                        df_raw.at[idx_in_raw, 'Evidence_Image'] = final_img
                        df_raw.at[idx_in_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna(""))
                        st.success("บันทึกข้อมูลเรียบร้อย!"); time.sleep(1); st.rerun()

    except Exception as e: st.error(f"Error สอบสวน: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (คงเดิม)
# ==========================================
def traffic_module():
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None}), width='stretch')
    st.title("🚦 ระบบงานจราจร")
    st.info("ระบบจราจรกำลังทำงาน...")

# ==========================================
# 4. MAIN GATEWAY
# ==========================================
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.header("🔐 Central Login")
                pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            if c1.button("🕵️ เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                st.session_state.current_dept = "inv"; st.rerun()
            if c2.button("🚦 เข้าใช้งานจราจร", use_container_width=True, type="primary"):
                st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__":
    main()
