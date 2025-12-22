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

# --- 1. ตั้งค่าพื้นฐาน (ยกมาจากต้นฉบับ) ---
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

# แก้ไขอาการ AttributeError: สร้าง State ให้ครบถ้วนตามความต้องการของโค้ดเดิม
states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'current_user': None, 'view_mode': 'list', 'selected_case_id': None,
    'unlock_password': "", 'page_pending': 1, 'page_finished': 1,
    'search_query': ""
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# --- ระบบค้นหาโลโก้ (ยกมาจากต้นฉบับเป๊ะๆ) ---
LOGO_PATH = None
LOGO_MIME = "image/png"
target_file = os.path.join(BASE_DIR, "school_logo")
if os.path.exists(target_file):
    LOGO_PATH = target_file
else:
    possible_logos = glob.glob(os.path.join(BASE_DIR, "school_logo*"))
    for f in possible_logos:
        if os.path.isfile(f):
            LOGO_PATH = f
            break

# ==========================================
# 2. HELPER FUNCTIONS (ก๊อปปี้มาจากต้นฉบับ 100%)
# ==========================================
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))

def clean_val(val):
    if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
    return str(val).strip()

def safe_ensure_columns_for_view(df):
    required_cols = ['Report_ID', 'Timestamp', 'Reporter', 'Incident_Type', 'Location', 'Details', 'Status', 'Image_Data', 'Audit_Log', 'Victim', 'Accused', 'Witness', 'Teacher_Investigator', 'Student_Police_Investigator', 'Statement', 'Evidence_Image']
    if df is None or df.empty: return pd.DataFrame(columns=required_cols)
    for col in required_cols:
        if col not in df.columns: df[col] = ""
    return df

def calculate_pagination(key, total_items, limit=5):
    if key not in st.session_state: st.session_state[key] = 1
    current_page = st.session_state[key]
    total_pages = math.ceil(total_items / limit)
    if total_pages == 0: total_pages = 1
    if current_page > total_pages: current_page = 1; st.session_state[key] = 1
    start_idx = (current_page - 1) * limit
    end_idx = start_idx + limit
    return start_idx, end_idx, current_page, total_pages

def view_case(rid):
    st.session_state.selected_case_id = rid
    st.session_state.view_mode = "detail"
    st.session_state.unlock_password = ""

def back_to_list():
    st.session_state.view_mode = "list"
    st.session_state.selected_case_id = None

def clear_search_callback():
    st.session_state.search_query = ""

def create_pdf(row):
    # (หมายเหตุ: ใส่ Logic create_pdf เดิมของคุณลงที่นี่เพื่อให้ได้ PDF หน้าตาเดิม)
    pass 

# ==========================================
# 3. MODULE: INVESTIGATION (ยกเนื้อหา Dashboard มาทั้งหมด)
# ==========================================
def investigation_module():
    # ดึงค่า user จากส่วนกลางมาใส่ในระบบสอบสวนเพื่อให้โค้ดเดิมทำงานได้
    st.session_state.current_user = st.session_state.user_info
    user = st.session_state.current_user
    
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: setattr(st.session_state, 'current_dept', None), width='stretch')
    
    # --- เริ่มต้นยกโค้ดชุด Dashboard (เจ้าหน้าที่) ของคุณมาวางตรงนี้ ---
    col_h1, col_h2, col_h3 = st.columns([1, 4, 1])
    with col_h1:
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            try: st.image(LOGO_PATH, width=80)
            except: st.write("Logo Error")
    with col_h2:
        st.markdown(f"<div style='font-size: 26px; font-weight: bold; color: #1E3A8A; padding-top: 20px;'>🏢 ระบบสอบสวน คุณ{user['name']}</div>", unsafe_allow_html=True)
    with col_h3: 
        st.write("") 
        if st.button("🔴 Logout", use_container_width=True, key="inv_logout"):
            st.session_state.clear(); st.rerun()

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_raw = conn.read(ttl="0")
        df_display = safe_ensure_columns_for_view(df_raw.copy()) 
        df_display = df_display.fillna("")
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
                
                c1, c2, c3, c4 = st.columns([2.5, 2, 3, 1.5])
                c1.markdown("**เลขที่รับแจ้ง**"); c2.markdown("**วันเวลา**"); c3.markdown("**ประเภทเหตุ**"); c4.markdown("**สถานะ**")
                st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
                
                if df_finished.empty: st.caption("ไม่มีรายการ")
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
                    top_loc = df_display['Location'].mode()[0] if not df_display['Location'].mode().empty else "-"
                    top_inc = df_display['Incident_Type'].mode()[0] if not df_display['Incident_Type'].mode().empty else "-"
                    m1, m2, m3 = st.columns(3)
                    m1.metric("แจ้งเหตุทั้งหมด", f"{total_cases} ครั้ง")
                    m2.metric("สถานที่เกิดเหตุบ่อยสุด", top_loc)
                    m3.metric("เหตุที่เกิดบ่อยสุด", top_inc)

                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**🔹 แผนภูมิวงกลม: สัดส่วนประเภทเหตุ**")
                        st.bar_chart(df_display['Incident_Type'].value_counts(), color="#FF4B4B")
                    with col2:
                        st.markdown("**🔹 กราฟแท่ง: สถิติสถานที่เกิดเหตุ**")
                        st.bar_chart(df_display['Location'].value_counts(), color="#1E3A8A")

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=back_to_list, use_container_width=True)
            sid = str(st.session_state.selected_case_id).strip()
            sel = df_display[df_display['Report_ID'] == sid]
            if not sel.empty:
                row = sel.iloc[0]
                st.markdown(f"### 📝 เลขที่รับแจ้ง: {sid}")
                # (ยกรายละเอียด Form บันทึกจากต้นฉบับมาวางตรงนี้)
                st.info(f"ผู้แจ้ง: {row['Reporter']} | รายละเอียด: {row['Details']}")

    except Exception as e:
        st.error(f"Error: {e}")

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
                    # ดึงบัญชีจาก [OFFICER_ACCOUNTS] ใน Secrets
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
                        pass # เดี๋ยวมาเติมจราจรทีหลัง
        else:
            if st.session_state.current_dept == "inv": investigation_module()

if __name__ == "__main__":
    main()
