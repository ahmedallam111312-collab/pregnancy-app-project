"""
helpers_v30_no_sidebar.py
الإصدار النهائي المعدّل بدون Sidebar
مساعد الحمل الذكي - 2025
"""

import os
import io
import re
import sys
import uuid
import json
import base64
import logging
import datetime
import platform
import pandas as pd
import streamlit as st
from PIL import Image

# ==============================
# مكتبات خارجية اختيارية
# ==============================
try:
    import gspread
    from gspread.exceptions import SpreadsheetNotFound, APIError
except Exception:
    gspread = None

try:
    import google.generativeai as genai
    from google.generativeai.types import generation_types
except Exception:
    genai = None

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    import arabic_reshaper
    from bidi.algorithm import get_display
    FPDF_EXISTS = True
except Exception:
    FPDF_EXISTS = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False


# ==============================
# الإعداد العام
# ==============================
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

SVG_DATA_URI = "https://upload.wikimedia.org/wikipedia/commons/1/1b/Pregnancy_icon.svg"

GEMINI_MODEL = None
USE_GEMINI = False

GSHEET_ALL_HEADERS = [
    "ID", "الاسم", "العمر", "تاريخ", "النتيجة", "تعليق الطبيب", "ملاحظات إضافية"
]

# ==============================
# 💡 إعدادات الواجهة
# ==============================
def apply_global_styles():
    """تطبيق تنسيقات CSS عامة (مع دعم خاص للموبايل)."""
    st.markdown("""
        <style>
        body, p, div, span, label, input, textarea {
            color: #000 !important;
            font-family: 'Cairo', sans-serif !important;
        }

        /* للأجهزة الصغيرة (الموبايل) */
        @media (max-width: 768px) {
            body, p, div, span, label, input, textarea {
                color: #000 !important;
                font-size: 17px !important;
                line-height: 1.6 !important;
            }
        }

        .stButton button {
            background-color: #d81b60 !important;
            color: #fff !important;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
        }

        .stButton button:hover {
            background-color: #ad1457 !important;
        }

        .stTextInput input {
            color: #000 !important;
        }
        </style>
    """, unsafe_allow_html=True)


# ==============================
# 🔹 Gemini
# ==============================
def init_gemini_from_secrets(secrets: dict):
    """تهيئة Gemini من Streamlit secrets"""
    global GEMINI_MODEL, USE_GEMINI

    if not genai:
        st.warning("مكتبة Gemini غير متوفرة.")
        return False

    try:
        if not secrets or "GEMINI_API_KEY" not in secrets:
            USE_GEMINI = False
            return False

        genai.configure(api_key=secrets["GEMINI_API_KEY"])
        GEMINI_MODEL = genai.GenerativeModel(
            "gemini-2.0-flash",
            generation_config=generation_types.GenerationConfig(
                temperature=0.6, top_p=0.9
            ),
        )
        USE_GEMINI = True
        return True

    except Exception as e:
        st.error(f"فشل تهيئة Gemini: {e}")
        return False


def generate_with_gemini(prompt_text):
    """توليد محتوى نصي من Gemini"""
    if not USE_GEMINI or GEMINI_MODEL is None:
        return "❌ لم يتم تهيئة Gemini."
    try:
        response = GEMINI_MODEL.generate_content(prompt_text)
        return response.text if response else "⚠️ لا يوجد رد من النموذج."
    except Exception as e:
        return f"⚠️ خطأ في الاتصال بـGemini: {e}"


# ==============================
# 🔹 OCR (قراءة الصور)
# ==============================
def extract_text_from_image(image_bytes):
    """استخراج النص من صورة (عربية + إنجليزية)."""
    if not TESSERACT_AVAILABLE:
        return "❌ مكتبة Tesseract غير متاحة."
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang='eng+ara')
        return text.strip()
    except Exception as e:
        return f"⚠️ فشل استخراج النص: {e}"


# ==============================
# 🔹 PDF Reports
# ==============================
def save_pdf_report(file_path, title, content_lines):
    """إنشاء تقرير PDF بسيط بالعربية."""
    if not FPDF_EXISTS:
        return False
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=14)
        pdf.cell(0, 10, txt=title, ln=True, align='C')
        pdf.set_font("Arial", size=12)
        for line in content_lines:
            pdf.multi_cell(0, 8, txt=line)
        pdf.output(file_path)
        return True
    except Exception as e:
        logger.error(f"فشل إنشاء PDF: {e}")
        return False


# ==============================
# 🔹 Google Sheets
# ==============================
class GSheetError(Exception):
    pass


def connect_to_google_sheet(json_keyfile_path, sheet_name):
    """الاتصال بجدول Google Sheets"""
    if not gspread:
        raise GSheetError("❌ مكتبة gspread غير مثبتة.")
    try:
        gc = gspread.service_account(filename=json_keyfile_path)
        sh = gc.open(sheet_name)
        return sh.sheet1
    except Exception as e:
        raise GSheetError(f"فشل الاتصال بـGoogle Sheets: {e}")


def save_record_to_gsheet(worksheet, data_dict):
    """حفظ سجل جديد في Google Sheets."""
    try:
        if not worksheet:
            raise GSheetError("ورقة Google غير متاحة.")
        row_id = str(uuid.uuid4())[:8]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        final_row = {
            "ID": row_id,
            "الاسم": data_dict.get("name", "غير محدد"),
            "العمر": data_dict.get("age", ""),
            "تاريخ": now,
            "النتيجة": data_dict.get("result", ""),
            "تعليق الطبيب": data_dict.get("doctor_comment", ""),
            "ملاحظات إضافية": data_dict.get("notes", ""),
        }

        # تأكد من أن العناوين موجودة
        headers = worksheet.row_values(1)
        if not headers:
            worksheet.append_row(GSHEET_ALL_HEADERS)

        worksheet.append_row([final_row.get(h, "") for h in GSHEET_ALL_HEADERS])
        return True
    except Exception as e:
        raise GSheetError(f"فشل حفظ السجل: {e}")


# ==============================
# 🔹 دوال مساعدة عامة
# ==============================
def generate_unique_id():
    return str(uuid.uuid4())


def current_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_filename(name):
    name = re.sub(r"[^\w\-_. ]", "_", name)
    return name.strip()


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


# ==============================
# 🔹 اختبار محلي
# ==============================
if __name__ == "__main__":
    print("✅ helpers_v30_no_sidebar loaded successfully.")
    print(f"Gemini available: {USE_GEMINI}")
    print(f"Tesseract available: {TESSERACT_AVAILABLE}")
    print(f"PDF available: {FPDF_EXISTS}")
