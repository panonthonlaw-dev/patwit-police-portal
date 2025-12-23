import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time, ast
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# PDF & Chart Libraries
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
# 1. INITIAL SETTINGS & SESSION MANAGEMENT
# ==========================================
st.set_page_config(page_title="ศูนย์ปฏิบัติการกลางฯ", page_icon="👮‍♂️", layout="wide", initial_sidebar_state="collapsed")

# --- 1.1 CSS ปรับแต่งเพื่อความไวสูงสุด (NO ANIMATION) ---
st.markdown("""
<style>
    /* ปิด Animation ทั้งหมดเพื่อความเร็วสูงสุดและลดภาระเครื่อง */
    * { animation: none !important; transition: none !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;} [data-testid="collapsedControl"] {display: none;}
    
    /* สไตล์ Metric Card สำหรับงานจราจร */
    .metric-card { 
        background: white; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #e2e8f0; 
        text-align: center; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
    }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 0.85rem; color: #64748b; font-weight: bold; }
    .pct-green { color: #16a34a; font-size: 0.85rem; font-weight: bold; }
    img { opacity: 1 !important; }
</style>
""", unsafe_allow_html=True)

# --- 1.2 Session & Timeout Logic (15 นาที) ---
TIMEOUT_SECONDS = 15 * 60 

def check_inactivity():
    if 'last_active' not in st.session_state:
        st.session_state.last_active = time.time()
        return
    if time.time() - st.session_state.last_active > TIMEOUT_SECONDS:
        st.session_state.clear()
        st.session_state.timeout_msg = "⏳ หมดเวลาการเชื่อมต่อ (15 นาที) กรุณาเข้าสู่ระบบใหม่"
        st.rerun()
    else:
        st.session_state.last_active = time.time()

check_inactivity()

# Session States
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None, 'current_user': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query_main': "",
    'traffic_page': 'teacher', 'df_tra': None, 'search_results_df': None, 
    'current_user_pwd': "", 'edit_data': None, 'reset_count': 0
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")
FONT_BOLD = os.path.join(BASE_DIR, "THSarabunNewBold.ttf")

# Configs
SHEET_NAME_TRAFFIC = "Motorcycle_DB"
DRIVE_FOLDER_ID = "1WQGATGaGBoIjf44Yj_-DjuX8LZ8kbmBA"
GAS_APP_URL = "https://script.google.com/macros/s/AKfycbxRf6z032SxMkiI4IxtUBvWLKeo1LmIQAUMByoXidy4crNEwHoO6h0B-3hT0X7Q5g/exec"
UPGRADE_PASSWORD = st.secrets.get("UPGRADE_PASSWORD", "Patwitsafe")
OFFICER_ACCOUNTS = st.secrets.get("OFFICER_ACCOUNTS", {})

# Logo
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), 
                 next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: LOGO_BASE64 = base64.b64encode(f.read()).decode()

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""
def process_image(img_file):
    if not img_file: return ""
    try:
        img = Image.open(img_file).convert('RGB'); img.thumbnail((800, 800))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=65); return base64.b64encode(buf.getvalue()).decode()
    except: return ""

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    start_idx = (st.session_state[key] - 1) * limit
    end_idx = start_idx + limit
    return start_idx, end_idx, st.session_state[key], total_pages

def get_img_link(url):
    if not url or pd.isna(url): return None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

def connect_gsheet_universal():
    if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
        try:
            key_str = st.secrets["textkey"]["json_content"].strip()
            if key_str.startswith(("'","\"")): key_str = key_str[1:-1]
            creds_dict = json.loads(key_str.replace('\n', '\\n'), strict=False)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)).open(SHEET_NAME_TRAFFIC).sheet1
        except: pass
    return None

# ==========================================
# 2. MODULE: INVESTIGATION (ต้นฉบับ 100% - คำทางการครบ)
# ==========================================
def create_pdf_inv(row):
    rid = str(row.get('Report_ID', '')); date_str = str(row.get('Timestamp', ''))
    audit_log = str(row.get('Audit_Log', '')); latest_date = "-"
    if audit_log:
        try:
            lines = [l for l in audit_log.split('\n') if l.strip()]
            if lines and '[' in lines[-1] and ']' in lines[-1]: latest_date = lines[-1][lines[-1].find('[')+1:lines[-1].find(']')]
        except: pass
    p_name = st.session_state.user_info.get('name', 'System'); p_time = get_now_th().strftime("%d/%m/%Y %H:%M:%S")
    qr = qrcode.make(rid); qi = io.BytesIO(); qr.save(qi, format="PNG"); qr_b64 = base64.b64encode(qi.getvalue()).decode()
    img_html = ""
    if clean_val(row.get('Evidence_Image')):
        img_html += f"<div style='text-align:center;margin-top:10px;'><b>พยานหลักฐาน</b><br><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-width:380px;max-height:220px;object-fit:contain;border:1px solid #ccc;'></div>"
    if clean_val(row.get('Image_Data')):
        img_html += f"<div style='text-align:center;margin-top:10px;'><b>ภาพประกอบเหตุการณ์</b><br><img src='data:image/jpeg;base64,{row.get('Image_Data')}' style='max-width:380px;max-height:220px;object-fit:contain;border:1px solid #ccc;'></div>"
    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    html_content = f"""
    <html><head><style>@font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
    @page {{ size: A4; margin: 2cm; @bottom-right {{ content: "ผู้พิมพ์: {p_name} | เวลา: {p_time} | หน้า " counter(page); font-family: 'THSarabunNew'; font-size: 12pt; }} }}
    body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
    .header {{ text-align: center; position: relative; min-height: 80px; }} .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
    .qr {{ position: absolute; top: 0; right: 0; width: 60px; }} .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; min-height: 50px; white-space: pre-wrap; }}
    .sig-table {{ width: 100%; margin-top: 30px; text-align: center; border-collapse: collapse; }} .sig-table td {{ padding-bottom: 25px; vertical-align: top; }}
    </style></head><body><div class="header">{logo_html}<div style="font-size: 22pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
    <div style="font-size: 18pt;">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div><img class="qr" src="data:image/png;base64,{qr_b64}"></div><hr>
    <table style="width:100%;"><tr><td width="60%"><b>เลขที่รับแจ้ง:</b> {rid}</td><td width="40%" style="text-align:right;"><b>วันที่แจ้ง:</b> {date_str}<br><b>วันที่บันทึกผล:</b> {latest_date}</td></tr></table>
    <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
    <div style="margin-top:10px;"><b>รายละเอียดเหตุการณ์:</b></div><div class="box">{row.get('Details','-')}</div>
    <div><b>ผลการดำเนินการสอบสวน:</b></div><div class="box">{row.get('Statement','-')}</div>{img_html}
    <table class="sig-table"><tr><td width="50%">ลงชื่อ..........................................................<br>( {row.get('Victim','')} )<br>ผู้เสียหาย</td><td width="50%">ลงชื่อ..........................................................<br>( {row.get('Accused','')} )<br>ผู้ถูกกล่าวหา</td></tr>
    <tr><td>ลงชื่อ..........................................................<br>( {row.get('Student_Police_Investigator','')} )<br>ตำรวจนักเรียนผู้สอบสวน</td><td>ลงชื่อ..........................................................<br>( {row.get('Witness','')} )<br>พยาน</td></tr>
    <tr><td colspan="2"><br>ลงชื่อ..........................................................<br>( {row.get('Teacher_Investigator','')} )<br>ครูผู้สอบสวน</td></tr></table></body></html>"""
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

def investigation_module():
    user = st.session_state.user_info
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">🕵️ ระบบงานสอบสวน</span> | ผู้เข้าใช้: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); st.write("")
        b_h, b_l = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="inv_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_l.button("🚪 ออก", key="inv_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = df_raw.copy().fillna("")
        for c in ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']:
            if c not in df_display.columns: df_display[c] = ""
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหา", key="inv_q", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา")
                if c_btn_clear.button("❌ ล้าง"): st.rerun()
                filtered = df_display.copy()
                if search_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                df_p = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_f = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start_p, end_p, cur_p, tot_p = calculate_pagination('page_pending', len(df_p), 5)
                for i, row in df_p.iloc[start_p:end_p].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {row['Report_ID']}", key=f"inv_p_{i}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.warning(row['Status']); st.divider()
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, cur_f, tot_f = calculate_pagination('page_finished', len(df_f), 5)
                for i, row in df_f.iloc[start_f:end_f].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {row['Report_ID']}", key=f"inv_f_{i}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.success("เรียบร้อย"); st.divider()
            with tab_dash:
                tc = len(df_display)
                if tc > 0:
                    m1, m2, m3 = st.columns(3); m1.metric("แจ้งเหตุทั้งหมด", f"{tc} ครั้ง"); m2.metric("สถานที่เกิดเหตุบ่อยสุด", df_display['Location'].mode()[0]); m3.metric("เหตุที่เกิดบ่อยสุด", df_display['Incident_Type'].mode()[0])
                    st.divider(); c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📌 สรุปยอดตามสถานที่ (Top 5)**")
                        for l, c in df_display['Location'].value_counts().head(5).items(): st.markdown(f"- **{l}**: {c} ครั้ง <span style='color:red;'>({(c/tc)*100:.1f}%)</span>", unsafe_allow_html=True)
                    with c2: st.markdown("**🔹 ประเภทเหตุ**"); st.bar_chart(df_display['Incident_Type'].value_counts())
        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list'}), use_container_width=True)
            sid = st.session_state.selected_case_id; row = df_display[df_display['Report_ID'] == sid].iloc[0]
            st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
            with st.form("full_inv_form"):
                c1, c2 = st.columns(2); v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim'])); v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused'])); v_wit = c1.text_input("พยาน", value=clean_val(row['Witness'])); v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator'])); v_stu = c1.text_input("ตำรวจนักเรียนผู้สอบสวน *", value=clean_val(row['Student_Police_Investigator'])); v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0); v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']))
                if st.form_submit_button("💾 บันทึกข้อมูล"):
                    df_raw.at[df_display[df_display['Report_ID']==sid].index[0], 'Statement'] = v_stmt; df_raw.at[df_display[df_display['Report_ID']==sid].index[0], 'Status'] = v_sta
                    df_raw.at[df_display[df_display['Report_ID']==sid].index[0], 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                    conn.update(data=df_raw.fillna("")); st.success("บันทึกเรียบร้อย!"); time.sleep(1); st.rerun()
            st.download_button("📥 โหลด PDF (สำนวนคดี)", create_pdf_inv(row), f"Report_{sid}.pdf", use_container_width=True)
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (คืนระบบค้นหา กรอง เปอร์เซ็นต์ และสถานะ)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.session_state.officer_name, st.session_state.officer_role = user.get('name', 'N/A'), user.get('role', 'teacher')
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f"""<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">🚦 ระบบงานจราจร</span> | ผู้เข้าใช้: {st.session_state.officer_name}</div></div>""", unsafe_allow_html=True)
    with c_nav:
        st.write(""); st.write(""); b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="tra_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="tra_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    if st.session_state.df_tra is None:
        try:
            sheet = connect_gsheet_universal(); vals = sheet.get_all_values()
            if len(vals) > 1: st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])])
        except: pass

    if st.session_state.traffic_page == 'teacher':
        if st.session_state.df_tra is not None:
            df_full = st.session_state.df_tra; total = len(df_full); has_lic = len(df_full[df_full['C7'].str.contains("มี", na=False)]); has_tax = len(df_full[df_full['C8'].str.contains("ปกติ|✅", na=False)]); has_hel = len(df_full[df_full['C9'].str.contains("มี", na=False)])
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-card'><div class='metric-label'>ลงทะเบียน</div><div class='metric-value'>{total} คน</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-card'><div class='metric-label'>ใบขับขี่</div><div class='metric-value'>{has_lic} <span class='pct-green'>({(has_lic/total)*100:.1f}%)</span></div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric-card'><div class='metric-label'>ภาษีปกติ</div><div class='metric-value'>{has_tax} <span class='pct-green'>({(has_tax/total)*100:.1f}%)</span></div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='metric-card'><div class='metric-label'>มีหมวก</div><div class='metric-value'>{has_hel} <span class='pct-green'>({(has_hel/total)*100:.1f}%)</span></div></div>", unsafe_allow_html=True)
        st.write("")
        c_btn1, c_btn2 = st.columns(2)
        if c_btn1.button("🔄 ดึงข้อมูลล่าสุด"): st.session_state.df_tra = None; st.session_state.search_results_df = None; st.rerun()
        if c_btn2.button("📊 รายงานสถิติ"): st.session_state.traffic_page = 'dash'; st.rerun()
        
        q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_search_input")
        c_s, c_cl = st.columns([4, 1])
        do_s = c_s.button("ค้นหา", type="primary", use_container_width=True)
        if c_cl.button("ล้างค่า", use_container_width=True): st.session_state.search_results_df = None; st.rerun()
        
        st.caption("▼ ตัวกรองข้อมูล"); col_f1, col_f2, col_f3 = st.columns(3); u_lv, u_br = [], []
        if st.session_state.df_tra is not None:
            u_lv = sorted(list(set([str(x).split('/')[0] for x in st.session_state.df_tra.iloc[:, 3].unique()]))); u_br = sorted(list(set(st.session_state.df_tra.iloc[:, 4].unique())))
        f_risk = col_f1.selectbox("🚨 กลุ่มปัญหา:", ["ทั้งหมด", "❌ ไม่มีใบขับขี่", "❌ ภาษีขาด", "❌ ไม่สวมหมวก"]); f_lv = col_f2.selectbox("📚 ระดับชั้น:", ["ทั้งหมด"] + u_lv); f_br = col_f3.selectbox("🏍️ ยี่ห้อรถ:", ["ทั้งหมด"] + u_br)
        
        if do_s or st.button("⚡ กรองข้อมูลตามเงื่อนไข", use_container_width=True):
            st.session_state.search_results_df = None
            if not q.strip() and f_risk == "ทั้งหมด" and f_lv == "ทั้งหมด" and f_br == "ทั้งหมด": st.error("⚠️ กรุณากรอกข้อมูล")
            elif st.session_state.df_tra is not None:
                df = st.session_state.df_tra.copy()
                if q.strip(): df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
                if f_risk != "ทั้งหมด": idx = 7 if "ใบขับขี่" in f_risk else (8 if "ภาษี" in f_risk else 9); df = df[df.iloc[:, idx].astype(str).str.contains("ไม่มี|ขาด")]
                if f_lv != "ทั้งหมด": df = df[df.iloc[:, 3].astype(str).str.contains(f_lv)]
                if f_br != "ทั้งหมด": df = df[df.iloc[:, 4] == f_br]
                if len(df) == len(st.session_state.df_tra) and not q.strip(): st.warning("ℹ️ ข้อมูลกว้างเกินไป"); st.session_state.search_results_df = None
                else: st.session_state.search_results_df = df

        if st.session_state.search_results_df is not None:
            tdf = st.session_state.search_results_df
            if tdf.empty: st.warning("❌ ไม่พบข้อมูล")
            else:
                st.success(f"ค้นพบ {len(tdf)} รายการ")
                for i, row in tdf.iterrows():
                    v = row.tolist(); sc = int(v[13]) if len(v)>13 and str(v[13]).isdigit() else 100
                    with st.expander(f"📍 {v[6]} | {v[1]}"):
                        st.markdown(f"**สถานะเอกสาร:** 🪪 ใบขับขี่: {v[7]} | 📝 ภาษี: {v[8]} | 🪖 หมวก: {v[9]}")
                        st.write(f"คะแนน: {sc}"); st.image(get_img_link(v[14]), width=200)
                        if st.session_state.officer_role == "admin":
                            with st.form(key=f"sc_f_{i}"):
                                pts = st.number_input("แต้ม", 1, 50, 5); nt = st.text_area("เหตุผล"); pwd = st.text_input("รหัสยืนยัน", type="password")
                                if st.form_submit_button("🔴 หักแต้ม") and nt and pwd == st.session_state.current_user_pwd:
                                    s = connect_gsheet_universal(); cell = s.find(str(v[2])); ns = max(0, sc-pts); action = "หัก"; tn = get_now_th().strftime('%d/%m/%Y %H:%M'); old_log = str(v[12]).strip() if str(v[12]).lower()!="nan" else ""; new_log = f"{old_log}\n[{tn}] {action} {pts} คะแนน: {nt}"; s.update(f'M{cell.row}:N{cell.row}', [[new_log, str(ns)]]); st.success("บันทึกแล้ว"); st.session_state.df_tra = None; st.rerun()

        if st.session_state.current_user_pwd == "Patwit1510":
            with st.expander("⚙️ ระบบจัดการเลื่อนชั้นเรียน (Super Admin Only)"):
                up_pwd = st.text_input("รหัสเลื่อนชั้น", type="password", key="prom_pwd")
                if st.button("ยืนยันเลื่อนชั้น", use_container_width=True) and up_pwd == UPGRADE_PASSWORD:
                    s = connect_gsheet_universal(); d = s.get_all_values(); h = d[0]; r = d[1:]; nr = []
                    for row in r:
                        ol = str(row[3]); nl = ol
                        if "ม.1" in ol: nl=ol.replace("ม.1","ม.2")
                        elif "ม.6" in ol: nl="จบการศึกษา 🎓"
                        row[3] = nl; nr.append(row)
                    s.clear(); s.update('A1', [h] + nr); st.success("สำเร็จ!"); st.session_state.df_tra = None; st.rerun()
    elif st.session_state.traffic_page == 'dash':
        if st.button("⬅️ กลับ"): st.session_state.traffic_page = 'teacher'; st.rerun()
        if st.session_state.df_tra is not None:
            df = st.session_state.df_tra.copy(); df.columns = [f"Col_{i}" for i in range(len(df.columns))] 
            c1, c2, c3 = st.columns(3)
            with c1: st.plotly_chart(px.pie(df, names='Col_7', title="ใบขับขี่", hole=0.3), use_container_width=True)
            with c2: st.plotly_chart(px.pie(df, names='Col_8', title="ภาษี", hole=0.3), use_container_width=True)
            with c3: st.plotly_chart(px.pie(df, names='Col_9', title="หมวก", hole=0.3), use_container_width=True)

# ==========================================
# 4. MODULE: ANALYTICS (หัวข้อไว้ก่อน ห้ามทำอย่างอื่น)
# ==========================================
def analytics_module():
    st.header("📊 วิเคราะห์พฤติกรรม")
    st.info("💡 ส่วนนี้เป็นพื้นที่สำหรับหัวข้อวิเคราะห์ข้อมูลพฤติกรรมศาสตร์ในอนาคต")

# ==========================================
# 5. MAIN ENTRY (แก้ไข Syntax Error)
# ==========================================
def main():
    if 'timeout_msg' in st.session_state and st.session_state.timeout_msg: st.error(st.session_state.timeout_msg); del st.session_state.timeout_msg
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                if LOGO_PATH: st.image(LOGO_PATH, width=120)
                st.markdown("<h3 style='text-align:center;'>ศูนย์ปฏิบัติการกลาง<br>สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h3>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    if pwd_in in OFFICER_ACCOUNTS:
                        st.session_state.logged_in = True; st.session_state.user_info = OFFICER_ACCOUNTS[pwd_in]; st.session_state.current_user_pwd = pwd_in; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            c_br, c_nav = st.columns([7, 2.5])
            with c_br:
                c_lo, c_tx = st.columns([1, 6])
                with c_lo: 
                    if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
                with c_tx: st.markdown('<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;">🏢 เลือกแผนกปฏิบัติงาน</div></div>', unsafe_allow_html=True)
            with c_nav:
                st.write(""); st.write("")
                if st.button("🚪 ออกจากระบบ", key="m_logout", use_container_width=True): st.session_state.clear(); st.rerun()
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", key="btn_inv", use_container_width=True, type='primary'):
                        st.session_state.view_mode = "list"
                        st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", key="btn_tra", use_container_width=True, type='primary'):
                        st.session_state.current_dept = "tra"; st.session_state.traffic_page = 'teacher'; st.session_state.search_results_df = None; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าใช้งาน Analytics", key="btn_ana", use_container_width=True, type='primary'):
                        st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
