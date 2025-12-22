# --- ฟังก์ชันสร้าง PDF (แก้ไขให้ดึงรูปภาพใส่ใน PDF ด้วย) ---
def create_pdf(row):
    rid = str(row.get('Report_ID', ''))
    qr = qrcode.make(rid)
    qr_buffer = io.BytesIO(); qr.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
    
    logo_html = f'<img style="width:60px;" src="data:image/png;base64,{LOGO_BASE64}">' if LOGO_BASE64 else ""
    
    # ดึงรูปภาพหลักฐาน (ถ้ามี) เพื่อใส่ใน PDF
    img_data_b64 = clean_val(row.get('Image_Data'))
    evidence_img_b64 = clean_val(row.get('Evidence_Image'))
    
    image_section_html = ""
    # ถ้ามีรูปจากผู้แจ้ง
    if img_data_b64:
        image_section_html += f"""
        <p><b>รูปภาพหลักฐานจากผู้แจ้งเหตุ:</b></p>
        <div style="text-align:center;"><img src="data:image/jpeg;base64,{img_data_b64}" style="max-width: 400px; max-height: 300px; border: 1px solid #ccc;"></div>
        """
    # ถ้ามีรูปหลักฐานเพิ่มเติมจากผู้สอบสวน
    if evidence_img_b64:
        image_section_html += f"""
        <p><b>รูปภาพหลักฐานเพิ่มเติมจากการสอบสวน:</b></p>
        <div style="text-align:center;"><img src="data:image/jpeg;base64,{evidence_img_b64}" style="max-width: 400px; max-height: 300px; border: 1px solid #ccc;"></div>
        """

    html_content = f"""
    <html>
    <head>
        <style>
            @font-face {{ font-family: 'THSarabunNew'; src: url('file://{FONT_FILE}'); }}
            body {{ font-family: 'THSarabunNew'; font-size: 16pt; line-height: 1.3; padding: 20px; }}
            .header {{ text-align: center; position: relative; }}
            .qr {{ position: absolute; top: 0; right: 0; width: 60px; }}
            .box {{ border: 1px solid #000; padding: 10px; margin-bottom: 10px; min-height: 80px; white-space: pre-wrap; }}
            img {{ display: block; margin: 10px auto; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html}
            <div style="font-size: 20pt; font-weight: bold;">สถานีตำรวจภูธรโรงเรียนโพนทองพัฒนาวิทยา</div>
            <div>ใบสรุปรายงานเหตุการณ์และผลการสอบสวน</div>
            <img class="qr" src="data:image/png;base64,{qr_base64}">
        </div>
        <hr>
        <p><b>เลขที่รับแจ้ง:</b> {rid} | <b>วันที่แจ้ง:</b> {row.get('Timestamp','-')}</p>
        <p><b>ผู้แจ้ง:</b> {row.get('Reporter','-')} | <b>ประเภทเหตุ:</b> {row.get('Incident_Type','-')} | <b>สถานที่:</b> {row.get('Location','-')}</p>
        
        <p><b>รายละเอียดเหตุการณ์:</b></p>
        <div class="box">{row.get('Details','-')}</div>
        
        <p><b>ผลการดำเนินการสอบสวน:</b></p>
        <div class="box">{row.get('Statement','-')}</div>
        
        {image_section_html}  <br>
        <table style="width:100%; text-align:center; margin-top: 20px;">
            <tr>
                <td>ลงชื่อ.........................................<br>({row.get('Victim','-')})<br>ผู้เสียหาย</td>
                <td>ลงชื่อ.........................................<br>({row.get('Accused','-')})<br>ผู้ถูกกล่าวหา</td>
            </tr>
        </table>
        <div style="text-align:center; margin-top: 20px;">
            ลงชื่อ.........................................<br>({row.get('Teacher_Investigator', '-')})<br>ครูผู้สอบสวน
        </div>
    </body>
    </html>
    """
    return HTML(string=html_content, base_url=BASE_DIR).write_pdf(font_config=FontConfiguration())
