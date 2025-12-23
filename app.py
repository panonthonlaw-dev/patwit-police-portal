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

# คืนค่า Session State ทุกตัวตามที่โค้ดเดิมต้องการ (ห้ามลบ)
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None, 'current_user': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query_main': "",
    'reset_count': 0, 'traffic_page': 'teacher', 'search_results_df': None, 'edit_data': None,
    'df_tra': None, 'current_user_pwd': "", 'last_active': time.time()
}
for key, val in states.items():
    if key not in st.session_state:
        st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")

# --- ระบบค้นหาโลโก้ ---
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), 
                 next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))

def get_base64_image(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
LOGO_BASE64 = get_base64_image(LOGO_PATH)

# Common Helpers
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
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except: return ""

# ==========================================
# 2. MODULE: INVESTIGATION (Copy-Paste เดิม 100%)
# ==========================================
# ห้ามแก้ไขฟังก์ชันและถ้อยคำในก้อนนี้เด็ดขาด

def safe_ensure_columns_for_view_inv(df):
    required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    df_new = df.copy()
    for col in required_cols:
        if col not in df_new.columns: df_new[col] = ""
    return df_new

def calculate_pagination_inv(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    start_idx = (st.session_state[key] - 1) * limit
    return start_idx, start_idx + limit, st.session_state[key], total_pages

def create_pdf_inv(row):
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
    p_name = st.session_state.user_info.get('name', 'System')
    p_time = get_now_th().strftime("%d/%m/%Y %H:%M:%S")
    qr = qrcode.make(rid); qi = io.BytesIO(); qr.save(qi, format="PNG"); qr_b64 = base64.b64encode(qi.getvalue()).decode()
    
    img_html = ""
    if clean_val(row.get('Evidence_Image')):
        img_html = f"<div style='margin-top:10px;page-break-inside:avoid;'><b>หลักฐานประกอบ:</b><br><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-height:150px;border:1px solid #ccc;'></div>"
    
    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    html_content = f"""
    <html><head><style>@font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
    @page {{ size: A4; margin: 2cm; @bottom-right {{ content: "ผู้พิมพ์: {p_name} | เวลา: {p_time} | หน้า " counter(page); font-family: 'THSarabunNew'; font-size: 12pt; }} }}
    body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
    .header {{ text-align: center; position: relative; min-height: 80px; }} .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
    .qr {{ position: absolute; top: 0; right: 0; width: 60px; }} .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; min-height: 50px; white-space: pre-wrap; }}
    .sig-table {{ width: 100%; margin-top: 30px; text-align: center; }}
    </style></head><body>
    <div class="header">{logo_html}<div style="font-size: 22pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
    <div style="font-size: 18pt;">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div><img class="qr" src="data:image/png;base64,{qr_base64}"></div><hr>
    <table style="width:100%;"><tr><td width="60%"><b>เลขที่รับแจ้ง:</b> {rid}</td><td width="40%" style="text-align:right;"><b>วันที่แจ้ง:</b> {date_str}<br><b>วันที่บันทึกผล:</b> {latest_date}</td></tr></table>
    <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
    <div style="margin-top:10px;"><b>รายละเอียดเหตุการณ์:</b></div><div class="box">{row.get('Details','-')}</div>
    <div><b>ผลการดำเนินการสอบสวน:</b></div><div class="box">{row.get('Statement','-')}</div>{img_html}
    <table class="sig-table">
        <tr><td width="50%">ลงชื่อ..........................................................<br>( {row.get('Victim','')} )<br>ผู้เสียหาย</td><td width="50%">ลงชื่อ..........................................................<br>( {row.get('Accused','')} )<br>ผู้ถูกกล่าวหา</td></tr>
        <tr><td>ลงชื่อ..........................................................<br>( {row.get('Student_Police_Investigator','')} )<br>ตำรวจนักเรียนผู้สอบสวน</td><td>ลงชื่อ..........................................................<br>( {row.get('Witness','')} )<br>พยาน</td></tr>
        <tr><td colspan="2"><br>ลงชื่อ..........................................................<br>( {row.get('Teacher_Investigator','')} )<br>ครูผู้สอบสวน</td></tr>
    </table></body></html>"""
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

def investigation_module():
    st.session_state.current_user = st.session_state.user_info
    user = st.session_state.current_user
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
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
        df_display = safe_ensure_columns_for_view_inv(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหา", placeholder="เลขเคส, ชื่อ, หรือเหตุการณ์...", key="search_query_main", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา", use_container_width=True)
                if c_btn_clear.button("❌ ล้าง", use_container_width=True): st.rerun()
                filtered = df_display.copy()
                if search_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_p = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_f = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start_p, end_p, cur_p, tot_p = calculate_pagination_inv('page_pending', len(df_p), 5)
                h1, h2, h3, h4 = st.columns([2.5, 2, 3, 1.5])
                h1.markdown("**เลขที่รับแจ้ง**"); h2.markdown("**วันเวลา**"); h3.markdown("**ประเภทเหตุ**"); h4.markdown("**สถานะ**")
                st.divider()
                if df_p.empty: st.caption("ไม่มีรายการ")
                for i, row in df_p.iloc[start_p:end_p].iterrows():
                    rid = row['Report_ID']
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {rid}", key=f"p_{i}", use_container_width=True, on_click=lambda r=rid: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.markdown("<span style='color:orange;font-weight:bold'>⏳ รอ</span>", unsafe_allow_html=True); st.divider()
                
                if tot_p > 1:
                    cp1, cp2, cp3 = st.columns([1, 2, 1])
                    if cp1.button("⬅️ ย้อนกลับ (รอ)", disabled=(cur_p==1)): st.session_state.page_pending -= 1; st.rerun()
                    cp2.markdown(f"<div style='text-align:center;'>หน้า {cur_p} / {tot_p}</div>", unsafe_allow_html=True)
                    if cp3.button("ถัดไป (รอ) ➡️", disabled=(cur_p==tot_p)): st.session_state.page_pending += 1; st.rerun()

                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, cur_f, tot_f = calculate_pagination_inv('page_finished', len(df_f), 5)
                for i, row in df_f.iloc[start_f:end_f].iterrows():
                    rid = row['Report_ID']
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {rid}", key=f"f_{i}", use_container_width=True, on_click=lambda r=rid: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.markdown("<span style='color:green;font-weight:bold'>✅ เรียบร้อย</span>", unsafe_allow_html=True); st.divider()

            with tab_dash:
                tc = len(df_display)
                if tc > 0:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("แจ้งเหตุทั้งหมด", f"{tc} ครั้ง"); m2.metric("สถานที่บ่อยสุด", df_display['Location'].mode()[0]); m3.metric("เหตุบ่อยสุด", df_display['Incident_Type'].mode()[0])
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📌 สรุปยอดตามสถานที่ (Top 5)**")
                        for l, c in df_display['Location'].value_counts().head(5).items():
                            p = (c/tc)*100; st.markdown(f"- **{l}**: {c} ครั้ง <span style='color:red;'>({p:.1f}%)</span>", unsafe_allow_html=True)
                    with c2:
                        st.markdown("**📌 สรุปยอดตามประเภทเหตุ**")
                        for t, c in df_display['Incident_Type'].value_counts().head(5).items():
                            p = (c/tc)*100; st.markdown(f"- **{t}**: {c} ครั้ง <span style='color:red;'>({p:.1f}%)</span>", unsafe_allow_html=True)
                    col1, col2 = st.columns(2)
                    with col1: st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2: st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list'}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx_raw = sel.index[0]; row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}"); st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']): st.image(base64.b64decode(row['Image_Data']), width=500)
                cur_sta = clean_val(row['Status']); is_lock = (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510")
                if user.get('role') != 'admin': is_lock = True
                if is_lock and cur_sta == "ดำเนินการเรียบร้อย" and user.get('role') == 'admin':
                    pwd = st.text_input("รหัสปลดล็อก", type="password")
                    if st.button("ยืนยันปลดล็อก"):
                        if pwd == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()
                with st.form("full_inv_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_lock)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_lock)
                    v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_lock)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_lock)
                    v_stu = c1.text_input("ตำรวจนักเรียน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_lock)
                    v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=is_lock)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_lock)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่ม", type=['jpg','png'], disabled=is_lock)
                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_lock:
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Witness'] = v_wit; df_raw.at[idx_raw, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx_raw, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx_raw, 'Statement'] = v_stmt; df_raw.at[idx_raw, 'Status'] = v_sta
                        if ev_img: df_raw.at[idx_raw, 'Evidence_Image'] = process_image(ev_img)
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกแล้ว!"); time.sleep(1); st.rerun()
                st.divider()
                try:
                    pdf_data = create_pdf_inv(row)
                    st.download_button(label="📥 ดาวน์โหลด PDF", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except: st.error("PDF ขัดข้อง")
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ไส้ใน 100% - แก้จุด Syntax และดึงข้อมูล)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    st.markdown("""<style>
        .metric-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .metric-value { font-size: 2.5rem; font-weight: 800; color: #1e293b; }
        .metric-percent { font-size: 1.1rem; color: #16a34a; font-weight: bold; }
    </style>""", unsafe_allow_html=True)

    def load_tra_data():
        try:
            kd = json.loads(st.secrets["textkey"]["json_content"].replace('\n', '\\n'), strict=False)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(kd, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
            sh = gspread.authorize(creds).open(SHEET_NAME_TRAFFIC).sheet1
            vals = sh.get_all_values()
            if len(vals) > 1:
                st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])])
                return True
        except: return False

    def get_img_tra(url):
        m = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
        fid = m.group(1) or m.group(2) if m else None
        return f"https://drive.google.com/thumbnail?id={fid}&sz=w800" if fid else url

    def create_pdf_tra(vals, img_url1, img_url2, face_url=None, printed_by="ระบบอัตโนมัติ"):
        buffer = io.BytesIO(); c = canvas.Canvas(buffer, pagesize=A4); width, height = A4
        if os.path.exists(FONT_FILE):
            pdfmetrics.registerFont(TTFont('Thai', FONT_FILE))
            pdfmetrics.registerFont(TTFont('ThaiBold', FONT_BOLD if os.path.exists(FONT_BOLD) else FONT_FILE))
            fn, fb = 'Thai', 'ThaiBold'
        else: fn, fb = 'Helvetica', 'Helvetica-Bold'
        logo = next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None)
        if logo: c.drawImage(logo, 50, height - 85, width=50, height=50, mask='auto')
        c.setFont(fb, 22); c.drawCentredString(width/2, height - 50, "แบบทะเบียนประวัติรถจักรยานยนต์นักเรียน")
        c.setFont(fn, 18); c.drawCentredString(width/2, height - 72, "โรงเรียนโพนทองพัฒนาวิทยา"); c.line(50, height - 85, width - 50, height - 85)
        name, std_id, plate, score = str(vals[1]), str(vals[2]), str(vals[6]), str(vals[13])
        c.setFont(fn, 16); c.drawString(60, height - 115, f"ชื่อ-นามสกุล: {name}"); c.drawString(60, height - 135, f"รหัสนักเรียน: {std_id}"); c.drawString(300, height - 155, f"ทะเบียน: {plate}")
        c.setFont(fb, 18); c.drawString(60, height - 185, f"คะแนนความประพฤติคงเหลือ: {score} คะแนน")
        def draw_img(url, x, y, w, h):
            try:
                res = requests.get(url, timeout=5); img_data = ImageReader(io.BytesIO(res.content))
                c.drawImage(img_data, x, y, width=w, height=h, preserveAspectRatio=True, mask='auto'); c.rect(x, y, w, h)
            except: pass
        draw_img(img_url1, 70, height - 415, 180, 180); draw_img(img_url2, 300, height - 415, 180, 180)
        pt = (datetime.now() + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M'); c.setFont(fn, 10); c.drawRightString(width-30, 20, f"พิมพ์โดย: {printed_by} | {pt}"); c.save(); buffer.seek(0); return buffer

    if st.session_state.df_tra is None:
        with st.spinner("⏳ กำลังโหลดฐานข้อมูลจราจร..."): load_tra_data()

    if st.session_state.df_tra is not None:
        df = st.session_state.df_tra
        col_u, col_l = st.columns([3, 1])
        col_u.info(f"👤 ผู้ใช้งานจราจร: {user['name']} (สิทธิ์: {user['role']})")
        if col_l.button("🚪 Logout", key="tra_logout"): st.session_state.clear(); st.rerun()

        if st.session_state.traffic_page == 'teacher':
            c1, c2 = st.columns(2)
            if c1.button("🔄 ดึงข้อมูลล่าสุด", use_container_width=True): load_tra_data(); st.rerun()
            if c2.button("📊 รายงานสถิติ", use_container_width=True): st.session_state.traffic_page = 'dash'; st.rerun()
            total = len(df); lok = df[df.iloc[:,7].str.contains("มี", na=False)].shape[0]; tok = df[df.iloc[:,8].str.contains("ปกติ|✅", na=False)].shape[0]; hok = df[df.iloc[:,9].str.contains("มี", na=False)].shape[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">รถทั้งหมด</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-card"><div class="metric-value">{lok}</div><div class="metric-percent">{(lok/total*100) if total else 0:.1f}%</div><div class="metric-label">ใบขับขี่</div></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-card"><div class="metric-value">{tok}</div><div class="metric-percent">{(tok/total*100) if total else 0:.1f}%</div><div class="metric-label">ภาษี</div></div>', unsafe_allow_html=True)
            m4.markdown(f'<div class="metric-card"><div class="metric-value">{hok}</div><div class="metric-percent">{(hok/total*100) if total else 0:.1f}%</div><div class="metric-label">หมวก</div></div>', unsafe_allow_html=True)
            st.markdown("---")
            search_q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_search")
            res_df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)] if search_q else df.head(10)
            for i, row in res_df.iterrows():
                v = row.tolist()
                with st.expander(f"📍 {v[6]} | {v[1]}"):
                    st.markdown(f"### 👤 {v[1]} (รหัส: {v[2]})"); ci1, ci2, ci3 = st.columns(3)
                    ci1.image(get_img_tra(v[14]), caption="เจ้าของรถ"); ci2.image(get_img_tra(v[10]), caption="หลังรถ"); ci3.image(get_img_tra(v[11]), caption="ข้างรถ")
                    st.download_button(f"📥 โหลด PDF {v[6]}", create_pdf_tra(v, get_img_tra(v[10]), get_img_tra(v[11]), get_img_tra(v[14]), user['name']), f"{v[6]}.pdf")
        elif st.session_state.traffic_page == 'dash':
            if st.button("⬅️ กลับหน้าจัดการ"): st.session_state.traffic_page = 'teacher'; st.rerun()
            st.plotly_chart(px.pie(df, names=df.columns[7], title="สัดส่วนใบขับขี่"), use_container_width=True)

# ==========================================
# 4. MAIN ENTRY
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
                        st.session_state.logged_in = True; st.session_state.user_info = accs[pwd_in]
                        st.session_state.current_user_pwd = pwd_in; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type="primary"):
                        st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__": main()
