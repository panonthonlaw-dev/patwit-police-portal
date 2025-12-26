import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz, random, os, base64, io, qrcode, glob, math, mimetypes, json, requests, re, textwrap, time, ast
import html  # <--- ✅ สำคัญมาก ต้องมีบรรทัดนี้ครับ ไม่งั้นจะ Error
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster

# ==========================================
# 0. GLOBAL CONFIGURATIONS & DATA
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ประกาศตัวแปร LOGO_PATH สำหรับใช้ทั่วทั้งแอป
LOGO_PATH = next((f for f in glob.glob(os.path.join(BASE_DIR, "school_logo*")) if os.path.isfile(f)), 
                 next((f for f in ["logo.png", "logo.jpg", "logo"] if os.path.exists(f)), None))

# โหลดโลโก้เป็น Base64 สำหรับ PDF
LOGO_BASE64 = ""
if LOGO_PATH and os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f: 
        LOGO_BASE64 = base64.b64encode(f.read()).decode()

# ตารางอ้างอิงพิกัดภายในโรงเรียน
COORD_MAP = {
    "อาคาร 1": {"lat": 16.293080624461656, "lon": 103.97334404257019},
    "อาคาร 2": {"lat": 16.29279814390506, "lon": 103.97334845175875},
    "อาคาร 3": {"lat": 16.292547130677022, "lon": 103.9742885660193},
    "อาคาร 4": {"lat": 16.292464708883504, "lon": 103.97328212630455},
    "อาคาร 5": {"lat": 16.29409615213189, "lon": 103.97431743733651},
    "หอประชุมเทาทอง": {"lat": 16.2933910148143, "lon": 103.97435250954894},
    "หอประชุมไทรทอง": {"lat": 16.292976522262947, "lon": 103.97455635743196},
    "อาคารไฟฟ้าสนามฟุตบอล": {"lat": 16.29471891331982, "lon": 103.97219748923851},
    "สนามบาส": {"lat": 16.294180437912743, "lon": 103.97201431305878},
    "โรงอาหาร": {"lat": 16.292685117630384, "lon": 103.97202378933812},
    "สนามปิงปอง": {"lat": 16.293241855058024, "lon": 103.97291845970389},
    "สวนหลังห้องปกครอง": {"lat": 16.29356823258865, "lon": 103.97472900714698},
    "สนามเปตอง": {"lat": 16.29400957119914, "lon": 103.97312938272556},
    "สวนเกษตร": {"lat": 16.294127310210936, "lon": 103.97369507232361},
    "สวนหลังไทรทอง": {"lat": 16.29297281083706, "lon": 103.9741158275382},
    "ห้องน้ำโรงอาหาารติดอาคาร4": {"lat": 16.292463682879095, "lon": 103.97264722383926},
    "ห้องน้ำหลังอาคาร3": {"lat": 16.292126722514713, "lon": 103.97403520772245},
    "ห้องน้ำอาคารไฟฟ้า": {"lat": 16.29465819963838, "lon": 103.97237918736676},
    "ห้องน้ำหลังอาคาร5": {"lat": 16.293816914880985, "lon": 103.97437580456852},
    "อื่นๆ": {"lat": 16.293596638838643, "lon": 103.97250289339189} 
}

# --- ฟังก์ชันคำนวณชื่อชีต ---
def get_target_sheet_name():
    now_th = datetime.now(pytz.timezone('Asia/Bangkok'))
    current_buddhist_year = now_th.year + 543
    if now_th.month >= 5:
        ac_year = current_buddhist_year
    else:
        ac_year = current_buddhist_year - 1
    return f"Investigation_{ac_year}"

# ==========================================
# 1. MODULE: HAZARD ANALYTICS
# ==========================================
def hazard_analytics_module():
    if st.button("🏠 กลับเมนูหลัก", use_container_width=True):
        st.session_state.current_dept = None
        st.rerun()

    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>📍 Intelligence Map & Risk Analytics</h2>", unsafe_allow_html=True)

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        target_sheet = get_target_sheet_name()

        # ✅ ปรับ TTL เป็น 21600 วินาที (6 ชั่วโมง) ตามความต้องการ
        df_raw = conn.read(worksheet=target_sheet, ttl=21600)
        df_inv = pd.DataFrame(df_raw)

        if not df_inv.empty:
            # ดึงพิกัดจาก COORD_MAP อ้างอิงตาม Location ในชีต
            def get_coord(loc_name, axis):
                loc_clean = str(loc_name).strip()
                res = COORD_MAP.get(loc_clean, COORD_MAP["อื่นๆ"])
                return res[axis]

            df_inv['f_lat'] = df_inv['Location'].apply(lambda x: get_coord(x, 'lat'))
            df_inv['f_lon'] = df_inv['Location'].apply(lambda x: get_coord(x, 'lon'))

            # สร้างแผนที่กึ่งกลางโรงเรียน
            m = folium.Map(location=[16.2935, 103.9735], zoom_start=18)
            
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
                attr='Google Satellite', name='Google Satellite', overlay=False, control=True
            ).add_to(m)

            cluster = MarkerCluster().add_to(m)
            for _, row in df_inv.iterrows():
                # เพิ่ม Jitter เล็กน้อยเพื่อให้จุดไม่ทับกันสนิทในอาคารเดียวกัน
                j_lat = row['f_lat'] + random.uniform(-0.00003, 0.00003)
                j_lon = row['f_lon'] + random.uniform(-0.00003, 0.00003)
                
                folium.CircleMarker(
                    location=[j_lat, j_lon],
                    radius=8, color='white', weight=1, fill=True,
                    fill_color='#dc2626', fill_opacity=0.8,
                    popup=f"<b>จุดเกิดเหตุ: {row['Location']}</b><br>ID: {row['Report_ID']}<br>เหตุ: {row['Incident_Type']}"
                ).add_to(cluster)

            st_folium(m, width="100%", height=600, returned_objects=[])
            
            st.info("💡 ข้อมูลนี้เป็นข้อมูลสรุป (Caching 6 Hours) เพื่อความเสถียรของระบบ")
            
            if st.button("🔄 อัปเดตข้อมูลเดี๋ยวนี้ (Manual Refresh)"):
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("ยังไม่มีข้อมูลการแจ้งเหตุในปีการศึกษานี้")

    except Exception as e:
        st.error(f"Error: {e}")

# ... (ส่วนที่เหลือของโค้ด เช่น investigation_module, main และอื่นๆ ให้จัดเรียงตามลำดับเดิม) ...

if __name__ == "__main__":
    main()
