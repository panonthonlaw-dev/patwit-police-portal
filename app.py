import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import re
import requests
import time
import io

# --- 1. การตั้งค่าเบื้องต้น ---
st.set_page_config(page_title="ระบบตำรวจโรงเรียน", page_icon="👮‍♂️", layout="wide")

# Initialize Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_dept' not in st.session_state: st.session_state.current_dept = None
if 'traffic_df' not in st.session_state: st.session_state.traffic_df = None

# --- 2. ฟังก์ชันดึงรูปภาพแบบป้องกันจอขาว (Private Access) ---
def load_drive_image(url, creds):
    """ดึงรูปจาก Google Drive โดยใช้ Creds เพื่อแก้ปัญหารูปไม่ขึ้น"""
    if not url or str(url) == "nan":
        return "https://via.placeholder.com/150"
    try:
        # สกัด File ID จาก URL
        file_id = None
        match = re.search(r'/d/([a-zA-Z0-9_-]+)|id=([a-zA-Z0-9_-]+)', str(url))
        if match:
            file_id = match.group(1) or match.group(2)
        
        if file_id:
            # ใช้ Token จากกุญแจ (Service Account) ไขเข้าไปดึงไฟล์
            if not creds.access_token or creds.access_token_expired:
                creds.refresh(requests.Request())
            
            headers = {"Authorization": f"Bearer {creds.access_token}"}
            api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            res = requests.get(api_url, headers=headers, timeout=10)
            
            if res.status_code == 200:
                return res.content
    except Exception as e:
        print(f"Image Error: {e}")
    return "https://via.placeholder.com/150"

# --- 3. ส่วนเชื่อมต่อข้อมูล (GSheets) ---
def get_gsheet_client():
    creds_dict = dict(st.secrets["traffic_creds"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds), creds

def load_data():
    try:
        client, _ = get_gsheet_client()
        sheet = client.open("Motorcycle_DB").sheet1
        data = sheet.get_all_values()
        if len(data) > 1:
            # อ้างอิงโครงสร้างคอลัมน์จาก Motorcycle_DB
            return pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        st.error(f"ไม่สามารถโหลดข้อมูลได้: {e}")
    return None

# --- 4. หน้าหลักระบบงานจราจร ---
def traffic_module():
    st.header("🚦 ระบบบริหารงานจราจร (Motorcycle DB)")
    
    client, creds = get_gsheet_client()
    if st.session_state.traffic_df is None:
        st.session_state.traffic_df = load_data()
    
    df = st.session_state.traffic_df
    
    if df is not None:
        # ระบบค้นหา
        search_q = st.text_input("🔍 ค้นหาด้วย ชื่อ-สกุล / เลขประจำตัว / ทะเบียน", placeholder="พิมพ์ข้อมูลเพื่อค้นหา...")
        
        if search_q:
            # ค้นหาในคอลัมน์ที่เกี่ยวข้อง
            results = df[df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)]
            
            if not results.empty:
                for idx, row in results.iterrows():
                    with st.expander(f"🏍️ {row['ทะเบียน']} | {row['ชื่อ-สกุล']} (แต้มปัจจุบัน: {row['คะแนน']})", expanded=True):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            # ดึงรูปจากคอลัมน์ 'รูปภาพ1'
                            img_data = load_drive_image(row['รูปภาพ1'], creds)
                            st.image(img_data, caption="รูปถ่ายในระบบ", use_container_width=True)
                        
                        with col2:
                            st.write(f"**รหัสนักเรียน:** {row['เลขประจำตัว']}")
                            st.write(f"**ระดับชั้น:** {row['ชั้น']}")
                            st.write(f"**สถานะ:** ใบขับขี่ ({row['ใบขับขี่']}), ภาษี ({row['พรบ_ภาษี']})")
                            
                            st.divider()
                            # --- ระบบจัดการแต้ม ---
                            st.subheader("🛠️ จัดการคะแนน")
                            with st.form(f"score_form_{idx}"):
                                points = st.number_input("แต้ม", 1, 100, 5, key=f"p_{idx}")
                                reason = st.text_input("เหตุผล", placeholder="ระบุสาเหตุการหัก/เพิ่มแต้ม", key=f"r_{idx}")
                                c_sub1, c_sub2 = st.columns(2)
                                deduct = c_sub1.form_submit_button("🔴 หักแต้ม", use_container_width=True)
                                add = c_sub2.form_submit_button("🟢 เพิ่มแต้ม", use_container_width=True)
                                
                                if (deduct or add) and reason:
                                    # อัปเดตข้อมูลใน Google Sheets
                                    sheet = client.open("Motorcycle_DB").sheet1
                                    cell = sheet.find(str(row['เลขประจำตัว']))
                                    current_score = int(row['คะแนน'])
                                    new_score = current_score - points if deduct else current_score + points
                                    new_score = max(0, min(100, new_score))
                                    
                                    # บันทึก Log ประวัติ
                                    now = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')
                                    action = "หัก" if deduct else "เพิ่ม"
                                    history_log = f"{row['ประวัติ']}\n[{now}] {action} {points} แต้ม: {reason}"
                                    
                                    # คอลัมน์ M (ประวัติ) และ N (คะแนน)
                                    sheet.update(f'M{cell.row}:N{cell.row}', [[history_log, str(new_score)]])
                                    st.success("บันทึกข้อมูลเรียบร้อยแล้ว!")
                                    st.session_state.traffic_df = None # สั่งให้โหลดใหม่
                                    time.sleep(1)
                                    st.rerun()
            else:
                st.warning("ไม่พบข้อมูลที่ค้นหา")

# --- 5. การจัดการหน้าจอหลัก (Main Logic) ---
def main():
    if not st.session_state.logged_in:
        # หน้า Login
        st.title("👮‍♂️ ระบบตำรวจนักเรียน")
        password = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
        if st.button("เข้าสู่ระบบ"):
            if password in st.secrets.get("OFFICER_ACCOUNTS", {}):
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        # หน้า Dashboard เจ้าหน้าที่
        st.sidebar.button("🏠 หน้าแรก", on_click=lambda: setattr(st.session_state, 'current_dept', None))
        if st.sidebar.button("🚪 ออกจากระบบ"):
            st.session_state.logged_in = False
            st.rerun()
            
        if st.session_state.current_dept is None:
            st.title("ยินดีต้อนรับสู่ระบบปฏิบัติการ")
            if st.button("🚦 งานจราจร"):
                st.session_state.current_dept = "traffic"
                st.rerun()
        elif st.session_state.current_dept == "traffic":
            traffic_module()

if __name__ == "__main__":
    main()
