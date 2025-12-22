# --- 5. OFFICER PORTAL (หน้าเข้าสู่ระบบ & เลือกแผนก) ---
def officer_portal():
    user = st.session_state.current_user_data
    
    # Header
    h1, h2, h3 = st.columns([1, 5, 1])
    with h1: 
        if LOGO_PATH: st.image(LOGO_PATH, width=80)
    with h2:
        st.markdown(f"#### 🏢 ศูนย์ปฏิบัติการตำรวจโรงเรียนโพนทองพัฒนาวิทยา\n**เจ้าหน้าที่:** {user['name']} | **บทบาท:** {user['role']}")
    with h3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_dept = None
            st.rerun()

    st.markdown("---")

    # ส่วนเลือกแผนก (ลบ height ออกแล้ว)
    if st.session_state.current_dept is None:
        st.markdown("<h2 style='text-align:center;'>เลือกหมวดหมู่การปฏิบัติงาน</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            # แก้จุดนี้: ลบ height=200
            if st.button("🔎 เข้าสู่งานสืบสวน (จัดการเคสรับแจ้งเหตุ)", use_container_width=True):
                st.session_state.current_dept = "inv"
                st.rerun()
        with col2:
            # แก้จุดนี้: ลบ height=200
            if st.button("🚦 เข้าสู่งานจราจร (ทะเบียนรถ/วินัยจราจร)", use_container_width=True):
                st.session_state.current_dept = "traffic"
                st.rerun()
    else:
        # ปุ่มสลับแผนก
        if st.button("🔄 สลับแผนกงาน", use_container_width=True):
            st.session_state.current_dept = None
            st.rerun()
        
        st.markdown("---")
        # เข้าสู่หน้างานแต่ละแผนก
        if st.session_state.current_dept == "inv":
            investigation_department()
        elif st.session_state.current_dept == "traffic":
            traffic_department()
