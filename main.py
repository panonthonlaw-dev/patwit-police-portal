import streamlit as st

# --- 1. ตั้งค่า Page Config (ต้องมีอันเดียวและอยู่บนสุด) ---
st.set_page_config(page_title="ระบบรวมศูนย์สถานีตำรวจนักเรียน", page_icon="👮‍♂️", layout="wide")

# --- 2. ฟังก์ชันรวมระบบสอบสวน (Copy โค้ดสอบสวนมาใส่ที่นี่) ---
def investigation_app():
    # [นำ Code ทั้งหมดของแอปสอบสวนที่คุณส่งมา วางลงที่นี่]
    # **ข้อควรระวัง**: ลบ st.set_page_config ออกจากส่วนนี้
    st.sidebar.markdown("---")
    if st.sidebar.button("⬅️ กลับหน้าเลือกแผนก"):
        st.session_state.app_mode = "portal"
        st.rerun()
    
    # ... (เนื้อหาโค้ดสอบสวนเดิม) ...

# --- 3. ฟังก์ชันรวมระบบจราจร (Copy โค้ดจราจรมาใส่ที่นี่) ---
def traffic_app():
    # [นำ Code ทั้งหมดของแอปจราจรที่คุณส่งมา วางลงที่นี่]
    # **ข้อควรระวัง**: ลบ st.set_page_config ออกจากส่วนนี้
    st.sidebar.markdown("---")
    if st.sidebar.button("⬅️ กลับหน้าเลือกแผนก"):
        st.session_state.app_mode = "portal"
        st.rerun()

    # ... (เนื้อหาโค้ดจราจรเดิม) ...

# --- 4. ระบบ Login และ Navigation ส่วนกลาง ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "login"

# หน้า Login ส่วนกลาง
if st.session_state.app_mode == "login":
    st.markdown("<h1 style='text-align: center;'>🔐 ระบบเจ้าหน้าที่ส่วนกลาง</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("central_login"):
            pwd = st.text_input("รหัสผ่านเจ้าหน้าที่", type="password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)
            if submitted:
                # ตรวจสอบจาก secrets (ดึงรายชื่อจาก officer_accounts)
                accounts = st.secrets.get("officer_accounts", {})
                if pwd in accounts:
                    st.session_state.logged_in = True
                    st.session_state.current_user = accounts[pwd]
                    st.session_state.app_mode = "portal"
                    st.rerun()
                else:
                    st.error("รหัสผ่านไม่ถูกต้อง")

# หน้าเลือกแผนก
elif st.session_state.app_mode == "portal":
    st.markdown(f"<h2 style='text-align: center;'>สวัสดีคุณ {st.session_state.current_user['name']}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>กรุณาเลือกฝ่ายที่ต้องการปฏิบัติงาน</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### 📋 ฝ่ายสอบสวน")
            st.write("จัดการรายงานเหตุการณ์, บันทึกคำให้การ และออกรายงาน PDF")
            if st.button("เข้าใช้งานสอบสวน", use_container_width=True, type="primary"):
                st.session_state.app_mode = "investigation"
                st.rerun()
                
    with col2:
        with st.container(border=True):
            st.markdown("### 🏍️ ฝ่ายจราจร")
            st.write("ตรวจสอบทะเบียนรถ, จัดการคะแนนวินัย และออกบัตรอนุญาต")
            if st.button("เข้าใช้งานจราจร", use_container_width=True, type="primary"):
                st.session_state.app_mode = "traffic"
                st.rerun()

    if st.button("🔴 ออกจากระบบ"):
        st.session_state.clear()
        st.rerun()

# เรียกใช้ฟังก์ชันตามโหมด
elif st.session_state.app_mode == "investigation":
    investigation_app()

elif st.session_state.app_mode == "traffic":
    traffic_app()
