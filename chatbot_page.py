import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
# import sys ❌ تم حذف استيراد sys بالكامل


# --- استيراد الموارد المشتركة (الآن ستنجح لأن المسار رسمي) ---
try:
    from shared_helpers import (
        apply_global_styles, build_sidebar,
        MODEL_NAME, MEDICAL_KB, USE_GEMINI,
        get_gsheet_connection, get_patient_history_df, GSheetError, safe_get
    )
except ImportError:
    st.title("❌ خطأ في الإعداد")
    st.error("فشل استيراد shared_helpers.py. يرجى التأكد من أن الملف موجود في المجلد الرئيسي (Root).")
    st.stop()

# --- 💡💡 تطبيق الـ CSS والقائمة الجانبية 💡💡 ---
apply_global_styles()
build_sidebar()


def show_chatbot_page():
    """
    يعرض واجهة الدردشة الذكية، مع ميزة تحميل تاريخ المريضة.
    """

    # --- التحقق من إعدادات الـ AI ---
    if not USE_GEMINI:
        st.error("خدمة الذكاء الاصطناعي غير مُعدة. يرجى مراجعة ملف .streamlit/secrets.toml.")
        st.stop()

    st.title("💬 الدردشة الذكية")
    st.info("اطرحي أي سؤال عام، أو أدخلي الرقم التعريفي أولاً للحصول على نصيحة مخصصة بناءً على تاريخك.")

    # --- 💡💡 (3. الميزة الجديدة: تحميل تاريخ المريضة) 💡💡 ---
    try:
        worksheet = get_gsheet_connection()
    except GSheetError as e:
        st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        st.stop()

    # تهيئة المتغيرات في session_state
    if 'chatbot_patient_id' not in st.session_state:
        st.session_state.chatbot_patient_id = ""
    if 'chatbot_history_summary' not in st.session_state:
        st.session_state.chatbot_history_summary = "لا يوجد تاريخ مرضي مسجل."

    patient_id = st.text_input("الرقم التعريفي (اختياري)", st.session_state.chatbot_patient_id)

    if st.button("تحميل تاريخ المريضة"):
        history_summary = "لا يوجد تاريخ مرضي مسجل."
        if patient_id:
            try:
                history_df = get_patient_history_df(worksheet, patient_id)
                if not history_df.empty:
                    last_record = history_df.iloc[-1]
                    # إنشاء ملخص بسيط لآخر زيارة
                    history_summary = (
                        f"المريضة لديها تاريخ مسجل. "
                        f"الاسم: {last_record.get('patient_name', 'N/A')}. "
                        f"آخر زيارة: {last_record.get('timestamp', 'N/A')}. "
                        f"آخر ضغط: {last_record.get('systolic_bp', 'N/A')}/{last_record.get('diastolic_bp', 'N/A')}. "
                        f"آخر سكر صائم: {last_record.get('fasting_glucose', 'N/A')}. "
                        f"تاريخها الطبي: {last_record.get('past_medical_history', 'N/A')}."
                    )
                    st.session_state.chatbot_patient_id = patient_id
                    st.success(f"تم تحميل تاريخ المريضة: {last_record.get('patient_name', 'N/A')}")
                else:
                    st.warning("لم يتم العثور على سجل مطابق لهذا الرقم التعريفي.")
                    st.session_state.chatbot_patient_id = ""
            except Exception as e:
                st.error(f"خطأ أثناء جلب التاريخ: {e}")
                history_summary = "خطأ في تحميل التاريخ."
        else:
            st.info("لم يتم إدخال رقم تعريفي. سيقدم المساعد نصائح عامة.")
            st.session_state.chatbot_patient_id = ""

        # (هام) إعادة تعيين الشات عند تغيير المريض
        if st.session_state.chatbot_history_summary != history_summary:
            st.session_state.chatbot_history_summary = history_summary
            if "chat_session" in st.session_state:
                del st.session_state.chat_session
            if "chat_history_display" in st.session_state:
                del st.session_state.chat_history_display
            st.rerun()
    # --- (نهاية الميزة الجديدة) ---

    # --- إعداد نموذج الدردشة (نصي فقط) ---
    try:
        chat_model = genai.GenerativeModel(
            MODEL_NAME,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
    except Exception as e:
        st.error(f"حدث خطأ أثناء إعداد نموذج Gemini: {e}")
        st.stop()

    # --- إعداد البرومبت الأساسي (System Prompt) ---
    # (الآن أصبح ديناميكيًا بناءً على تاريخ المريضة)
    history_context = st.session_state.chatbot_history_summary
    system_prompt = f"""
    أنت مساعد طبي ذكي متخصص في الحمل. مهمتك هي الإجابة على أسئلة المستخدمات.

    معلومات المريضة الحالية:
    ---
    {history_context}
    ---

    يجب عليك الالتزام بالقواعد التالية بصرامة:
    1.  **استخدم السياق أعلاه وقاعدة المعرفة هذه فقط:** \n{MEDICAL_KB.to_string()}\n
    2.  إذا كان لدى المريضة تاريخ مرضي (مثل Preeclampsia سابقة)، اجعل تحذيراتك أكثر جدية.
    3.  لا تقدم أي معلومات طبية خارج هذه القاعدة. إذا سئلت عن شيء غير موجود، قل "ليس لدي معلومات كافية عن هذا الموضوع."
    4.  قم دائمًا بتقييم الأعراض بناءً على "Risk_Signs" في قاعدة المعرفة.
    5.  حدد مستوى الإلحاح (روتيني، استشارة قريبة، طوارئ طبية) بوضوح في إجابتك.
    6.  كن لطيفًا ومتعاطفًا، ولكن دقيقًا ومباشرًا.
    """

    # --- تهيئة سجل الدردشة ---
    if "chat_session" not in st.session_state:
        try:
            # بدء جلسة الدردشة مع البرومبت الأساسي
            st.session_state.chat_session = chat_model.start_chat(history=[
                {"role": "user", "parts": [system_prompt]},
                {"role": "model",
                 "parts": ["أهلاً بكِ، أنا مساعد الحمل الذكي. كيف يمكنني مساعدتك اليوم؟ (يرجى وصف الأعراض بوضوح)"]}
            ])
            # تهيئة سجل العرض على الشاشة
            st.session_state.chat_history_display = [
                {"role": "assistant",
                 "content": "أهلاً بكِ، أنا مساعد الحمل الذكي. كيف يمكنني مساعدتك اليوم؟ (يرجى وصف الأعراض بوضوح)"}
            ]
        except Exception as e:
            st.error(f"فشل في بدء جلسة الدردشة: {e}")
            st.session_state.chat_session = None
            st.session_state.chat_history_display = []

    # --- عرض رسائل الدردشة السابقة ---
    if "chat_history_display" in st.session_state:
        for message in st.session_state.chat_history_display:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # --- استقبال مدخلات المستخدم ---
    if prompt := st.chat_input("وصفي أعراضك هنا..."):
        # 1. عرض رسالة المستخدم
        st.session_state.chat_history_display.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. إرسال الرسالة إلى Gemini والحصول على الرد
        if st.session_state.chat_session:
            try:
                with st.spinner("المساعد الذكي يفكر..."):
                    response = st.session_state.chat_session.send_message(prompt)

                    # التحقق من حظر الأمان
                    if not response.parts:
                        response_text = "تم حظر الرد من قبل نظام الأمان. يرجى إعادة صياغة سؤالك."
                    else:
                        response_text = response.text

                # 3. عرض رد المساعد
                st.session_state.chat_history_display.append({"role": "assistant", "content": response_text})
                with st.chat_message("assistant"):
                    st.markdown(response_text)

            except Exception as e:
                st.error(f"حدث خطأ أثناء معالجة الرد: {e}")
        else:
            st.error("عذرًا، خدمة الدردشة غير متاحة حاليًا.")


# --- 💡💡 السطر الأهم: شغل الدالة الرئيسية 💡💡 ---
show_chatbot_page()
```eof

**الآن، يرجى إرسال كود ملف `pages/dashboard.py` ليتم تعديله (حذف كود `sys.path`).**
