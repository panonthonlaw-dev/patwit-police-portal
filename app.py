import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import pytz, os, base64, io, qrcode, glob, math, time
from PIL import Image

# PDF Libraries
try:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
except: pass

# ==========================================
# 1. INITIAL SETTINGS
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# Session States ครบถ้วนตามระบบเดิม
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# ระบบโลโก้โรงเรียน
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

# --- ฟังก์ชันสร้าง PDF (แก้ไขให้ดึงรูปภาพใส่ใน PDF ด้วย) ---
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    qr = qrcode.make(rid)
    qr_buffer = io.BytesIO(); qr.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
    
    logo_html = f'<img style="width:60px;" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    
    # ดึงรูปภาพหลักฐาน (ถ้ามี) เพื่อใส่ใน PDF
    img_data_b64 = clean_val(row.get('Image_Data'))
    evidence_img_b64 = clean_val(row.get('Evidence_Image'))
    
    image_section_html = ""
    # ถ้ามีรูปจากผู้แจ้ง
    if img_data_b64:
        image_section_html += f"""
        <p><b>รูปภาพหลักฐานจากผู้แจ้งเหตุ:</b></p>
        <div style="text-align:center;"><img src="data:image/jpeg;base64,{img_data_b64}" style="max-width: 400px; max-height: 300px; border: 1px solid #ccc;"></div>
        """
    # ถ้ามีรูปหลักฐานเพิ่มเติมจากผู้สอบสวน
    if evidence_img_b64:
        image_section_html += f"""
        <p><b>รูปภาพหลักฐานเพิ่มเติมจากการสอบสวน:</b></p>
        <div style="text-align:center;"><img src="data:image/jpeg;base64,{evidence_img_b64}" style="max-width: 400px; max-height: 300px; border: 1px solid #ccc;"></div>
        """

    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; padding: 20px; }}
            .header {{ text-align: center; position: relative; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; padding: 10px; margin-bottom: 10px; min-height: 80px; white-space: pre-wrap; }}
            img {{ display: block; margin: 10px auto; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div style="font-size: 20pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div>ใบสรุปรายงานเหตุการณ์และผลการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_base64}">
        </div>
        <hr>
        <p><b>เลขที่รับแจ้ง:</b> {rid} | <b>วันที่แจ้ง:</b> {row.get('Timestamp','-')}</p>
        <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
        
        <p><b>รายละเอียดเหตุการณ์:</b></p>
        <div class="box">{row.get('Details','-')}</div>
        
        <p><b>ผลการดำเนินการสอบสวน:</b></p>
        <div class="box">{row.get('Statement','-')}</div>
        
        {image_section_html}  <br>
        <table style="width:100%; text-align:center; margin-top: 20px;">
            <tr>
                <td>ลงชื่อ.........................................<br>({row.get('Victim','-')})<br>ผู้เสียหาย</td>
                <td>ลงชื่อ.........................................<br>({row.get('Accused','-')})<br>ผู้ถูกกล่าวหา</td>
            </tr>
        </table>
        <div style="text-align:center; margin-top: 20px;">
            ลงชื่อ.........................................<br>({row.get('Teacher_Investigator', '-')})<br>ครูผู้สอบสวน
        </div>
    </body>
    </html>
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
        # แปลง Report_ID เป็น String ป้องกันความผิดพลาดในการค้นหา
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            st.title(f"🏢 ระบบสอบสวน คุณ{user['name']}")
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            
            with tab_list:
                df_pending = df_display[df_display['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_finished = df_display[df_display['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                for idx, row in df_pending.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {row['Report_ID']}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("⏳ รอ")
                    st.divider()

                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่เรียบร้อย</h4>", unsafe_allow_html=True)
                for idx, row in df_finished.head(10).iterrows():
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"✅ {row['Report_ID']}", key=f"f_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type']); c4.write("✅ จบ")
                    st.divider()

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx_raw = sel.index[0]
                row = sel.iloc[0]
                
                # --- ส่วนแสดงรายละเอียดและรูปภาพ (จุดสำคัญที่เคยหายไป) ---
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                    
                    # การดึงรูปภาพ Image_Data (จากฐานข้อมูล)
                    img_data = clean_val(row['Image_Data'])
                    if img_data:
                        try:
                            st.image(base64.b64decode(img_data), width=500, caption="📸 รูปภาพประกอบจากผู้แจ้ง")
                        except: st.warning("ไม่สามารถแสดงรูปภาพหลักฐานได้")

                # ระบบล็อกการแก้ไข
                is_admin = user.get('role') == 'admin'
                is_locked = (clean_val(row['Status']) == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510")
                if not is_admin: is_locked = True

                if is_locked and clean_val(row['Status']) == "ดำเนินการเรียบร้อย" and is_admin:
                    pwd = st.text_input("ปลดล็อกการแก้ไข (Patwit1510)", type="password")
                    if st.button("🔓 ปลดล็อก"):
                        if pwd == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                # ฟอร์มบันทึกผลการสอบสวน
                with st.form("edit_case_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_locked)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_locked)
                    v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_locked)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_locked)
                    v_stu = c1.text_input("ตำรวจนักเรียน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_locked)
                    v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=is_locked)
                    v_stmt = st.text_area("ผลการสอบสวน *", value=clean_val(row['Statement']), disabled=is_locked)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่ม", type=['jpg','png'], disabled=is_locked)

                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_locked:
                        df_raw.at[idx_raw, 'Victim'] = v_vic
                        df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Statement'] = v_stmt
                        df_raw.at[idx_raw, 'Status'] = v_sta
                        if ev_img: df_raw.at[idx_raw, 'Evidence_Image'] = process_image(ev_img)
                        conn.update(data=df_raw.fillna(""))
                        st.success("บันทึกข้อมูลเรียบร้อย!"); time.sleep(1); st.rerun()

                # ปุ่มสร้าง PDF (เพิ่มเข้าไปโดยไม่กระทบส่วนอื่น)
                st.divider()
                try:
                    pdf_data = create_pdf(row)
                    st.download_button(label="📥 ดาวน์โหลดใบสรุปคดี (PDF)", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except: st.error("ไม่สามารถสร้าง PDF ได้ในขณะนี้")

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
                    accs = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accs:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accs[pwd]
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
            elif st.session_state.current_dept == "tra": 
                st.sidebar.button("⬅️ กลับ", on_click=lambda: st.session_state.update({'current_dept': None}))
                st.title("🚦 ระบบจราจร")

if __name__ == "__main__":
    main()
