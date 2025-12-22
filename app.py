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

# ==========================================
# 1. CONFIG & SESSION STATE
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# สร้าง State ให้ครบถ้วนเพื่อรองรับฟังก์ชัน Detail และ PDF
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query': ""
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# --- ระบบค้นหาโลโก้ ---
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

def get_base64_image(image_path):
    if not image_path or not os.path.exists(image_path): return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

LOGO_BASE64 = get_base64_image(LOGO_PATH) if LOGO_PATH else ""

# ==========================================
# 2. HELPER FUNCTIONS (ต้นฉบับเป๊ะๆ)
# ==========================================
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

def calculate_pagination(key, total_items, limit=5):
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    start_idx = (st.session_state[key] - 1) * limit
    return start_idx, start_idx + limit, st.session_state[key], total_pages

# --- ฟังก์ชันสร้าง PDF (ยกมาทั้งก้อนจากโค้ดสอบสวน) ---
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

    printer_name = st.session_state.user_info.get('name', 'System')
    print_time = get_now_th().strftime("%d/%m/%Y %H:%M:%S")

    qr = qrcode.make(rid)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    evidence_html = f"<div style='margin-top: 10px;'><b>หลักฐานประกอบ:</b><br><img src='data:image/jpeg;base64,{row.get('Evidence_Image')}' style='max-height: 150px;'></div>" if row.get('Evidence_Image') else ""
    logo_html = f'<img class="logo" src="data:{LOGO_MIME};base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""

    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
            .header {{ text-align: center; position: relative; min-height: 80px; }}
            .logo {{ position: absolute; top: 0; left: 0; width: 60px; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; background-color: #f9f9f9; padding: 10px; margin-bottom: 10px; min-height: 50px; white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div style="font-size: 22pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div style="font-size: 18pt; font-weight: bold;">ใบสรุปรายงานเหตุการณ์และผลการดำเนินการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_base64}">
        </div>
        <hr>
        <b>เลขที่รับแจ้ง:</b> {rid} | <b>วันที่แจ้ง:</b> {date_str} | <b>วันที่บันทึกผล:</b> {latest_date}<br>
        <b>ผู้แจ้ง:</b> {reporter} | <b>ประเภทเหตุ:</b> {incident} | <b>สถานที่:</b> {location}
        <div style="margin-top:10px;"><b>รายละเอียดเหตุการณ์:</b></div><div class="box">{details}</div>
        <div><b>ผลการดำเนินการสอบสวน:</b></div><div class="box">{statement}</div>
        {evidence_html}
    </body>
    </html>
    """
    font_config = FontConfiguration()
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=font_config)

# ==========================================
# 3. MODULE: INVESTIGATION (ยกเนื้อหามาทั้งหมด)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # UI Header
    col_h1, col_h2, col_h3 = st.columns([1, 4, 1])
    with col_h1:
        if LOGO_PATH and os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=80)
    with col_h2:
        st.markdown(f"<div style='font-size: 26px; font-weight: bold; color: #1E3A8A; padding-top: 20px;'>🏢 ระบบสอบสวน คุณ{user['name']}</div>", unsafe_allow_html=True)
    with col_h3:
        if st.button("🔴 Logout", key="inv_logout", use_container_width=True): st.session_state.clear(); st.rerun()

    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy())
        df_display = df_display.fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            # --- หน้า LIST (รายการ) ---
            tab_list, tab_dash = st.tabs(["📋 รายการแจ้งเหตุ", "📊 แดชบอร์ดสถิติ"])
            with tab_list:
                # ระบบค้นหา
                search_q = st.text_input("ค้นหา", placeholder="เลขเคส, ชื่อ, หรือเหตุการณ์...", key="search_query_main")
                filtered_df = df_display.copy()
                if search_q:
                    filtered_df = filtered_df[filtered_df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_pending = filtered_df[filtered_df['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_finished = filtered_df[filtered_df['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                # รายการรอสอบสวน
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start_p, end_p, curr_p, tot_p = calculate_pagination('page_pending', len(df_pending), 5)
                for index, row in df_pending.iloc[start_p:end_p].iterrows():
                    raw_rid = row['Report_ID']
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"📝 {raw_rid}", key=f"p_{index}", use_container_width=True, on_click=lambda r=raw_rid: (st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'})))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type'])
                    c4.markdown("<span style='color:orange;'>⏳ รอสอบสวน</span>", unsafe_allow_html=True)
                    st.divider()

                # รายการที่จบแล้ว
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, curr_f, tot_f = calculate_pagination('page_finished', len(df_finished), 5)
                for index, row in df_finished.iloc[start_f:end_f].iterrows():
                    raw_rid = row['Report_ID']
                    c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                    with c1: st.button(f"✅ {raw_rid}", key=f"f_{index}", use_container_width=True, on_click=lambda r=raw_rid: (st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'})))
                    c2.write(row['Timestamp']); c3.write(row['Incident_Type'])
                    c4.markdown("<span style='color:green;'>✅ เรียบร้อย</span>", unsafe_allow_html=True)
                    st.divider()

        elif st.session_state.view_mode == "detail":
            # --- หน้า DETAIL (รายละเอียดสอบสวน + พิมพ์ PDF) ---
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'selected_case_id': None}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx = sel.index[0]
                row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']):
                        st.image(base64.b64decode(row['Image_Data']), width=400, caption="หลักฐาน")

                st.divider()
                st.write("#### ✍️ บันทึกผลการสอบสวน")
                
                # สิทธิ์ Admin เท่านั้นที่แก้ได้
                is_admin = user.get('role') == 'admin'
                with st.form("investigation_form"):
                    v_vic = st.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=not is_admin)
                    v_acc = st.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=not is_admin)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=not is_admin)
                    v_sta = st.selectbox("สถานะ", ["รอดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=not is_admin)
                    ev_img = st.file_uploader("📸 แนบรูปหลักฐานเพิ่มเติม", type=['jpg','png'], disabled=not is_admin)
                    
                    if st.form_submit_button("💾 บันทึกข้อมูล", use_container_width=True) and is_admin:
                        final_img = process_image(ev_img) if ev_img else row['Evidence_Image']
                        df_raw.at[idx, 'Victim'] = v_vic
                        df_raw.at[idx, 'Accused'] = v_acc
                        df_raw.at[idx, 'Statement'] = v_stmt
                        df_raw.at[idx, 'Status'] = v_sta
                        df_raw.at[idx, 'Evidence_Image'] = final_img
                        df_raw.at[idx, 'Audit_Log'] = f"{clean_val(row['Audit_Log'])}\n[{get_now_th().strftime('%d/%m/%Y %H:%M')}] แก้ไขโดย {user['name']}"
                        conn.update(data=df_raw.fillna(""))
                        st.success("บันทึกสำเร็จ!"); time.sleep(1); st.rerun()

                # --- ปุ่มดาวน์โหลด PDF ---
                st.markdown("#### 🖨️ เมนูพิมพ์รายงาน")
                try:
                    pdf_bytes = create_pdf(row)
                    st.download_button(label="📥 ดาวน์โหลดสรุปสำนวน (PDF)", data=pdf_bytes, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True)
                except Exception as e:
                    st.error(f"การสร้าง PDF ขัดข้อง: {e}")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 4. MAIN ENTRY
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
                    accounts = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accounts:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accounts[pwd]
                        st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                    st.session_state.current_dept = "inv"; st.rerun()
            with c2: st.button("เข้าใช้งานจราจร (ยังไม่เปิด)", use_container_width=True, disabled=True)
        else:
            if st.session_state.current_dept == "inv": investigation_module()

if __name__ == "__main__":
    main()
