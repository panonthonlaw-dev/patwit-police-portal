import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, json, time, re
from PIL import Image

# PDF Libraries
try:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
except:
    pass

# ==========================================
# 1. INITIAL SETTINGS
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_info' not in st.session_state: st.session_state.user_info = {}
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'selected_case_id' not in st.session_state: st.session_state.selected_case_id = None
if 'unlock_password' not in st.session_state: st.session_state.unlock_password = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# ระบบโลโก้
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), None)
def get_base64_image(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
LOGO_BASE64 = get_base64_image(LOGO_PATH)

def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val):
    if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
    return str(val).strip()

# ==========================================
# 2. PDF SYSTEM (คืนค่าลายเซ็นและ Footer ครบ 100%)
# ==========================================
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    qr = qrcode.make(rid)
    qr_buffer = io.BytesIO(); qr.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    
    # ดึงวันเวลาล่าสุดจาก Audit Log (ตาม Logic เดิมของคุณ)
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

    img_data_b64 = clean_val(row.get('Image_Data'))
    evidence_img_b64 = clean_val(row.get('Evidence_Image'))
    
    image_html = ""
    if img_data_b64:
        image_html += f'<div style="text-align:center;"><p><b>หลักฐานจากผู้แจ้ง:</b></p><img src="data:image/jpeg;base64,{img_data_b64}" style="max-width: 350px; max-height: 200px; object-fit: contain;"></div>'
    if evidence_img_b64:
        image_html += f'<div style="text-align:center;"><p><b>หลักฐานเพิ่มเติม:</b></p><img src="data:image/jpeg;base64,{evidence_img_b64}" style="max-width: 350px; max-height: 200px; object-fit: contain;"></div>'

    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            @page {{
                size: A4; margin: 2cm;
                @bottom-right {{
                    content: "ผู้พิมพ์: {printer_name} | เวลา: {print_time} | หน้า " counter(page);
                    font-family: 'THSarabunNew'; font-size: 12pt;
                }}
            }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
            .header {{ text-align: center; position: relative; min-height: 80px; }}
            .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; padding: 10px; margin-bottom: 10px; min-height: 50px; white-space: pre-wrap; }}
            .sig-table {{ width: 100%; margin-top: 20px; text-align: center; }}
            .sig-table td {{ padding-bottom: 20px; vertical-align: top; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div style="font-size: 22pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div style="font-size: 18pt; font-weight: bold;">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_base64}">
        </div>
        <hr>
        <table style="width:100%;">
            <tr>
                <td><b>เลขที่รับแจ้ง:</b> {rid}</td>
                <td style="text-align:right;"><b>วันที่แจ้ง:</b> {row.get('Timestamp','-')}<br><b>วันที่บันทึกผล:</b> {latest_date}</td>
            </tr>
        </table>
        <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
        <p><b>รายละเอียดเหตุการณ์:</b></p><div class="box">{row.get('Details','-')}</div>
        <p><b>ผลการดำเนินการสอบสวน:</b></p><div class="box">{row.get('Statement','-')}</div>
        {image_html}
        <table class="sig-table">
            <tr>
                <td width="50%">ลงชื่อ..........................................................<br>( {row.get('Victim','')} )<br>ผู้เสียหาย</td>
                <td width="50%">ลงชื่อ..........................................................<br>( {row.get('Accused','')} )<br>ผู้ถูกกล่าวหา</td>
            </tr>
            <tr>
                <td>ลงชื่อ..........................................................<br>( {row.get('Student_Police_Investigator','')} )<br>ตำรวจนักเรียนผู้สอบสวน</td>
                <td>ลงชื่อ..........................................................<br>( {row.get('Witness','')} )<br>พยาน</td>
            </tr>
            <tr>
                <td colspan="2"><br>ลงชื่อ..........................................................<br>( {row.get('Teacher_Investigator','')} )<br>ครูผู้สอบสวน</td>
            </tr>
        </table>
    </body>
    </html>
    """
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

# ==========================================
# 3. MODULE: INVESTIGATION (หน้าตาเดิมครบ 100%)
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
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                df_p = df_display[df_display['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                for idx, row in df_p.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {row['Report_ID']}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("⏳ รอ")
                    st.divider()

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx_raw = sel.index[0]; row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']): st.image(base64.b64decode(row['Image_Data']), width=500)

                is_locked = (clean_val(row['Status']) == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510")
                if is_locked and st.session_state.user_info['role'] == 'admin':
                    pwd = st.text_input("ปลดล็อกแก้ไข (Patwit1510)", type="password")
                    if st.button("🔓 ปลดล็อก"):
                        if pwd == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("full_edit_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย", value=clean_val(row['Victim']), disabled=is_locked)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา", value=clean_val(row['Accused']), disabled=is_locked)
                    v_wit = c2.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_locked)
                    v_stu = c1.text_input("ตำรวจนักเรียน", value=clean_val(row['Student_Police_Investigator']), disabled=is_locked)
                    v_tea = c2.text_input("ครูผู้สอบสวน", value=clean_val(row['Teacher_Investigator']), disabled=is_locked)
                    v_sta = c1.selectbox("สถานะ", ["รอดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=is_locked)
                    v_stmt = st.text_area("ผลการสอบสวน", value=clean_val(row['Statement']), disabled=is_locked)
                    if st.form_submit_button("💾 บันทึก"):
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Witness'] = v_wit; df_raw.at[idx_raw, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx_raw, 'Teacher_Investigator'] = v_tea; df_raw.at[idx_raw, 'Statement'] = v_stmt
                        df_raw.at[idx_raw, 'Status'] = v_sta
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกสำเร็จ!"); st.rerun()

                # ปุ่มสร้าง PDF
                try:
                    pdf_data = create_pdf(row)
                    st.download_button(label="📥 ดาวน์โหลด PDF (สำนวนคดี)", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except Exception as e: st.error(f"PDF Error: {e}")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 4. MAIN ENTRY
# ==========================================
def main():
    if not st.session_state.logged_in:
        # หน้า Login... (เหมือนเดิม)
        st.title("🔐 Central Login")
        pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
        if st.button("เข้าสู่ระบบ"):
            accs = st.secrets.get("OFFICER_ACCOUNTS", {})
            if pwd in accs: st.session_state.logged_in = True; st.session_state.user_info = accs[pwd]; st.rerun()
    else:
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            if st.button("🕵️ เข้าใช้งานสอบสวน", use_container_width=True):
                st.session_state.current_dept = "inv"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()

if __name__ == "__main__": main()
