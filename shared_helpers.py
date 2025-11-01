# ==============================
# shared_helpers.py (Final Full Version)
# ==============================

import os
import io
import re
import json
import uuid
import base64
import logging
import datetime
import platform
import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, APIError
import google.generativeai as genai
from google.generativeai.types import generation_types
from PIL import Image

# ==============================
# 🔹 إعداد اللوج
# ==============================
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ==============================
# 🔹 متغيرات عامة
# ==============================
MODEL_NAME = 'gemini-2.5-flash'
GEMINI_MODEL = None
USE_GEMINI = False
FPDF_EXISTS = False
TESSERACT_AVAILABLE = False
ARABIC_FONT_PATH = "DejaVuSans.ttf"

# ==============================
# 🔹 محاولات استيراد آمنة
# ==============================
try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    import arabic_reshaper
    from bidi.algorithm import get_display
    if os.path.exists(ARABIC_FONT_PATH):
        FPDF_EXISTS = True
except Exception as e:
    logger.warning(f"PDF/Arabic libs not fully available: {e}")

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except Exception as e:
    logger.warning(f"Tesseract not available: {e}")

# ==============================
# 🔹 ثوابت واجهة المستخدم
# ==============================
SVG_DATA_URI = "https://upload.wikimedia.org/wikipedia/commons/1/1b/Pregnancy_icon.svg"


# ==============================
# 🔹 تهيئة Gemini
# ==============================
def init_gemini_from_secrets(secrets: dict):
    global GEMINI_MODEL, USE_GEMINI

    try:
        if not secrets or "GEMINI_API_KEY" not in secrets:
            logger.warning("GEMINI_API_KEY not found in secrets.")
            USE_GEMINI = False
            return False

        genai.configure(api_key=secrets["GEMINI_API_KEY"])

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        GEMINI_MODEL = genai.GenerativeModel(
            MODEL_NAME,
            generation_config=generation_types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7,
                top_p=0.95
            ),
            safety_settings=safety_settings
        )
        USE_GEMINI = True
        logger.info("✅ Gemini initialized successfully.")
        return True

    except Exception as e:
        logger.exception(f"Failed to initialize Gemini: {e}")
        USE_GEMINI = False
        return False


# ==============================
# 🔹 دوال المظهر العام
# ==============================
def apply_global_styles():
    """تطبيق تنسيقات CSS على صفحات Streamlit"""
    st.markdown("""
        <style>
        /* عام */
        body {
            font-family: 'Cairo', sans-serif !important;
            background-color: #fff5f8;
        }
        /* أزرار */
        .stButton button {
            background-color: #d81b60 !important;
            color: white !important;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            transition: 0.3s;
        }
        .stButton button:hover {
            background-color: #ad1457 !important;
        }
        /* شريط جانبي */
        section[data-testid="stSidebar"] {
            background-color: #fce4ec !important;
        }
        </style>
    """, unsafe_allow_html=True)


def build_sidebar():
    """إنشاء القائمة الجانبية الرئيسية"""
    with st.sidebar:
        st.image(SVG_DATA_URI, width=180)
        st.markdown("## 🩺 القائمة الرئيسية")
        st.page_link("app1.py", label="🏠 الصفحة الرئيسية", icon="🏠")
        st.page_link("pages/assessment_wizard.py", label="👩‍⚕️ التقييم الشامل")
        st.page_link("pages/dashboard.py", label="📊 لوحة المتابعة")
        st.page_link("pages/chatbot_page.py", label="💬 الدردشة الذكية")
        st.page_link("pages/weekly_guide.py", label="📅 دليل الحمل الأسبوعي")
        st.page_link("pages/fmc_counter.py", label="👣 عداد حركة الجنين")
        st.markdown("---")
        st.caption("إصدار المشروع: v27 - 2025")


# ==============================
# 🔹 دوال مساعدة عامة
# ==============================
def connect_to_google_sheet(json_keyfile_path, sheet_name):
    try:
        gc = gspread.service_account(filename=json_keyfile_path)
        sh = gc.open(sheet_name)
        worksheet = sh.sheet1
        return worksheet
    except SpreadsheetNotFound:
        logger.error(f"❌ Spreadsheet '{sheet_name}' not found.")
    except APIError as e:
        logger.error(f"❌ Google Sheets API error: {e}")
    except Exception as e:
        logger.error(f"❌ Unknown error while connecting to Sheets: {e}")
    return None


def extract_text_from_image(image_bytes):
    if not TESSERACT_AVAILABLE:
        return "Tesseract not available"
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang='eng+ara')
        return text.strip()
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""


def save_pdf_report(file_path, title, content_lines):
    if not FPDF_EXISTS:
        return False
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=14)
        pdf.cell(200, 10, txt=title, ln=True, align='C')
        pdf.set_font("Arial", size=12)
        for line in content_lines:
            pdf.multi_cell(0, 8, txt=line)
        pdf.output(file_path)
        return True
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return False


def generate_with_gemini(prompt_text):
    if not USE_GEMINI or GEMINI_MODEL is None:
        return "Gemini not initialized."
    try:
        response = GEMINI_MODEL.generate_content(prompt_text)
        return response.text if response else "No response."
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return str(e)


# ==============================
# 🔹 دوال إضافية صغيرة
# ==============================
def generate_unique_id():
    return str(uuid.uuid4())


def current_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def base64_encode(data):
    return base64.b64encode(data.encode()).decode()


def base64_decode(encoded):
    return base64.b64decode(encoded).decode()


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Created directory: {path}")


def normalize_filename(name):
    name = re.sub(r'[^\w\-_. ]', '_', name)
    return name.strip()


# ==============================
# 🔹 اختبار (عند التشغيل المباشر)
# ==============================
if __name__ == "__main__":
    print("✅ shared_helpers.py imported successfully.")
    print(f"FPDF: {FPDF_EXISTS} | Tesseract: {TESSERACT_AVAILABLE}")

