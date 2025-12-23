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

# ระบบ Session State สำหรับควบคุมหน้าหลัก (ส่วนกลาง)
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_info" not in st.session_state: st.session_state.user_info = {}
if "current_dept" not in st.session_state: st.session_state.current_dept = None

# สร้าง Session State สำหรับ "ไส้ใน" (ยกมาจากต้นฉบับเพื่อให้โค้ดเดิมทำงานได้)
if "current_user" not in st.session_state: st.session_state.current_user = None
if 'view_mode' not in st.session_state: st.session_state.view_mode = "list"
if 'selected_case_id' not in st.session_state: st.session_state.selected_case_id = None
if 'unlock_password' not in st.session_state: st.session_state.unlock_password = ""
if 'page_pending' not in st.session_state: st.session_state.page_pending = 1
if 'page_finished' not in st.session_state: st.session_state.page_finished = 1
if 'search_query' not in st.session_state: st.session_state.search_query = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# ==========================================
# 2. ฟังก์ชันช่วย (ยกมาจากต้นฉบับ 100%)
# ==========================================
def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

# --- ระบบค้นหาโลโก้ (ต้นฉบับ) ---
LOGO_PATH = None
LOGO_MIME = "image/png"
target_file = os.path.join(BASE_DIR, "school_logo")
if os.path.exists(target_file):
    LOGO_PATH = target_file
else:
    possible_logos = glob.glob(os.path.join(BASE_DIR, "school_logo*"))
    for f in possible_logos:
        if os.path.isfile(f):
            LOGO_PATH = f; break
LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

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

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    return (st.session_state[key] - 1) * limit, st.session_state[key] * limit, st.session_state[key], total_pages

def safe_ensure_columns_for_view(df):
    required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    df_new = df.copy()
    for col in required_cols:
        if col not in df_new.columns: df_new[col] = ""
    return df_new

def view_case(rid):
    st.session_state.selected_case_id = rid
    st.session_state.view_mode = "detail"
    st.session_state.unlock_password = ""

def back_to_list():
    st.session_state.view_mode = "list"
    st.session_state.selected_case_id = None

def clear_search_callback():
    st.session_state.search_query = ""

# --- ฟังก์ชันสร้าง PDF (ก๊อปปี้มาเป๊ะๆ ลายเซ็น 5 คน + Footer + รูปหลักฐาน) ---
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    date_str = str(row.get('Timestamp', ''))
    reporter = str(row.get('Reporter', '-'))
    incident = str(row.get('Incident_Type', '-'))
    location = str(row.get('Location', '-'))
    details = str(row.get('Details', '-'))
    statement = str(row.get('Statement', '-'))
    
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

    printer_name = st.session_state.current_user['name'] if st.session_state.current_user else "System"
    print_time = get_now_th().strftime("%d/%m/%Y %H:%M:%S")

    qr = qrcode.make(rid); qi = io.BytesIO(); qr.save(qi, format="PNG")
    qr_base64 = base64.b64encode(qi.getvalue()).decode()

    evidence_html = f"<div style='margin-top: 10px; page-break-inside: avoid;'><b>หลักฐานประกอบ:</b><br><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-height: 150px; border: 1px solid #ccc;'></div>" if row.get('Evidence_Image') else ""
    logo_html = f'<img class="logo" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""

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
            .header {{ text-align: center; position: relative; margin-bottom: 20px; min-height: 80px; }}
            .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; margin-bottom: 10px; min-height: 50px; white-space: pre-wrap; }}
            .sig-table {{ width: 100%; margin-top: 30px; text-align: center; }}
            .sig-table td {{ padding-bottom: 30px; vertical-align: top; }}
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
        <p><b>ผู้แจ้ง:</b> {reporter}</p>
        <p><b>ประเภทเหตุ:</b> {incident} | <b>สถานที่:</b> {location}</p>
        <div style="margin-top:10px;"><b>รายละเอียดเหตุการณ์:</b></div><div class="box">{details}</div>
        <div><b>ผลการดำเนินการสอบสวน:</b></div><div class="box">{statement}</div>
        {evidence_html}
        <table class="sig-table">
            <tr>
                <td width="50%">ลงชื่อ..........................................................<br>( {row.get('Victim', '')} )<br>ผู้เสียหาย</td>
                <td width="50%">ลงชื่อ..........................................................<br>( {row.get('Accused', '')} )<br>ผู้ถูกกล่าวหา</td>
            </tr>
            <tr>
                <td>ลงชื่อ..........................................................<br>( {row.get('Student_Police_Investigator', '')} )<br>ตำรวจนักเรียนผู้สอบสวน</td>
                <td>ลงชื่อ..........................................................<br>( {row.get('Witness', '')} )<br>พยาน</td>
            </tr>
            <tr>
                <td colspan="2"><br>ลงชื่อ..........................................................<br>( {row.get('Teacher_Investigator', '')} )<br>ครูผู้สอบสวน</td>
            </tr>
        </table>
    </body>
    </html>
    """
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

# ==========================================
# 3. ไส้ในแผนกสอบสวน (ยกมาจากต้นฉบับ 100%)
# ==========================================
def investigation_module():
    # ผูกข้อมูล User ส่วนกลางเข้ากับโค้ดเดิม
    st.session_state.current_user = st.session_state.user_info
    user = st.session_state.current_user
    
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')

    # --- เริ่มก๊อปปี้จากจุดนี้ ---
    col_h1, col_h2, col_h3 = st.columns([1, 4, 1])
    with col_h1:
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            try: st.image(LOGO_PATH, width=80)
            except: st.write("Logo Error")
    with col_h2:
        st.markdown(f"<div style='font-size: 26px; font-weight: bold; color: #1E3A8A; padding-top: 20px;'>🏢 ระบบสอบสวน คุณ{user['name']}</div>", unsafe_allow_html=True)
    with col_h3: 
        st.write("") 
        if st.button("🔴 Logout", key="inv_logout", use_container_width=True):
            st.session_state.clear(); st.rerun()

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy()).fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                with c_search:
                    search_q = st.text_input("ค้นหา", placeholder="เลขเคส, ชื่อ, หรือเหตุการณ์...", key="search_query", label_visibility="collapsed")
                with c_btn_search: st.button("🔍 ค้นหา", use_container_width=True)
                with c_btn_clear: st.button("❌ ล้าง", on_click=clear_search_callback, use_container_width=True)
                
                filtered_df = df_display.copy()
                if search_q:
                    filtered_df = filtered_df[filtered_df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_pending = filtered_df[filtered_df['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_finished = filtered_df[filtered_df['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start_p, end_p, curr_p, tot_p = calculate_pagination('page_pending', len(df_pending), 5)
                
                c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                c1.markdown("**เลขที่รับแจ้ง**"); c2.markdown("**วันเวลา**"); c3.markdown("**ประเภทเหตุ**"); c4.markdown("**สถานะ**")
                st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
                
                if df_pending.empty: st.caption("ไม่มีรายการ")
                for index, row in df_pending.iloc[start_p:end_p].iterrows():
                    raw_rid = str(row.get('Report_ID', '')).strip()
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {raw_rid}", key=f"p_{index}", use_container_width=True, on_click=view_case, args=(raw_rid,))
                    with cc2: st.write(row.get('Timestamp', '-'))
                    with cc3: st.write(row.get('Incident_Type', '-'))
                    with cc4: st.markdown(f"<span style='color:orange;font-weight:bold'>⏳ รอสอบสวน</span>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 5px 0; opacity: 0.3;'>", unsafe_allow_html=True)
                
                if tot_p > 1:
                    cp1, cp2, cp3 = st.columns([1, 2, 1])
                    with cp1: 
                        if st.button("⬅️ ย้อนกลับ (รอ)", key="prev_p", disabled=(curr_p==1)): st.session_state.page_pending -= 1; st.rerun()
                    with cp2: st.markdown(f"<div style='text-align:center;'>หน้า {curr_p} / {tot_p}</div>", unsafe_allow_html=True)
                    with cp3: 
                        if st.button("ถัดไป (รอ) ➡️", key="next_p", disabled=(curr_p==tot_p)): st.session_state.page_pending += 1; st.rerun()

                st.markdown("---")
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, curr_f, tot_f = calculate_pagination('page_finished', len(df_finished), 5)
                c1f, c2f, c3f, c4f = st.columns([2.5, 2, 3, 1.5])
                c1f.markdown("**เลขที่รับแจ้ง**"); c2f.markdown("**วันเวลา**"); c3f.markdown("**ประเภทเหตุ**"); c4f.markdown("**สถานะ**")
                st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
                for index, row in df_finished.iloc[start_f:end_f].iterrows():
                    raw_rid = str(row.get('Report_ID', '')).strip()
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {raw_rid}", key=f"f_{index}", use_container_width=True, on_click=view_case, args=(raw_rid,))
                    with cc2: st.write(row.get('Timestamp', '-'))
                    with cc3: st.write(row.get('Incident_Type', '-'))
                    with cc4: st.markdown(f"<span style='color:green;font-weight:bold'>✅ เรียบร้อย</span>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 5px 0; opacity: 0.3;'>", unsafe_allow_html=True)

            with tab_dash:
                st.subheader("📊 สรุปสถิติ")
                total_cases = len(df_display)
                if not df_display.empty:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("แจ้งเหตุทั้งหมด", f"{total_cases} ครั้ง")
                    m2.metric("สถานที่เกิดเหตุบ่อยสุด", df_display['Location'].mode()[0])
                    m3.metric("เหตุที่เกิดบ่อยสุด", df_display['Incident_Type'].mode()[0])

                    st.markdown("---")
                    c_text1, c_text2 = st.columns(2)
                    with c_text1:
                        st.markdown("**📌 สรุปยอดตามสถานที่ (Top 5)**")
                        loc_counts = df_display['Location'].value_counts().head(5)
                        for loc, count in loc_counts.items():
                            percent = (count / total_cases) * 100
                            st.markdown(f"- **{loc}**: {count} ครั้ง <span style='color:red; font-size:0.8em;'>({percent:.1f}%)</span>", unsafe_allow_html=True)
                    with c_text2:
                        st.markdown("**📌 สรุปยอดตามประเภทเหตุ**")
                        type_counts = df_display['Incident_Type'].value_counts().head(5)
                        for inc, count in type_counts.items():
                            percent = (count / total_cases) * 100
                            st.markdown(f"- **{inc}**: {count} ครั้ง <span style='color:red; font-size:0.8em;'>({percent:.1f}%)</span>", unsafe_allow_html=True)
                    
                    st.divider()
                    col1, col2 = st.columns(2)
                    with col1: st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2: st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")

                    st.markdown("---")
                    st.subheader("📈 สถิติเชิงลึก (Advanced Analytics)")
                    df_display['dt'] = pd.to_datetime(df_display['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                    df_display_clean = df_display.dropna(subset=['dt'])
                    df_display_clean['Hour'] = df_display_clean['dt'].dt.hour
                    heatmap_df = pd.crosstab(df_display_clean['Location'], df_display_clean['Incident_Type'])
                    st.write("**🔥 ความสัมพันธ์: สถานที่ vs ประเภทเหตุ**")
                    st.dataframe(heatmap_df, use_container_width=True)

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=back_to_list, use_container_width=True)
            sid = str(st.session_state.selected_case_id).strip()
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx = sel.index[0]; row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row.get('Reporter')} | **สถานที่:** {row.get('Location')}")
                    st.info(f"**รายละเอียด:** {row.get('Details')}")
                    if clean_val(row.get('Image_Data')):
                        st.image(base64.b64decode(row['Image_Data']), width=500, caption="หลักฐานจากผู้แจ้ง")

                is_admin = user.get('role') == 'admin'
                cur_sta = clean_val(row.get('Status'))
                is_locked = True if (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510") else False
                if not is_admin: is_locked = True

                if is_locked and cur_sta == "ดำเนินการเรียบร้อย" and is_admin:
                    st.error("🔒 เคสนี้ดำเนินการเรียบร้อยแล้ว (ใช้รหัส Patwit1510 เพื่อแก้ไข)")
                    pwd_in = st.text_input("รหัสปลดล็อค", type="password")
                    if st.button("ยืนยันปลดล็อค"):
                        if pwd_in == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("full_inv_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row.get('Victim')), disabled=is_locked)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row.get('Accused')), disabled=is_locked)
                    v_wit = c1.text_input("พยาน", value=clean_val(row.get('Witness')), disabled=is_locked)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row.get('Teacher_Investigator')), disabled=is_locked)
                    v_stu = c1.text_input("ตำรวจนักเรียน *", value=clean_val(row.get('Student_Police_Investigator')), disabled=is_locked)
                    v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=is_locked)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row.get('Statement')), disabled=is_locked)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่ม", type=['jpg','png'], disabled=is_locked)

                    if st.form_submit_button("💾 บันทึกข้อมูลและประวัติ") and not is_locked:
                        final_img = process_image(ev_img) if ev_img else row.get('Evidence_Image')
                        df_raw.at[idx, 'Victim'] = v_vic; df_raw.at[idx, 'Accused'] = v_acc
                        df_raw.at[idx, 'Witness'] = v_wit; df_raw.at[idx, 'Teacher_Investigator'] = v_tea
                        df_raw.at[idx, 'Student_Police_Investigator'] = v_stu
                        df_raw.at[idx, 'Statement'] = v_stmt; df_raw.at[idx, 'Status'] = v_sta
                        df_raw.at[idx, 'Evidence_Image'] = final_img
                        df_raw.at[idx, 'Audit_Log'] = f"{clean_val(row.get('Audit_Log'))}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna("")); st.success("บันทึกเรียบร้อย!"); time.sleep(1); st.rerun()

                st.divider()
                with st.container(border=True):
                    st.markdown("#### 🖨️ เมนูพิมพ์รายงาน")
                    try:
                        pdf_data = create_pdf(row)
                        st.download_button(label="📥 ดาวน์โหลด PDF", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                    except Exception as e: st.error(f"สร้าง PDF ขัดข้อง: {e}")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 4. MAIN GATEWAY & CENTRAL LOGIN
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
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd_in in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd_in]
                        st.rerun()
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
                st.title("🚦 ระบบจราจร")
                st.sidebar.button("⬅️ กลับหน้าหลัก", on_click=lambda: setattr(st.session_state, 'current_dept', None))

if __name__ == "__main__":
    main()
