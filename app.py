import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# PDF Libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except: pass

# ==========================================
# 1. INITIAL SETTINGS & LOGO
# ==========================================
st.set_page_config(page_title="ระบบเจ้าหน้าที่ส่วนกลาง", page_icon="👮‍♂️", layout="wide")

states = {
    'logged_in': False, 'user_info': {}, 'current_dept': None,
    'view_mode': 'list', 'selected_case_id': None, 'unlock_password': "",
    'page_pending': 1, 'page_finished': 1, 'search_query': "",
    'df_traffic': None
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "THSarabunNew.ttf")

# ดึงโลโก้สำหรับ PDF
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), None)
def get_base64_image(path):
    if not path or not os.path.exists(path): return ""
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
LOGO_BASE64 = get_base64_image(LOGO_PATH)

# Helpers
def get_now_th(): return datetime.now(pytz.timezone('Asia/Bangkok'))
def clean_val(val):
    if pd.isna(val) or str(val).lower() in ["nan", "none", ""] or val is None: return ""
    return str(val).strip()

# --- ฟังก์ชันสร้าง PDF (เพิ่มกลับเข้ามา) ---
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    qr = qrcode.make(rid)
    qr_io = io.BytesIO()
    qr.save(qr_io, format="PNG")
    qr_b64 = base64.b64encode(qr_io.getvalue()).decode()
    
    logo_html = f'<img style="width:60px;" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    
    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; }}
            .header {{ text-align: center; position: relative; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; padding: 10px; min-height: 100px; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div style="font-size: 20pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div>ใบสรุปรายงานเหตุการณ์และผลการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_b64}">
        </div>
        <hr>
        <p><b>เลขที่:</b> {rid} | <b>วันที่แจ้ง:</b> {row.get('Timestamp','-')}</p>
        <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภท:</b> {row.get('Incident_Type','-')}</p>
        <p><b>รายละเอียดเหตุการณ์:</b></p>
        <div class="box">{row.get('Details','-')}</div>
        <p><b>ผลการสอบสวน:</b></p>
        <div class="box">{row.get('Statement','-')}</div>
        <br>
        <table style="width:100%; text-align:center;">
            <tr>
                <td>ลงชื่อ..........................<br>({row.get('Victim','-')})<br>ผู้เสียหาย</td>
                <td>ลงชื่อ..........................<br>({row.get('Accused','-')})<br>ผู้ถูกกล่าวหา</td>
            </tr>
        </table>
    </body>
    </html>
    """
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())

# ==========================================
# 2. MODULE: INVESTIGATION
# ==========================================
def investigation_module():
    user = st.session_state.user_info
    st.sidebar.button("⬅️ กลับหน้าเลือกแผนก", on_click=lambda: st.session_state.update({'current_dept': None, 'view_mode': 'list'}), width='stretch')
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        df_raw = conn.read(ttl="0")
        df_display = df_raw.copy().fillna("")
        df_display['Report_ID'] = df_display['Report_ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if st.session_state.view_mode == "list":
            st.title(f"🏢 ระบบสอบสวน คุณ{user['name']}")
            # ... (ส่วน List รายการเดิมที่คุณมีอยู่แล้ว) ...
            st.write("เลือกรายการจากตารางด้านล่าง...")
            for idx, row in df_display.head(5).iterrows():
                if st.button(f"📝 {row['Report_ID']}", key=f"btn_{idx}"):
                    st.session_state.update({'selected_case_id': row['Report_ID'], 'view_mode': 'detail'})
                    st.rerun()

        elif st.session_state.view_mode == "detail":
            st.button("⬅️ กลับหน้ารายการ", on_click=lambda: st.session_state.update({'view_mode': 'list', 'unlock_password': ""}))
            sid = st.session_state.selected_case_id
            sel = df_display[df_display['Report_ID'] == sid]
            
            if not sel.empty:
                row = sel.iloc[0]
                # --- (ส่วนฟอร์มบันทึกข้อมูลเดิมของคุณ) ---
                st.subheader(f"📄 รายละเอียดเคส: {sid}")
                
                # [จำลองฟอร์มของคุณ]
                with st.container(border=True):
                    st.write(f"**ผู้แจ้ง:** {row['Reporter']}")
                    st.info(f"**รายละเอียด:** {row['Details']}")
                
                # --- ส่วน PDF ที่เพิ่มเข้าไป (ไม่ยุ่งส่วนอื่น) ---
                st.divider()
                with st.container(border=True):
                    st.markdown("#### 🖨️ พิมพ์รายงานสำนวนคดี")
                    try:
                        pdf_bytes = create_pdf(row)
                        st.download_button(
                            label="📥 ดาวน์โหลดรายงานสรุป (PDF)",
                            data=pdf_bytes,
                            file_name=f"Report_{sid}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                    except Exception as e:
                        st.error(f"ไม่สามารถสร้าง PDF ได้: {e}")

    except Exception as e: st.error(f"Error: {e}")

# ==========================================
# MAIN & TRAFFIC (คงเดิม)
# ==========================================
def main():
    if not st.session_state.logged_in:
        # Login Logic...
        pass
    else:
        if st.session_state.current_dept == "inv": investigation_module()
        # ส่วนเลือกแผนก...

if __name__ == "__main__":
    main()
