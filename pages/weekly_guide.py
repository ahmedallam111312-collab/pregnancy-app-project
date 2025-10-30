import streamlit as st
import pandas as pd
import sys
import os

# 💡💡 --- (1. كود إصلاح مسار الاستيراد) --- 💡💡
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
# 💡💡 --- (نهاية الكود المضاف) --- 💡💡

try:
    # --- (💡 تعديل: تمت إضافة build_sidebar) ---
    from shared_helpers import apply_global_styles, build_sidebar, safe_get, WEEKLY_GUIDE
except ImportError:
    st.error("فشل استيراد shared_helpers.py. تأكد أن الملف موجود في المجلد الرئيسي.")
    st.stop()

# --- 💡💡 (2. تطبيق الـ CSS والقائمة الجانبية) 💡💡 ---
apply_global_styles()
build_sidebar()  # <-- 💡 (تمت إضافة هذا السطر ليحل مشكلة اختفاء القائمة)


def show_weekly_guide():
    st.title("📅 دليل الحمل أسبوع بأسبوع")

    weekly_guide = WEEKLY_GUIDE  # <-- (استخدام الثابت المستورد)

    default_week = 8

    # --- محاولة قراءة أسبوع الحمل من التقييم الأخير ---
    last_record_dict = {}
    if 'patient_history_df' in st.session_state and not st.session_state.patient_history_df.empty:
        last_record_dict = st.session_state.patient_history_df.iloc[-1].to_dict()

    hist_week_val = safe_get(last_record_dict, 'gestational_week', default_week)
    try:
        hist_week = int(hist_week_val)
    except (ValueError, TypeError):
        hist_week = default_week

    current_week_guess = hist_week
    selected_week_input = st.number_input("اختاري أسبوع الحمل:", 1, 40, value=max(1, min(40, current_week_guess)),
                                          step=1)
    available_weeks = sorted(weekly_guide.keys())
    closest_week = min(available_weeks, key=lambda w: abs(w - selected_week_input))

    st.info(f"عرض معلومات الأسبوع {closest_week}")
    info = weekly_guide[closest_week]
    col1, col2 = st.columns(2);
    col1.subheader(f"👶 تطور الجنين");
    col1.write(info["f"]);
    col2.subheader("🤰 التغيرات في جسمكِ");
    col2.write(info["m"]);

    st.subheader("✨ نصائح هامة لكِ");
    st.write(info["t"])  # <-- (💡 تصحيح: جعل النصائح بعرض الصفحة الكامل)


# --- (في نهاية ملف weekly_guide.py) ---

# تهيئة متغيرات الصفحة دي
if 'patient_history_df' not in st.session_state:
    st.session_state.patient_history_df = pd.DataFrame()

# 💡💡 السطر الأهم: شغل الدالة الرئيسية
show_weekly_guide()

