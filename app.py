import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time
from PIL import Image

# PDF Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import plotly.express as px

# ==========================================
# 1. INITIAL SETTINGS & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# สร้าง Session State ให้ครบถ้วนตามความต้องการของระบบเดิม
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'current_user': None, 'view_mode': 'list', 'selected_case_id': None,
    'unlock_password': "", 'page_pending': 1, 'page_finished': 1,
    'search_query': ""
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# --- ระบบค้นหาโลโก้ ---
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

def safe_ensure_columns_for_view(df):
    required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    df_new = df.copy()
    for col in required_cols:
        if col not in df_new.columns: df_new[col] = ""
    return df_new

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    start_idx = (st.session_state[key] - 1) * limit
    return start_idx, start_idx + limit, st.session_state[key], total_pages

def process_image(img_file):
    if img_file is None: return ""
    try:
        img = Image.open(img_file)
        if img.mode in ('RGBA', 'LA', 'P'): img = img.convert('RGB')
        img.thumbnail((800, 800))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except: return ""

def view_case(rid):
    st.session_state.selected_case_id = rid
    st.session_state.view_mode = "detail"
    st.session_state.unlock_password = ""

def back_to_list():
    st.session_state.view_mode = "list"
    st.session_state.selected_case_id = None

# ==========================================
# 2. PDF SYSTEM (ต้นฉบับ 100% - ลายเซ็น 5 คน + Footer)
# ==========================================
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    date_str = str(row.get('Timestamp', ''))
    
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

    qr = qrcode.make(rid); qi = io.BytesIO(); qr.save(qi, format="PNG")
    qr_base64 = base64.b64encode(qi.getvalue()).decode()

    # Image logic for PDF
    img_html = ""
    for k in ['Image_Data', 'Evidence_Image']:
        if clean_val(row.get(k)):
            img_html += f'<div style="text-align:center;margin-top:10px;"><img src="data:image/jpeg;base64,{row[k]}" style="max-width:380px;max-height:220px;object-fit:contain;border:1px solid #ccc;"></div>'

    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""

    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            @page {{
                size: A4; margin: 2cm;
                @bottom-right {{ content: "ผู้พิมพ์: {printer_name} | เวลา: {print_time} | หน้า " counter(page); font-family: 'THSarabunNew'; font-size: 12pt; }}
            }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
            .header {{ text-align: center; position: relative; min-height: 80px; }}
            .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; min-height: 50px; white-space: pre-wrap; }}
            .sig-table {{ width: 100%; margin-top: 30px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div style="font-size: 22pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div style="font-size: 18pt;">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_base64}">
        </div>
        <hr>
        <table style="width:100%;">
            <tr>
                <td width="60%"><b>เลขที่รับแจ้ง:</b> {rid}</td>
                <td width="40%" style="text-align:right;"><b>วันที่แจ้ง:</b> {date_str}<br><b>วันที่บันทึกผล:</b> {latest_date}</td>
            </tr>
        </table>
        <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
        <div style="margin-top:10px;"><b>รายละเอียดเหตุการณ์:</b></div><div class="box">{row.get('Details','-')}</div>
        <div><b>ผลการดำเนินการสอบสวน:</b></div><div class="box">{row.get('Statement','-')}</div>
        {img_html}
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
# 3. MODULE: INVESTIGATION (100% UNMODIFIED UI)
# ==========================================
def investigation_module():
    st.session_state.current_user = st.session_state.user_info
    user = st.session_state.current_user
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # --- DASHBOARD HEADER ---
    col_h1, col_h2, col_h3 = st.columns([1, 4, 1])
    with col_h1:
        if LOGO_PATH: st.image(LOGO_PATH, width=80)
    with col_h2:
        st.markdown(f"<div style='font-size: 26px; font-weight: bold; color: #1E3A8A; padding-top: 20px;'>🏢 ระบบสอบสวน คุณ{user['name']}</div>", unsafe_allow_html=True)
    with col_h3:
        if st.button("🔴 Logout", key="inv_logout", use_container_width=True):
            st.session_state.clear(); st.rerun()

    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            
            with tab_list:
                # ระบบค้นหา
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหา", placeholder="เลขเคส, ชื่อ, หรือเหตุการณ์...", key="search_query_main", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา", use_container_width=True)
                if c_btn_clear.button("❌ ล้าง", use_container_width=True): st.rerun()

                filtered = df_display.copy()
                if search_q:
                    filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                # การกรองเคส (Pending / Finished)
                df_p = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_f = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                # --- ⏳ รายการที่รอการดำเนินการ ---
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start_p, end_p, cur_p, tot_p = calculate_pagination('page_pending', len(df_p), 5)
                h1, h2, h3, h4 = st.columns([2.5, 2, 3, 1.5])
                h1.markdown("**เลขที่รับแจ้ง**"); h2.markdown("**วันเวลา**"); h3.markdown("**ประเภทเหตุ**"); h4.markdown("**สถานะ**")
                st.divider()
                
                if df_p.empty: st.caption("ไม่มีรายการ")
                for i, row in df_p.iloc[start_p:end_p].iterrows():
                    rid = row['Report_ID']
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {rid}", key=f"p_{i}", use_container_width=True, on_click=view_case, args=(rid,))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type'])
                    cc4.markdown("<span style='color:orange;font-weight:bold'>⏳ รอสอบสวน</span>", unsafe_allow_html=True)
                    st.divider()
                
                if tot_p > 1:
                    cp1, cp2, cp3 = st.columns([1, 2, 1])
                    if cp1.button("⬅️ ย้อนกลับ (รอ)", disabled=(cur_p==1)): st.session_state.page_pending -= 1; st.rerun()
                    cp2.markdown(f"<div style='text-align:center;'>หน้า {cur_p} / {tot_p}</div>", unsafe_allow_html=True)
                    if cp3.button("ถัดไป (รอ) ➡️", disabled=(cur_p==tot_p)): st.session_state.page_pending += 1; st.rerun()

                # --- ✅ รายการที่ดำเนินการเรียบร้อย ---
                st.markdown("---")
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, cur_f, tot_f = calculate_pagination('page_finished', len(df_f), 5)
                h1f, h2f, h3f, h4f = st.columns([2.5, 2, 3, 1.5])
                h1f.markdown("**เลขที่รับแจ้ง**"); h2f.markdown("**วันเวลา**"); h3f.markdown("**ประเภทเหตุ**"); h4f.markdown("**สถานะ**")
                st.divider()

                if df_f.empty: st.caption("ไม่มีรายการที่ดำเนินการเรียบร้อย")
                for i, row in df_f.iloc[start_f:end_f].iterrows():
                    rid = row['Report_ID']
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {rid}", key=f"f_{i}", use_container_width=True, on_click=view_case, args=(rid,))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type'])
                    cc4.markdown("<span style='color:green;font-weight:bold'>✅ เรียบร้อย</span>", unsafe_allow_html=True)
                    st.divider()

            with tab_dash:
                # --- สถิติภาพรวม ---
                total_cases = len(df_display)
                if not df_display.empty:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("แจ้งเหตุทั้งหมด", f"{total_cases} ครั้ง")
                    m2.metric("สถานที่เกิดเหตุบ่อยสุด", df_display['Location'].mode()[0])
                    m3.metric("เหตุที่เกิดบ่อยสุด", df_display['Incident_Type'].mode()[0])
                    st.divider()
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**🔹 ประเภทเหตุ**"); st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2:
                        st.markdown("**🔹 สถานที่เกิดเหตุ**"); st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=back_to_list, use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                idx_raw = sel.index[0]; row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                    # การแสดงรูปภาพ (ปรับขนาด 500px)
                    if clean_val(row['Image_Data']):
                        st.image(base64.b64decode(row['Image_Data']), width=500, caption="หลักฐานจากผู้แจ้ง")

                is_admin = user.get('role') == 'admin'
                cur_sta = clean_val(row['Status'])
                is_lock = (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510")
                if not is_admin: is_lock = True

                if is_lock and cur_sta == "ดำเนินการเรียบร้อย" and is_admin:
                    st.error("🔒 เคสนี้ดำเนินการเรียบร้อยแล้ว (ใช้รหัส Patwit1510 เพื่อแก้ไข)")
                    pwd_in = st.text_input("รหัสปลดล็อก", type="password")
                    if st.button("ยืนยันปลดล็อก"):
                        if pwd_in == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("full_inv_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_lock)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_lock)
                    v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_lock)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_lock)
                    v_stu = c1.text_input("ตำรวจนักเรียน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_lock)
                    v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=is_lock)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_lock)
                    ev_img_file = st.file_uploader("📸 แนบรูปหลักฐานเพิ่มเติม", type=['jpg','png'], disabled=is_lock)

                    if st.form_submit_button("💾 บันทึกข้อมูลและประวัติ") and not is_lock:
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Witness'] = v_wit; df_raw.at[idx_raw, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx_raw, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx_raw, 'Statement'] = v_stmt; df_raw.at[idx_raw, 'Status'] = v_sta
                        if ev_img_file: df_raw.at[idx_raw, 'Evidence_Image'] = process_image(ev_img_file)
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกเรียบร้อย!"); time.sleep(1); st.rerun()

                # --- 🖨️ ปุ่มดาวน์โหลด PDF ---
                st.divider()
                try:
                    pdf_data = create_pdf(row)
                    st.download_button(label="📥 ดาวน์โหลดสรุปสำนวน (PDF)", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except Exception as e: st.error(f"สร้าง PDF ขัดข้อง: {e}")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 4. MAIN GATEWAY
# ==========================================
def main():
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align:center;'>👮‍♂️ Central Login</h2>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accs = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_in in accs:
                        st.session_state.logged_in = True; st.session_state.user_info = accs[pwd_in]; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", width='stretch', type='primary'):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", width='stretch', type='primary'):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": 
                st.title("🚦 ระบบจราจร"); st.sidebar.button("⬅️ กลับ", on_click=lambda: setattr(st.session_state, 'current_dept', None))

if __name__ == "__main__": main()
