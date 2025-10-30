"""
Professional Pregnancy AI Assistant (Graduation Project - v26 - Final Sidebar Fix)
This is the main entry point (Home Page) for the Streamlit app.
It now calls the global sidebar and style functions from shared_helpers.
"""

import streamlit as st
import base64
import platform
import os
import sys

# --- 1. كود إصلاح مسار الاستيراد (مهم جداً) ---
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)
# --- (نهاية الكود) ---

try:
    # --- 2. استيراد الدوال العامة من الملف المشترك ---
    from shared_helpers import apply_global_styles, build_sidebar, SVG_DATA_URI
except ImportError:
    st.error("فشل استيراد shared_helpers.py. تأكد أن الملف موجود في المجلد الرئيسي.")
    st.stop()


# --- Page Config (يجب أن يكون أول أمر Streamlit) ---
st.set_page_config(page_title="مساعد الحمل الذكي", layout="wide",
                   initial_sidebar_state="expanded")

# --- 💡💡 3. تطبيق الـ CSS والقائمة الجانبية في كل صفحة 💡💡 ---
apply_global_styles()
build_sidebar()


# ---------------------------------------------------------------------
# --- محتوى الصفحة الرئيسية ---
# ---------------------------------------------------------------------

st.image(SVG_DATA_URI, width=420)
st.title("مساعد الحمل الذكي")
st.markdown(
    f"""<p style="text-align: center; font-size: 1.1em; color: #880E4F;">مشروع تخرج مقدم بواسطة: <strong>أحمد</strong></p>""",
    unsafe_allow_html=True)
st.markdown("---")

st.subheader("أهلاً بكِ في نظام المتابعة الذكي!")
st.markdown("يرجى اختيار إحدى الخدمات من **القائمة الجانبية** (على اليمين في النسخة العربية) للبدء، أو استخدم الاختصارات السريعة:")

st.info("✅ **تم الإصلاح:** ستظهر القائمة الجانبية العربية الآن في جميع الصفحات الفرعية.")


# --- (أزرار التنقل في الصفحة الرئيسية) ---
st.divider()
st.subheader("الوصول السريع للخدمات")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("👩‍⚕️ التقييم الشامل", use_container_width=True):
        st.switch_page("pages/assessment_wizard.py")
    if st.button("📊 لوحة المتابعة", use_container_width=True):
        st.switch_page("pages/dashboard.py")

with col2:
    if st.button("💬 الدردشة الذكية", use_container_width=True):
        st.switch_page("pages/chatbot_page.py")
    if st.button("📅 دليل الحمل الأسبوعي", use_container_width=True):
        st.switch_page("pages/weekly_guide.py")

with col3:
    if st.button("👣 عداد حركة الجنين", use_container_width=True):
        st.switch_page("pages/fmc_counter.py")
# --- (نهاية الكود) ---
