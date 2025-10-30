import sys
import os
import streamlit as st
import pandas as pd
import plotly.express as px

# 💡💡 --- (1. كود إصلاح مسار الاستيراد) --- 💡💡
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
# 💡💡 --- (نهاية الكود المضاف) --- 💡💡

try:
    # --- (💡 تعديل: تمت إضافة build_sidebar و GSheetError) ---
    from shared_helpers import (
        apply_global_styles, build_sidebar,
        get_gsheet_connection, get_patient_history_df,
        GSheetError # (يفضل استيراد الأخطاء المخصصة)
    )
except ImportError:
    st.error("فشل استيراد shared_helpers.py. تأكد أن الملف موجود في المجلد الرئيسي.")
    st.stop()

# --- 💡💡 (2. تطبيق الـ CSS والقائمة الجانبية) 💡💡 ---
apply_global_styles()
build_sidebar() # <-- 💡 (تمت إضافة هذا السطر ليحل مشكلة اختفاء القائمة)


def show_dashboard():
    st.title("📊 لوحة متابعة المريضة")
    st.markdown("هنا يمكنكِ عرض السجل التاريخي للقياسات والتحاليل.")

    try:
        worksheet = get_gsheet_connection()
    except GSheetError as e: # <-- (أفضل استخدام الخطأ المخصص)
        st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطأ غير متوقع في الاتصال: {e}")
        st.stop()

    # --- 1. إدخال الرقم التعريفي ---
    st.subheader("🔍 يرجى إدخال الرقم التعريفي للمريضة")

    # استخدام session_state للاحتفاظ بالرقم التعريفي
    if 'dashboard_patient_id' not in st.session_state:
        st.session_state.dashboard_patient_id = ""

    patient_id_input = st.text_input("الرقم التعريفي (Patient ID)",
                                     value=st.session_state.dashboard_patient_id,
                                     key="dashboard_patient_id_input")

    if not patient_id_input:
        st.info("أدخل الرقم التعريفي لعرض البيانات.")
        st.stop()

    # تحديث الـ session_state
    st.session_state.dashboard_patient_id = patient_id_input

    # --- 2. جلب البيانات ---
    try:
        with st.spinner("جاري تحميل السجل التاريخي..."):
            history_df = get_patient_history_df(worksheet, patient_id_input)
    except Exception as e:
        st.error(f"❌ فشل في جلب البيانات: {e}")
        st.stop()

    if history_df.empty:
        st.warning("لم يتم العثور على أي سجلات لهذا الرقم التعريفي. يرجى التأكد من صحته.")
        st.stop()

    # --- 3. عرض الرسوم البيانية ---
    st.markdown("---")
    st.header(f"📈 الرسوم البيانية للمريضة: {history_df['patient_name'].iloc[-1]}")

    # التأكد من أن الأعمدة رقمية
    history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
    numeric_cols = ['current_weight_kg', 'systolic_bp', 'diastolic_bp', 'fasting_glucose']
    for col in numeric_cols:
        history_df[col] = pd.to_numeric(history_df[col], errors='coerce')

    # --- Chart 1: Weight Gain ---
    st.subheader("⚖️ متابعة زيادة الوزن")
    fig_weight = px.line(history_df.dropna(subset=['current_weight_kg']),
                         x='timestamp',
                         y='current_weight_kg',
                         title="تطور الوزن (كجم) عبر الزيارات",
                         markers=True,
                         labels={'timestamp': 'تاريخ الزيارة', 'current_weight_kg': 'الوزن (كجم)'})
    fig_weight.update_layout(title_x=0.5, xaxis_title="التاريخ", yaxis_title="الوزن (كجم)")
    st.plotly_chart(fig_weight, use_container_width=True)

    # --- Chart 2: Blood Pressure ---
    st.subheader("❤️ متابعة ضغط الدم")
    # نحتاج لإعادة هيكلة البيانات قليلاً لـ Plotly
    bp_df = history_df.dropna(subset=['systolic_bp', 'diastolic_bp'])
    bp_df_melted = bp_df.melt(id_vars=['timestamp'],
                              value_vars=['systolic_bp', 'diastolic_bp'],
                              var_name='نوع الضغط',
                              value_name='القيمة')

    fig_bp = px.line(bp_df_melted,
                     x='timestamp',
                     y='القيمة',
                     color='نوع الضغط',
                     title="تطور ضغط الدم (الانقباضي والانبساطي)",
                     markers=True,
                     labels={'timestamp': 'تاريخ الزيارة', 'القيمة': 'قيمة الضغط (mmHg)', 'نوع الضغط': 'نوع الضغط'})
    fig_bp.update_layout(title_x=0.5, xaxis_title="التاريخ", yaxis_title="الضغط (mmHg)")
    st.plotly_chart(fig_bp, use_container_width=True)

    # --- Chart 3: Fasting Glucose ---
    st.subheader("🩸 متابعة سكر الدم (صائم)")
    fig_glucose = px.line(history_df.dropna(subset=['fasting_glucose']),
                          x='timestamp',
                          y='fasting_glucose',
                          title="تطور سكر الدم الصائم (mg/dL)",
                          markers=True,
                          labels={'timestamp': 'تاريخ الزيارة', 'fasting_glucose': 'السكر الصائم (mg/dL)'})
    fig_glucose.update_layout(title_x=0.5, xaxis_title="التاريخ", yaxis_title="السكر (mg/dL)")
    # إضافة خطوط مرجعية
    fig_glucose.add_hline(y=95, line_dash="dot", line_color="red", annotation_text="الحد الأقصى (95)")
    fig_glucose.add_hline(y=70, line_dash="dot", line_color="orange", annotation_text="الحد الأدنى (70)")
    st.plotly_chart(fig_glucose, use_container_width=True)

    # --- 4. عرض البيانات كجدول ---
    with st.expander("عرض السجل الكامل كجدول"):
        st.dataframe(history_df)


# --- تشغيل الدالة الرئيسية ---
if 'dashboard_patient_id' not in st.session_state:
    st.session_state.dashboard_patient_id = ""
show_dashboard()

