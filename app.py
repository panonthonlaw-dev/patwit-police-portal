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

# --- 1.1 CSS ปรับแต่งเพื่อลดภาระเครื่อง (NO ANIMATION / MAX SPEED) ---
st.markdown("""
<style>
    /* 1. ปิด Animation/Transition/Transform ทั้งหมดแบบถาวร */
    *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        transform: none !important; /* ปิดเอฟเฟกต์เด้ง/ขยายเวลาชี้ */
        scroll-behavior: auto !important;
    }

    /* 2. ซ่อนส่วนประกอบระบบที่ไม่จำเป็น (แถบสีรุ้งด้านบน/Footer) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;} 
    .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    
    /* 3. ปรับแต่ง Card ให้เบา (เอาเงาออก) */
    .metric-card { 
        background: white; 
        padding: 10px; 
        border-radius: 8px; 
        border: 1px solid #d1d5db; /* ใช้เส้นธรรมดาแทนเงา */
        text-align: center; 
        box-shadow: none !important; /* ปิดเงา ลดภาระ GPU */
    }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 0.9rem; color: #64748b; }
    
    /* 4. บังคับแสดงผลภาพแบบเร็ว */
    img { opacity: 1 !important; image-rendering: -webkit-optimize-contrast; }
</style>
""", unsafe_allow_html=True)

# --- 1.2 Session & Timeout Logic (60 นาที + กัน Refresh หลุด) ---
TIMEOUT_SECONDS = 60 * 60  # ตั้งเวลา 60 นาที

def check_inactivity():
    # 1. ตรวจสอบเวลา Timeout
    if 'last_active' not in st.session_state:
        st.session_state.last_active = time.time()
        
    if time.time() - st.session_state.last_active > TIMEOUT_SECONDS:
        st.session_state.clear()
        st.query_params.clear() # ล้างค่าใน URL ด้วย
        st.session_state.timeout_msg = "⏳ หมดเวลาการเชื่อมต่อ (60 นาที) กรุณาเข้าสู่ระบบใหม่"
        st.rerun()
    else:
        st.session_state.last_active = time.time()

    # 2. ระบบกู้คืนสถานะเมื่อกด Refresh (ดึงค่าจาก URL กลับมา)
    if not st.session_state.get('logged_in') and st.query_params.get("logged_in") == "true":
        st.session_state.logged_in = True
        st.session_state.user_info = {
            'name': st.query_params.get("name", ""),
            'role': st.query_params.get("role", "")
        }
        st.session_state.current_user_pwd = st.query_params.get("pwd", "")
        st.rerun() # รีโหลดเพื่อเข้าสู่ระบบทันที

    # 3. บันทึกสถานะปัจจุบันลง URL (เพื่อให้กด Refresh แล้วไม่หาย)
    if st.session_state.get('logged_in'):
        # อัปเดต URL เฉพาะเมื่อค่ายังไม่ตรง
        if st.query_params.get("logged_in") != "true":
            st.query_params["logged_in"] = "true"
            st.query_params["name"] = st.session_state.user_info.get("name", "")
            st.query_params["role"] = st.session_state.user_info.get("role", "")
            st.query_params["pwd"] = st.session_state.current_user_pwd

check_inactivity()

# Session States
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None, 'current_user': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query_main': "",
    'traffic_page': 'teacher', 'df_tra': None, 'search_results_df': None, 
    'current_user_pwd': "", 'edit_data': None, 'reset_count': 0,
    'preserve_search': False
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

# ==========================================
# 2. MODULE: INVESTIGATION
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
            st.markdown(f"""
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%;">
                <div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
                <div style="font-size: 16px; color: #475569; margin-top: 4px;">
                    <span style="font-weight: bold;">🕵️ ระบบงานสอบสวน</span> | ผู้เข้าใช้: {user['name']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    with c_nav:
        st.write("")
        st.write("")
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", use_container_width=True, key="inv_home_btn"):
            setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="inv_logout_btn", use_container_width=True):
            st.query_params.clear()  # <--- เพิ่มบรรทัดนี้ เพื่อล้างค่าใน URL
            st.session_state.clear()
            st.rerun()
            
    
    # --- [ส่วนที่เพิ่ม: คำนวณปีการศึกษา (พ.ค. - เม.ย.) + เผื่อปีหน้า] ---
    now_th = get_now_th()
    current_buddhist_year = now_th.year + 543
    
    # Logic: ตัดรอบปีการศึกษาที่เดือน 5 (พฤษภาคม)
    if now_th.month >= 5:
        current_ac_year = current_buddhist_year
    else:
        current_ac_year = current_buddhist_year - 1

    # สร้างตัวเลือกปี: เอาปีหน้า (เผื่อไว้) + ปีปัจจุบัน + ย้อนหลัง 3 ปี
    # เช่น ถ้าปีการศึกษาปัจจุบันคือ 2568 -> จะได้ [2569, 2568, 2567, 2566, 2565]
    start_year = current_ac_year + 1  # เริ่มต้นที่ปีหน้า (2569)
    year_options = [str(start_year - i) for i in range(5)] # สร้างรายการ 5 ปี

    c_year_filter, _ = st.columns([2, 8])
    with c_year_filter:
        # index=1 คือให้ Default เป็นปีปัจจุบัน (ตัวเลือกที่ 2 ในลิสต์)
        sel_year = st.selectbox("📅 เลือกปีการศึกษา", year_options, index=1, key="inv_year_sel")
    
    # สร้างชื่อชีตเป้าหมาย (ต้องตรงกับชื่อ Tab ใน Google Sheets)
    target_sheet = f"Investigation_{sel_year}"
    # ---------------------------------------------------------------------

    conn = st.connection("gsheets", type=GSheetsConnection)
    # ... (ส่วนถัดไปเหมือนเดิม conn.read ...)
    try:
        # อ่านข้อมูลจากชีตตามปีที่เลือก (ใช้ ttl=10 เพื่อความลื่นไหล)
        df_raw = conn.read(worksheet=target_sheet, ttl=10)
        
        # --- [Logic เดิม: การจัดการข้อมูล] ---
        df_display = df_raw.copy().fillna("")
        
        # ตรวจสอบและสร้างคอลัมน์ที่ขาดหายไป (ป้องกัน Error กรณีขึ้นปีใหม่แล้วหัวตารางไม่ครบ)
        required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
        for c in required_cols:
            if c not in df_display.columns: df_display[c] = ""
            
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
# --- [ส่วนที่เพิ่ม: การ์ดสถิติสรุปภาพรวม (Metric Cards)] ---
        # 1. คำนวณตัวเลข
        total_cases = len(df_display)
        pending = len(df_display[df_display['Status'] == "รอดำเนินการ"])
        process = len(df_display[df_display['Status'] == "อยู่ระหว่างการดำเนินการ"])
        finished = len(df_display[df_display['Status'] == "ดำเนินการเรียบร้อย"])

        # 2. แสดงผล 4 คอลัมน์
        m1, m2, m3, m4 = st.columns(4)
        
        # Card 1: ทั้งหมด
        m1.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">เคสปี {sel_year}</div>
            <div class="metric-value">{total_cases}</div>
        </div>
        """, unsafe_allow_html=True)

        # Card 2: รอดำเนินการ (สีส้ม/เหลือง)
        m2.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">รอดำเนินการ</div>
            <div class="metric-value" style="color: #f59e0b;">{pending}</div>
        </div>
        """, unsafe_allow_html=True)

        # Card 3: ระหว่างดำเนินการ (สีฟ้า)
        m3.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">กำลังดำเนินการ</div>
            <div class="metric-value" style="color: #3b82f6;">{process}</div>
        </div>
        """, unsafe_allow_html=True)

        # Card 4: เรียบร้อย (สีเขียว)
        m4.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">เสร็จสิ้น</div>
            <div class="metric-value" style="color: #22c55e;">{finished}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # เว้นบรรทัดให้นิดหน่อย
        # -------------------------------------------------------
        # ... (หลังจากนี้เป็นโค้ด if st.session_state.view_mode == "list": ของเดิม ปล่อยไว้เหมือนเดิม) ...

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
                start_p, end_p, cur_p, tot_p = calculate_pagination('page_pending', len(df_p), 5)
                h1, h2, h3, h4 = st.columns([2.5, 2, 3, 1.5])
                h1.markdown("**เลขที่รับแจ้ง**"); h2.markdown("**วันเวลา**"); h3.markdown("**ประเภทเหตุ**"); h4.markdown("**สถานะ**")
                st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
                
                if df_p.empty: st.caption("ไม่มีรายการ")
                for i, row in df_p.iloc[start_p:end_p].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {row['Report_ID']}", key=f"p_{i}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type'])
                    cc4.markdown(f"<span style='color:orange;font-weight:bold'>⏳ {row['Status']}</span>", unsafe_allow_html=True); st.divider()
                
                if tot_p > 1:
                    cp1, cp2, cp3 = st.columns([1, 2, 1])
                    if cp1.button("⬅️ ย้อนกลับ", disabled=st.session_state.page_pending==1, key="pp"): st.session_state.page_pending-=1; st.rerun()
                    cp2.markdown(f"<div style='text-align:center;'>{st.session_state.page_pending} / {tot_p}</div>", unsafe_allow_html=True)
                    if cp3.button("ถัดไป ➡️", disabled=st.session_state.page_pending==tot_p, key="pn"): st.session_state.page_pending+=1; st.rerun()

                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, cur_f, tot_f = calculate_pagination('page_finished', len(df_f), 5)
                for i, row in df_f.iloc[start_f:end_f].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {row['Report_ID']}", key=f"f_{i}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail', 'unlock_password': ""}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type'])
                    cc4.markdown("<span style='color:green;font-weight:bold'>✅ ดำเนินการเรียบร้อย</span>", unsafe_allow_html=True); st.divider()

            with tab_dash:
                tc = len(df_display)
                if tc > 0:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("แจ้งเหตุทั้งหมด", f"{tc} ครั้ง")
                    m2.metric("สถานที่เกิดเหตุบ่อยสุด", df_display['Location'].mode()[0] if not df_display.empty else "-")
                    m3.metric("เหตุที่เกิดบ่อยสุด", df_display['Incident_Type'].mode()[0] if not df_display.empty else "-")
                    st.markdown("---")
                    c_text1, c_text2 = st.columns(2)
                    with c_text1:
                        st.markdown("**📌 สรุปยอดตามสถานที่ (Top 5)**")
                        for l, c in df_display['Location'].value_counts().head(5).items():
                            p = (c/tc)*100; st.markdown(f"- **{l}**: {c} ครั้ง <span style='color:red; font-size:0.8em;'>({p:.1f}%)</span>", unsafe_allow_html=True)
                    with c_text2:
                        st.markdown("**📌 สรุปยอดตามประเภทเหตุ**")
                        for t, c in df_display['Incident_Type'].value_counts().head(5).items():
                            p = (c/tc)*100; st.markdown(f"- **{t}**: {c} ครั้ง <span style='color:red; font-size:0.8em;'>({p:.1f}%)</span>", unsafe_allow_html=True)
                    st.divider()
                    col1, col2 = st.columns(2)
                    with col1: st.markdown("**🔹 ประเภทเหตุ**"); st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2: st.markdown("**🔹 สถานที่เกิดเหตุ**"); st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list'}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx_raw = sel.index[0]; row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}"); st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']): st.image(base64.b64decode(row['Image_Data']), width=500, caption="หลักฐานจากผู้แจ้ง")
                cur_sta = clean_val(row['Status'])
                is_lock = (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510")
                if user.get('role') != 'admin': is_lock = True
                
                if is_lock and cur_sta == "ดำเนินการเรียบร้อย" and user.get('role') == 'admin':
                    pwd = st.text_input("รหัสปลดล็อค", type="password")
                    if st.button("ยืนยันปลดล็อค"):
                        if pwd == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("full_inv_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_lock)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_lock)
                    v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_lock)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_lock)
                    v_stu = c1.text_input("ตำรวจนักเรียนผู้สอบสวน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_lock)
                    v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"].index(cur_sta) if cur_sta in ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"] else 0, disabled=is_lock)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_lock)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่ม", type=['jpg','png'], disabled=is_lock)
                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_lock:
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Witness'] = v_wit; df_raw.at[idx_raw, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx_raw, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx_raw, 'Statement'] = v_stmt; df_raw.at[idx_raw, 'Status'] = v_sta
                        if ev_img: df_raw.at[idx_raw, 'Evidence_Image'] = process_image(ev_img)
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกเรียบร้อย!"); time.sleep(1); st.rerun()
                
                if clean_val(row['Audit_Log']):
                    with st.expander("📜 ประวัติการบันทึก (Audit Log)"): st.code(row['Audit_Log'])

                st.divider()
                try:
                    pdf_data = create_pdf_inv(row)
                    st.download_button(label="📥 ดาวน์โหลด PDF (สำนวนคดี)", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except: st.error("PDF ขัดข้อง")
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับ 100% - บังคับค้นหา)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.session_state.officer_name = user.get('name', 'N/A')
    st.session_state.officer_role = user.get('role', 'teacher')
    st.session_state.current_user_pwd = st.session_state.current_user_pwd 

    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f"""
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%;">
                <div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
                <div style="font-size: 16px; color: #475569; margin-top: 4px;">
                    <span style="font-weight: bold;">🚦 ระบบงานจราจร</span> | ผู้เข้าใช้: {st.session_state.officer_name}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    with c_nav:
        st.write("") 
        st.write("")
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", key="tra_home_btn", use_container_width=True):
            setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="inv_logout_btn", use_container_width=True):
            st.query_params.clear()  # <--- เพิ่มบรรทัดนี้ เพื่อล้างค่าใน URL
            st.session_state.clear()
            st.rerun()
    st.markdown("---")

    def connect_gsheet_universal():
        if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
            try:
                key_str = st.secrets["textkey"]["json_content"]
                key_str = key_str.strip()
                if key_str.startswith("'") and key_str.endswith("'"): key_str = key_str[1:-1]
                if key_str.startswith('"') and key_str.endswith('"'): key_str = key_str[1:-1]
                try: creds_dict = json.loads(key_str, strict=False)
                except: creds_dict = json.loads(key_str.replace('\n', '\\n'), strict=False)
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                return gspread.authorize(creds).open(SHEET_NAME_TRAFFIC).sheet1
            except: pass

        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            creds_dict = dict(st.secrets["connections"]["gsheets"])
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds).open(SHEET_NAME_TRAFFIC).sheet1
            
        raise Exception("ไม่สามารถอ่าน Credentials ได้")

    def load_tra_data():
        try:
            sheet = connect_gsheet_universal()
            vals = sheet.get_all_values()
            if len(vals) > 1:
                st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])])
                return True
        except: return False

    def upload_to_drive(file_obj, filename):
        file_content = file_obj.getvalue()
        base64_str = base64.b64encode(file_content).decode('utf-8')
        payload = {"folder_id": DRIVE_FOLDER_ID, "filename": filename, "file": base64_str, "mimeType": file_obj.type}
        try:
            res = requests.post(GAS_APP_URL, json=payload).json()
            return res.get("link") if res.get("status") == "success" else None
        except: return None

    def get_img_link(url):
        match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
        file_id = match.group(1) or match.group(2) if match else None
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

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
        c.setFont(fn, 18); c.drawCentredString(width/2, height - 72, "โรงเรียนโพนทองพัฒนาวิทยา")
        c.line(50, height - 85, width - 50, height - 85)
        name, std_id, classroom, brand, color, plate = str(vals[1]), str(vals[2]), str(vals[3]), str(vals[4]), str(vals[5]), str(vals[6])
        lic_s, tax_s, hel_s = str(vals[7]), str(vals[8]), str(vals[9])
        raw_note = str(vals[12]).strip() if len(vals) > 12 else ""
        note_text = raw_note if raw_note and raw_note.lower() != "nan" else "ไม่พบประวัติ"
        score = str(vals[13]) if len(vals) > 13 and str(vals[13]).lower() != "nan" else "100"
        c.setFont(fn, 16); c.drawString(60, height - 115, f"ชื่อ-นามสกุล: {name}"); c.drawString(300, height - 115, f"ยี่ห้อรถ: {brand}")
        c.drawString(60, height - 135, f"รหัสนักเรียน: {std_id}"); c.drawString(300, height - 135, f"สีรถ: {color}")
        c.drawString(60, height - 155, f"ระดับชั้น: {classroom}"); c.setFont(fb, 16); c.drawString(300, height - 155, f"ทะเบียน: {plate}")
        c.setFont(fb, 18); color_val = (0.7, 0, 0) if int(score) < 80 else (0, 0.5, 0); c.setFillColorRGB(*color_val)
        c.drawString(60, height - 185, f"คะแนนความประพฤติจราจรคงเหลือ: {score} คะแนน"); c.setFillColorRGB(0, 0, 0)
        c.setFont(fn, 16); lm = "(/)" if "มี" in lic_s else "( )"; tm = "(/)" if "ปกติ" in tax_s or "✅" in tax_s else "( )"; hm = "(/)" if "มี" in hel_s else "( )"
        c.drawString(60, height - 210, f"สถานะเอกสาร:  {lm} ใบขับขี่    {tm} ภาษี/พรบ.    {hm} หมวกกันน็อค")
        def draw_img(url, x, y, w, h):
            try:
                if url:
                    res = requests.get(url, timeout=5); img_data = ImageReader(io.BytesIO(res.content))
                    c.drawImage(img_data, x, y, width=w, height=h, preserveAspectRatio=True, mask='auto'); c.rect(x, y, w, h)
            except: pass
        draw_img(img_url1, 70, height - 415, 180, 180); draw_img(img_url2, 300, height - 415, 180, 180)
        note_y = height - 455; c.setFont(fb, 16); c.drawString(60, note_y, "ประวัติบันทึกการทำผิดวินัยจราจร:")
        c.setFont(fn, 15); text_obj = c.beginText(70, note_y - 25); text_obj.setLeading(20)
        for line in note_text.split('\n'):
            for w_line in textwrap.wrap(line, width=75): text_obj.textLine(w_line)
        c.drawText(text_obj)
        sign_y = 180 
        c.setFont(fn, 16); c.drawString(60, sign_y, "ลงชื่อ ......................................... เจ้าของรถ"); c.drawString(100, sign_y - 20, f"({name})")
        if face_url: draw_img(face_url, 450, height - 200, 90, 110)
        c.drawString(320, sign_y, "ลงชื่อ ......................................... ครูผู้ตรวจสอบ"); c.drawString(340, sign_y - 20, "(.........................................)")
        c.setFont(fn, 10); c.setFillColorRGB(0.5, 0.5, 0.5)
        print_time = (datetime.now() + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M')
        c.drawRightString(width - 30, 20, f"พิมพ์โดย: {printed_by} | เมื่อ: {print_time}")
        c.save(); buffer.seek(0); return buffer

    if st.session_state.df_tra is None:
        load_tra_data()

    if st.session_state.traffic_page == 'teacher':
        # --- [ส่วนสถิติภาพรวม: % อยู่ด้านล่าง + สีเขียว + ไม่มีทศนิยม] ---
        if st.session_state.df_tra is not None:
            df = st.session_state.df_tra
            total = len(df)
            # นับจำนวน
            has_lic = len(df[df['C7'].str.contains("มี", na=False)])
            has_tax = len(df[df['C8'].str.contains("ปกติ|✅", na=False)])
            has_hel = len(df[df['C9'].str.contains("มี", na=False)])
            
            # คำนวณ % เป็นจำนวนเต็ม
            p_lic = int((has_lic / total * 100)) if total > 0 else 0
            p_tax = int((has_tax / total * 100)) if total > 0 else 0
            p_hel = int((has_hel / total * 100)) if total > 0 else 0

            # แสดงผล: ใช้ <div> เพื่อแยกบรรทัด และ style บังคับสีเขียว/ขนาด
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-card'><div class='metric-label'>ลงทะเบียน</div><div class='metric-value'>{total}</div><div style='font-size:1rem; color:#64748b;'>คน</div></div>", unsafe_allow_html=True)
            
            c2.markdown(f"<div class='metric-card'><div class='metric-label'>ใบขับขี่</div><div class='metric-value'>{has_lic}</div><div style='color:#16a34a; font-size:1.1rem; font-weight:bold; margin-top:-5px;'>{p_lic}%</div></div>", unsafe_allow_html=True)
            
            c3.markdown(f"<div class='metric-card'><div class='metric-label'>ภาษี/พรบ.</div><div class='metric-value'>{has_tax}</div><div style='color:#16a34a; font-size:1.1rem; font-weight:bold; margin-top:-5px;'>{p_tax}%</div></div>", unsafe_allow_html=True)
            
            c4.markdown(f"<div class='metric-card'><div class='metric-label'>หมวกกันน็อค</div><div class='metric-value'>{has_hel}</div><div style='color:#16a34a; font-size:1.1rem; font-weight:bold; margin-top:-5px;'>{p_hel}%</div></div>", unsafe_allow_html=True)
            st.write("") 
        # -------------------------------------------------------------------------
        c1, c2 = st.columns(2)
        if c1.button("🔄 ดึงข้อมูลล่าสุด"): 
            st.session_state.df_tra = None 
            st.session_state.search_results_df = None
            load_tra_data()
            st.rerun()
        if c2.button("📊 รายงานสถิติ"): 
            if st.session_state.df_tra is None: load_tra_data()
            st.session_state.traffic_page = 'dash'; st.rerun()
        
        st.write("")
        c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
        q = c_search.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_search_input")
        do_search = c_btn_search.button("ค้นหา", type="primary", use_container_width=True)
        do_clear = c_btn_clear.button("ล้างค่า", type="secondary", use_container_width=True)

        if do_clear:
            st.session_state.search_results_df = None
            st.rerun()

        st.caption("▼ ตัวกรองข้อมูล (เลือกแล้วกด '⚡ กรองข้อมูล')")
        col_f1, col_f2, col_f3 = st.columns(3)
        unique_lv, unique_br = [], []
        if st.session_state.df_tra is not None:
            unique_lv = sorted(list(set([str(x).split('/')[0] for x in st.session_state.df_tra.iloc[:, 3].unique()])))
            unique_br = sorted(list(set(st.session_state.df_tra.iloc[:, 4].unique())))
        
        f_risk = col_f1.selectbox("🚨 กลุ่มปัญหา:", ["ทั้งหมด", "❌ ไม่มีใบขับขี่", "❌ ภาษีขาด", "❌ ไม่สวมหมวก"])
        f_lv = col_f2.selectbox("📚 ระดับชั้น:", ["ทั้งหมด"] + unique_lv)
        f_br = col_f3.selectbox("🏍️ ยี่ห้อรถ:", ["ทั้งหมด"] + unique_br)
        do_filter = st.button("⚡ กรองข้อมูลตามเงื่อนไข", use_container_width=True)

        if do_search or do_filter:
            st.session_state.search_results_df = None
            
            has_search_term = bool(q.strip())
            has_filter = (f_risk != "ทั้งหมด" or f_lv != "ทั้งหมด" or f_br != "ทั้งหมด")
            
            if not has_search_term and not has_filter:
                st.error("⚠️ กรุณากรอกข้อมูลหรือเลือกตัวกรองเพื่อค้นหา")
            else:
                if st.session_state.df_tra is None: load_tra_data()
                if st.session_state.df_tra is not None:
                    # ใช้ df_search เพื่อไม่ให้กระทบ df หลัก
                    df = st.session_state.df_tra.copy()
                    
                    # --- [แก้ไขใหม่] Logic ค้นหา Smart Search ---
                    if has_search_term:
                        s_val = q.strip()
                        # แปลงเป็น String และลบช่องว่างหัวท้ายออกก่อนค้นหา (แก้ปัญหาค้นไม่เจอ)
                        col_name = df.iloc[:, 1].astype(str).str.strip()  # ชื่อ
                        col_id = df.iloc[:, 2].astype(str).str.strip()    # รหัส
                        col_plate = df.iloc[:, 6].astype(str).str.strip() # ทะเบียน

                        mask = (
                            col_name.str.contains(s_val, case=False) | # ชื่อ: ค้นหาบางส่วนได้
                            col_id.str.startswith(s_val) |             # รหัส: ต้อง "ขึ้นต้นด้วย" (แก้ปัญหาเลข 1 ตัวเดียวเหมาหมด)
                            col_plate.str.contains(s_val, case=False)  # ทะเบียน: ค้นหาบางส่วนได้
                        )
                        df = df[mask]
                    # ----------------------------------------

                    # ส่วนการกรอง (Logic เดิม)
                    if f_risk != "ทั้งหมด": 
                        idx = 7 if "ใบขับขี่" in f_risk else (8 if "ภาษี" in f_risk else 9)
                        df = df[df.iloc[:, idx].astype(str).str.contains("ไม่มี|ขาด")]
                    if f_lv != "ทั้งหมด": df = df[df.iloc[:, 3].astype(str).str.contains(f_lv)]
                    if f_br != "ทั้งหมด": df = df[df.iloc[:, 4] == f_br]
                    
                    if df.empty:
                         st.warning("❌ ไม่พบข้อมูล")
                         st.session_state.search_results_df = None
                    elif len(df) == len(st.session_state.df_tra) and not has_search_term and not has_filter:
                         st.warning("ℹ️ ข้อมูลกว้างเกินไป กรุณาระบุรายละเอียดเพิ่มเติม")
                         st.session_state.search_results_df = None
                    else:
                         st.session_state.search_results_df = df
                else:
                    st.error("โหลดข้อมูลไม่สำเร็จ")

        if st.session_state.search_results_df is not None:
            target_df = st.session_state.search_results_df
            if target_df.empty: st.warning("❌ ไม่พบข้อมูล")
            else:
                st.success(f"ค้นพบ {len(target_df)} รายการ")
                for i, row in target_df.iterrows():
                    v = row.tolist(); sc = int(v[13]) if len(v)>13 and str(v[13]).isdigit() else 100
                    sc_color = "#22c55e" if sc >= 80 else ("#eab308" if sc >= 50 else "#ef4444")
                    with st.expander(f"📍 {v[6]} | {v[1]}"):
                        c1, c2 = st.columns([1.5, 1])
                        with c1: st.markdown(f"### 👤 {v[1]}"); st.caption(f"🆔 {v[2]} | {v[3]}")
                        with c2: st.markdown(f"### 🏍️ {v[6]}")
                        # --- [โค้ดส่วนที่เพิ่ม: แสดงสถานะเอกสาร] ---
                        st.markdown(f"""
                        <div style="background-color:#f8f9fa; padding:10px; border-radius:5px; margin: 5px 0;">
                            <b>สถานะเอกสาร:</b><br>
                            🪪 ใบขับขี่: {v[7]} &nbsp;|&nbsp; 
                            📝 ภาษี: {v[8]} &nbsp;|&nbsp; 
                            🪖 หมวก: {v[9]}
                        </div>
                        """, unsafe_allow_html=True)
                        # ----------------------------------------
                        st.markdown(f"<span style='font-size:1.2rem;font-weight:bold;color:{sc_color};'>คะแนน: {sc}/100</span>", unsafe_allow_html=True)
                        c_img1, c_img2, c_img3 = st.columns(3)
                        c_img1.image(get_img_link(v[14]), caption="เจ้าของ")
                        c_img2.image(get_img_link(v[10]), caption="หลัง")
                        c_img3.image(get_img_link(v[11]), caption="ข้าง")
                        
                        if st.session_state.officer_role == "admin":
                            col_act1, col_act2 = st.columns(2)
                            col_act1.download_button("📥 โหลด PDF", create_pdf_tra(v, get_img_link(v[10]), get_img_link(v[11]), get_img_link(v[14]), st.session_state.officer_name), f"{v[6]}.pdf", use_container_width=True)
                            if col_act2.button("✏️ แก้ไขข้อมูล", key=f"ed_{i}", use_container_width=True): st.session_state.edit_data = v; st.session_state.traffic_page = 'edit'; st.rerun()
                            with st.form(key=f"sc_form_{i}"):
                                pts = st.number_input("แต้ม", 1, 50, 5); note = st.text_area("เหตุผล"); pwd = st.text_input("รหัสยืนยัน", type="password")
                                c_sub1, c_sub2 = st.columns(2)
                                deduct = c_sub1.form_submit_button("🔴 หักแต้ม", use_container_width=True)
                                add = c_sub2.form_submit_button("🟢 เพิ่มแต้ม", use_container_width=True)
                                if (deduct or add) and note and pwd == st.session_state.current_user_pwd:
                                    sheet = connect_gsheet_universal(); cell = sheet.find(str(v[2]))
                                    ns = max(0, sc-pts) if deduct else min(100, sc+pts)
                                    action = "หัก" if deduct else "เพิ่ม"
                                    tn = (datetime.now()+timedelta(hours=7)).strftime('%d/%m/%Y %H:%M')
                                    old_log = str(v[12]).strip() if str(v[12]).lower()!="nan" else ""
                                    new_log = f"{old_log}\n[{tn}] {action} {pts} คะแนน: {note} (โดย: {st.session_state.officer_name})"
                                    sheet.update(f'M{cell.row}:N{cell.row}', [[new_log, str(ns)]])
                                    st.success("บันทึกแล้ว"); load_tra_data(); st.rerun()
                                elif (deduct or add): st.error("รหัสผิดหรือข้อมูลไม่ครบ")
        else:
            st.info("ℹ️ กรุณากรอกคำค้นหาหรือใช้ตัวกรองเพื่อแสดงข้อมูล")

        st.markdown("---")
        if st.session_state.current_user_pwd == "Patwit1510":
            with st.expander("⚙️ ระบบจัดการเลื่อนชั้นเรียน (Super Admin Only)"):
                st.warning("⚠️ คำเตือน:ระบบจะเป็นการแก้ไขถาวรไม่สามารถย้อนกลับได้กรุณาระมัดระวง")
                up_pwd = st.text_input("รหัสเลื่อนชั้น", type="password", key="prom_pwd")
                if st.button("ยืนยันเลื่อนชั้น", use_container_width=True) and up_pwd == UPGRADE_PASSWORD:
                    s = connect_gsheet_universal(); d = s.get_all_values(); h = d[0]; r = d[1:]; nr = []
                    for row in r:
                        ol = str(row[3]); nl = ol
                        if "ม.1" in ol: nl=ol.replace("ม.1","ม.2")
                        elif "ม.2" in ol: nl=ol.replace("ม.2","ม.3")
                        elif "ม.3" in ol: nl="จบการศึกษา 🎓"
                        elif "ม.4" in ol: nl=ol.replace("ม.4","ม.5")
                        elif "ม.5" in ol: nl=ol.replace("ม.5","ม.6")
                        elif "ม.6" in ol: nl="จบการศึกษา 🎓"
                        row[3] = nl; nr.append(row)
                    s.clear(); s.update('A1', [h] + nr); st.success("สำเร็จ!"); load_tra_data(); st.rerun()

    elif st.session_state.traffic_page == 'edit':
        st.subheader("✏️ แก้ไขข้อมูล")
        v = st.session_state.edit_data
        with st.form("edit_form"):
            nm = st.text_input("ชื่อ", v[1]); cl = st.text_input("ชั้น", v[3]); br = st.selectbox("ยี่ห้อ", ["Honda", "Yamaha", "Suzuki", "GPX", "Kawasaki", "อื่นๆ"]); co = st.text_input("สี", v[5]); pl = st.text_input("ทะเบียน", v[6])
            lc = st.radio("ใบขับขี่", ["✅ มี", "❌ ไม่มี"], index=0 if "มี" in v[7] else 1, horizontal=True); tx = st.radio("ภาษี", ["✅ ปกติ", "❌ ขาด"], index=0 if "ปกติ" in v[8] or "✅" in v[8] else 1, horizontal=True); hl = st.radio("หมวก", ["✅ มี", "❌ ไม่มี"], index=0 if "มี" in v[9] else 1, horizontal=True)
            nf = st.file_uploader("เปลี่ยนรูปหลัง"); ns = st.file_uploader("เปลี่ยนรูปข้าง")
            if st.form_submit_button("บันทึก", type="primary", use_container_width=True):
                sheet = connect_gsheet_universal(); cell = sheet.find(str(v[2])); l1, l2 = v[10], v[11]
                if nf: l1 = upload_to_drive(nf, f"{v[2]}_F_n.jpg")
                if ns: l2 = upload_to_drive(ns, f"{v[2]}_S_n.jpg")
                sheet.update(f'B{cell.row}:L{cell.row}', [[nm, v[2], cl, br, co, pl, lc, tx, hl, l1, l2]])
                load_tra_data(); st.success("เสร็จสิ้น"); st.session_state.traffic_page = 'teacher'; st.rerun()
        if st.button("ยกเลิก", use_container_width=True): st.session_state.traffic_page = 'teacher'; st.rerun()

    elif st.session_state.traffic_page == 'dash':
        if st.button("⬅️ กลับหน้าจัดการจราจร", use_container_width=True): 
            st.session_state.traffic_page = 'teacher'; st.rerun()
            
        if st.session_state.df_tra is not None:
            df = st.session_state.df_tra.copy()
            # เตรียมข้อมูลพื้นฐาน
            df['Score'] = pd.to_numeric(df['C13'], errors='coerce').fillna(100)
            df['LV'] = df['C3'].apply(lambda x: str(x).split('/')[0] if pd.notna(x) and '/' in str(x) else str(x))
            total_all = len(df)

            st.markdown("<h2 style='text-align:center; color:#1E3A8A; margin-bottom:20px;'>📋 รายงานสรุปผลการดำเนินงานด้านวินัยจราจร</h2>", unsafe_allow_html=True)

            # --- หมวดหมู่ที่ 1: กรอบภาพรวม (ดีไซน์ทางการ) ---
            avg_all = df['Score'].mean()
            at_risk = len(df[df['Score'] < 60])

            # สร้างกรอบทางการด้วย HTML/CSS
            st.markdown(f"""
            <div style="border: 2px solid #1E3A8A; border-radius: 15px; padding: 25px; background-color: #f8fafc; margin-bottom: 25px;">
                <h4 style="color: #1E3A8A; margin-top: 0; border-bottom: 1px solid #cbd5e1; padding-bottom: 10px;">📌 บทสรุปผู้บริหาร (Executive Summary)</h4>
                <div style="display: flex; justify-content: space-around; align-items: center; flex-wrap: wrap; gap: 20px; padding-top: 15px;">
                    <div style="text-align: center;">
                        <div style="font-size: 14px; color: #64748b; font-weight: bold;">จำนวนพาหนะลงทะเบียน</div>
                        <div style="font-size: 32px; font-weight: 800; color: #1e293b;">{total_all} <span style="font-size: 16px; font-weight: normal;">คัน</span></div>
                    </div>
                    <div style="border-left: 1px solid #cbd5e1; height: 50px;" class="hide-mobile"></div>
                    <div style="text-align: center;">
                        <div style="font-size: 14px; color: #64748b; font-weight: bold;">คะแนนวินัยเฉลี่ยภาพรวม</div>
                        <div style="font-size: 32px; font-weight: 800; color: #16a34a;">{avg_all:.2f} <span style="font-size: 16px; font-weight: normal;">แต้ม</span></div>
                    </div>
                    <div style="border-left: 1px solid #cbd5e1; height: 50px;" class="hide-mobile"></div>
                    <div style="text-align: center;">
                        <div style="font-size: 14px; color: #64748b; font-weight: bold;">กลุ่มเฝ้าระวังพิเศษ (แต้ม < 60)</div>
                        <div style="font-size: 32px; font-weight: 800; color: #ef4444;">{at_risk} <span style="font-size: 16px; font-weight: normal;">คน</span></div>
                    </div>
                </div>
            </div>
            <style>
                @media (max-width: 600px) {{ .hide-mobile {{ display: none; }} }}
            </style>
            """, unsafe_allow_html=True)

            # --- หมวดหมู่ที่ 2: สถิติละเอียดแยกตามระดับชั้น (ตารางครบทุกข้อมูล) ---
            st.markdown("#### 📚 ข้อมูลวิเคราะห์เชิงลึกรายระดับชั้น / กลุ่มบุคลากร")
            
            # คำนวณข้อมูลรายกลุ่ม
            # C7=ใบขับขี่, C8=ภาษี, C9=หมวก
            def calc_group_stats(group):
                n = len(group)
                lic = (group['C7'].str.contains("มี", na=False)).sum()
                tax = (group['C8'].str.contains("ปกติ|✅", na=False)).sum()
                hel = (group['C9'].str.contains("มี", na=False)).sum()
                
                return pd.Series({
                    'จำนวนรถ': n,
                    'คะแนนเฉลี่ย': group['Score'].mean(),
                    'ใบขับขี่ (คน)': lic,
                    'ใบขับขี่ (%)': (lic/n*100) if n>0 else 0,
                    'ภาษีปกติ (คัน)': tax,
                    'ภาษีปกติ (%)': (tax/n*100) if n>0 else 0,
                    'สวมหมวก (คน)': hel,
                    'สวมหมวก (%)': (hel/n*100) if n>0 else 0
                })

            summary_table = df.groupby('LV').apply(calc_group_stats).reset_index()
            summary_table = summary_table.rename(columns={'LV': 'ระดับชั้น/กลุ่ม'})
            
            # เรียงจากจำนวนรถมากไปน้อย
            summary_table = summary_table.sort_values('จำนวนรถ', ascending=False)

            # จัดรูปแบบตัวเลขให้สวยงาม
            format_map = {
                'คะแนนเฉลี่ย': '{:.2f}',
                'ใบขับขี่ (%)': '{:.1f}%',
                'ภาษีปกติ (%)': '{:.1f}%',
                'สวมหมวก (%)': '{:.1f}%',
                'จำนวนรถ': '{:,.0f}',
                'ใบขับขี่ (คน)': '{:,.0f}',
                'ภาษีปกติ (คัน)': '{:,.0f}',
                'สวมหมวก (คน)': '{:,.0f}'
            }
            
            for col, fmt in format_map.items():
                summary_table[col] = summary_table[col].apply(lambda x: fmt.format(x))

            # แสดงผลตารางแบบ Interactive (มีแถบเลื่อนถ้าจอเล็ก)
            st.dataframe(summary_table, use_container_width=True, hide_index=True)

            st.write("")
            st.info("💡 **หมายเหตุ:** ข้อมูลเปอร์เซ็นต์คำนวณจากจำนวนรถที่ลงทะเบียนในแต่ละระดับชั้นนั้นๆ")
            st.caption(f"ออกรายงาน ณ วันที่: {get_now_th().strftime('%d/%m/%Y %H:%M')}")
# ==========================================
# 4. MAIN ENTRY (แก้ไขย่อหน้าให้ถูกต้อง)
# ==========================================
def main():
    if 'timeout_msg' in st.session_state and st.session_state.timeout_msg:
        st.error(st.session_state.timeout_msg)
        del st.session_state.timeout_msg

    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                if LOGO_PATH and os.path.exists(LOGO_PATH):
                    st.image(LOGO_PATH, width=120)
                st.markdown("<h3 style='text-align:center;'>ศูนย์ปฏิบัติการกลาง<br>สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h3>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accs = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_in in accs:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accs[pwd_in]
                        st.session_state.current_user_pwd = pwd_in
                        st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            c_brand, c_nav = st.columns([7, 2.5])
            with c_brand:
                c_logo, c_text = st.columns([1, 6])
                with c_logo:
                    if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
                with c_text:
                    st.markdown("""
                    <div style="display: flex; flex-direction: column; justify-content: center; height: 100%;">
                        <div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
                        <div style="font-size: 16px; color: #475569; margin-top: 4px;">🏢 เลือกแผนกปฏิบัติงาน</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # --- จุดที่เคย Error (แก้ไขแล้ว) ---
            with c_nav:
                st.write("")
                st.write("")
                # สังเกตการย่อหน้าใต้ if ต้องขยับเข้ามา
                if st.button("🚪 ออกจากระบบ", key="main_logout", use_container_width=True):
                    st.query_params.clear() 
                    st.session_state.clear()
                    st.rerun()
            # --------------------------------
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary', key="btn_to_inv"):
                        st.session_state.current_dept = "inv"; st.session_state.view_mode = "list"
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary', key="btn_to_tra"):
                        st.session_state.current_dept = "tra"
                        st.session_state.traffic_page = 'teacher'
                        st.session_state.search_results_df = None
                        st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()

if __name__ == "__main__": main()
