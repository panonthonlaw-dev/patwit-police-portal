import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time
from PIL import Image

# PDF Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass
import plotly.express as px

# ==========================================
# 1. INITIAL SETTINGS (รักษาโครงสร้างเดิม)
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# สร้าง Session State ให้ครบตามความต้องการของโค้ดเดิมทั้งหมด
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
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), None)
LOGO_MIME = "image/png"
def get_base64_image(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
LOGO_BASE64 = get_base64_image(LOGO_PATH)

# ==========================================
# 2. HELPER FUNCTIONS (ดึงมาจากต้นฉบับเป๊ะๆ)
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

def calculate_pagination(key, total_items, limit=5):
    total_pages = math.ceil(total_items / limit) or 1
    if st.session_state[key] > total_pages: st.session_state[key] = 1
    return (st.session_state[key] - 1) * limit, st.session_state[key] * limit, st.session_state[key], total_pages

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

def create_pdf(row):
    # (ฟังก์ชัน PDF ที่ยกมาจากต้นฉบับ รักษารูปแบบเดิมเป๊ะ)
    rid = str(row.get('Report_ID', ''))
    qr = qrcode.make(rid)
    qi = io.BytesIO(); qr.save(qi, format="PNG")
    qr_b64 = base64.b64encode(qi.getvalue()).decode()
    logo_html = f'<img style="width:60px;" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    html_content = f"""<html><head><style>@font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
    body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
    .header {{ text-align: center; position: relative; }} .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
    .box {{ border: 1px solid #000; padding: 10px; margin-bottom: 10px; min-height: 80px; white-space: pre-wrap; }}</style></head>
    <body><div class="header">{logo_html}<div style="font-size: 20pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
    <div>ใบสรุปรายงานเหตุการณ์และผลการสอบสวน</div><img class="qr" src="data:image/png;base64,{qr_b64}"></div><hr>
    <p><b>เลขที่รับแจ้ง:</b> {rid} | <b>วันที่แจ้ง:</b> {row.get('Timestamp','-')}</p>
    <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
    <p><b>รายละเอียดเหตุการณ์:</b></p><div class="box">{row.get('Details','-')}</div>
    <p><b>ผลการดำเนินการสอบสวน:</b></p><div class="box">{row.get('Statement','-')}</div><br>
    <table style="width:100%; text-align:center;"><tr>
    <td>ลงชื่อ.........................................<br>({row.get('Victim','-')})<br>ผู้เสียหาย</td>
    <td>ลงชื่อ.........................................<br>({row.get('Accused','-')})<br>ผู้ถูกกล่าวหา</td>
    </tr></table></body></html>"""
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

# ==========================================
# 3. MODULE: INVESTIGATION (ยกต้นฉบับมาวาง 100%)
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None, 'view_mode': 'list'}), width='stretch')
    
    # --- ส่วนหัว Dashboard (ยกคำพูดมาเป๊ะๆ) ---
    col_h1, col_h2, col_h3 = st.columns([1, 4, 1])
    with col_h1:
        if LOGO_PATH and os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=80)
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
                # ระบบค้นหา (ยกมาเป๊ะๆ)
                c_search, c_btn_search, c_btn_clear = st.columns([3, 1, 1])
                search_q = c_search.text_input("ค้นหา", placeholder="เลขเคส, ชื่อ, หรือเหตุการณ์...", label_visibility="collapsed")
                c_btn_search.button("🔍 ค้นหา", use_container_width=True)
                if c_btn_clear.button("❌ ล้าง", use_container_width=True): st.rerun()

                filtered = df_display.copy()
                if search_q:
                    filtered = filtered[filtered.apply(lambda r: r.astype(str).str.contains(search_q, case=False).any(), axis=1)]
                
                df_pending = filtered[filtered['Status'].isin(["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ"])][::-1]
                df_finished = filtered[filtered['Status'] == "ดำเนินการเรียบร้อย"][::-1]

                # --- รายการที่รอ ---
                st.markdown("<h4 style='color:#1E3A8A; background-color:#f0f2f6; padding:10px; border-radius:5px;'>⏳ รายการที่รอการดำเนินการ</h4>", unsafe_allow_html=True)
                start, end, curr, tot = calculate_pagination('page_pending', len(df_pending))
                c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                c1.markdown("**เลขที่รับแจ้ง**"); c2.markdown("**วันเวลา**"); c3.markdown("**ประเภทเหตุ**"); c4.markdown("**สถานะ**")
                st.divider()
                for idx, row in df_pending.iloc[start:end].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"📝 {row['Report_ID']}", key=f"p_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.markdown("<span style='color:orange;'>⏳ รอสอบสวน</span>", unsafe_allow_html=True)
                    st.divider()

                # --- รายการที่จบแล้ว (แก้ไขให้กลับมา) ---
                st.markdown("<h4 style='color:#2e7d32; background-color:#e8f5e9; padding:10px; border-radius:5px;'>✅ รายการที่ดำเนินการเรียบร้อย</h4>", unsafe_allow_html=True)
                start_f, end_f, curr_f, tot_f = calculate_pagination('page_finished', len(df_finished))
                for idx, row in df_finished.iloc[start_f:end_f].iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2.5, 2, 3, 1.5])
                    with cc1: st.button(f"✅ {row['Report_ID']}", key=f"f_{idx}", use_container_width=True, on_click=lambda r=row['Report_ID']: st.session_state.update({'selected_case_id': r, 'view_mode': 'detail'}))
                    cc2.write(row['Timestamp']); cc3.write(row['Incident_Type']); cc4.markdown("<span style='color:green;'>✅ เรียบร้อย</span>", unsafe_allow_html=True)
                    st.divider()

            with tab_dash:
                # --- แดชบอร์ดสถิติ (ยกมาครบทุกตัว) ---
                if not df_display.empty:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("แจ้งเหตุทั้งหมด", f"{len(df_display)} ครั้ง")
                    m2.metric("สถานที่บ่อยสุด", df_display['Location'].mode()[0])
                    m3.metric("เหตุบ่อยสุด", df_display['Incident_Type'].mode()[0])
                    st.divider()
                    c1, c2 = st.columns(2)
                    with c1: st.markdown("**🔹 ประเภทเหตุ**"); st.bar_chart(df_display['Incident_Type'].value_counts())
                    with c2: st.markdown("**🔹 สถานที่**"); st.bar_chart(df_display['Location'].value_counts())

        elif st.session_state.view_mode == "detail":
            # --- หน้าจัดการรายละเอียด (เป๊ะตามต้นฉบับ + PDF) ---
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}), use_container_width=True)
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                idx = sel.index[0]; row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']} | **สถานที่:** {row['Location']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                    if clean_val(row['Image_Data']): st.image(base64.b64decode(row['Image_Data']), width=400, caption="หลักฐานจากผู้แจ้ง")
                
                # ระบบ Lock & ปลดล็อก
                cur_sta = clean_val(row['Status'])
                is_admin = user.get('role') == 'admin'
                is_lock = True if (cur_sta == "ดำเนินการเรียบร้อย" and st.session_state.unlock_password != "Patwit1510") else False
                if not is_admin: is_lock = True

                if is_lock and cur_sta == "ดำเนินการเรียบร้อย" and is_admin:
                    pwd = st.text_input("ปลดล็อคการแก้ไข (Patwit1510)", type="password")
                    if st.button("🔓 ปลดล็อค"): 
                        if pwd == "Patwit1510": st.session_state.unlock_password = "Patwit1510"; st.rerun()

                with st.form("edit_inv_form"):
                    c1, c2 = st.columns(2)
                    v_vic = c1.text_input("ผู้เสียหาย *", value=clean_val(row['Victim']), disabled=is_lock)
                    v_acc = c2.text_input("ผู้ถูกกล่าวหา *", value=clean_val(row['Accused']), disabled=is_lock)
                    v_wit = c1.text_input("พยาน", value=clean_val(row['Witness']), disabled=is_lock)
                    v_tea = c2.text_input("ครูผู้สอบสวน *", value=clean_val(row['Teacher_Investigator']), disabled=is_lock)
                    v_stu = c1.text_input("ตำรวจนักเรียน *", value=clean_val(row['Student_Police_Investigator']), disabled=is_lock)
                    v_sta = c2.selectbox("สถานะ", ["รอดำเนินการ", "อยู่ระหว่างการดำเนินการ", "ดำเนินการเรียบร้อย", "ยกเลิก"], index=0, disabled=is_lock)
                    v_stmt = st.text_area("ผลการดำเนินการสอบสวน *", value=clean_val(row['Statement']), disabled=is_lock)
                    ev_img = st.file_uploader("📸 รูปหลักฐานเพิ่มเติม", type=['jpg','png'], disabled=is_lock)

                    if st.form_submit_button("💾 บันทึกข้อมูล") and not is_lock:
                        df_raw.at[idx, 'Victim'] = v_vic; df_raw.at[idx, 'Accused'] = v_acc
                        df_raw.at[idx, 'Statement'] = v_stmt; df_raw.at[idx, 'Status'] = v_sta
                        if ev_img: df_raw.at[idx, 'Evidence_Image'] = process_image(ev_img)
                        conn.update(data=df_raw.fillna(""))
                        st.success("บันทึกสำเร็จ!"); st.rerun()

                # ระบบ PDF (เพิ่มเข้าไปต่อท้าย)
                st.divider()
                try:
                    pdf_data = create_pdf(row)
                    st.download_button(label="📥 ดาวน์โหลด PDF", data=pdf_data, file_name=f"Report_{sid}.pdf", mime="application/pdf", use_container_width=True)
                except: st.error("PDF ขัดข้อง")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 4. MAIN GATEWAY & LOGIN
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
                    accs = st.secrets.get("OFFICER_ACCOUNTS", {})
                    if pwd in accs:
                        st.session_state.logged_in = True
                        st.session_state.user_info = accs[pwd]
                        st.rerun()
                    else: st.error("❌ รหัสผิด")
    else:
        if st.session_state.current_dept is None:
            st.title("🏢 เลือกแผนกปฏิบัติงาน")
            c1, c2 = st.columns(2)
            if c1.button("🕵️ เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                st.session_state.current_dept = "inv"; st.rerun()
            if c2.button("🚦 เข้าใช้งานจราจร", use_container_width=True, type="primary"):
                st.session_state.current_dept = "tra"; st.rerun()
        else:
            if st.session_state.current_dept == "inv": investigation_module()
            elif st.session_state.current_dept == "tra": st.title("🚦 ระบบจราจร"); st.sidebar.button("⬅️ กลับ", on_click=lambda: st.session_state.update({'current_dept': None}))

if __name__ == "__main__":
    main()
