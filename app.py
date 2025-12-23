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
import plotly.graph_objects as go

# ==========================================
# 1. INITIAL SETTINGS & SESSION MANAGEMENT
# ==========================================
st.set_page_config(page_title="ศูนย์ปฏิบัติการกลางฯ", page_icon="👮‍♂️", layout="wide", initial_sidebar_state="collapsed")

# --- 1.1 CSS ซ่อน UI Streamlit & GitHub ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;} [data-testid="collapsedControl"] {display: none;}
    .metric-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #1e293b; } .metric-label { font-size: 0.9rem; color: #64748b; }
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

# State Initialization
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query_main': "",
    'traffic_page': 'teacher', 'df_tra': None, 'search_results_df': None, 
    'current_user_pwd': "", 'edit_data': None
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

LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), 
                 next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""

# แก้ไขฟังก์ชันรูปภาพเพื่อป้องกัน MediaFileStorageError
def get_drive_image_url(url):
    if not url or pd.isna(url) or str(url).strip() == "": return None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    start_idx = (st.session_state[key] - 1) * limit
    return start_idx, start_idx + limit, st.session_state[key], total_pages

# --- GSHEET UNIVERSAL CONNECTOR ---
def connect_gsheet_universal():
    if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
        try:
            key_str = st.secrets["textkey"]["json_content"].strip()
            if key_str.startswith(("'","\"")): key_str = key_str[1:-1]
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
    raise Exception("Credential Error")

# ==========================================
# 2. MODULE: INVESTIGATION (ต้นฉบับครบ 100%)
# ==========================================
def create_pdf_inv(row):
    rid = str(row.get('Report_ID', '')); date_str = str(row.get('Timestamp', ''))
    p_name = st.session_state.user_info.get('name', 'System'); p_time = get_now_th().strftime("%d/%m/%Y %H:%M:%S")
    qr = qrcode.make(rid); qi = io.BytesIO(); qr.save(qi, format="PNG"); qr_b64 = base64.b64encode(qi.getvalue()).decode()
    img_html = ""
    if clean_val(row.get('Evidence_Image')):
        img_html += f"<div style='text-align:center;margin-top:10px;'><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-width:380px;max-height:220px;border:1px solid #ccc;'></div>"
    if clean_val(row.get('Image_Data')):
        img_html += f"<div style='text-align:center;margin-top:10px;'><img src='data:image/jpeg;base64,{row.get('Image_Data')}' style='max-width:380px;max-height:220px;border:1px solid #ccc;'></div>"
    
    logo_base64_inv = ""
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f: logo_base64_inv = base64.b64encode(f.read()).decode()
    logo_html = f'<img class="logo" src="data:image/png;base64,{logo_base64_inv}">' if logo_base64_inv else ""
    
    html_content = f"""
    <html><head><style>@font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
    @page {{ size: A4; margin: 2cm; @bottom-right {{ content: "ผู้พิมพ์: {p_name} | หน้า " counter(page); font-family: 'THSarabunNew'; font-size: 12pt; }} }}
    body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
    .header {{ text-align: center; position: relative; min-height: 80px; }} .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
    .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; min-height: 50px; white-space: pre-wrap; }}
    </style></head><body><div class="header">{logo_html}<div style="font-size: 22pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
    <div style="font-size: 18pt;">ใบสรุปรายงานคดีสอบสวน</div><img style="position:absolute; top:0; right:0; width:60px;" src="data:image/png;base64,{qr_b64}"></div><hr>
    <p><b>เลขที่รับแจ้ง:</b> {rid} | <b>วันที่:</b> {date_str}</p>
    <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')}</p>
    <div style="margin-top:10px;"><b>รายละเอียด:</b></div><div class="box">{row.get('Details','-')}</div>
    <div><b>ผลการสอบสวน:</b></div><div class="box">{row.get('Statement','-')}</div>{img_html}
    </body></html>"""
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
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", key="inv_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="inv_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = df_raw.copy().fillna("")
        for c in ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']:
            if c not in df_display.columns: df_display[c] = ""
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 สถิติภาพรวม"])
            with tab_list:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหาเคส", placeholder="เลขเคส, ชื่อ...", key="inv_q", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา")
                if c_btn_clear.button("❌ ล้าง"): st.rerun()
                
                filtered = df_display.copy()
                if search_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_p = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_f = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                st.markdown("#### ⏳ รายการที่รอการดำเนินการ")
                start_p, end_p, cur_p, tot_p = calculate_pagination('page_pending', len(df_p), 5)
                for i, row in df_p.iloc[start_p:end_p].iterrows():
                    col1, col2, col3 = st.columns([2, 5, 2])
                    with col1: st.button(f"📝 {row['Report_ID']}", key=f"p_{i}", on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    col2.write(f"**เหตุ:** {row['Incident_Type']} | **ผู้แจ้ง:** {row['Reporter']}")
                    col3.warning(row['Status'])

                st.markdown("#### ✅ รายการที่ดำเนินการเรียบร้อย")
                start_f, end_f, cur_f, tot_f = calculate_pagination('page_finished', len(df_f), 5)
                for i, row in df_f.iloc[start_f:end_f].iterrows():
                    col1, col2, col3 = st.columns([2, 5, 2])
                    with col1: st.button(f"✅ {row['Report_ID']}", key=f"f_{i}", on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    col2.write(f"**เหตุ:** {row['Incident_Type']} | **วันที่:** {row['Timestamp']}")
                    col3.success("เรียบร้อย")
            
            with tab_dash:
                st.plotly_chart(px.pie(df_display, names='Incident_Type', title="สัดส่วนประเภทเหตุการณ์"), use_container_width=True)

        elif st.session_state.view_mode == "detail":
            if st.button("⬅️ กลับหน้ารายการ"): st.session_state.view_mode = "list"; st.rerun()
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx_raw = sel.index[0]; row = sel.iloc[0]
                st.subheader(f"📝 เลขที่รับแจ้ง: {sid}")
                with st.form("inv_edit_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย", value=row['Victim'])
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา", value=row['Accused'])
                    v_sta = st.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0)
                    v_stmt = st.text_area("ผลการสอบสวน", value=row['Statement'])
                    if st.form_submit_button("💾 บันทึกข้อมูล"):
                        df_raw.at[idx_raw, 'Victim'] = v_vic; df_raw.at[idx_raw, 'Accused'] = v_acc
                        df_raw.at[idx_raw, 'Statement'] = v_stmt; df_raw.at[idx_raw, 'Status'] = v_sta
                        df_raw.at[idx_raw, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกสำเร็จ!"); time.sleep(1); st.rerun()
                
                if clean_val(row['Audit_Log']):
                    with st.expander("📜 ประวัติการบันทึก (Audit Log)"): st.code(row['Audit_Log'])
                st.download_button("📥 โหลด PDF (สำนวนคดี)", create_pdf_inv(row), f"Report_{sid}.pdf", use_container_width=True)
    except Exception as e: st.error(f"Error Investigation: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับครบ + ระบบเลื่อนชั้น + แก้รูปภาพ)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    st.session_state.officer_name = user.get('name', 'N/A')
    st.session_state.officer_role = user.get('role', 'teacher')

    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">🚦 ระบบงานจราจร</span> | ผู้เข้าใช้: {st.session_state.officer_name}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); st.write("")
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", key="tra_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="tra_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    def load_tra_data():
        try:
            sheet = connect_gsheet_universal(); vals = sheet.get_all_values()
            if len(vals) > 1: st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])])
            return True
        except: return False

    if st.session_state.df_tra is None: load_tra_data()

    if st.session_state.traffic_page == 'teacher':
        c1, c2 = st.columns(2)
        if c1.button("🔄 ดึงข้อมูลล่าสุด"): st.session_state.df_tra = None; load_tra_data(); st.rerun()
        if c2.button("📊 รายงานสถิติจราจร"): st.session_state.traffic_page = 'dash'; st.rerun()
        
        st.write("")
        q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_q_main")
        
        # ตัวกรอง
        st.caption("▼ ตัวกรองข้อมูล")
        cf1, cf2 = st.columns(2)
        unique_lv = sorted(list(set([str(x).split('/')[0] for x in st.session_state.df_tra.iloc[:, 3].unique()]))) if st.session_state.df_tra is not None else []
        f_lv = cf1.selectbox("📚 ระดับชั้น:", ["ทั้งหมด"] + unique_lv)
        f_risk = cf2.selectbox("🚨 กลุ่มปัญหา:", ["ทั้งหมด", "ไม่มีใบขับขี่", "ภาษีขาด", "ไม่สวมหมวก"])
        
        if st.button("⚡ กรองและค้นหาข้อมูล", use_container_width=True, type="primary"):
            df = st.session_state.df_tra.copy()
            if q: df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
            if f_lv != "ทั้งหมด": df = df[df.iloc[:, 3].astype(str).str.contains(f_lv)]
            if f_risk != "ทั้งหมด":
                idx = 7 if "ใบขับขี่" in f_risk else (8 if "ภาษี" in f_risk else 9)
                df = df[df.iloc[:, idx].astype(str).str.contains("ไม่มี|ขาด")]
            st.session_state.search_results_df = df

        if st.session_state.search_results_df is not None:
            tdf = st.session_state.search_results_df
            if tdf.empty: st.warning("❌ ไม่พบข้อมูล")
            else:
                for i, row in tdf.iterrows():
                    v = row.tolist(); sc = int(v[13]) if len(v)>13 and str(v[13]).isdigit() else 100
                    with st.expander(f"📍 {v[6]} | {v[1]}"):
                        st.markdown(f"### 👤 {v[1]} | คะแนน: {sc}")
                        
                        # --- FIX: แสดงรูปภาพแบบถูกต้องเพื่อเลี่ยง MediaFileStorageError ---
                        img_urls = [get_drive_image_url(v[14]), get_drive_image_url(v[10]), get_drive_image_url(v[11])]
                        # กรองเฉพาะที่ไม่เป็น None
                        valid_imgs = [img for img in img_urls if img]
                        if valid_imgs: st.image(valid_imgs, width=220)
                        
                        if st.session_state.officer_role == "admin":
                            with st.form(key=f"sc_f_{i}"):
                                pts = st.number_input("แต้ม", 1, 50, 5); note = st.text_area("เหตุผลการหักคะแนน")
                                pwd = st.text_input("รหัสยืนยัน", type="password")
                                if st.form_submit_button("🔴 หักคะแนน"):
                                    if pwd == st.session_state.current_user_pwd:
                                        s = connect_gsheet_universal(); cell = s.find(str(v[2]))
                                        ns = max(0, sc-pts); tn = get_now_th().strftime('%d/%m/%Y %H:%M')
                                        old = str(v[12]).strip() if str(v[12]).lower()!="nan" else ""
                                        new_log = f"{old}\n[{tn}] หัก {pts} คะแนน: {note}"
                                        s.update(f'M{cell.row}:N{cell.row}', [[new_log, str(ns)]])
                                        st.success("บันทึกสำเร็จ"); load_tra_data(); st.rerun()
                                    else: st.error("รหัสผิด")

        # --- ระบบเลื่อนชั้นเรียน (ต้นฉบับ 100%) ---
        st.markdown("---")
        if st.session_state.current_user_pwd == "Patwit1510":
            with st.expander("⚙️ ระบบจัดการเลื่อนชั้นเรียน (Super Admin Only)"):
                st.warning("⚠️ การเลื่อนชั้นจะปรับระดับชั้นของนักเรียนทุกคนในฐานข้อมูล")
                up_pwd = st.text_input("รหัสเลื่อนชั้น (Patwitnext)", type="password")
                if st.button("ยืนยันการเลื่อนชั้นเรียน", use_container_width=True):
                    if up_pwd == UPGRADE_PASSWORD:
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
                        s.clear(); s.update('A1', [h] + nr); st.success("เลื่อนชั้นสำเร็จ!"); load_tra_data(); st.rerun()

    elif st.session_state.traffic_page == 'dash':
        if st.button("⬅️ กลับ"): st.session_state.traffic_page = 'teacher'; st.rerun()
        if st.session_state.df_tra is not None:
            st.plotly_chart(px.pie(st.session_state.df_tra, names='C7', title="สถานะใบขับขี่รวม"), use_container_width=True)

# ==========================================
# 4. MODULE: BEHAVIORAL ANALYTICS (โมดูลเสริม - ไม่แตะต้อง DB)
# ==========================================
def analytics_module():
    user = st.session_state.user_info
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์วิเคราะห์พฤติกรรมและมาตรการเชิงป้องกัน</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">📊 ระบบวิเคราะห์พฤติกรรมศาสตร์ (Analytics)</span> | ผู้เชี่ยวชาญ: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="ana_h_btn"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="ana_o_btn"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    try:
        # ดึงข้อมูลมาวิเคราะห์แบบ Read-Only
        conn = st.connection("gsheets", type=GSheetsConnection); df_inv = conn.read(ttl="0").fillna("")
        sheet_tra = connect_gsheet_universal(); vals_tra = sheet_tra.get_all_values()
        df_tra = pd.DataFrame(vals_tra[1:], columns=vals_tra[0]) if len(vals_tra) > 1 else pd.DataFrame()

        st.markdown("### 🔍 ผลการวิเคราะห์ระดับความเสี่ยงรายชั้น")
        
        # ค้นหาเรื่องที่เสี่ยงที่สุด
        top_risk = df_inv['Incident_Type'].value_counts().idxmax() if 'Incident_Type' in df_inv.columns and not df_inv.empty else "ไม่มีข้อมูล"
        
        # กราฟแท่งเปรียบเทียบความผิดรายชั้น (จราจร vs สอบสวน)
        if 'ชั้น/ห้อง' in df_tra.columns:
            df_tra['Level'] = df_tra['ชั้น/ห้อง'].apply(lambda x: str(x).split('/')[0] if x else "N/A")
            tra_lv = df_tra['Level'].value_counts()
            inv_lv = df_inv['Grade'].value_counts() if 'Grade' in df_inv.columns else pd.Series()
            
            comb = pd.DataFrame({'งานจราจร': tra_lv, 'งานสอบสวน': inv_lv}).fillna(0).reset_index().rename(columns={'index': 'ชั้น'})
            comb = comb[comb['ชั้น'].str.contains("ม.", na=False)].sort_values('ชั้น')
            
            fig = px.bar(comb, x='ชั้น', y=['งานจราจร', 'งานสอบสวน'], barmode='group', title="เปรียบเทียบสถิติพฤติกรรมผิดระเบียบ")
            st.plotly_chart(fig, use_container_width=True)

            st.error(f"🚩 **ความเสี่ยงสูงสุด:** พฤติกรรมประเภท **{top_risk}** มีแนวโน้มเกิดขึ้นบ่อยที่สุด")
            st.info("💡 **มาตรการแนะนำ:** ควรกวดขันวินัยในระดับชั้นที่มีสถิติรวมสูงกว่าค่าเฉลี่ย")
    except: st.warning("ข้อมูลยังไม่เพียงพอสำหรับการวิเคราะห์เปรียบเทียบ")

# ==========================================
# 5. MAIN ENTRY (Timeout Check)
# ==========================================
def main():
    if 'timeout_msg' in st.session_state and st.session_state.timeout_msg:
        st.error(st.session_state.timeout_msg); del st.session_state.timeout_msg

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
                        st.session_state.logged_in = True; st.session_state.user_info = OFFICER_ACCOUNTS[pwd_in]
                        st.session_state.current_user_pwd = pwd_in; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            c_brand, c_nav = st.columns([7, 2.5])
            with c_brand:
                c_logo, c_text = st.columns([1, 6])
                with c_logo: 
                    if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
                with c_text:
                    st.markdown('<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;">🏢 เลือกแผนกปฏิบัติงาน</div></div>', unsafe_allow_html=True)
            with c_nav:
                st.write(""); st.write("")
                if st.button("🚪 ออกจากระบบ", key="m_out_btn", use_container_width=True): st.session_state.clear(); st.rerun()
            st.markdown("---")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าสู่ระบบสอบสวน", key="btn_inv_m", use_container_width=True, type='primary'): st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าสู่ระบบจราจร", key="btn_tra_m", use_container_width=True, type='primary'): st.session_state.current_dept = "tra"; st.session_state.traffic_page = 'teacher'; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าสู่ระบบ Analytics", key="btn_ana_m", use_container_width=True, type='primary'): st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
