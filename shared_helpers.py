# ==============================
# shared_helpers.py (Safe Version)
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

# ========== إعداد لوج آمن ==========
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ========== متغيرات عامة ==========
MODEL_NAME = 'gemini-2.5-flash'
GEMINI_MODEL = None
USE_GEMINI = False
FPDF_EXISTS = False
TESSERACT_AVAILABLE = False

ARABIC_FONT_PATH = "DejaVuSans.ttf"


# =====================================
# محاولات استيراد مكتبات إضافية بأمان
# =====================================
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


# =============================
# دالة تهيئة Gemini بأمان
# =============================
def init_gemini_from_secrets(secrets: dict):
    """
    استخدمها داخل app.py بعد تحميل st.secrets
    """
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


# =============================
# Google Sheets Utility
# =============================
def connect_to_google_sheet(json_keyfile_path, sheet_name):
    """
    ربط مع Google Sheets
    """
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


# =============================
# OCR Utility (Image to Text)
# =============================
def extract_text_from_image(image_bytes):
    """
    استخراج النص من صورة باستخدام Tesseract
    """
    if not TESSERACT_AVAILABLE:
        return "Tesseract not available"

    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang='eng+ara')
        return text.strip()
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""


# =============================
# PDF Utility
# =============================
def save_pdf_report(file_path, title, content_lines):
    """
    إنشاء تقرير PDF بسيط
    """
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


# =============================
# Gemini Prompt Utility
# =============================
def generate_with_gemini(prompt_text):
    """
    إرسال prompt إلى Gemini وإرجاع الرد
    """
    if not USE_GEMINI or GEMINI_MODEL is None:
        return "Gemini not initialized."

    try:
        response = GEMINI_MODEL.generate_content(prompt_text)
        return response.text if response else "No response."
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return str(e)


# =============================
# Misc Helpers
# =============================
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


# =============================
# اختبار بسيط (اختياري)
# =============================
if __name__ == "__main__":
    print("✅ shared_helpers.py imported successfully.")
    print(f"FPDF: {FPDF_EXISTS} | Tesseract: {TESSERACT_AVAILABLE}")
