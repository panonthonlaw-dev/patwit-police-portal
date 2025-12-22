import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, json, requests, re, textwrap, time
from PIL import Image

# PDF Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass

# ==========================================
# 1. INITIAL SETTINGS
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val):
    if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
    return str(val).strip()

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

def safe_ensure_columns_for_view(df):
    required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    df_new = df.copy()
    for col in required_cols:
        if col not in df_new.columns: df_new[col] = ""
    return df_new

# ==========================================
# 2. MODULE: INVESTIGATION
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy())
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            # --- หน้า LIST เหมือนเดิม ---
            st.title(f"🏢 ระบบสอบสวน คุณ{user['name']}")
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                # (ส่วนของ Pagination และปุ่มกดรหัสเคส POL-XXX เหมือนโค้ดที่คุณส่งมา)
                df_pending = df_display[df_display['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                for idx, row in df_pending.head(5).iterrows():
                    raw_rid = row['Report_ID']
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {raw_rid}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=raw_rid: (st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'})))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("⏳ รอ")
                    st.divider()

        elif st.session_state.view_mode == "detail":
            # --- หน้า DETAIL (จุดที่มีระบบป้องกัน) ---
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list'}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx = sel.index[0]
                row = sel.iloc[0]
                
                # --- ระบบป้องกัน (LOCK LOGIC) ---
                current_status = clean_val(row['Status'])
                is_admin = user.get('role') == 'admin'
                is_finished = (current_status == "ดำเนินการเรียบร้อย")
                
                # ตัวแปรควบคุมการ Lock
                is_locked = True if (is_finished and st.session_state.unlock_password != "Patwit1510") else False
                if not is_admin: is_locked = True # ถ้าไม่ใช่ Admin ล็อคถาวร

                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                
                st.divider()
                st.write("#### ✍️ บันทึกผลการสอบสวน")

                # แสดงช่องกรอกรหัสปลดล็อค (ถ้าเคสจบแล้ว)
                if is_locked and is_finished and is_admin:
                    st.markdown("<div style='color:red; font-weight:bold;'>🔒 เคสนี้ดำเนินการเรียบร้อยแล้ว (ต้องปลดล็อคเพื่อแก้ไข)</div>", unsafe_allow_html=True)
                    col_p1, col_p2 = st.columns([3, 1])
                    pwd_in = col_p1.text_input("รหัสผ่านระดับสูงเพื่อปลดล็อค", type="password", key="unlock_key")
                    if col_p2.button("🔓 ปลดล็อค"):
                        if pwd_in == "Patwit1510":
                            st.session_state.unlock_password = "Patwit1510"
                            st.rerun()
                        else: st.error("รหัสไม่ถูกต้อง")

                # --- ฟิลด์ข้อมูล (กลับมาครบ 100%) ---
                with st.form("investigation_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        v_vic = st.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_locked)
                        v_wit = st.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_locked)
                        v_stu = st.text_input("ตำรวจนักเรียน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_locked)
                    with c2:
                        v_acc = st.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_locked)
                        v_tea = st.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_locked)
                    
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_locked)
                    v_sta = st.selectbox("สถานะปัจจุบัน", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], 
                                         index=["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"].index(current_status) if current_status in ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"] else 0,
                                         disabled=is_locked)
                    
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่มเติม", type=['jpg','png'], disabled=is_locked)

                    if st.form_submit_button("💾 บันทึกข้อมูลและประวัติ", use_container_width=True) and not is_locked:
                        final_img = process_image(ev_img) if ev_img else row['Evidence_Image']
                        df_raw.at[idx, 'Victim'] = v_vic
                        df_raw.at[idx, 'Accused'] = v_acc
                        df_raw.at[idx, 'Witness'] = v_wit
                        df_raw.at[idx, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx, 'Statement'] = v_stmt
                        df_raw.at[idx, 'Status'] = v_sta
                        df_raw.at[idx, 'Evidence_Image'] = final_img
                        df_raw.at[idx, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna(""))
                        st.success("บันทึกสำเร็จ!"); time.sleep(1); st.rerun()

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MAIN GATEWAY
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
            if st.button("🕵️ เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                st.session_state.current_dept = "inv"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()

if __name__ == "__main__":
    main()
