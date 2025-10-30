import streamlit as st
import datetime
# import sys ❌ تم حذف استيراد sys بالكامل
import os # تم الاحتفاظ بـ os لاستخدامه في plotly

try:
    # --- استيراد الدوال من الملف المشترك (الآن ستنجح لأن المسار رسمي) ---
    from shared_helpers import apply_global_styles, build_sidebar
except ImportError:
    st.title("❌ خطأ في الإعداد")
    st.error("فشل استيراد shared_helpers.py. يرجى التأكد من أن الملف موجود في المجلد الرئيسي (Root).")
    st.stop()

# --- 💡💡 تطبيق الـ CSS والقائمة الجانبية 💡💡 ---
apply_global_styles()
build_sidebar()


def show_fmc_counter():
    st.title("👣 عداد حركة الجنين (FMC)")

    # --- (تم حذف زر "العودة للقائمة الرئيسية" من هنا) ---

    st.markdown("""
    **متى وكيف؟**
    * 🗓️ يُنصح بالبدء بالمراقبة المنتظمة حوالي **الأسبوع 28**.
    * ⏰ اختاري وقتاً يكون فيه طفلك نشيطاً عادةً (غالبًا بعد الأكل).
    * 🧘‍♀️ استلقي على جانبك الأيسر وركزي.
    * 👆 اضغطي على "بدء العد الآن".
    * ✅ مع كل حركة (ركلة، لفة)، اضغطي على "تسجيل حركة".
    * 🏁 الهدف: **10 حركات** خلال **ساعتين (120 دقيقة)**.
    * ❗ **هام:** إذا لم تشعري بـ 10 حركات خلال ساعتين، أو لاحظتِ **انخفاضًا كبيرًا** في نمط الحركة المعتاد لطفلك، **تواصلي مع طبيبك أو المستشفى فورًا للاطمئنان.**
    """)
    st.divider()

    if st.session_state.fmc_start_time is None:
        if st.button("⏰ بدء العد الآن", type="primary", use_container_width=True):
            st.session_state.fmc_start_time = datetime.datetime.now();
            st.session_state.fmc_count = 0;
            st.rerun()
    else:
        minutes_elapsed = int((datetime.datetime.now() - st.session_state.fmc_start_time).total_seconds() // 60)
        met_col1, met_col2 = st.columns(2);
        met_col1.metric("الحركات", f"{st.session_state.fmc_count} / 10");
        met_col2.metric("الوقت", f"{minutes_elapsed} دقيقة")
        st.progress(st.session_state.fmc_count / 10)
        if st.button("➕ تسجيل حركة", use_container_width=True, disabled=(st.session_state.fmc_count >= 10)):
            st.session_state.fmc_count += 1
            if st.session_state.fmc_count >= 10: st.balloons(); st.success(
                f"🎉 ممتاز! 10 حركات في {minutes_elapsed} دقيقة."); st.session_state.fmc_start_time = None
            st.rerun()
        if minutes_elapsed >= 120 and st.session_state.fmc_count < 10: st.error(
            "‼️ مر ساعتان ولم يتم تسجيل 10 حركات. تواصلي مع طبيبكِ.")
        if st.button(
                "🔄 إعادة البدء"): st.session_state.fmc_start_time = None; st.session_state.fmc_count = 0; st.rerun()

# --- (في نهاية ملف fmc_counter.py) ---

# تهيئة متغيرات الصفحة دي
if 'fmc_start_time' not in st.session_state:
    st.session_state.fmc_start_time = None
if 'fmc_count' not in st.session_state:
    st.session_state.fmc_count = 0

# 💡💡 السطر الأهم: شغل الدالة الرئيسية
show_fmc_counter()
