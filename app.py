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
# 1. INITIAL SETTINGS
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

# ดึงโลโก้สำหรับ PDF
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), None)
def get_base64_image(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
LOGO_BASE64 = get_base64_image(LOGO_PATH)

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

# --- [เพิ่มจุดที่ 1] ฟังก์ชันสร้าง PDF (ยกมาจากโค้ดสอบสวนเดิม) ---
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    qr = qrcode.make(rid)
    qr_io = io.BytesIO()
    qr.save(qr_io, format="PNG")
    qr_b64 = base64.b64encode(qr_io.getvalue()).decode()
    logo_html = f'<img style="width:60px;" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    
    html_content = f"""
    <html>
    <head><style>@font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
    body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
    .header {{ text-align: center; position: relative; }} .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
    .box {{ border: 1px solid #000; padding: 10px; min-height: 80px; margin-top: 5px; white-space: pre-wrap; }}</style></head>
    <body><div class="header">{logo_html}<div style="font-size: 20pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
    <div>ใบสรุปรายงานเหตุการณ์และผลการสอบสวน</div><img class="qr" src="data:image/png;base64,{qr_b64}"></div><hr>
    <p><b>เลขที่:</b> {rid} | <b>วันที่แจ้ง:</b> {row.get('Timestamp','-')}</p>
    <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภท:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
    <p><b>รายละเอียดเหตุการณ์:</b></p><div class="box">{row.get('Details','-')}</div>
    <p><b>ผลการสอบสวน:</b></p><div class="box">{row.get('Statement','-')}</div><br>
    <table style="width:100%; text-align:center;"><tr>
    <td>ลงชื่อ..........................<br>({row.get('Victim','-')})<br>ผู้เสียหาย</td>
    <td>ลงชื่อ..........................<br>({row.get('Accused','-')})<br>ผู้ถูกกล่าวหา</td>
    </tr></table></body></html>
    """
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

# ==========================================
# 2. MODULE: INVESTIGATION
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None, 'view_mode': 'list'}), width='stretch')
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        df_raw = conn.read(ttl="0")
        df_display = df_raw.copy().fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            st.title(f"🏢 ระบบสอบสวน คุณ{user['name']}")
            # ... (ส่วนหน้ารายการคงเดิม) ...
            for idx, row in df_display.head(10).iterrows():
                if st.button(f"📝 {row['Report_ID']}", key=f"btn_{idx}", use_container_width=True):
                    st.session_state.update({'selected_case_id': row['Report_ID'], 'view_mode': 'detail'})
                    st.rerun()

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx_in_raw = sel.index[0]
                row = sel.iloc[0]
                
                # --- ส่วนแสดงรายละเอียดและรูปภาพ (รักษาของเดิมไว้ครบ) ---
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียดเหตุการณ์:** {row['Details']}")
                    if clean_val(row['Image_Data']):
                        st.image(base64.b64decode(row['Image_Data']), width=400, caption="หลักฐานจากผู้แจ้ง")

                # --- ส่วนฟอร์มบันทึกข้อมูล (รักษาของเดิมไว้ครบ) ---
                current_status = clean_val(row['Status'])
                is_admin = user.get('role') == 'admin'
                is_locked = True if (current_status == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510") else False
                
                if is_locked and is_admin:
                    st.warning("🔒 เคสนี้ดำเนินการเรียบร้อยแล้ว ใส่รหัส Patwit1510 เพื่อปลดล็อค")
                    pwd_in = st.text_input("รหัสปลดล็อค", type="password")
                    if st.button("ยืนยันปลดล็อค"):
                        if pwd_in == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("edit_case_form"):
                    col1, col2 = st.columns(2)
                    v_vic = col1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_locked)
                    v_acc = col2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_locked)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_locked)
                    v_sta = col2.selectbox("สถานะ", ["รอดำเนินการ", "ดำเนินการเรียบร้อย"], index=0, disabled=is_locked)
                    ev_img = st.file_uploader("📸 รูปหลักฐานเพิ่มเติม", type=['jpg','png'], disabled=is_locked)

                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_locked:
                        final_img = process_image(ev_img) if ev_img else row['Evidence_Image']
                        df_raw.at[idx_in_raw, 'Victim'] = v_vic
                        df_raw.at[idx_in_raw, 'Statement'] = v_stmt
                        df_raw.at[idx_in_raw, 'Status'] = v_sta
                        df_raw.at[idx_in_raw, 'Evidence_Image'] = final_img
                        conn.update(data=df_raw.fillna(""))
                        st.success("บันทึกแล้ว"); st.rerun()

                # --- [เพิ่มจุดที่ 2] ปุ่ม PDF (ไม่ยุ่งส่วนอื่น) ---
                st.divider()
                try:
                    pdf_data = create_pdf(row)
                    st.download_button(label="📥 ดาวน์โหลดสรุปสำนวน (PDF)", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except: st.error("สร้าง PDF ไม่สำเร็จ")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# MAIN ENTRY
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
            elif st.session_state.current_dept == "tra": st.title("🚦 ระบบจราจร"); st.sidebar.button("⬅️ กลับ", on_click=lambda: st.session_state.update({'current_dept': None}))

if __name__ == "__main__":
    main()
