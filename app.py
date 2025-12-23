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

# --- 1.1 CSS ปรับแต่งความไวสูงสุด (NO ANIMATION) ---
st.markdown("""
<style>
    * { animation: none !important; transition: none !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .stDeployButton {display:none;}
    [data-testid="stSidebar"] {display: none;} [data-testid="collapsedControl"] {display: none;}
    .metric-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 2.5rem; font-weight: 800; color: #1e293b; } 
    .metric-label { font-size: 1rem; color: #64748b; }
    img { opacity: 1 !important; }
</style>
""", unsafe_allow_html=True)

# --- 1.2 Session & Timeout Logic ---
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

# Initialize Session States
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

LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: LOGO_BASE64 = base64.b64encode(f.read()).decode()

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""

def get_img_link(url):
    if not url or pd.isna(url) or str(url).strip() == "": return None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
    file_id = match.group(1) or match.group(2) if match else None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w800" if file_id else url

def process_image(img_file):
    if not img_file: return ""
    try:
        img = Image.open(img_file).convert('RGB')
        img.thumbnail((800, 800))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65)
        return base64.b64encode(buf.getvalue()).decode()
    except: return ""

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    start_idx = (st.session_state[key] - 1) * limit
    return start_idx, start_idx + limit, st.session_state[key], total_pages

def connect_gsheet_universal():
    if "textkey" in st.secrets and "json_content" in st.secrets["textkey"]:
        try:
            key_str = st.secrets["textkey"]["json_content"].strip()
            if key_str.startswith(("'","\"")): key_str = key_str[1:-1]
            creds_dict = json.loads(key_str.replace('\n', '\\n'), strict=False)
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
# 2. MODULE: INVESTIGATION (ต้นฉบับ 100% + กู้คืนเปอร์เซ็นต์)
# ==========================================
def create_pdf_inv(row):
    rid = str(row.get('Report_ID', '')); date_str = str(row.get('Timestamp', ''))
    audit_log = str(row.get('Audit_Log', '')); latest_date = "-"
    if audit_log:
        try:
            lines = [l for l in audit_log.split('\n') if l.strip()]
            if lines and '[' in lines[-1] and ']' in lines[-1]: latest_date = lines[-1][lines[-1].find('[')+1:lines[-1].find(']')]
        except: pass
    p_name = st.session_state.user_info.get('name', 'System'); qr = qrcode.make(rid); qi = io.BytesIO(); qr.save(qi, format="PNG"); qr_b64 = base64.b64encode(qi.getvalue()).decode()
    img_html = ""
    if clean_val(row.get('Evidence_Image')): img_html += f"<div style='text-align:center;'><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-width:380px;border:1px solid #ccc;'></div>"
    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    html_content = f"<html><head><style>@font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }} body {{ font-family: 'THSarabunNew'; font-size: 16pt; }} .header {{ text-align: center; position: relative; }} .logo {{ position: absolute; left: 0; width: 60px; }} .box {{ border: 1px solid #000; padding: 10px; min-height: 50px; }} </style></head><body><div class=\"header\">{logo_html}<div style=\"font-size: 22pt; font-weight: bold;\">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style=\"font-size: 18pt;\">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div><img style=\"position:absolute; right:0; width:60px;\" src=\"data:image/png;base64,{qr_b64}\"></div><hr><p><b>เลขที่รับแจ้ง:</b> {rid} | <b>ผู้แจ้ง:</b> {row.get('Reporter','-')}</p><div class=\"box\">{row.get('Statement','-')}</div>{img_html}</body></html>"
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
        st.write(""); st.write(""); b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="inv_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="inv_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = df_raw.copy().fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if st.session_state.view_mode == "list":
            tab1, tab2 = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab1:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                s_q = c_search.text_input("ค้นหา", key="inv_q", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา")
                if c_btn_clear.button("❌ ล้าง"): st.rerun()
                filtered = df_display.copy()
                if s_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(s_q, case=False).any(), axis=1)]
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
            with tab2:
                tc = len(df_display)
                if tc > 0:
                    m1, m2, m3 = st.columns(3); m1.metric("แจ้งเหตุทั้งหมด", f"{tc} ครั้ง"); m2.metric("สถานที่เกิดเหตุบ่อยสุด", df_display['Location'].mode()[0]); m3.metric("เหตุที่เกิดบ่อยสุด", df_display['Incident_Type'].mode()[0])
                    st.markdown("---"); c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📌 สรุปยอดตามสถานที่ (Top 5)**")
                        for l, c in df_display['Location'].value_counts().head(5).items():
                            p = (c/tc)*100
                            st.markdown(f"- **{l}**: {c} ครั้ง <span style='color:red;'>({p:.1f}%)</span>", unsafe_allow_html=True)
                    with c2: st.markdown("**🔹 ประเภทเหตุ**"); st.bar_chart(df_display['Incident_Type'].value_counts())
        elif st.session_state.view_mode == "detail":
            if st.button("⬅️ กลับหน้ารายการ"): st.session_state.view_mode = "list"; st.rerun()
            sid = st.session_state.selected_case_id; row = df_display[df_display['Report_ID'] == sid].iloc[0]
            st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
            with st.form("full_inv_form"):
                c1, c2 = st.columns(2)
                v_vic = c1.text_input("ผู้เสียหาย", value=row['Victim']); v_acc = c2.text_input("ผู้ถูกกล่าวหา", value=row['Accused'])
                v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0)
                v_stmt = st.text_area("ผลการดำเนินการสอบสวน", value=row['Statement'])
                if st.form_submit_button("💾 บันทึกข้อมูล"):
                    df_raw.at[df_display[df_display['Report_ID']==sid].index[0], 'Statement'] = v_stmt; df_raw.at[df_display[df_display['Report_ID']==sid].index[0], 'Status'] = v_sta
                    df_raw.at[df_display[df_display['Report_ID']==sid].index[0], 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                    conn.update(data=df_raw.fillna("")); st.success("บันทึกแล้ว!"); time.sleep(1); st.rerun()
            st.download_button("📥 โหลด PDF (สำนวนคดี)", create_pdf_inv(row), f"Report_{sid}.pdf", use_container_width=True)
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับ 100% กู้คืน Pie & Metric)
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
        c1, c2 = st.columns(2)
        if c1.button("🔄 ดึงข้อมูลล่าสุด"): st.session_state.df_tra = None; st.rerun()
        if c2.button("📊 รายงานสถิติ"): st.session_state.traffic_page = 'dash'; st.rerun()
        q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_q")
        if st.button("ค้นหา", type="primary") or q:
            if not q.strip(): st.error("⚠️ กรุณากรอกข้อมูล")
            elif st.session_state.df_tra is not None:
                df = st.session_state.df_tra.copy()
                st.session_state.search_results_df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
        if st.session_state.search_results_df is not None:
            for i, row in st.session_state.search_results_df.iterrows():
                v = row.tolist()
                with st.expander(f"📍 {v[6]} | {v[1]}"):
                    st.write(f"คะแนน: {v[13]}"); st.image(get_img_link(v[14]), width=200)
                    if st.session_state.officer_role == "admin":
                        with st.form(key=f"sc_f_{i}"):
                            pts = st.number_input("แต้ม", 1, 50, 5); nt = st.text_area("เหตุผล"); pwd = st.text_input("รหัสยืนยัน", type="password")
                            if st.form_submit_button("🔴 หักแต้ม") and pwd == st.session_state.current_user_pwd:
                                s = connect_gsheet_universal(); cell = s.find(str(v[2])); ns = max(0, int(v[13])-pts); tn = get_now_th().strftime('%d/%m/%Y %H:%M')
                                s.update(f'M{cell.row}:N{cell.row}', [[f"{v[12]}\n[{tn}] หัก {pts}: {nt}", str(ns)]]); st.success("บันทึกแล้ว"); st.session_state.df_tra = None; st.rerun()
        if st.session_state.current_user_pwd == "Patwit1510":
            with st.expander("⚙️ ระบบจัดการเลื่อนชั้นเรียน (Patwitnext)"):
                up_pwd = st.text_input("รหัสเลื่อนชั้น", type="password")
                if st.button("ยืนยันเลื่อนชั้นทั้งโรงเรียน"):
                    if up_pwd == UPGRADE_PASSWORD:
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
            total = len(df); m1, m2 = st.columns(2)
            with m1: st.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">รถทั้งหมด</div></div>', unsafe_allow_html=True)

# ==========================================
# 4. MODULE: ANALYTICS (ดึงมาสรุปผลเท่านั้น ห้ามแก้ DB)
# ==========================================
def analytics_module():
    user = st.session_state.user_info
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์วิเคราะห์พฤติกรรมและมาตรการเชิงป้องกัน</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">📊 ระบบวิเคราะห์เชิงลึก (Analytics)</span> | ผู้เชี่ยวชาญ: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); b_h, b_o = st.columns(2)
        if b_h.button("🏠 หน้าหลัก", key="ana_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_o.button("🚪 ออก", key="ana_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")
    with st.spinner("⏳ ประมวลผล Big Data เปรียบเทียบ..."):
        try:
            conn_inv = st.connection("gsheets", type=GSheetsConnection); df_inv = conn_inv.read(ttl="0").fillna("")
            sheet_tra = connect_gsheet_universal(); v_t = sheet_tra.get_all_values()
            df_tra = pd.DataFrame(v_t[1:], columns=[f"C{i}" for i in range(len(v_t[0]))])
            if not df_tra.empty:
                df_tra['Level'] = df_tra['C3'].apply(lambda x: str(x).split('/')[0] if x else "N/A")
                tra_stats = df_tra['Level'].value_counts(); inv_stats = df_inv['Location'].value_counts()
                comb = pd.DataFrame({'งานจราจร': tra_stats, 'งานสอบสวน': inv_stats}).fillna(0).reset_index().rename(columns={'index': 'ชั้น'})
                comb = comb[comb['ชั้น'].str.contains("ม.", na=False)].sort_values('ชั้น')
                st.plotly_chart(px.bar(comb, x='ชั้น', y=['งานจราจร', 'งานสอบสวน'], barmode='group', title="เปรียบเทียบสถิติพฤติกรรมรายระดับชั้น"), use_container_width=True)
                risk = df_inv['Incident_Type'].value_counts().idxmax() if not df_inv.empty else "N/A"
                st.error(f"🚩 **ความเสี่ยงสูงสุดในระบบสอบสวน:** {risk}")
        except: st.warning("ระบบกำลังบูรณาการฐานข้อมูล...")

# ==========================================
# 5. MAIN ENTRY (แก้ไขจุดบกพร่องเรื่องการรีเซ็ตหน้า)
# ==========================================
def main():
    if 'timeout_msg' in st.session_state and st.session_state.timeout_msg: st.error(st.session_state.timeout_msg); del st.session_state.timeout_msg
    if not st.session_state.logged_in:
        _, col, _ = st.columns([1, 1.2, 1])
        with col:
            st.markdown("<br><br>", unsafe_allow_html=True); with st.container(border=True):
                if LOGO_PATH: st.image(LOGO_PATH, width=120)
                st.markdown("<h3 style='text-align:center;'>ศูนย์ปฏิบัติการกลาง<br>สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</h3>", unsafe_allow_html=True)
                pwd_in = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
                if st.button("เข้าสู่ระบบ", width='stretch', type='primary'):
                    accs = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_in in accs:
                        st.session_state.logged_in = True; st.session_state.user_info = accs[pwd_in]; st.session_state.current_user_pwd = pwd_in; st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            c_brand, c_nav = st.columns([7, 2.5])
            with c_brand:
                c_logo, c_text = st.columns([1, 6])
                with c_logo: 
                    if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
                with c_text: st.markdown('<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;">🏢 เลือกแผนกปฏิบัติงาน</div></div>', unsafe_allow_html=True)
            with c_nav:
                st.write(""); st.write(""); 
                if st.button("🚪 ออกจากระบบ", key="m_logout", use_container_width=True): st.session_state.clear(); st.rerun()
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary', key="btn_to_inv"):
                        st.session_state.current_dept = "inv"; st.session_state.view_mode = "list" # กู้คืน: บังคับกลับหน้าลิสต์
                        st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary', key="btn_to_tra"):
                        st.session_state.current_dept = "tra"; st.session_state.traffic_page = 'teacher'
                        st.session_state.search_results_df = None; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าใช้งาน Analytics", use_container_width=True, type='primary', key="btn_to_ana"):
                        st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
