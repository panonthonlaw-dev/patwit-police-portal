# --- คัดลอกไปทับฟังก์ชัน traffic_module เดิม ---
def traffic_module():
    st.markdown("### 🚦 ระบบบริหารงานจราจรและวินัยนักเรียน")
    
    # 1. สร้าง Creds เพื่อใช้ดึงทั้ง Sheet และ รูปภาพ
    creds_dict = dict(st.secrets["traffic_creds"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 2. โหลดข้อมูล
    if st.session_state.traffic_df is None:
        try:
            sheet = client.open("Motorcycle_DB").sheet1
            vals = sheet.get_all_values()
            if len(vals) > 1:
                st.session_state.traffic_df = pd.DataFrame(vals[1:], columns=[f"C{i}" for i in range(len(vals[0]))])
        except Exception as e: st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")

    df = st.session_state.traffic_df
    
    # ... (ส่วนแสดงสถิติ Dashboard คงเดิม) ...
    if df is not None:
        total = len(df)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("รถทั้งหมด", f"{total} คัน")
        # ... (Dashboard Logic เดิม) ...

    st.markdown("---")
    
    # 3. ระบบค้นหา
    col_q, col_btn = st.columns([4, 1])
    q = col_q.text_input("🔍 ค้นหา (ชื่อ / รหัส / ทะเบียน)", placeholder="ระบุข้อมูลที่ต้องการค้นหา...")
    
    if col_btn.button("ค้นหา", use_container_width=True, type="primary") or q:
        st.session_state.search_results_df = df[df.iloc[:, [1, 2, 6]].apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]

    # 4. แสดงผลการค้นหา (แก้ตรงนี้ให้ดึงรูปได้จริง!)
    if st.session_state.search_results_df is not None:
        for i, row in st.session_state.search_results_df.iterrows():
            v = row.tolist()
            with st.expander(f"🏍️ {v[6]} | {v[1]} (คะแนน: {v[13]})", expanded=True):
                c1, c2 = st.columns([1, 2])
                
                with c1:
                    # [แก้ใหม่] ดึงรูปโดยใช้ Creds (เจาะโฟลเดอร์ส่วนตัวได้)
                    with st.spinner("โหลดรูป..."):
                        img_bytes = load_private_image(v[14], creds) # v[14] คือรููปหน้าตรง
                        st.image(img_bytes, caption="รูปเจ้าของรถ", use_container_width=True)
                
                with c2:
                    st.markdown(f"**ชื่อ:** {v[1]} | **รหัส:** {v[2]} | **ชั้น:** {v[3]}")
                    st.markdown(f"**ยี่ห้อ:** {v[4]} | **สี:** {v[5]} | **ทะเบียน:** {v[6]}")
                    
                    # --- ฟอร์มจัดการแต้ม ---
                    st.markdown("#### 🛠️ จัดการคะแนน")
                    with st.form(f"score_form_{i}"):
                        pts = st.number_input("จำนวนแต้ม", 1, 100, 5)
                        note = st.text_input("เหตุผล", placeholder="เช่น ไม่สวมหมวกกันน็อค")
                        col_sub1, col_sub2 = st.columns(2)
                        sub_deduct = col_sub1.form_submit_button("🔴 หักแต้ม", use_container_width=True)
                        sub_add = col_sub2.form_submit_button("🟢 เพิ่มแต้ม", use_container_width=True)
                        
                        if (sub_deduct or sub_add) and note:
                            # ใช้ client ตัวเดิมที่สร้างไว้ด้านบน
                            sheet = client.open("Motorcycle_DB").sheet1
                            cell = sheet.find(str(v[2]))
                            curr = int(v[13])
                            new_score = curr - pts if sub_deduct else curr + pts
                            new_score = max(0, min(100, new_score))
                            
                            ts = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')
                            old_log = str(v[12]).strip() if str(v[12]).lower() != "nan" else ""
                            act = "หัก" if sub_deduct else "เพิ่ม"
                            editor = st.session_state.current_user_data['name']
                            new_log = f"{old_log}\n[{ts}] {act} {pts}: {note} (โดย: {editor})"
                            
                            sheet.update(f'M{cell.row}:N{cell.row}', [[new_log, str(new_score)]])
                            st.success("บันทึกสำเร็จ!"); st.session_state.traffic_df = None; st.rerun()

                    # ปุ่ม PDF (ส่ง creds ไปให้ด้วยถ้าจะทำรูปใน PDF)
                    st.download_button("🖨️ พิมพ์ใบประวัติ", data=b"PDF_DATA", disabled=True, help="กำลังปรับปรุงระบบ PDF")
