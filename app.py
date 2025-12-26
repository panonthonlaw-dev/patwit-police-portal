import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time, ast
import html  # <--- ✅ สำคัญมาก ต้องมีบรรทัดนี้ครับ ไม่งั้นจะ Error
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster

# ตารางอ้างอิงพิกัดภายในโรงเรียน (คุณเปลี่ยนตัวเลข Lat/Lon เป็นค่าจริงที่คุณเตรียมไว้ได้เลย)
COORD_MAP = {
    "อาคาร 1": {"lat": 16.293080624461656, "lon": 103.97334404257019},
    "อาคาร 2": {"lat": 16.29279814390506, "lon": 103.97334845175875},
    "อาคาร 3": {"lat": 16.292547130677022, "lon": 103.9742885660193},
    "อาคาร 4": {"lat": 16.292464708883504, "lon": 103.97328212630455},
    "อาคาร 5": {"lat": 16.29409615213189, "lon": 103.97431743733651},
    "หอประชุมเทาทอง": {"lat": 16.2933910148143, "lon": 103.97435250954894},
    "หอประชุมไทรทอง": {"lat": 16.292976522262947, "lon": 103.97455635743196},
    "อาคารไฟฟ้าสนามฟุตบอล": {"lat": 16.29471891331982, "lon": 103.97219748923851},
    "สนามบาส": {"lat": 16.294180437912743, "lon": 103.97201431305878},
    "โรงอาหาร": {"lat": 16.292685117630384, "lon": 103.97202378933812},
    "สนามปิงปอง": {"lat": 16.293241855058024, "lon": 103.97291845970389},
    "สวนหลังห้องปกครอง": {"lat": 16.29356823258865, "lon": 103.97472900714698},
    "สนามเปตอง": {"lat": 16.29400957119914, "lon": 103.97312938272556},
    "สวนเกษตร": {"lat": 16.294127310210936, "lon": 103.97369507232361},
    "สวนหลังไทรทอง": {"lat": 16.29297281083706, "lon": 103.9741158275382},
    "ห้องน้ำโรงอาหาารติดอาคาร4": {"lat": 16.292463682879095, "lon": 103.97264722383926},
    "ห้องน้ำหลังอาคาร3": {"lat": 16.292126722514713, "lon": 103.97403520772245},
    "ห้องน้ำอาคารไฟฟ้า": {"lat": 16.29465819963838, "lon": 103.97237918736676},
    "ห้องน้ำหลังอาคาร5": {"lat": 16.293816914880985, "lon": 103.97437580456852},
    "อื่นๆ": {"lat": 16.293596638838643, "lon": 103.97250289339189} # พิกัดกลางโรงเรียน
}

# --- วางฟังก์ชันนี้ไว้ส่วนบนๆ ของโค้ด ---
def get_target_sheet_name():
    now_th = datetime.now(pytz.timezone('Asia/Bangkok'))
    current_buddhist_year = now_th.year + 543
    if now_th.month >= 5:
        ac_year = current_buddhist_year
    else:
        ac_year = current_buddhist_year - 1
    return f"Investigation_{ac_year}"

def hazard_analytics_module():
    if st.button("🏠 กลับเมนูหลัก", use_container_width=True):
        st.session_state.current_dept = None
        st.rerun()

    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>📍 Intelligence Map & Risk Analytics</h2>", unsafe_allow_html=True)

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        target_sheet = get_target_sheet_name()

        # ✅ ปรับ TTL เป็น 21600 วินาที (6 ชั่วโมง)
        df_raw = conn.read(worksheet=target_sheet, ttl=21600)
        df_inv = pd.DataFrame(df_raw)

        if not df_inv.empty:
            # (ส่วนสร้างแผนที่ m ที่นี่)
            # ตัวอย่างการดึงค่า:
            # m = folium.Map(location=[16.2935, 103.9725], zoom_start=17)
            
            st_folium(m, width="100%", height=600, returned_objects=[])
            
            # แจ้งผู้ใช้ให้ทราบว่าข้อมูลอัปเดตเป็นรอบ
            st.info("💡 ข้อมูลนี้เป็นข้อมูลสรุป (Caching 6 Hours) เพื่อความเสถียรของระบบ")
            
            # 🔄 เพิ่มปุ่มรีเฟรชด้วยมือ (Manual Refresh) กรณีต้องการข้อมูลล่าสุดจริงๆ
            if st.button("🔄 อัปเดตข้อมูลเดี๋ยวนี้ (Manual Refresh)"):
                st.cache_data.clear() # ล้าง Cache ทั้งหมด
                st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")

#--------------------
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

# --- 1.1 CSS ปรับแต่ง ---
st.markdown("""
<style>
    /* 1. ลบคำสั่งปิด Animation ออก เพื่อให้ War Room กะพริบได้ */
    *, *::before, *::after {
        scroll-behavior: auto !important;
    }

    /* 2. ซ่อนส่วนประกอบระบบที่ไม่จำเป็น */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;} 
    .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    
    /* 3. ปรับแต่ง Card ให้เบา */
    .metric-card { 
        background: white; 
        padding: 10px; 
        border-radius: 8px; 
        border: 1px solid #d1d5db; 
        text-align: center; 
        box-shadow: none !important; 
    }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 0.9rem; color: #64748b; }
    
    /* 4. บังคับแสดงผลภาพแบบเร็ว */
    img { opacity: 1 !important; image-rendering: -webkit-optimize-contrast; }
</style>
""", unsafe_allow_html=True)

# --- 1.2 Session & Timeout Logic ---
TIMEOUT_SECONDS = 60 * 60  # ตั้งเวลา 60 นาที

def check_inactivity():
    if 'last_active' not in st.session_state:
        st.session_state.last_active = time.time()
    
    if time.time() - st.session_state.last_active > TIMEOUT_SECONDS:
        st.session_state.clear()
        st.query_params.clear()
        st.session_state.timeout_msg = "⏳ หมดเวลาการเชื่อมต่อ กรุณาเข้าสู่ระบบใหม่"
        st.rerun()
    else:
        st.session_state.last_active = time.time()

    if not st.session_state.get('logged_in') and st.query_params.get("logged_in") == "true":
        st.session_state.logged_in = True
        accs = st.secrets.get("OFFICER_ACCOUNTS", {})
        pwd = st.query_params.get("pwd", "")
        if pwd in accs:
            st.session_state.user_info = accs[pwd]
            st.session_state.current_user_pwd = pwd
        else:
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

        if st.query_params.get("dept"): 
            st.session_state.current_dept = st.query_params.get("dept")
        if st.query_params.get("v_mode"): 
            st.session_state.view_mode = st.query_params.get("v_mode")
        if st.query_params.get("case_id"): 
            st.session_state.selected_case_id = st.query_params.get("case_id")
        
        st.rerun()

    if st.session_state.get('logged_in'):
        st.query_params["logged_in"] = "true"
        st.query_params["pwd"] = st.session_state.get("current_user_pwd", "")
        if st.session_state.get("current_dept"):
            st.query_params["dept"] = st.session_state.current_dept

check_inactivity()

# Session States initialization
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
            st.query_params.clear()
            st.session_state.clear()
            st.rerun()

    now_th = get_now_th()
    current_buddhist_year = now_th.year + 543
    if now_th.month >= 5:
        current_ac_year = current_buddhist_year
    else:
        current_ac_year = current_buddhist_year - 1

    start_year = current_ac_year + 1
    year_options = [str(start_year - i) for i in range(5)]

    c_year_filter, _ = st.columns([2, 8])
    with c_year_filter:
        sel_year = st.selectbox("📅 เลือกปีการศึกษา", year_options, index=1, key="inv_year_sel")
    
    target_sheet = f"Investigation_{sel_year}"
    conn = st.connection("gsheets", type=GSheetsConnection)

    try:
        df_raw = conn.read(worksheet=target_sheet, ttl=10)
        df_display = df_raw.copy().fillna("")
        
        required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 
                        'Location', 'Details', 'Status', 'Image_Data', 
                        'Audit_Log', 'Victim', 'Accused', 'Witness', 
                        'Teacher_Investigator', 'Student_Police_Investigator', 
                        'Statement', 'Evidence_Image', 'lat', 'lon']
        for c in required_cols:
            if c not in df_display.columns: df_display[c] = ""
            
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        total_cases = len(df_display)
        pending = len(df_display[df_display['Status'] == "รอดำเนินการ"])
        process = len(df_display[df_display['Status'] == "อยู่ระหว่างการดำเนินการ"])
        finished = len(df_display[df_display['Status'] == "ดำเนินการเรียบร้อย"])

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="metric-card"><div class="metric-label">เคสปี {sel_year}</div><div class="metric-value">{total_cases}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-label">รอดำเนินการ</div><div class="metric-value" style="color: #dc2626;">{pending}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><div class="metric-label">กำลังดำเนินการ</div><div class="metric-value" style="color: #3b82f6;">{process}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-label">เสร็จสิ้น</div><div class="metric-value" style="color: #22c55e;">{finished}</div></div>', unsafe_allow_html=True)
        st.write("")

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
                    cc2.write(row['Timestamp'])
                    cc3.write(row['Incident_Type'])
                    status_text = str(row['Status']).strip()
                    if status_text == "รอดำเนินการ":
                        color_code = "#dc2626"; icon = "⏳"
                    elif status_text == "อยู่ระหว่างการดำเนินการ":
                        color_code = "#2563eb"; icon = "🔵"
                    else:
                        color_code = "orange"; icon = "⏳"
                    with cc4: st.markdown(f"<span style='color:{color_code}; font-weight:bold'>{icon} {status_text}</span>", unsafe_allow_html=True)
                    st.divider()
                
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
                    with col1: 
                        st.markdown("**🔹 ประเภทเหตุ**")
                        st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2: 
                        st.markdown("**🔹 สถานที่เกิดเหตุ**")
                        st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")

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
                is_lock = (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "UPGRADE_PASSWORD")
                if user.get('role') != 'admin': is_lock = True
                
                if is_lock and cur_sta == "ดำเนินการเรียบร้อย" and user.get('role') == 'admin':
                    pwd = st.text_input("รหัสปลดล็อค", type="password")
                    if st.button("ยืนยันปลดล็อค"):
                        if pwd == UPGRADE_PASSWORD: 
                            st.session_state.unlock_password = "UPGRADE_PASSWORD"
                            st.rerun()

                with st.form("full_inv_form"):
                    st.markdown("##### 📌 อัปเดตสถานะคดี")
                    v_sta = st.selectbox("สถานะปัจจุบัน", 
                                        ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], 
                                        index=["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"].index(cur_sta) if cur_sta in ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"] else 0,
                                        disabled=is_lock)
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_lock)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_lock)
                    v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_lock)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_lock)
                    v_stu = c1.text_input("ตำรวจนักเรียนผู้สอบสวน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_lock)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_lock)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่ม", type=['jpg','png'], disabled=is_lock)
                    
                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_lock:
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Witness'] = v_wit; df_raw.at[idx_raw, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx_raw, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx_raw, 'Statement'] = v_stmt; df_raw.at[idx_raw, 'Status'] = v_sta
                        if ev_img: df_raw.at[idx_raw, 'Evidence_Image'] = process_image(ev_img)
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(worksheet=target_sheet, data=df_raw.fillna(""))
                        st.success("บันทึกเรียบร้อย!"); time.sleep(1); st.rerun()
                
                if clean_val(row['Audit_Log']):
                    with st.expander("📜 ประวัติการบันทึก (Audit Log)"): st.code(row['Audit_Log'])

                st.divider()
                try:
                    pdf_data = create_pdf_inv(row)
                    st.download_button(label="📥 ดาวน์โหลด PDF (สำนวนคดี)", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                except: st.error("PDF ขัดข้อง")
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC
# ==========================================
def traffic_module():
    # ... (เนื้อหาฟังก์ชัน traffic_module จัดย่อหน้าตามโครงสร้างมาตรฐาน) ...
    pass

# ==========================================
# 4. MAIN ENTRY
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
                if st.button("เข้าสู่ระบบ", use_container_width=True, type='primary'):
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
            
            with c_nav:
                st.write(""); st.write("")
                if st.button("🚪 ออกจากระบบ", key="main_logout", use_container_width=True):
                    st.query_params.clear()
                    st.session_state.clear()
                    st.rerun()
            
            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4) 
            
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary', key="btn_to_inv"):
                        st.session_state.current_dept = "inv"
                        st.session_state.view_mode = "list"
                        st.query_params["dept"] = "inv"
                        st.rerun()
            
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary', key="btn_to_tra"):
                        st.session_state.current_dept = "tra"
                        st.session_state.traffic_page = 'teacher'
                        st.session_state.search_results_df = None
                        st.query_params["dept"] = "tra"
                        st.rerun()

            with c3:
                with st.container(border=True):
                    st.subheader("🖥️ War Room")
                    if st.button("เปิดจอเฝ้าระวังเหตุ", use_container_width=True, type='primary', key="btn_to_monitor"):
                        st.session_state.current_dept = "monitor_view"
                        st.query_params["dept"] = "monitor_view"
                        st.rerun()

            with c4:
                with st.container(border=True):
                    st.subheader("📍 แผนที่จุดเสี่ยง")
                    if st.button("ดูแผนที่วิเคราะห์", use_container_width=True, type="primary", key="btn_to_hazard"):
                        st.session_state.current_dept = "hazard_map" 
                        st.query_params["dept"] = "hazard_map"
                        st.rerun()

            st.write("")
            if st.button("🚪 ออกจากระบบ", use_container_width=True, key="main_logout_fixed"):
                st.query_params.clear()
                st.session_state.clear()
                st.rerun()
        else:
            if st.session_state.current_dept == "inv": 
                investigation_module()
            elif st.session_state.current_dept == "tra": 
                traffic_module()
            elif st.session_state.current_dept == "monitor_view":
                monitor_center_module()
            elif st.session_state.current_dept == "hazard_map":
                hazard_analytics_module()

if __name__ == "__main__":
    main()
