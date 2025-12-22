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

# --- ระบบค้นหาโลโก้โรงเรียน ---
LOGO_PATH = None
LOGO_MIME = "image/png"
target_file = os.path.join(BASE_DIR, "school_logo")
if os.path.exists(target_file):
    LOGO_PATH = target_file
else:
    possible_logos = glob.glob(os.path.join(BASE_DIR, "school_logo*"))
    for f in possible_logos:
        if os.path.isfile(f):
            LOGO_PATH = f; break

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

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

# --- ฟังก์ชันสร้าง PDF (ยกมาทั้งก้อนจากโค้ดสอบสวนดั้งเดิม) ---
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    date_str = str(row.get('Timestamp', ''))
    reporter = str(row.get('Reporter', '-'))
    incident = str(row.get('Incident_Type', '-'))
    location = str(row.get('Location', '-'))
    details = str(row.get('Details', '-'))
    statement = str(row.get('Statement', '-'))
    
    audit_log = str(row.get('Audit_Log', ''))
    latest_date = "-"
    if audit_log:
        try:
            lines = [line for line in audit_log.split('\n') if line.strip()]
            if lines:
                last_line = lines[-1]
                if '[' in last_line and ']' in last_line:
                    latest_date = last_line[last_line.find('[')+1 : last_line.find(']')]
        except: pass

    printer_name = st.session_state.user_info.get('name', 'System')
    print_time = get_now_th().strftime("%d/%m/%Y %H:%M:%S")

    qr = qrcode.make(rid)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    evidence_html = f"<div style='margin-top: 10px; page-break-inside: avoid;'><b>หลักฐานประกอบ:</b><br><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-height: 150px;'></div>" if row.get('Evidence_Image') else ""
    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""

    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; margin: 20px; }}
            .header {{ text-align: center; position: relative; min-height: 100px; }}
            .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .title {{ font-size: 20pt; font-weight: bold; }}
            .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; margin-bottom: 10px; min-height: 80px; white-space: pre-wrap; }}
            .sig-table {{ width: 100%; margin-top: 30px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div class="title">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div style="font-size: 18pt;">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_base64}">
        </div>
        <hr>
        <p><b>เลขที่รับแจ้ง:</b> {rid} | <b>วันที่แจ้ง:</b> {date_str} | <b>วันที่บันทึกผล:</b> {latest_date}</p>
        <p><b>ผู้แจ้ง:</b> {reporter} | <b>ประเภทเหตุ:</b> {incident} | <b>สถานที่:</b> {location}</p>
        <p><b>รายละเอียดเหตุการณ์:</b></p>
        <div class="box">{details}</div>
        <p><b>ผลการดำเนินการสอบสวน:</b></p>
        <div class="box">{statement}</div>
        {evidence_html}
        <table class="sig-table">
            <tr>
                <td>ลงชื่อ.........................................<br>({row.get('Victim', '-')})<br>ผู้เสียหาย</td>
                <td>ลงชื่อ.........................................<br>({row.get('Accused', '-')})<br>ผู้ถูกกล่าวหา</td>
            </tr>
        </table>
        <div style="text-align:center; margin-top: 20px;">
            ลงชื่อ.........................................<br>({row.get('Teacher_Investigator', '-')})<br>ครูผู้สอบสวน
        </div>
        <p style="font-size: 10pt; text-align: right; margin-top: 20px;">ผู้พิมพ์: {printer_name} | เวลา: {print_time}</p>
    </body>
    </html>
    """
    font_config = FontConfiguration()
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=font_config)

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
            st.title(f"🏢 ระบบสอบสวน คุณ{user['name']}")
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                df_pending = df_display[df_display['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                for idx, row in df_pending.head(10).iterrows():
                    raw_rid = row['Report_ID']
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {raw_rid}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=raw_rid: (st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'})))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("⏳ รอ")
                    st.divider()

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx = sel.index[0]
                row = sel.iloc[0]
                
                # --- ระบบป้องกัน (LOCK LOGIC) ---
                current_status = clean_val(row['Status'])
                is_admin = user.get('role') == 'admin'
                is_finished = (current_status == "ดำเนินการเรียบร้อย")
                is_locked = True if (is_finished and st.session_state.unlock_password != "Patwit1510") else False
                if not is_admin: is_locked = True 

                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']):
                        st.image(base64.b64decode(row['Image_Data']), width=400, caption="หลักฐานจากผู้แจ้ง")
                
                st.divider()
                st.write("#### ✍️ บันทึกผลการสอบสวน")

                if is_locked and is_finished and is_admin:
                    st.markdown("<div style='color:red; font-weight:bold;'>🔒 เคสนี้ดำเนินการเรียบร้อยแล้ว (ต้องปลดล็อคเพื่อแก้ไข)</div>", unsafe_allow_html=True)
                    col_p1, col_p2 = st.columns([3, 1])
                    pwd_in = col_p1.text_input("รหัสผ่านระดับสูงเพื่อปลดล็อค", type="password", key="unlock_key")
                    if col_p2.button("🔓 ปลดล็อค"):
                        if pwd_in == "Patwit1510":
                            st.session_state.unlock_password = "Patwit1510"
                            st.rerun()
                        else: st.error("รหัสไม่ถูกต้อง")

                # --- ฟิลด์ข้อมูลและฟอร์มบันทึก ---
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

                # --- ส่วนของ PDF (กลับมาแล้ว!) ---
                st.markdown("---")
                with st.container(border=True):
                    st.markdown("#### 🖨️ เมนูพิมพ์รายงาน")
                    col_pdf1, col_pdf2 = st.columns([3, 1])
                    col_pdf1.caption("ดาวน์โหลดรายงานสรุปสำนวนคดีในรูปแบบ PDF เพื่อใช้เป็นหลักฐานและบันทึกประวัติ")
                    try:
                        pdf_data = create_pdf(row)
                        col_pdf2.download_button(label="📥 ดาวน์โหลด PDF", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                    except Exception as e:
                        col_pdf2.error("สร้าง PDF ไม่สำเร็จ")
                        st.caption(f"Error: {e}")

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
