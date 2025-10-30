import streamlit as st
import pandas as pd
import datetime
import os
import re
import uuid
# import sys ❌ تم حذف استيراد sys بالكامل


# --- استيراد الدوال المشتركة والمتغيرات (يجب أن يعمل هذا الآن في Streamlit Cloud) ---
try:
    from shared_helpers import (
        apply_global_styles, build_sidebar, 
        get_gsheet_connection, get_patient_history_df, get_relevant_risk_factors,
        calculate_bmi, ocr_with_tesseract, ai_generate_final_report, save_record_to_gsheet,
        safe_get, get_urgency_color, create_pdf_bytes, FPDF_EXISTS, ARABIC_FONT_PATH,
        GSHEET_LAB_HEADERS, TESSERACT_AVAILABLE, GSheetError, AIError, PDFError, OCRError
    )
except ImportError:
    # ❌ لن نستخدم st.error هنا، لكننا سنفشل بهدوء للسماح لـ Streamlit بالعمل
    st.title("❌ خطأ في الإعداد")
    st.error("فشل استيراد shared_helpers.py. يرجى التأكد من أن الملف موجود في المجلد الرئيسي (Root).")
    st.stop()


# --- 💡💡 تطبيق الـ CSS والقائمة الجانبية 💡💡 ---
apply_global_styles() 
build_sidebar() 


def assessment_wizard():
    """Handles the multi-step assessment workflow."""

    try:
        worksheet = get_gsheet_connection()
    except GSheetError as e:
        st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطأ غير متوقع في الاتصال: {e}")
        st.stop()

    # --- (أزرار التنقل) ---
    col_nav1, _ = st.columns([1, 1])
    if st.session_state.assessment_step > 0:
        if col_nav1.button("➡️ العودة للخطوة السابقة"):
            st.session_state.assessment_step -= 1
            st.rerun()

    # Define steps
    steps = ['أسبوع الحمل', 'الرقم التعريفي', 'المعلومات الأساسية', 'القياسات وعوامل الخطورة', 'الأعراض الحالية',
             'التحاليل ورفع الصور', 'التقرير النهائي']
    current_step_index = st.session_state.assessment_step

    if current_step_index >= len(steps):
        st.session_state.assessment_step = 0
        st.rerun()

    st.subheader(f"الخطوة {current_step_index + 1} من {len(steps)}: {steps[current_step_index]}")
    st.progress((current_step_index + 1) / len(steps))
    st.markdown("---")

    # --- STEP 0: GESTATIONAL WEEK (NEW) ---
    if st.session_state.assessment_step == 0:
        st.header("📅 ما هو أسبوع الحمل الحالي؟")
        default_gw = 8
        if 'patient_history_df' in st.session_state and not st.session_state.patient_history_df.empty:
            default_gw = int(safe_get(st.session_state.patient_history_df.iloc[-1].to_dict(), 'gestational_week', 8))

        gestational_week_input = st.number_input("أسبوع الحمل", 1, 45, value=default_gw)

        if st.button("التالي ⬅️"):
            st.session_state.form_data['gestational_week'] = gestational_week_input
            st.session_state.assessment_step = 1
            st.rerun()

    # --- STEP 1: PATIENT ID ---
    elif st.session_state.assessment_step == 1:
        st.header("💖 أدخلي الرقم التعريفي الخاص بكِ")
        patient_id = st.text_input("الرقم التعريفي (Patient ID)", key="patient_id_input",
                                   value=st.session_state.patient_id).strip()

        if st.button("التالي ⬅️"):
            if not patient_id:
                st.error("يرجى إدخال الرقم التعريفي للمتابعة.")
            else:
                st.session_state.patient_id = patient_id
                with st.spinner("جاري البحث عن السجل التاريخي..."):
                    st.session_state.patient_history_df = get_patient_history_df(worksheet, patient_id)
                st.session_state.assessment_step = 2
                st.rerun()

    # --- STEP 2: PATIENT INFO (after ID is entered) ---
    elif st.session_state.assessment_step == 2:
        st.header("👤 2. المعلومات الأساسية والتاريخ المرضي")
        last_record = {}
        patient_name = ""
        if not st.session_state.patient_history_df.empty:
            last_record = st.session_state.patient_history_df.iloc[-1].to_dict()
            patient_name = safe_get(last_record, 'patient_name', '')
            st.success(f"أهلاً بعودتكِ، {patient_name}! 👋")
        else:
            if st.session_state.patient_id: st.info("لم يتم العثور على سجل سابق. أهلاً بكِ!")

        with st.form("step2_form"):
            col_info1, col_info2 = st.columns(2);
            with col_info1:
                patient_name_input = st.text_input("✨ **اسمكِ بالكامل**", value=patient_name if patient_name else "")
                age = st.number_input("**العمر**", 15, 60, value=int(safe_get(last_record, 'age', 25)), format="%d")
            with col_info2:
                gravida = st.number_input("الحمل رقم (G)", 0, 20, value=int(safe_get(last_record, 'gravida', 1)))
                para = st.number_input("الولادات السابقة (P)", 0, 20, value=int(safe_get(last_record, 'para', 0)))
                abortion = st.number_input("الإجهاض السابق (A)", 0, 20, value=int(safe_get(last_record, 'abortion', 0)))
            past_medical_history = st.text_area("🩺 **التاريخ الطبي السابق**", height=50,
                                                value=safe_get(last_record, 'past_medical_history', ''))
            current_medications = st.text_area("💊 **الأدوية الحالية**", height=50)

            if st.form_submit_button("التالي ⬅️"):
                if not patient_name_input or not age:
                    st.error("يرجى إدخال الاسم والعمر.")
                else:
                    st.session_state.form_data['patient_name'] = patient_name_input
                    st.session_state.form_data['age'] = age
                    st.session_state.form_data['gravida'] = gravida
                    st.session_state.form_data['para'] = para
                    st.session_state.form_data['abortion'] = abortion
                    st.session_state.form_data['past_medical_history'] = past_medical_history
                    st.session_state.form_data['current_medications'] = current_medications
                    st.session_state.assessment_step = 3
                    st.rerun()

    # --- STEP 3: MEASUREMENTS & RISKS ---
    elif st.session_state.assessment_step == 3:
        st.header("📏 3. القياسات وعوامل الخطورة")
        last_record = st.session_state.patient_history_df.iloc[
            -1].to_dict() if not st.session_state.patient_history_df.empty else {}

        def get_default_value(key, default, min_val, max_val, is_float=False):
            val = safe_get(last_record, key, default)
            try:
                num_val = float(val) if is_float else int(val);
                return max(min_val, min(max_val, num_val))
            except (ValueError, TypeError):
                return default

        with st.form("step3_form"):
            with st.container(border=True):
                st.subheader("القياسات الأساسية")
                col_meas1, col_meas2, col_meas3 = st.columns(3);
                height_cm = col_meas1.number_input("**الطول (سم)**", 100, 250, placeholder="165",
                                                   value=get_default_value('height_cm', 160, 100, 250))
                pre_preg_weight = col_meas2.number_input("**الوزن قبل الحمل (كجم)**", 30.0, 250.0, placeholder="65.0",
                                                         value=get_default_value('pre_pregnancy_weight_kg', 60.0, 30.0,
                                                                                 250.0, is_float=True), format="%.1f")
                current_weight = col_meas3.number_input("**الوزن الحالي (كجم)**", 30.0, 250.0, placeholder="75.0",
                                                        format="%.1f")

            with st.container(border=True):
                gestational_week = st.session_state.form_data.get('gestational_week', 8)
                st.subheader(f"❗ عوامل الخطورة (المناسبة للأسبوع {gestational_week})")
                current_risk_factors = get_relevant_risk_factors(gestational_week)
                if not current_risk_factors:
                    st.info("لا توجد عوامل خطورة محددة مطلوبة في هذا الأسبوع.")
                selected_risk_factors = [rf for rf in current_risk_factors if st.checkbox(rf, key=f"rf_{rf}")]

            if st.form_submit_button("التالي ⬅️"):
                if not all([height_cm > 0, pre_preg_weight > 0, current_weight > 0]):
                    st.error("يرجى إدخال قيم صحيحة للطول والوزن.")
                else:
                    st.session_state.form_data['height_cm'] = height_cm
                    st.session_state.form_data['pre_pregnancy_weight_kg'] = pre_preg_weight
                    st.session_state.form_data['current_weight'] = current_weight
                    st.session_state.form_data['selected_risk_factors'] = selected_risk_factors
                    st.session_state.assessment_step = 4
                    st.rerun()

    # --- STEP 4: SYMPTOMS ---
    elif st.session_state.assessment_step == 4:
        st.header("❓ 4. الأعراض الحالية")
        with st.form("step4_form"):
            symptoms_text = st.text_area("✍️ **صفي ما تشعرين به بالتفصيل...**", height=150)

            st.divider()
            st.subheader("الغثيان والقيء (إن وجد)")
            nausea_timing = st.text_input("متى تشعرين بالغثيان؟", placeholder="مثال: صباحًا، طوال اليوم، بعد الأكل")
            vomiting_frequency = st.number_input("كم مرة تقيأتِ في آخر 24 ساعة؟", min_value=0, max_value=50, step=1,
                                                 value=0)

            if st.form_submit_button("التالي ⬅️"):
                if not symptoms_text:
                    st.error("يرجى وصف الأعراض للمتابعة.")
                else:
                    st.session_state.form_data['symptoms_text'] = symptoms_text
                    st.session_state.form_data['nausea_timing'] = nausea_timing
                    st.session_state.form_data['vomiting_frequency'] = vomiting_frequency
                    st.session_state.assessment_step = 5
                    st.rerun()

    # --- STEP 5: LABS & UPLOAD ---
    elif st.session_state.assessment_step == 5:
        st.header("🔬 5. نتائج التحاليل (إن وجدت)")

        lab_input_method = st.radio("كيف تفضلين إدخال التحاليل؟", ["إدخال يدوي", "رفع صورة تقرير"], horizontal=True)

        with st.form("step5_form"):
            if lab_input_method == "إدخال يدوي":
                with st.container(border=True):
                    st.markdown("**العلامات الحيوية:**")
                    lab_cols1 = st.columns([1, 1, 1]);
                    systolic_bp = lab_cols1[0].number_input("ضغط الدم الانقباضي", value=None, placeholder="120");
                    diastolic_bp = lab_cols1[1].number_input("ضغط الدم الانبساطي", value=None, placeholder="80");
                    bnp = lab_cols1[2].number_input("BNP (pg/mL)", value=None, placeholder="<100")
                    if systolic_bp is not None and diastolic_bp is not None and diastolic_bp >= systolic_bp: st.warning(
                        "تنبيه: ضغط الدم الانبساطي أعلى من أو يساوي الانقباضي.")
                    st.markdown("**متابعة السكر:**")
                    lab_cols2 = st.columns(3);
                    fasting_glucose = lab_cols2[0].number_input("سكر صائم (mg/dL)", value=None, placeholder="90");
                    ogtt_1h = lab_cols2[1].number_input("OGTT - 1 Hr (mg/dL)", value=None, placeholder="180");
                    ogtt_2h = lab_cols2[2].number_input("OGTT - 2 Hr (mg/dL)", value=None, placeholder="155")
                    st.markdown("**تحاليل الدم الأخرى:**")
                    lab_cols3 = st.columns(3);
                    hba1c = lab_cols3[0].number_input("HbA1c (%)", value=None, placeholder="5.5", format="%.1f");
                    hb = lab_cols3[1].number_input("Hemoglobin (g/dL)", value=None, placeholder="12.0", format="%.1f");
                    platelets = lab_cols3[2].number_input("Platelets (x10^3/μL)", value=None, placeholder="250")
                    st.markdown("**وظائف الكلى والكبد:**")
                    lab_cols4 = st.columns(3);
                    alt = lab_cols4[0].number_input("ALT (U/L)", value=None, placeholder="20");
                    ast = lab_cols4[1].number_input("AST (U/L)", value=None, placeholder="20");
                    creatinine = lab_cols4[2].number_input("Creatinine (mg/dL)", value=None, placeholder="0.7",
                                                           format="%.1f")
                    st.markdown("**تحليل البول:**")
                    lab_cols5 = st.columns(2);
                    urine_protein = lab_cols5[0].selectbox("بروتين البول",
                                                           ["Negative", "Trace", "+", "++", "+++", "++++"], index=0);
                    urine_ketones = lab_cols5[1].selectbox("كيتون البول",
                                                           ["Negative", "Trace", "Small", "Moderate", "Large"], index=0)

            elif lab_input_method == "رفع صورة تقرير":
                uploaded_image = st.file_uploader("📂 ارفعي صورة تقرير التحاليل", type=['jpg', 'jpeg', 'png'],
                                                  key=f'uploader_{st.session_state.uploaded_image_key}')

            submitted = st.form_submit_button("💖 تحليل وإنشاء التقرير", type="primary", use_container_width=True)

        if lab_input_method == "رفع صورة تقرير":
            if uploaded_image and (not st.session_state.ocr_results or uploaded_image.file_id != st.session_state.get(
                    'last_uploaded_id')):
                try:
                    with st.spinner("🔬 قراءة الصورة..."):
                        st.session_state.ocr_results = ocr_with_tesseract(uploaded_image.getvalue())
                        st.session_state.last_uploaded_id = uploaded_image.file_id
                        st.rerun()
                except OCRError as e:
                    st.error(f"❌ خطأ في قراءة الصورة: {e}")
                    st.session_state.ocr_results = ""  # مسح النتائج القديمة

            elif not uploaded_image:
                st.session_state.ocr_results = ""
                st.session_state.last_uploaded_id = None

            if st.session_state.ocr_results:
                st.text_area("النص المستخرج (للمراجعة):", value=st.session_state.ocr_results, height=150,
                             key="ocr_display_after_form")

        if submitted:
            if lab_input_method == "إدخال يدوي" and systolic_bp is not None and diastolic_bp is not None and systolic_bp <= diastolic_bp:
                st.error("❌ قيمة ضغط الدم الانقباضي يجب أن تكون أعلى من الانبساطي.")
                st.stop()

            ocr_text_for_analysis = st.session_state.ocr_results if lab_input_method == "رفع صورة تقرير" else ""

            with st.status("👩‍⚕️ يقوم المساعد الذكي بتحليل حالتكِ...", expanded=True) as status:
                status.write("📊 تجميع البيانات...")
                pre_preg_bmi, pre_preg_bmi_cat = calculate_bmi(st.session_state.form_data['pre_pregnancy_weight_kg'],
                                                               st.session_state.form_data['height_cm'])
                weight_gain = round(st.session_state.form_data['current_weight'] - st.session_state.form_data[
                    'pre_pregnancy_weight_kg'], 1)

                patient_info = {
                    "name": st.session_state.form_data['patient_name'], "age": st.session_state.form_data['age'],
                    "week": st.session_state.form_data['gestational_week'],
                    "gravida": st.session_state.form_data['gravida'], "para": st.session_state.form_data['para'],
                    "abortion": st.session_state.form_data['abortion'],
                    "past_medical_history": st.session_state.form_data['past_medical_history'],
                    "current_medications": st.session_state.form_data['current_medications'],
                    "pre_preg_weight": st.session_state.form_data['pre_pregnancy_weight_kg'],
                    "current_weight": st.session_state.form_data['current_weight'],
                    "weight_gain": weight_gain, "pre_preg_bmi": pre_preg_bmi,
                    "pre_pregnancy_bmi_category": pre_preg_bmi_cat,
                    "risk_factors": st.session_state.form_data['selected_risk_factors'],
                    "nausea_timing": st.session_state.form_data.get('nausea_timing', ''),  # Add nausea
                    "vomiting_frequency": st.session_state.form_data.get('vomiting_frequency', 0)  # Add vomiting
                }
                labs = {}
                if lab_input_method == "إدخال يدوي":
                    labs = locals()

                st.session_state.last_patient_info = patient_info
                st.session_state.last_labs = {k: labs.get(k) for k in GSHEET_LAB_HEADERS}

                status.write("🧠 استدعاء الذكاء الاصطناعي...")

                try:
                    ai_data_dict = ai_generate_final_report(
                        patient_info, labs, st.session_state.patient_history_df,
                        st.session_state.form_data['symptoms_text'], ocr_text_for_analysis
                    )
                    report_text = ai_data_dict.get('detailed_report', 'لم يتمكن الذكاء الاصطناعي من إنشاء تقرير.')
                    ai_extracted_labs = ai_data_dict.get('extracted_labs', {})
                    urgency = ai_data_dict.get('urgency', 'غير محدد')
                    brief_summary = ai_data_dict.get('brief_summary', 'لم يتمكن الذكاء الاصطناعي من إنشاء ملخص.')

                except AIError as e:
                    status.update(label=f"فشل تحليل الذكاء الاصطناعي: {e}", state="error")
                    st.error(f"❌ فشل تحليل الذكاء الاصطناعي: {e}")
                    st.stop()
                except Exception as e:
                    status.update(label=f"خطأ غير متوقع: {e}", state="error")
                    st.error(f"❌ حدث خطأ غير متوقع أثناء استدعاء AI: {e}")
                    st.stop()

                st.session_state.final_report = report_text
                st.session_state.ai_extracted_labs = ai_extracted_labs
                st.session_state.urgency = urgency
                st.session_state.brief_summary = brief_summary

                status.write("💾 حفظ السجل...")
                full_record = {
                    "record_id": str(uuid.uuid4()),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "patient_id": st.session_state.patient_id,
                    **patient_info,
                    "risk_factors": ", ".join(patient_info['risk_factors']) or "None",
                    "symptoms_text": st.session_state.form_data['symptoms_text'],
                    **{h: ai_extracted_labs.get(h, labs.get(h, "N/A")) for h in GSHEET_LAB_HEADERS},
                    "ocr_results": ocr_text_for_analysis or "N/A",
                    "brief_summary": brief_summary or "N/A",
                    "final_ai_report": report_text or "N/A",
                    "urgency_assessment": urgency
                }

                try:
                    save_record_to_gsheet(worksheet, full_record)
                    st.success("💾 تم حفظ السجل بنجاح في Google Sheets.")
                    status.update(label="اكتمل التحليل!", state="complete")
                    st.session_state.assessment_step = 6  # Go to final report step
                    st.rerun()
                except GSheetError as e:
                    status.update(label=f"فشل الحفظ: {e}", state="error")
                    st.error(f"❌ فشل الحفظ: {e}")
                    st.stop()
                except Exception as e:
                    status.update(label=f"خطأ غير متوقع: {e}", state="error")
                    st.error(f"❌ خطأ غير متوقع أثناء الحفظ: {e}")
                    st.stop()

    # --- STEP 6: FINAL REPORT ---
    elif st.session_state.assessment_step == 6:
        st.header("💌 تقريركِ الشامل من المساعد الذكي")
        st.balloons()

        urgency_level = st.session_state.get('urgency', 'غير محدد')
        urgency_color = get_urgency_color(urgency_level)
        if urgency_color == "error":
            st.error(f"**🚨 تقييم الخطورة: {urgency_level}**", icon="🚨")
        elif urgency_color == "warning":
            st.warning(f"**⚠️ تقييم الخطورة: {urgency_level}**", icon="⚠️")
        else:
            st.success(f"**✅ تقييم الخطورة: {urgency_level}**", icon="✅")

        st.subheader("📝 ملخص سريع لحالتكِ")
        st.info(st.session_state.get('brief_summary', 'يرجى مراجعة التقرير المفصل.'))

        with st.expander("🔬 عرض التقرير الطبي المفصل"):
            st.markdown(st.session_state.final_report)

        if FPDF_EXISTS and os.path.exists(ARABIC_FONT_PATH):
            try:
                pdf_bytes = create_pdf_bytes(st.session_state.final_report, st.session_state.last_patient_info,
                                             st.session_state.last_labs)
                if pdf_bytes:
                    st.download_button(
                        label="⬇️ تحميل التقرير (PDF)", data=pdf_bytes,
                        file_name=f"Report_{st.session_state.patient_id}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
            except PDFError as e:
                st.warning(f"لم نتمكن من إنشاء ملف PDF: {e}")
            except Exception as e:
                st.warning(f"لم نتمكن من إنشاء ملف PDF: خطأ غير متوقع {e}")

        if st.button("🔄 بدء تقييم جديد"):
            keys_to_clear = [
                'assessment_step', 'patient_id', 'ocr_results', 'final_report',
                'urgency', 'brief_summary', 'analysis_complete', 'patient_history_df',
                'form_data', 'last_uploaded_id', 'ai_extracted_labs',
                'last_patient_info', 'last_labs'
            ]
            
            for key in keys_to_clear:
                if key in st.session_state:
                    if key == 'patient_history_df':
                        st.session_state[key] = pd.DataFrame()
                    elif key == 'form_data' or key == 'ai_extracted_labs' or key == 'last_patient_info' or key == 'last_labs':
                        st.session_state[key] = {}
                    else:
                        defaults = {
                            'assessment_step': 0, 'patient_id': "", 'ocr_results': "",
                            'final_report': None, 'urgency': 'غير محدد',
                            'brief_summary': '', 'analysis_complete': False,
                            'last_uploaded_id': None
                        }
                        if key in defaults:
                            st.session_state[key] = defaults[key]
                        else:
                            try:
                                del st.session_state[key]
                            except:
                                pass # تجاهل إذا كان المفتاح غير موجود

            st.session_state.assessment_step = 0
            st.rerun()


# --- (في نهاية ملف assessment_wizard.py) ---
# (تهيئة متغيرات الحالة)
if 'assessment_step' not in st.session_state:
    st.session_state.assessment_step = 0
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}
if 'patient_id' not in st.session_state:
    st.session_state.patient_id = ""
if 'patient_history_df' not in st.session_state:
    st.session_state.patient_history_df = pd.DataFrame()
if 'ocr_results' not in st.session_state:
    st.session_state.ocr_results = ""
if 'last_uploaded_id' not in st.session_state:
    st.session_state.last_uploaded_id = None
if 'uploaded_image_key' not in st.session_state:
    st.session_state.uploaded_image_key = 0
if 'ai_extracted_labs' not in st.session_state:
    st.session_state.ai_extracted_labs = {}
if 'last_patient_info' not in st.session_state:
    st.session_state.last_patient_info = {}
if 'last_labs' not in st.session_state:
    st.session_state.last_labs = {}

# 💡💡 السطر الأهم: شغل الدالة الرئيسية
assessment_wizard()
