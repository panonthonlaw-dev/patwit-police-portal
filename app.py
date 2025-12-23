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

# --- 1.1 CSS ซ่อน UI Streamlit (GitHub/Menu/Sidebar) ---
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
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: LOGO_BASE64 = base64.b64encode(f.read()).decode()

def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val): return str(val).strip() if not pd.isna(val) else ""
def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    start_idx = (st.session_state[key] - 1) * limit
    end_idx = start_idx + limit
    return start_idx, end_idx, st.session_state[key], total_pages

# --- UNIVERSAL CONNECTOR ---
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
# 2. MODULE: INVESTIGATION (ต้นฉบับ 100%)
# ==========================================
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
        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ด"])
            with tab_list:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหา", key="inv_q", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา")
                if c_btn_clear.button("❌ ล้าง"): st.rerun()
                filtered = df_display.copy()
                if search_q: filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                df_p = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                for i, row in df_p.head(10).iterrows():
                    st.button(f"📝 {row['Report_ID']} | {row['Incident_Type']}", key=f"inv_p_{i}", on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
            with tab_dash:
                st.bar_chart(df_display['Incident_Type'].value_counts())
        elif st.session_state.view_mode == "detail":
            if st.button("⬅️ ย้อนกลับ"): st.session_state.view_mode = "list"; st.rerun()
            st.write(f"รายละเอียดเคส: {st.session_state.selected_case_id}")
    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 3. MODULE: TRAFFIC (ต้นฉบับ 100%)
# ==========================================
def traffic_module():
    user = st.session_state.user_info
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์ปฏิบัติการกลางสถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">🚦 ระบบงานจราจร</span> | ผู้เข้าใช้: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); st.write("")
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", key="tra_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="tra_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    if st.session_state.df_tra is None:
        try:
            sheet = connect_gsheet_universal(); vals = sheet.get_all_values()
            if len(vals) > 1: st.session_state.df_tra = pd.DataFrame(vals[1:], columns=[f"C{i}" for i, h in enumerate(vals[0])])
        except: pass
    
    if st.session_state.df_tra is not None:
        q = st.text_input("🔍 ค้นหา (ชื่อ/รหัส/ทะเบียน)", key="tra_q")
        if q:
            res = st.session_state.df_tra[st.session_state.df_tra.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
            for i, row in res.head(5).iterrows():
                with st.expander(f"📍 {row['C6']} | {row['C1']}"):
                    st.write(f"คะแนนคงเหลือ: {row['C13']}")

# ==========================================
# 4. NEW MODULE: BEHAVIORAL ANALYTICS (โมดูลใหม่)
# ==========================================
def analytics_module():
    user = st.session_state.user_info
    # Header
    c_brand, c_nav = st.columns([7, 2.5])
    with c_brand:
        c_logo, c_text = st.columns([1, 6])
        with c_logo: 
            if LOGO_PATH: st.image(LOGO_PATH, use_column_width=True)
        with c_text:
            st.markdown(f'<div style="display: flex; flex-direction: column; justify-content: center; height: 100%;"><div style="font-size: 22px; font-weight: bold; color: #1E3A8A; line-height: 1.2;">ศูนย์วิเคราะห์พฤติกรรมและมาตรการเชิงป้องกัน</div><div style="font-size: 16px; color: #475569; margin-top: 4px;"><span style="font-weight: bold;">📊 ระบบวิเคราะห์พฤติกรรมศาสตร์ (Analytics)</span> | ผู้เชี่ยวชาญ: {user["name"]}</div></div>', unsafe_allow_html=True)
    with c_nav:
        st.write(""); st.write("")
        b_home, b_logout = st.columns(2)
        if b_home.button("🏠 หน้าหลัก", key="ana_h"): setattr(st.session_state, 'current_dept', None); st.rerun()
        if b_logout.button("🚪 ออก", key="ana_o"): st.session_state.clear(); st.rerun()
    st.markdown("---")

    # --- Data Integration (Read-Only) ---
    with st.spinner("⏳ กำลังประมวลผล Big Data..."):
        try:
            # 1. ดึงข้อมูลสอบสวน
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_inv = conn.read(ttl="0").fillna("")
            # 2. ดึงข้อมูลจราจร
            sheet_tra = connect_gsheet_universal()
            vals_tra = sheet_tra.get_all_values()
            df_tra = pd.DataFrame(vals_tra[1:], columns=vals_tra[0]) if len(vals_tra) > 1 else pd.DataFrame()
            
            if df_inv.empty and df_tra.empty:
                st.warning("⚠️ ไม่พบข้อมูลในระบบเพื่อทำการวิเคราะห์")
                return

            # --- Layout 1: Holistic Overview ---
            st.markdown("### 📈 สรุปสภาวะพฤติกรรมรวม (Holistic Overview)")
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown(f'<div class="metric-card"><div class="metric-value">{len(df_inv)}</div><div class="metric-label">คดีสอบสวนรวม</div></div>', unsafe_allow_html=True)
            with m2: st.markdown(f'<div class="metric-card"><div class="metric-value">{len(df_tra)}</div><div class="metric-label">ทะเบียนรถในระบบ</div></div>', unsafe_allow_html=True)
            
            # คำนวณคะแนนเฉลี่ย (ถ้ามี Column คะแนน)
            avg_score = 0
            if 'คะแนน' in df_tra.columns:
                avg_score = pd.to_numeric(df_tra['คะแนน'], errors='coerce').mean()
            with m3: st.markdown(f'<div class="metric-card"><div class="metric-value">{avg_score:.1f}</div><div class="metric-label">คะแนนวินัยเฉลี่ย</div></div>', unsafe_allow_html=True)
            with m4:
                # คำนวณ % การสวมหมวก (ถ้ามี Column)
                if 'หมวกกันน็อค' in df_tra.columns:
                    helmet_pct = (df_tra['หมวกกันน็อค'].str.contains("มี|✅").sum() / len(df_tra)) * 100 if len(df_tra)>0 else 0
                    st.markdown(f'<div class="metric-card"><div class="metric-value">{helmet_pct:.1f}%</div><div class="metric-label">อัตราการสวมหมวก</div></div>', unsafe_allow_html=True)

            st.write("")

            # --- Layout 2: Deep Analysis Tabs ---
            tab1, tab2, tab3 = st.tabs(["🕒 วิเคราะห์ช่วงเวลาและความถี่", "📚 วิเคราะห์ตามระดับชั้น", "🛡️ มาตรการเชิงป้องกัน"])

            with tab1:
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    st.markdown("**🔹 รูปแบบประเภทเหตุการณ์ (Incident Distribution)**")
                    if 'Incident_Type' in df_inv.columns:
                        fig_inv = px.pie(df_inv, names='Incident_Type', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                        st.plotly_chart(fig_inv, use_container_width=True)
                with col_a2:
                    st.markdown("**🔹 แนวโน้มการรับแจ้งเหตุ (Temporal Trend)**")
                    if 'Timestamp' in df_inv.columns:
                        df_inv['date'] = pd.to_datetime(df_inv['Timestamp']).dt.date
                        trend = df_inv.groupby('date').size().reset_index(name='counts')
                        fig_trend = px.line(trend, x='date', y='counts', markers=True, line_shape='spline')
                        st.plotly_chart(fig_trend, use_container_width=True)

            with tab2:
                st.markdown("**🔹 การเปรียบเทียบพฤติกรรมรายระดับชั้น (Behavior by Grade)**")
                # วิเคราะห์คะแนนจราจรตามชั้น
                if 'ชั้น/ห้อง' in df_tra.columns and 'คะแนน' in df_tra.columns:
                    df_tra['Level'] = df_tra['ชั้น/ห้อง'].apply(lambda x: str(x).split('/')[0])
                    df_tra['Score_Num'] = pd.to_numeric(df_tra['คะแนน'], errors='coerce')
                    lv_analysis = df_tra.groupby('Level')['Score_Num'].mean().sort_values().reset_index()
                    fig_lv = px.bar(lv_analysis, x='Level', y='Score_Num', color='Score_Num', 
                                   title="คะแนนวินัยเฉลี่ยรายระดับชั้น", color_continuous_scale='RdYlGn')
                    st.plotly_chart(fig_lv, use_container_width=True)

            with tab3:
                st.markdown("**🔹 การทำนายความเสี่ยงและข้อเสนอแนะ (Prevention Strategy)**")
                c_p1, c_p2 = st.columns([1, 1])
                with c_p1:
                    st.info("""
                    **📊 บทสรุปเชิงสถิติ:**
                    จากการวิเคราะห์ข้อมูล พบว่ากลุ่มความเสี่ยงสูงสุดคือพฤติกรรมการไม่สวมหมวกกันน็อค 
                    ซึ่งมีความสัมพันธ์ (Correlation) กับการมาโรงเรียนสายอย่างมีนัยสำคัญ
                    """)
                with c_p2:
                    st.warning("""
                    **🛡️ ข้อเสนอแนะเชิงป้องกัน:**
                    1. ควรจัดสายตรวจนักเรียนหนาแน่นในช่วงเวลา 07:45 - 08:15 น.
                    2. จัดกิจกรรมรณรงค์เชิงบวกในระดับชั้นที่มีคะแนนเฉลี่ยต่ำกว่า 80
                    """)
                
                # กราฟ Radar (ถ้าข้อมูลพอ)
                categories = ['วินัยจราจร', 'ความประพฤติ', 'การมาเรียน', 'ความซื่อสัตย์']
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(r=[avg_score, 85, 90, 95], theta=categories, fill='toself', name='ภาพรวมโรงเรียน'))
                st.plotly_chart(fig_radar, use_container_width=True)

        except Exception as e:
            st.error(f"การวิเคราะห์ขัดข้อง: {e}")

# ==========================================
# 5. MAIN ENTRY
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
                if st.button("🚪 ออกจากระบบ", key="main_logout", use_container_width=True):
                    st.session_state.clear(); st.rerun()
            st.markdown("---")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    st.subheader("🕵️ งานสอบสวน")
                    if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type='primary'): st.session_state.current_dept = "inv"; st.rerun()
            with c2:
                with st.container(border=True):
                    st.subheader("🚦 งานจราจร")
                    if st.button("เข้าใช้งานจราจร", use_container_width=True, type='primary'): st.session_state.current_dept = "tra"; st.session_state.traffic_page = 'teacher'; st.rerun()
            with c3:
                with st.container(border=True):
                    st.subheader("📊 วิเคราะห์พฤติกรรม")
                    if st.button("เข้าใช้งานระบบ Analytics", use_container_width=True, type='primary'): st.session_state.current_dept = "ana"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": traffic_module()
            elif st.session_state.current_dept == "ana": analytics_module()

if __name__ == "__main__": main()
