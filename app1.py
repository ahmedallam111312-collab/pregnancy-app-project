"""
Professional Pregnancy AI Assistant (Graduation Project - **v12 - Mobile & Pink UI**)
Features:
- **Premium Front-End:** **Fully mobile-responsive**, **new pink color scheme**, dashboard layout, interactive Plotly charts, SVG logo, refined CSS.
- **Enhanced AI Logic:** Includes detailed patient history, AI "thinks aloud", assesses urgency, intelligently parses OCR, considers medications.
- **Expanded Knowledge Base & Weekly Guide.**
- **Local OCR + AI Cleaning.**
- **Multi-Tool Interface:** Assessment, Weekly Guide, FMC.
- **Advanced Medical Handling:** Pregnancy weight gain, BP, Hypoglycemia.
- **Contextual AI:** Incorporates history, expanded risk factors, medications.
- Saves data instantly to Google Sheets.
"""
# --------------------------- CONFIGURE HERE ---------------------------
GDRIVE_SHEET_NAME = "GDM_Research_Data_V2"
TESSERACT_CMD_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# ---------------------------------------------------------------------

import datetime
import streamlit as st
import pandas as pd
import gspread
from gspread.exceptions import SpreadsheetNotFound, APIError
import google.generativeai as genai
from PIL import Image
import io
import os
import plotly.express as px
import re
import json
import uuid # For generating unique record IDs
import base64 # For SVG logo

# --- PDF Generation Modules ---
FPDF_EXISTS = False
try:
    from fpdf import FPDF
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_FONT_PATH = "DejaVuSans.ttf"
    if os.path.exists(ARABIC_FONT_PATH):
        FPDF_EXISTS = True
    else:
        # Only show local warning
        if platform.system() == "Windows":
            st.warning(f"ملف الخط '{ARABIC_FONT_PATH}' مفقود. لن تعمل ميزة PDF.")
except ImportError:
    st.warning("مكتبات PDF (fpdf2, arabic-reshaper, python-bidi) غير مثبتة. لن تعمل ميزة تحميل PDF.")
# --------------------------------

# --- Tesseract Configuration ---
try:
    import pytesseract
    if platform.system() == "Windows" and os.path.exists(TESSERACT_CMD_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
        TESSERACT_AVAILABLE = True
    elif platform.system() != "Windows":
        # Assume it's installed on Streamlit Cloud
        TESSERACT_AVAILABLE = True
    else:
        st.error(f"لم يتم العثور على Tesseract في المسار: {TESSERACT_CMD_PATH}.")
        TESSERACT_AVAILABLE = False
except ImportError:
    st.error("مكتبة 'pytesseract' غير مثبتة.")
    TESSERACT_AVAILABLE = False
# --------------------------------

# --- AI Configuration ---
USE_GEMINI = False
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        MODEL_NAME = 'gemini-pro'
        USE_GEMINI = True
    else: st.warning("يرجى وضع مفتاح Google Gemini API في ملف .streamlit/secrets.toml.")
except Exception as e: st.error(f"حدث خطأ أثناء إعداد Gemini AI: {e}")
# -------------------------

st.set_page_config(page_title="مساعد الحمل الذكي", layout="wide", initial_sidebar_state="expanded")

# --- Initialize Session State ---
defaults = {
    'page': 'التقييم الشامل', 'patient_id': "", 'ocr_results': "", 'final_report': None, 'urgency': 'غير محدد',
    'analysis_complete': False, 'patient_history_df': pd.DataFrame(), 'fmc_count': 0,
    'fmc_start_time': None, 'uploaded_image_key': 0, 'form_data': {},
    'last_uploaded_id': None, 'ai_extracted_labs': {}, 'last_patient_info': {}, 'last_labs': {}
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)
# --------------------------------

# --- SVG Logo (More Pink) ---
SVG_LOGO = r'''
<svg xmlns="http://www.w3.org/2000/svg" width="420" height="160" viewBox="0 0 420 160">
  <defs>
    <linearGradient id="g1" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stop-color="#FF9A8B"/><stop offset="100%" stop-color="#FF69B4"/></linearGradient>
    <radialGradient id="r1" cx="30%" cy="30%" r="80%"><stop offset="0%" stop-color="#fff" stop-opacity="0.9"/><stop offset="60%" stop-color="#fff" stop-opacity="0.05"/></radialGradient>
    <filter id="f1" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="8" flood-color="#FF69B4" flood-opacity="0.3"/></filter>
  </defs>
  <rect x="6" y="6" rx="18" ry="18" width="408" height="148" fill="url(#g1)" opacity="0.98" filter="url(#f1)"/>
  <g transform="translate(36,28)">
    <circle cx="64" cy="44" r="44" fill="#fff" opacity="0.12"/>
    <circle cx="64" cy="44" r="36" fill="url(#g1)" stroke="#fff" stroke-opacity="0.12" stroke-width="2"/>
    <circle cx="64" cy="44" r="36" fill="url(#r1)" opacity="0.35"/>
    <text x="64" y="52" font-family="'Cairo', sans-serif" font-size="28" fill="#fff" text-anchor="middle" font-weight="bold">🤰</text>
   </g>
  <g transform="translate(145, 40)" style="font-family: 'Cairo', sans-serif;">
    <text x="0" y="32" font-size="22" font-weight="700" fill="#fff">مساعد الحمل الذكي</text>
    <text x="0" y="60" font-size="15" fill="#f7f7f7" opacity="0.95">كلية التمريض - مشروع تخرج</text>
  </g>
</svg>
'''
def svg_to_data_uri(svg_text: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode('utf-8')).decode('utf-8')
SVG_DATA_URI = svg_to_data_uri(SVG_LOGO)

# --- Knowledge Bases & Constants ---
@st.cache_data
def load_medical_kb():
    # ... (KB remains the same) ...
    return pd.read_csv(io.StringIO("""
Disease_Name,Common_Symptoms,Key_Lab_Tests,Normal_Range,Risk_Signs,Intervention
Gestational Diabetes,"عطش شديد، تبول متكرر، تعب، غثيان، زيادة وزن سريعة، التهابات متكررة","FBS, OGTT, HbA1c","FBS: <95; 1h: <180; 2h: <155","سكر غير منضبط، انخفاض حركات الجنين، زيادة وزن سريع للجنين","حمية قليلة السكر (تجنب العصائر والحلويات، تقسيم الوجبات)، نشاط بدني منتظم (مشي نصف ساعة يومياً)، مراقبة سكر الدم بالمنزل (4 مرات يومياً)، متابعة دكتور سكر وغدد، قد تحتاج لأنسولين"
Preeclampsia,"صداع شديد لا يستجيب للمسكنات، زغللة في النظر، تورم مفاجئ بالوجه/اليدين، ألم أعلى يمين البطن، ارتفاع ضغط","BP, Urine Protein, LFTs, Platelets, Creatinine","BP: <140/90, Protein: Negative/Trace","ضغط مرتفع >140/90 أو >160/110، بروتين بول ++، انخفاض صفائح (<100k)، ارتفاع وظائف كبد (ALT/AST)، صداع مستمر، زغللة","**طوارئ طبية**. راحة تامة (يفضل على الجانب الأيسر)، متابعة لصيقة بالمستشفى، أدوية ضغط (مثل Labetalol)، مراقبة الجنين، قد تحتاج لولادة مبكرة فوراً"
HELLP Syndrome,"ألم شديد أعلى يمين البطن، غثيان وقيء شديد، صداع، زغللة (قد يحدث مع تسمم الحمل أو بدونه)","Platelets, LFTs (AST/ALT), LDH","Platelets >150k, LFTs normal","انخفاض صفائح شديد (<100k)، ارتفاع إنزيمات كبد (AST/ALT > 70)، علامات تكسر دم (LDH مرتفع)","**طوارئ طبية قصوى**. نقل دم/صفائح إذا لزم، أدوية ضغط، الولادة الفورية هي العلاج الوحيد بغض النظر عن عمر الحمل."
Anemia,"دوخة عند الوقوف، تعب شديد وإرهاق، شحوب (في جفن العين)، خفقان، ضيق تنفس بسيط","Hb, Ferritin, CBC","Hb: >11 (T1/T3), >10.5 (T2)","شحوب شديد، ضيق تنفس عند المجهود، Hb < 9","مكملات حديد/فوليك أسيد (مثل Ferrous Fumarate) حسب وصفة الطبيب، نظام غذائي غني بالحديد (لحوم حمراء، كبدة، سبانخ، عدس) وفيتامين سي (برتقال، ليمون) لزيادة الامتصاص"
UTI,"ألم أو حرقان أثناء التبول، تكرار التبول، إلحاح بولي، ألم فوق العانة، رائحة بول كريهة","Urine Analysis, Urine Culture","WBCs <5, Nitrite Negative","حرارة، قشعريرة، ألم بالجانب (الكلى)، غثيان/قيء (علامات Pyelonephritis)","مضاد حيوي مناسب للحمل فوراً (حسب نتيجة المزرعة إن أمكن) مع إكمال الجرعة كاملة، شرب سوائل بكثرة (8-10 أكواب ماء يومياً)، تفريغ المثانة بانتظام"
Hyperemesis Gravidarum,"غثيان وقيء شديد ومستمر يمنع الأكل/الشرب، فقدان وزن >5% من وزن ما قبل الحمل","Ketones in Urine, Electrolytes, LFTs","Ketones: Negative","جفاف شديد (قلة بول، دوخة)، فقدان وزن ملحوظ، كيتون في البول، خلل أملاح (هايبوكاليميا)","تجنب الأطعمة الدسمة/الروائح القوية، وجبات صغيرة جداً وجافة (بسكويت مالح)، سوائل باردة، فيتامين B6، أدوية مضادة للقيء، قد تحتاج لسوائل وريدية بالمستشفى"
Preterm Labor Signs,"انقباضات رحمية منتظمة (>4/ساعة قبل الأسبوع 37)، آلام تشبه الدورة الشهرية، نزول ماء أو إفرازات دموية/مخاطية، ضغط شديد بالحوض","Cervical exam, Ultrasound (TVU)","Cervix closed & long (>2.5cm)","انقباضات منتظمة ومؤلمة، تغييرات بعنق الرحم (قصر/اتساع)","**طوارئ طبية**. راحة تامة، شرب سوائل، التوقف عن أي مجهود، التواصل مع الطبيب أو المستشفى **فوراً**، قد تحتاج لأدوية لإيقاف الانقباضات (Tocolytics) وحقنة الرئة للجنين"
Placenta Previa,"نزيف مهبلي أحمر فاتح مفاجئ **بدون ألم** (غالبًا في الثلث الثاني أو الثالث)","Ultrasound (السونار هو التشخيص الوحيد)","-","نزيف غزير ومتكرر، انقباضات رحمية مصاحبة للنزيف","راحة تامة، تجنب العلاقة الزوجية والفحص المهبلي تماماً، متابعة لصيقة بالسونار، الولادة تكون قيصرية دائماً. في حال النزيف الشديد: طوارئ"
Placental Abruption,"نزيف مهبلي داكن (قد يكون داخلياً بدون نزول دم)، **ألم شديد مستمر بالبطن**، بطن صلبة (كالحجر)، قلة حركة الجنين","Clinical diagnosis, Ultrasound (قد لا يظهر)","-","ألم شديد، بطن صلبة كلوح الخشب، توقف حركة الجنين، علامات صدمة للأم","**طوارئ طبية قصوى**. التوجه للطوارئ فوراً. غالباً ما تتطلب ولادة عاجلة (قيصرية أو طبيعية حسب الحالة)"
Cholestasis of Pregnancy,"**حكة شديدة** (خاصة في راحة اليدين وباطن القدمين) تزداد سوءاً في الليل، **بدون طفح جلدي**","Bile Acids, LFTs","Bile Acids < 10 μmol/L","حكة لا تحتمل، اصفرار الجلد (يرقان)، بول داكن، ارتفاع شديد في أحماض الصفراء (>40)","متابعة طبية قريبة، أدوية (Ursodiol) لتقليل الحكة والأحماض، مراقبة وظائف الكبد وحالة الجنين، قد تستدعي ولادة مبكرة (37-38 أسبوع)"
DVT (Deep Vein Thrombosis),"تورم في ساق واحدة (عادة اليسرى)، ألم شديد بالساق، احمرار، سخونة في المنطقة المتورمة","Doppler Ultrasound (سونار دوبلر)","-","ألم شديد عند ثني القدم للأعلى (Homan's sign)، تاريخ مرضي بجلطات","**تقييم فوري**. راحة ورفع الساق، أدوية مسيلة للدم (مثل Enoxaparin) مناسبة للحمل، تجنب الجلوس لفترات طويلة"
Peripartum Cardiomyopathy (PPCM),"ضيق تنفس عند الاستلقاء (orthopnea)، سعال ليلي، تورم شديد بالقدمين والساقين، خفقان، تعب شديد","Echo (موجات صوتية على القلب), BNP","BNP < 100 pg/mL (قد يرتفع قليلاً طبيعياً في الحمل)","ارتفاع BNP، انخفاض كفاءة عضلة القلب (EF) في الإيكو","**طوارئ قلب فورية**. راحة تامة، أدوية مدرة للبول وأدوية دعم القلب (ACEI/ARBs ممنوعة أثناء الحمل)، متابعة لصيقة مع طبيب قلب"
Normal Pregnancy,"غثيان خفيف (T1)، تعب (T1/T3)، زيادة وزن طبيعية، حركة جنين طبيعية، آلام ظهر/حوض بسيطة","Routine Antenal Care","-","عدم وجود علامات خطر (نزيف، صداع شديد، انقباضات منتظمة، قلة حركة جنين)","استمرار بالمتابعة، غذاء صحي، فيتامينات الحمل، نشاط بدني معتدل"
"""))

@st.cache_data
def load_weekly_guide():
     # **EXPANDED WEEKLY GUIDE**
    return {
        6: {"f": "بحجم حبة العدس (~0.6 سم). القلب يبدأ بالنبض، وبدايات تشكل الدماغ والوجه.", "m": "التعب الشديد والغثيان الصباحي (الذي قد يحدث طوال اليوم) هما الأكثر شيوعاً بسبب ارتفاع الهرمونات.", "t": "ابدئي بتناول حمض الفوليك (400 ميكروجرام) يومياً فوراً. تناولي وجبات صغيرة وجافة (بسكويت مالح) قبل النهوض من السرير لتقليل الغثيان."},
        12: {"f": "بحجم الليمونة الكبيرة (~5.4 سم). الأعضاء الرئيسية كلها تكونت. يمكنه فتح وإغلاق يديه. خطر الإجهاض يقل بشكل كبير بعد هذا الأسبوع.", "m": "الغثيان يبدأ بالتحسن. الرحم يكبر ليخرج من الحوض. قد تشعرين ببعض الدوخة بسبب تغيرات ضغط الدم.", "t": "الوقت المناسب لفحوصات الثلث الأول الهامة (مثل Nuchal Translucency). ابدئي بتمارين قاع الحوض (كيجل)."},
        16: {"f": "بحجم الأفوكادو (~11.6 سم). الهيكل العظمي يبدأ بالتصلب. الجهاز العصبي يبدأ بالعمل. قد تشعرين بحركاته الأولى الخفيفة (الرفة).", "m": "بطنك يبرز بوضوح. قد تشعرين بزيادة في الطاقة وتقليل الغثيان ('شهر العسل' للحمل).", "t": "الوقت مناسب لبدء تمارين الحمل الخفيفة. احرصي على شرب كميات كافية من الماء وتناول الألياف لتجنب الإمساك."},
        20: {"f": "بحجم الموزة (~25 سم من الرأس للقدم). يمكنكِ الشعور بحركاته بوضوح الآن! تتطور حواسه (السمع واللمس).", "m": "منتصف الطريق! الرحم يصل لمستوى السرة. الفحص التفصيلي للجنين (Anomaly Scan) هام جداً.", "t": "تأكدي من إجراء الفحص التفصيلي بالموجات فوق الصوتية للكشف عن أي تشوهات خلقية محتملة."},
        24: {"f": "بحجم قطعة الشمام (~30 سم). رئتاه تتطوران وتنتجان مادة السرفاكتانت الهامة للتنفس. يستجيب للأصوات.", "m": "قد تعانين من آلام الظهر وتورم خفيف في القدمين. هذا هو وقت فحص سكري الحمل.", "t": "احرصي على إجراء فحص تحمل الجلوكوز (OGTT). حاولي رفع قدميك عند الجلوس لتقليل التورم."},
        28: {"f": "يزن حوالي 1 كجم وطوله (~37 سم). يفتح ويغلق عينيه ويميز الضوء. فرصته في النجاة جيدة جدًا إذا ولد الآن.", "m": "زيادة الوزن تصبح أسرع. بداية الثلث الثالث. قد تشعرين بحرقة المعدة وضيق التنفس.", "t": "ابدئي بمراقبة حركة الجنين يوميًا (FMC). ناقشي مع طبيبك أعراض الولادة المبكرة. هذا هو وقت أخذ حقنة Anti-D إذا كانت فصيلة دمك سالبة."},
        32: {"f": "يزن حوالي 1.7 كجم (~42 سم). معظم الأعضاء اكتملت ما عدا الرئتين. يتخذ وضعية الولادة غالبًا.", "m": "قد تشعرين بضيق في التنفس أكثر بسبب حجم الرحم. تقلصات براكستون هكس (التدريبية) قد تزداد.", "t": "ابدئي في تعلم تقنيات التنفس للولادة. جهزي حقيبة المستشفى الأساسية. زيارات الطبيب قد تصبح كل أسبوعين."},
        36: {"f": "يزن حوالي 2.6 كجم (~47 سم). يعتبر الآن 'كامل المدة المبكرة'. يكتسب دهوناً تحت الجلد.", "m": "قد ينزل رأس الجنين في الحوض مما يسهل التنفس لكن يزيد الضغط أسفل البطن. زيارات الطبيب تصبح أسبوعية.", "t": "تأكدي من جاهزية حقيبة المستشفى كاملة. ناقشي خطة الولادة بالتفصيل مع طبيبك. إجراء مسحة GBS (للبكتيريا العقدية)."},
        40: {"f": "اكتمل النمو! متوسط الوزن ~3.4 كجم (~51 سم). جاهز للخروج للعالم.", "m": "وصلتِ للموعد المتوقع! قد تشعرين بالإرهاق والترقب. الولادة قد تبدأ في أي لحظة.", "t": "الصبر والمراقبة. استمري بمتابعة حركة الجنين. راقبي علامات بدء المخاض (انقباضات منتظمة وقوية، نزول الماء، الإفرازات المخاطية الدموية)."}
    }

medical_kb = load_medical_kb()
weekly_guide = load_weekly_guide()
IOM_GUIDELINES = { "نقص الوزن": (12.5, 18), "وزن طبيعي": (11.5, 16), "زيادة الوزن": (7, 11.5), "سمنة": (5, 9) }
RISK_FACTORS_LIST = [
    "العمر أكبر من 35 سنة", "العمر أقل من 18 سنة", "تاريخ عائلي لمرض السكري",
    "تاريخ عائلي لارتفاع ضغط الدم", "إصابة سابقة بسكري الحمل", "إصابة سابقة بتسمم الحمل",
    "متلازمة تكيس المبايض (PCOS)", "زيادة الوزن أو السمنة (BMI > 25)", "أمراض الكلى المزمنة",
    "أمراض المناعة الذاتية (مثل الذئبة)", "الحمل المتعدد (توأم أو أكثر)", "تاريخ مرضي بأمراض القلب"
]
GSHEET_LAB_HEADERS = ["systolic_bp", "diastolic_bp", "fasting_glucose", "ogtt_1h", "ogtt_2h", "hba1c", "hb", "platelets", "alt", "ast", "creatinine", "urine_protein", "urine_ketones", "bnp"]
GSHEET_ALL_HEADERS = ["record_id", "timestamp", "patient_id", "patient_name", "age", "gravida", "para", "abortion", "past_medical_history", "current_medications", "gestational_week", "height_cm", "pre_pregnancy_weight_kg", "current_weight_kg", "weight_gain_kg", "pre_pregnancy_bmi", "pre_pregnancy_bmi_category", "risk_factors", "symptoms_text"] + GSHEET_LAB_HEADERS + ["ocr_results", "final_ai_report", "urgency_assessment"]

# --- Core Functions ---
@st.cache_resource(ttl=300)
def get_gsheet_connection():
    try:
        if "gcp_service_account" not in st.secrets: st.error("❌ لم يتم العثور على معلومات اتصال Google Sheets."); return None
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        spreadsheet = gc.open(GDRIVE_SHEET_NAME)
        return spreadsheet.sheet1
    except SpreadsheetNotFound: st.error(f"❌ خطأ: لم يتم العثور على Google Sheet '{GDRIVE_SHEET_NAME}'. تأكد من الاسم والمشاركة."); return None
    except APIError as e: st.error(f"❌ خطأ API Google Sheets: {e}. تأكد من الأذونات وتفعيل APIs."); return None
    except Exception as e: st.error(f"❌ فشل الاتصال بـ Google Sheets: {e}"); return None

def get_patient_history_df(worksheet, patient_id_input):
    """Robustly fetches patient history."""
    try:
        if worksheet is None: return pd.DataFrame()
        all_values = worksheet.get_all_values()
        if len(all_values) <= 1: return pd.DataFrame()
        headers_raw = all_values[0]
        headers = []
        for h in headers_raw:
            cleaned_h = h.strip().lower()
            if cleaned_h: headers.append(cleaned_h)
            else: break
        num_cols = len(headers)
        data = [row[:num_cols] for row in all_values[1:]]
        df = pd.DataFrame(data, columns=headers)
        required_cols = ['patient_id', 'timestamp']
        if not all(col in df.columns for col in required_cols):
             if 'patient_id' not in df.columns: return pd.DataFrame()
        df = df.replace('', pd.NA)
        search_id = str(patient_id_input).strip().lower()
        if 'patient_id' not in df.columns: return pd.DataFrame()
        df['patient_id_str'] = df['patient_id'].astype(str).str.strip().str.lower()
        patient_df = df[df['patient_id_str'] == search_id].copy().drop(columns=['patient_id_str'])
        if patient_df.empty: return pd.DataFrame()
        if 'timestamp' in patient_df.columns:
            patient_df['timestamp'] = pd.to_datetime(patient_df['timestamp'], errors='coerce')
            patient_df.dropna(subset=['timestamp'], inplace=True)
        else: return patient_df
        numeric_cols = ['age', 'gravida', 'para', 'abortion', 'gestational_week', 'height_cm', 'pre_pregnancy_weight_kg', 'current_weight_kg', 'weight_gain_kg', 'pre_pregnancy_bmi', 'systolic_bp', 'diastolic_bp', 'fasting_glucose', 'ogtt_1h', 'ogtt_2h', 'hba1c', 'hb', 'platelets', 'alt', 'ast', 'creatinine', 'bnp']
        for col in numeric_cols:
            if col in patient_df.columns: patient_df[col] = pd.to_numeric(patient_df[col], errors='coerce')
        return patient_df.sort_values(by='timestamp', ascending=True)
    except Exception as e: print(f"Error fetching/processing history: {e}"); return pd.DataFrame()


def calculate_bmi(weight_kg, height_cm):
    if not height_cm or height_cm <= 0 or not weight_kg or weight_kg <=0 : return 0, "غير محدد"
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
    if bmi < 18.5: category = "نقص الوزن"
    elif 18.5 <= bmi < 25: category = "وزن طبيعي"
    elif 25 <= bmi < 30: category = "زيادة الوزن"
    else: category = "سمنة"
    return bmi, category

def ocr_with_tesseract(image_bytes):
    if not TESSERACT_AVAILABLE: return "Tesseract غير مفعل."
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)), lang='ara+eng') or "لم يتم قراءة نص."
    except Exception as e: return f"خطأ Tesseract: {e}"

def ai_generate_final_report(patient_info, labs, history_df, symptoms_text, ocr_text):
    """Generates the AI report, extracts structured labs, and assesses urgency."""
    if not USE_GEMINI: return "خدمة AI غير مفعلة.", {}, "غير محدد"

    history_summary = "لا يوجد سجل سابق."
    if not history_df.empty:
        prev = history_df.iloc[-1]
        prev_ts = safe_get(prev, 'timestamp', pd.NaT)
        history_summary = f"الزيارة السابقة ({prev_ts.strftime('%Y-%m-%d') if pd.notna(prev_ts) else '?'}): وزن={safe_get(prev,'current_weight_kg', '?')} كجم, ضغط={safe_get(prev,'systolic_bp', '?')}/{safe_get(prev,'diastolic_bp', '?')}, سكر صائم={safe_get(prev,'fasting_glucose', '?')}."
        current_weight_kg = patient_info.get('current_weight', 0); prev_weight_kg = safe_get(prev,'current_weight_kg', current_weight_kg)
        weight_trend = current_weight_kg - prev_weight_kg if pd.notna(current_weight_kg) and pd.notna(prev_weight_kg) else 0
        current_bp_sys = labs.get('systolic_bp', 0); prev_bp_sys = safe_get(prev,'systolic_bp', current_bp_sys)
        bp_trend = current_bp_sys - prev_bp_sys if pd.notna(current_bp_sys) and pd.notna(prev_bp_sys) else 0
        history_summary += f"\n   - التغير: وزن {weight_trend:+.1f} كجم, ضغط {bp_trend:+.0f} mmHg."

    manual_lab_summary = ", ".join([f"{k.replace('_',' ').title()}: {v}" for k, v in labs.items() if v is not None]) or "لا يوجد إدخال يدوي."

    prompt = f"""
    مهمتك: تحليل حالة حمل كمستشار طبي ذكي، تقديم تقرير مفصل للمريضة {patient_info['name']}، استخلاص قيم التحاليل، وتحديد مستوى الإلحاح.

    قاعدة المعرفة: {medical_kb.to_string()}
    أعمدة التحاليل المستهدفة للاستخلاص: {', '.join(GSHEET_LAB_HEADERS)}

    بيانات الحالة الحالية:
    - المعلومات الأساسية: {patient_info}
    - الأعراض النصية: "{symptoms_text}"
    - الأدوية الحالية: "{patient_info.get('current_medications', 'لا يوجد')}"
    - التحاليل اليدوية: "{manual_lab_summary}"
    - النص المستخرج من صورة التحاليل (قد يكون غير دقيق): "{ocr_text}"
    - ملخص الزيارة السابقة: {history_summary}

    الخطوات المطلوبة (فكر بصوت عالٍ):
    1.  **التشخيص التفريقي:** بناءً على الأعراض + التاريخ + عوامل الخطر (خاصة تاريخ أمراض القلب)، ما هي الاحتمالات؟
    2.  **تنظيف وتفسير OCR + الدمج:** ادمج التحاليل اليدوية مع القيم الموثوقة من النص "{ocr_text}". طابق الأسماء مع الأعمدة المستهدفة (e.g., Fasting Blood Sugar -> fasting_glucose, BNP -> bnp).
    3.  **الاستخلاص المنظم للتحاليل:** أنشئ قائمة JSON **فقط** بالقيم المستخلصة والمطابقة للأعمدة المستهدفة.
    4.  **تحليل الحالة الشامل:** قم بتقييم الحالة (وزن، ضغط، سكر، تاريخ، عوامل خطر، أدوية، اتجاهات).
    5.  **تقييم الإلحاح (Urgency):** بناءً على كل البيانات، صنف الحالة (متابعة روتينية، استشارة قريبة، تقييم فوري).
    6.  **التقرير النهائي (نصي):** اكتب تقريراً نصياً **مفصلاً واحترافياً** للمريضة يشمل:
        * ترحيب شخصي باسمها.
        * **التشخيص النهائي** الأكثر ترجيحًا مع **شرح تفصيلي** يربطه بكل البيانات.
        * **مستوى الإلحاح** وتفسير الإجراء المطلوب (مثال: "تقييم فوري يعني ضرورة التوجه للطوارئ حالاً").
        * **إرشادات وتدخلات عملية يمكن للمريضة البدء بها الآن:** قدم نصائح (غذاء، رياضة، مراقبة منزلية) **مرتبطة مباشرة بالنتائج والحالة والأدوية وأسبوع الحمل**. اذكر أمثلة محددة جداً.
        * ذكر **علامات الخطر** الواضحة (Risk_Signs).
        * **تأكيد واضح ومباشر على ضرورة المتابعة مع الطبيب.**

    **الإخراج المطلوب:**
    أولاً: مستوى الإلحاح (Urgency) في سطر منفصل (e.g., URGENCY: تقييم فوري).
    ثانياً: قائمة JSON المنظمة للتحاليل المستخلصة.
    ثالثاً: بعد سطر فاصل `--- REPORT TEXT ---`، ضع التقرير النصي الكامل للمريضة.
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt, generation_config={"temperature": 0.7, "top_p": 0.95})

        full_response_text = response.text.strip()
        extracted_labs = {}
        report_text = "لم يتمكن الذكاء الاصطناعي من إنشاء تقرير نصي." # Default
        urgency = "غير محدد" # Default

        # Attempt to parse Urgency, JSON, and Report Text
        lines = full_response_text.split('\n')
        json_part = ""
        report_part = ""
        json_started = False
        report_started = False

        for line in lines:
            line_stripped = line.strip()
            if line_stripped.upper().startswith("URGENCY:"):
                urgency = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("```json"):
                json_started = True
                json_part += line_stripped[7:]
            elif line_stripped.startswith("--- REPORT TEXT ---"):
                report_started = True
                json_started = False
            elif json_started and line_stripped.endswith("```"):
                json_part += line_stripped[:-3]
                json_started = False
            elif json_started:
                json_part += line + "\n"
            elif report_started:
                report_part += line + "\n"

        if json_part:
            try:
                json_match = re.search(r'\{.*\}', json_part, re.DOTALL)
                if json_match:
                    extracted_labs = json.loads(json_match.group(0).strip())
                    if not isinstance(extracted_labs, dict): extracted_labs = {}
                else: extracted_labs = {}
            except json.JSONDecodeError: extracted_labs = {}
        
        if report_part: report_text = report_part.strip()
        elif not report_part and not json_part and full_response_text: report_text = full_response_text

        return report_text, extracted_labs, urgency

    except Exception as e: return f"حدث خطأ أثناء استدعاء Gemini AI: {e}", {}, "خطأ"


def save_record_to_gsheet(worksheet, record: dict):
    """Saves a record, prioritizing AI extracted labs."""
    try:
        if worksheet is None: return False

        record_to_save = {h: record.get(h, "N/A") for h in GSHEET_ALL_HEADERS if h not in GSHEET_LAB_HEADERS}
        ai_labs = record.get('ai_extracted_labs', {})
        manual_labs = {k: record.get(k, "N/A") for k in GSHEET_LAB_HEADERS}
        for lab_header in GSHEET_LAB_HEADERS:
             ai_val = ai_labs.get(lab_header); manual_val = manual_labs.get(lab_header, "N/A")
             final_val = ai_val if ai_val is not None else manual_val
             numeric_sheet_cols = ['systolic_bp', 'diastolic_bp', 'fasting_glucose', 'ogtt_1h', 'ogtt_2h', 'hba1c', 'hb', 'platelets', 'alt', 'ast', 'creatinine', 'bnp'] # Added bnp
             if lab_header in numeric_sheet_cols:
                 try:
                     fv = float(final_val); final_val = int(fv) if fv == int(fv) else fv
                 except (ValueError, TypeError): final_val = "N/A"
             record_to_save[lab_header] = final_val if final_val is not None and final_val != "" else "N/A"

        record_to_save['urgency_assessment'] = record.get('urgency', 'N/A')
        record_to_save['record_id'] = str(uuid.uuid4())

        df = pd.DataFrame([record_to_save], columns=GSHEET_ALL_HEADERS)
        worksheet.append_rows(df.astype(str).fillna("N/A").values.tolist(), value_input_option='USER_ENTERED')
        
        st.success("💾 تم حفظ السجل بنجاح في Google Sheets.")
        return True
    except APIError as e: st.error(f"❌ فشل الحفظ (API Error): {e}"); return False
    except Exception as e: st.error(f"❌ فشل الحفظ (Unexpected): {e}"); return False

# --- Utility Functions ---
def safe_get(record, key, default):
    """Safely gets a value from a dictionary or Pandas Series, handling None and NA."""
    val = record.get(key)
    return default if pd.isna(val) or val is None else val

def get_urgency_color(urgency_text):
    urgency_lower = str(urgency_text).lower()
    if "فوري" in urgency_lower or "immediate" in urgency_lower or "urgent" in urgency_lower: return "error"
    elif "قريبة" in urgency_lower or "soon" in urgency_lower: return "warning"
    elif "روتيني" in urgency_lower or "routine" in urgency_lower: return "success"
    else: return "info" # Default for unknown/N/A

def create_pdf_bytes(report_text, patient_info, labs):
    """Creates a PDF file in memory, handling Arabic text."""
    if not FPDF_EXISTS or not os.path.exists(ARABIC_FONT_PATH):
        st.error(f"خطأ PDF: المكتبات أو ملف الخط '{ARABIC_FONT_PATH}' مفقود.")
        return None
    
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('DejaVu', '', ARABIC_FONT_PATH, uni=True)
    
    pdf.set_font('DejaVu', '', 16) 
    title = f"تقرير المساعد الذكي للمريضة: {patient_info.get('name', 'N/A')}"
    reshaped_title = arabic_reshaper.reshape(title); bidi_title = get_display(reshaped_title)
    pdf.cell(0, 10, bidi_title, ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font('DejaVu', '', 11)
    info_text = f"المعرف: {patient_info.get('id', 'N/A')} | العمر: {patient_info.get('age', 'N/A')} | أسبوع الحمل: {patient_info.get('week', 'N/A')}"
    reshaped_info = arabic_reshaper.reshape(str(info_text)); bidi_info = get_display(reshaped_info)
    pdf.cell(0, 8, bidi_info, ln=True, align='R')
    pdf.ln(5)

    pdf.set_font('DejaVu', '', 10)
    report_text_str = str(report_text or "")
    for line in report_text_str.split('\n'):
        line_stripped = line.strip()
        if line_stripped:
            reshaped_line = arabic_reshaper.reshape(line_stripped); bidi_line = get_display(reshaped_line)
            pdf.multi_cell(0, 7, bidi_line, align='R')
        else:
            pdf.ln(7) # Add a blank line
        
    return pdf.output(dest='S').encode('latin-1')

# --------------------------- UI STYLING ---------------------------
st.markdown("""
    <style>
         @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
        body, .stApp, input, textarea, button, select, label, div[data-baseweb="select"] > div, .stDataFrame *, .stTable * { font-family: 'Cairo', sans-serif !important; direction: rtl; }
        .stApp { background: linear-gradient(135deg, #FFF0F5 0%, #E6E6FA 100%); }
        .main > div { background-color: rgba(255, 255, 255, 0.95); padding: 2rem 3rem; border-radius: 25px; box-shadow: 0 15px 50px rgba(138, 43, 226, 0.12); border: 1px solid rgba(255, 255, 255, 0.3); }
        h1, h2, h3 { color: #8A2BE2; font-weight: 700; text-shadow: 1px 1px 2px rgba(0,0,0,0.05); }
        h1 { text-align: center; margin-bottom: 2.5rem; }
        h3 { border-bottom: 2px solid #D8BFD8; padding-bottom: 0.6rem; margin-top: 2rem; margin-bottom: 1rem; display: flex; align-items: center;}
        h3::before { content: '⭐ '; margin-left: 10px; font-size: 1.1em; color: #DA70D6; }
        h3:contains("المعلومات الأساسية")::before { content: '👤 '; }
        h3:contains("القياسات الأساسية")::before { content: '📏 '; }
        h3:contains("عوامل الخطورة")::before { content: '❗ '; }
        h3:contains("الأعراض الحالية")::before { content: '❓ '; }
        h3:contains("نتائج التحاليل")::before { content: '🔬 '; }
        .stButton>button { border-radius: 30px; border: none; color: white; background: linear-gradient(45deg, #DA70D6, #8A2BE2); padding: 15px 40px; font-size: 1.1em; font-weight: 700; box-shadow: 0 6px 20px rgba(138, 43, 226, 0.35); transition: all 0.3s ease; cursor: pointer; }
        .stButton>button:hover { transform: translateY(-5px) scale(1.05); box-shadow: 0 10px 30px rgba(138, 43, 226, 0.45); }
        .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { border-radius: 12px; border: 1px solid #D1C4E9 !important; box-shadow: inset 0 2px 4px rgba(0,0,0,0.06); transition: all 0.2s ease-in-out; padding: 10px 12px;}
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { border-color: #9575CD !important; box-shadow: 0 0 0 4px rgba(149, 117, 205, 0.15) !important; transform: scale(1.01); }
        .stDataFrame, .stTable { border-radius: 10px; overflow: hidden; border: 1px solid #E6E6FA; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        .stSpinner > div { border-top-color: #8A2BE2 !important; border-left-color: #8A2BE2 !important; }
        .stMetric { background-color: #EDE7F6; padding: 1rem 1.5rem; border-radius: 15px; border: 1px solid #D1C4E9; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.05);}
        .stMetric label { color: #673AB7; font-weight: bold; font-size: 0.9em;}
        .stMetric .st-ae { font-size: 2em; color: #512DA8; font-weight: 700;}
        .stProgress > div > div { background-image: linear-gradient(45deg, #BA68C8, #7E57C2); border-radius: 10px; }
        [data-testid="stSidebar"] { background-color: rgba(255, 255, 255, 0.9); backdrop-filter: blur(12px); border-right: 1px solid rgba(255, 255, 255, 0.25); box-shadow: 5px 0px 20px rgba(138, 43, 226, 0.08);}
        [data-testid="stSidebar"] img { display: block; margin-left: auto; margin-right: auto; margin-bottom: 0.5rem; }
        [data-testid="stSidebar"] h1 { color: #8A2BE2; margin-top: -15px; text-align: center; font-size: 1.8em;}
        [data-testid="stSidebar"] .stRadio > label { padding-bottom: 12px; font-size: 1.1em; font-weight: bold; color: #6A1B9A; display: block; text-align: center;}
        [data-testid="stSidebar"] .stRadio > div > label { background-color: rgba(230, 230, 250, 0.85); border-radius: 15px; padding: 12px 15px; margin-bottom: 8px; transition: all 0.3s ease; border: 1px solid transparent; display: block; text-align: center; cursor: pointer;}
        [data-testid="stSidebar"] .stRadio > div > label:hover { background-color: rgba(216, 191, 216, 1); border-color: #DA70D6; transform: translateX(-5px) scale(1.03); box-shadow: 0 4px 10px rgba(0,0,0,0.05);}
        [data-testid="stSidebar"] .stRadio > div[aria-checked="true"] > label { background: linear-gradient(45deg, #DA70D6, #8A2BE2); color: white; border-color: #8A2BE2; font-weight: bold; box-shadow: 0 6px 15px rgba(138, 43, 226, 0.3);}
        [data-testid="stSidebar"] .stRadio input { display: none; }
        .stContainer { border: 1px solid #E6E6FA; border-radius: 15px; padding: 1.5rem; margin-bottom: 1.5rem; background-color: rgba(255, 255, 255, 0.65);}
        .stAlert { border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; }
        .stAlert [data-testid="stMarkdownContainer"] p { font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --------------------------- SIDEBAR NAVIGATION ---------------------------
with st.sidebar:
    st.image(SVG_DATA_URI, width=280) # Use SVG logo
    st.markdown("---")
    page = st.radio("القائمة الرئيسية:", ["التقييم الشامل", "دليل الحمل الأسبوعي", "عداد حركة الجنين"], label_visibility="collapsed")
    st.markdown("---")
    st.info("مشروع تخرج مقدم بواسطة: **أحمد**")
    st.markdown("---")
    st.markdown("<sub>**إخلاء مسؤولية:** تعليمي فقط.</sub>", unsafe_allow_html=True)


# =========================== COMPREHENSIVE ASSESSMENT PAGE ===========================
if page == "التقييم الشامل":
    st.title("🌸 التقييم الشامل لصحة الحمل 🌸")
    worksheet = get_gsheet_connection()

    if worksheet is None: st.stop()

    patient_id = st.text_input("💖 أدخلي الرقم التعريفي الخاص بكِ", key="patient_id_input").strip()
    patient_name = ""
    last_record = {}

    if patient_id:
        st.session_state.patient_history_df = get_patient_history_df(worksheet, patient_id)
        if not st.session_state.patient_history_df.empty:
            last_record = st.session_state.patient_history_df.iloc[-1].to_dict()
            patient_name = safe_get(last_record, 'patient_name', '')
            last_visit_date = safe_get(last_record, 'timestamp', pd.NaT)
            st.success(f"أهلاً بعودتكِ، {patient_name}! 👋 آخر زيارة: {last_visit_date.strftime('%Y-%m-%d') if pd.notna(last_visit_date) else 'N/A'}")

            # --- Enhanced Dashboard Summary ---
            st.subheader("📊 لمحة سريعة عن آخر زيارة:")
            dash_cols = st.columns(5)
            dash_cols[0].metric("📅 أسبوع الحمل", f"{safe_get(last_record, 'gestational_week', '?')} أسبوع")
            dash_cols[1].metric("⚖️ الوزن الحالي", f"{safe_get(last_record, 'current_weight_kg', '?')} كجم")
            bp_sys=safe_get(last_record, 'systolic_bp', 0); bp_dia=safe_get(last_record, 'diastolic_bp', 0); bp_val=f"{bp_sys}/{bp_dia}" if bp_sys and bp_dia else "N/A"; bp_delta_color="inverse" if (bp_sys >= 140 or bp_dia >= 90) else "off"
            dash_cols[2].metric("🩸 ضغط الدم", bp_val, delta_color=bp_delta_color, help="الأحمر يشير لارتفاع الضغط")
            fbs_val=safe_get(last_record, 'fasting_glucose', float('nan')); fbs_str=f"{fbs_val}" if pd.notna(fbs_val) else "N/A"; fbs_delta_color="inverse" if fbs_val >= 95 else ("normal" if fbs_val < 70 else "off"); fbs_help="مرتفع >95, منخفض <70"
            dash_cols[3].metric("🍬 سكر صائم", fbs_str, delta_color=fbs_delta_color, help=fbs_help if pd.notna(fbs_val) else None)
            hba1c_val=safe_get(last_record, 'hba1c', float('nan')); hba1c_str=f"{hba1c_val}%" if pd.notna(hba1c_val) else "N/A"; hba1c_delta_color="inverse" if hba1c_val >= 6.5 else ("warning" if hba1c_val >= 5.7 else "off"); hba1c_help="مرتفع >6.5, طبيعي <5.7"
            dash_cols[4].metric("📈 HbA1c", hba1c_str, delta_color=hba1c_delta_color, help=hba1c_help if pd.notna(hba1c_val) else None)
            st.markdown("---")

            st.header("📈 السجل التاريخي ومتابعة التطورات")
            # **UI FIX:** Replaced messy dataframe with a cleaner comparison table
            st.subheader("مقارنة الزيارة الأخيرة بالبيانات الحالية")
            comp_data = {
                "البيان": ["أسبوع الحمل", "الوزن (كجم)", "ضغط الدم (mmHg)", "سكر صائم (mg/dL)"],
                "الزيارة الأخيرة": [
                    safe_get(last_record, 'gestational_week', 'N/A'),
                    safe_get(last_record, 'current_weight_kg', 'N/A'),
                    f"{safe_get(last_record, 'systolic_bp', 'N/A')} / {safe_get(last_record, 'diastolic_bp', 'N/A')}",
                    safe_get(last_record, 'fasting_glucose', 'N/A')
                ],
                "الزيارة الحالية (سيتم إدخالها)": ["-", "-", "-", "-"]
            }
            st.table(pd.DataFrame(comp_data).set_index("البيان"))

            charts_cols = st.columns(3)
            hist_df = st.session_state.patient_history_df
            # ... (Plotly charts remain the same) ...
            if 'current_weight_kg' in hist_df.columns and not hist_df['current_weight_kg'].dropna().empty and len(hist_df['current_weight_kg'].dropna()) > 1:
                try: fig_weight=px.line(hist_df.dropna(subset=['current_weight_kg']), x='timestamp', y='current_weight_kg', title='تطور الوزن', markers=True, labels={'timestamp':'التاريخ', 'current_weight_kg':'الوزن (كجم)'}); fig_weight.update_traces(hovertemplate='التاريخ: %{x|%Y-%m-%d}<br>الوزن: %{y} كجم'); charts_cols[0].plotly_chart(fig_weight, use_container_width=True)
                except Exception as e: charts_cols[0].info(f" خطأ عرض مخطط الوزن: {e} ")
            else: charts_cols[0].info("لا توجد بيانات كافية لعرض تطور الوزن.")
            if 'systolic_bp' in hist_df.columns and 'diastolic_bp' in hist_df.columns and not hist_df[['systolic_bp', 'diastolic_bp']].dropna().empty and len(hist_df[['systolic_bp', 'diastolic_bp']].dropna()) > 1:
                try: fig_bp=px.line(hist_df.dropna(subset=['systolic_bp', 'diastolic_bp']), x='timestamp', y=['systolic_bp', 'diastolic_bp'], title='تطور ضغط الدم', markers=True, labels={'timestamp':'التاريخ', 'value':'ضغط الدم (mmHg)'}); fig_bp.update_traces(hovertemplate='التاريخ: %{x|%Y-%m-%d}<br>الضغط: %{y} mmHg'); charts_cols[1].plotly_chart(fig_bp, use_container_width=True)
                except Exception as e: charts_cols[1].info(f" خطأ عرض مخطط الضغط: {e} ")
            else: charts_cols[1].info("لا توجد بيانات كافية لعرض تطور الضغط.")
            if 'fasting_glucose' in hist_df.columns and not hist_df['fasting_glucose'].dropna().empty and len(hist_df['fasting_glucose'].dropna()) > 1:
                try: fig_glucose=px.line(hist_df.dropna(subset=['fasting_glucose']), x='timestamp', y='fasting_glucose', title='تطور سكر الصائم', markers=True, labels={'timestamp':'التاريخ', 'fasting_glucose':'سكر الصائم (mg/dL)'}); fig_glucose.update_traces(hovertemplate='التاريخ: %{x|%Y-%m-%d}<br>سكر الصائم: %{y} mg/dL'); charts_cols[2].plotly_chart(fig_glucose, use_container_width=True)
                except Exception as e: charts_cols[2].info(f" خطأ عرض مخطط السكر: {e} ")
            else: charts_cols[2].info("لا توجد بيانات كافية لعرض تطور السكر.")
            st.markdown("---")
        else:
             if patient_id: st.info("لم يتم العثور على سجل سابق. أهلاً بكِ!")

    # --- Assessment Form ---
    with st.form("assessment_form"):
        st.header("📝 إدخال بيانات الزيارة الحالية")
        
        # **BUG FIX:** Helper function to safely get and clamp default values for number inputs
        def get_default_value(key, default, min_val, max_val, is_float=False):
            val = safe_get(last_record, key, default)
            try:
                num_val = float(val) if is_float else int(val)
                # Clamp the value within the min/max range
                return max(min_val, min(max_val, num_val))
            except (ValueError, TypeError):
                # Handle "N/A" or other non-numeric strings safely
                return default

        with st.container(border=True):
            st.subheader("👤 1. المعلومات الأساسية والتاريخ المرضي")
            col_info1, col_info2 = st.columns(2);
            with col_info1: 
                patient_name_input = st.text_input("✨ **اسمكِ بالكامل**", value=patient_name if patient_name else "")
                age = st.number_input("**العمر**", 15, 60, value=get_default_value('age', 25, 15, 60), format="%d")
            with col_info2: 
                 gravida = st.number_input("الحمل رقم (G)", 0, 20, value=get_default_value('gravida', 1, 0, 20))
                 para = st.number_input("الولادات السابقة (P)", 0, 20, value=get_default_value('para', 0, 0, 20))
                 abortion = st.number_input("الإجهاض السابق (A)", 0, 20, value=get_default_value('abortion', 0, 0, 20))
            past_medical_history = st.text_area("🩺 **التاريخ الطبي السابق**", height=50, value= safe_get(last_record, 'past_medical_history', ''))
            current_medications = st.text_area("💊 **الأدوية الحالية**", height=50)

        with st.container(border=True):
            st.subheader("📏 2. القياسات الأساسية")
            col_meas1, col_meas2, col_meas3, col_meas4 = st.columns(4);
            gestational_week = col_meas1.number_input("أسبوع الحمل", 1, 45, value=get_default_value('gestational_week', 8, 1, 45))
            height_cm = col_meas2.number_input("**الطول (سم)**", 100, 250, placeholder="165", value=get_default_value('height_cm', 160, 100, 250))
            pre_preg_weight = col_meas3.number_input("**الوزن قبل الحمل (كجم)**", 30.0, 250.0, placeholder="65.0", value=get_default_value('pre_pregnancy_weight_kg', 60.0, 30.0, 250.0, is_float=True), format="%.1f")
            current_weight = col_meas4.number_input("**الوزن الحالي (كجم)**", 30.0, 250.0, placeholder="75.0", format="%.1f")


        with st.container(border=True):
            st.subheader("❗ 3. عوامل الخطورة (إن وجدت)")
            selected_risk_factors = [rf for rf in RISK_FACTORS_LIST if st.checkbox(rf, key=f"rf_{rf}")]

        with st.container(border=True):
            st.subheader("❓ 4. الأعراض الحالية")
            symptoms_text = st.text_area("✍️ **صفي ما تشعرين به بالتفصيل...**", height=100)

        with st.container(border=True):
             st.subheader("🔬 5. نتائج التحاليل (إن وجدت)")
             st.markdown("**العلامات الحيوية:**")
             lab_cols1 = st.columns([1,1,1]); systolic_bp = lab_cols1[0].number_input("ضغط الدم الانقباضي", value=None, placeholder="120"); diastolic_bp = lab_cols1[1].number_input("ضغط الدم الانبساطي", value=None, placeholder="80"); bnp = lab_cols1[2].number_input("BNP (pg/mL)", value=None, placeholder="<100")
             if systolic_bp is not None and diastolic_bp is not None and diastolic_bp >= systolic_bp: st.warning("تنبيه: ضغط الدم الانبساطي أعلى من أو يساوي الانقباضي.")
             st.markdown("**متابعة السكر:**")
             lab_cols2 = st.columns(3); fasting_glucose = lab_cols2[0].number_input("سكر صائم (mg/dL)", value=None, placeholder="90"); ogtt_1h = lab_cols2[1].number_input("OGTT - 1 Hr (mg/dL)", value=None, placeholder="180"); ogtt_2h = lab_cols2[2].number_input("OGTT - 2 Hr (mg/dL)", value=None, placeholder="155")
             st.markdown("**تحاليل الدم الأخرى:**")
             lab_cols3 = st.columns(3); hba1c = lab_cols3[0].number_input("HbA1c (%)", value=None, placeholder="5.5", format="%.1f"); hb = lab_cols3[1].number_input("Hemoglobin (g/dL)", value=None, placeholder="12.0", format="%.1f"); platelets = lab_cols3[2].number_input("Platelets (x10^3/μL)", value=None, placeholder="250")
             st.markdown("**وظائف الكلى والكبد:**")
             lab_cols4 = st.columns(3); alt = lab_cols4[0].number_input("ALT (U/L)", value=None, placeholder="20"); ast = lab_cols4[1].number_input("AST (U/L)", value=None, placeholder="20"); creatinine = lab_cols4[2].number_input("Creatinine (mg/dL)", value=None, placeholder="0.7", format="%.1f")
             st.markdown("**تحليل البول:**")
             lab_cols5 = st.columns(2); urine_protein = lab_cols5[0].selectbox("بروتين البول", ["Negative", "Trace", "+", "++", "+++", "++++"], index=0); urine_ketones = lab_cols5[1].selectbox("كيتون البول", ["Negative", "Trace", "Small", "Moderate", "Large"], index=0)


        # --- Image Upload ---
        uploaded_image = st.file_uploader("📂 أو ارفعي صورة تقرير التحاليل", type=['jpg', 'jpeg', 'png'], key=f'uploader_{st.session_state.uploaded_image_key}')

        # --- Submit Button ---
        submitted = st.form_submit_button("💖 تحليل وإنشاء التقرير", type="primary", use_container_width=True)
        # End of form block

    # --- Logic after form definition ---
    ocr_processed_this_run = False
    if uploaded_image and (not st.session_state.ocr_results or uploaded_image.file_id != st.session_state.get('last_uploaded_id')):
        with st.spinner("🔬 قراءة الصورة..."):
            st.session_state.ocr_results = ocr_with_tesseract(uploaded_image.getvalue())
            st.session_state.last_uploaded_id = uploaded_image.file_id
            ocr_processed_this_run = True
    elif not uploaded_image and st.session_state.get('last_uploaded_id') is not None : # Clear if image removed
         st.session_state.ocr_results = ""; st.session_state.last_uploaded_id = None

    if st.session_state.ocr_results:
         st.text_area("النص المستخرج (للمراجعة):", value=st.session_state.ocr_results, height=150, key="ocr_display_after_form")

    if submitted:
        # Validation
        if not all([patient_id, patient_name_input, age, height_cm, height_cm > 0, pre_preg_weight, current_weight, symptoms_text]):
            st.error("❌ يرجى إكمال جميع الحقول الأساسية.")
        elif systolic_bp is not None and diastolic_bp is not None and systolic_bp <= diastolic_bp:
             st.error("❌ قيمة ضغط الدم الانقباضي يجب أن تكون أعلى من الانبساطي.")
        else:
            ocr_text_for_analysis = st.session_state.ocr_results

            with st.status("👩‍⚕️ يقوم المساعد الذكي بتحليل حالتكِ...", expanded=True) as status:
                st.write("📊 حساب المؤشرات...")
                pre_preg_bmi, pre_preg_bmi_cat = calculate_bmi(pre_preg_weight, height_cm)
                weight_gain = round(current_weight - pre_preg_weight, 1)
                patient_info = { "name": patient_name_input, "age": age, "week": gestational_week, "gravida": gravida, "para": para, "abortion": abortion, "past_medical_history": past_medical_history, "current_medications": current_medications, "pre_preg_weight": pre_preg_weight, "current_weight": current_weight, "weight_gain": weight_gain, "pre_preg_bmi": pre_preg_bmi, "pre_pregnancy_bmi_category": pre_preg_bmi_cat, "risk_factors": selected_risk_factors }
                labs = { "systolic_bp": systolic_bp, "diastolic_bp": diastolic_bp, "fasting_glucose": fasting_glucose, "ogtt_1h": ogtt_1h, "ogtt_2h": ogtt_2h, "hba1c": hba1c, "hb": hb, "platelets": platelets, "alt": alt, "ast": ast, "creatinine": creatinine, "urine_protein": urine_protein, "urine_ketones": urine_ketones, "bnp": bnp } # Added bnp
                
                # **BUG FIX**: Store correct data in session state for PDF
                st.session_state.last_patient_info = patient_info
                st.session_state.last_labs = labs

                status.write("🧠 استدعاء الذكاء الاصطناعي...")
                report_text, ai_extracted_labs, urgency = ai_generate_final_report(
                    patient_info, labs, st.session_state.patient_history_df,
                    symptoms_text, ocr_text_for_analysis
                )
                st.session_state.final_report = report_text
                st.session_state.ai_extracted_labs = ai_extracted_labs
                st.session_state.urgency = urgency

                status.write("💾 حفظ السجل في Google Sheets...")
                full_record = {
                    "record_id": str(uuid.uuid4()), # Add unique ID
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "patient_id": patient_id, "patient_name": patient_name_input, "age": age,
                    "gravida": gravida, "para": para, "abortion": abortion, "past_medical_history": past_medical_history or "N/A", "current_medications": current_medications or "N/A",
                    "gestational_week": gestational_week, "height_cm": height_cm,
                    "pre_pregnancy_weight_kg": pre_preg_weight, "current_weight_kg": current_weight, "weight_gain_kg": weight_gain,
                    "pre_pregnancy_bmi": pre_preg_bmi, "pre_pregnancy_bmi_category": pre_preg_bmi_cat,
                    "risk_factors": ", ".join(selected_risk_factors) or "None",
                    "symptoms_text": symptoms_text,
                    **{h: ai_extracted_labs.get(h, labs.get(h, "N/A")) for h in GSHEET_LAB_HEADERS}, # Prioritize AI labs
                    "ocr_results": ocr_text_for_analysis or "N/A",
                    "final_ai_report": report_text or "N/A",
                    "urgency_assessment": urgency # Save urgency
                }

                save_successful = save_record_to_gsheet(worksheet, full_record)

                if save_successful:
                     st.write("✅ اكتمل!")
                     st.session_state.analysis_complete = True
                     st.session_state.uploaded_image_key += 1
                     status.update(label="اكتمل التحليل!", state="complete", expanded=False)
                else:
                     status.update(label="فشل الحفظ!", state="error", expanded=True)

    # --- Display Final Report ---
    if st.session_state.analysis_complete:
        st.balloons()
        st.header("💌 تقريركِ الشامل من المساعد الذكي")

        urgency_level = st.session_state.get('urgency', 'غير محدد')
        urgency_color = get_urgency_color(urgency_level)
        if urgency_color == "error": st.error(f"**🚨 تقييم الخطورة والإلحاح: {urgency_level}**", icon="🚨")
        elif urgency_color == "warning": st.warning(f"**⚠️ تقييم الخطورة والإلحاح: {urgency_level}**", icon="⚠️")
        else: st.success(f"**✅ تقييم الخطورة والإلحاح: {urgency_level}**", icon="✅")
        
        with st.container(border=True):
             st.markdown(st.session_state.final_report)
        
        # --- PDF Download Button ---
        if FPDF_EXISTS:
            if os.path.exists(ARABIC_FONT_PATH):
                try:
                    # Use data stored in session state from submission
                    pdf_patient_name = st.session_state.last_patient_info.get("name", "N/A")
                    pdf_labs = {**st.session_state.last_labs, **st.session_state.ai_extracted_labs}
                    pdf_info = st.session_state.last_patient_info.copy()
                    pdf_info['id'] = patient_id
                    
                    pdf_bytes = create_pdf_bytes(st.session_state.final_report, pdf_info, pdf_labs) 
                    
                    if pdf_bytes:
                        st.download_button(
                            label="⬇️ تحميل التقرير (PDF)",
                            data=pdf_bytes,
                            file_name=f"Report_{patient_id}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.warning(f"لم نتمكن من إنشاء ملف PDF: {e}")
            else:
                 st.warning(f"لم يتم العثور على ملف الخط '{ARABIC_FONT_PATH}'. لا يمكن إنشاء PDF.")
        # --- End PDF Button ---


        if st.button("🔄 بدء تقييم جديد"):
            keys_to_clear = list(st.session_state.keys())
            keys_to_keep = ['page']
            for key in keys_to_clear:
                if key not in keys_to_keep:
                    del st.session_state[key]
            st.rerun()


# =========================== WEEKLY GUIDE PAGE ===========================
elif page == "دليل الحمل الأسبوعي":
    st.title("📅 دليل الحمل أسبوع بأسبوع")
    default_week = 8
    last_record_dict = st.session_state.patient_history_df.iloc[-1].to_dict() if not st.session_state.patient_history_df.empty else {}
    hist_week_val = safe_get(last_record_dict, 'gestational_week', default_week)
    try: hist_week = int(hist_week_val)
    except (ValueError, TypeError): hist_week = default_week
    current_week_guess = hist_week
    selected_week_input = st.number_input("اختاري أسبوع الحمل:", 1, 40, value=max(1, min(40, current_week_guess)), step=1)
    available_weeks = sorted(weekly_guide.keys())
    closest_week = min(available_weeks, key=lambda w: abs(w - selected_week_input))

    st.info(f"عرض معلومات الأسبوع {closest_week}")
    info = weekly_guide[closest_week]
    col1, col2 = st.columns(2); col1.subheader(f"👶 تطور الجنين"); col1.write(info["f"]); col2.subheader("🤰 التغيرات في جسمكِ"); col2.write(info["m"]); st.subheader("✨ نصائح هامة لكِ"); st.write(info["t"])


# =========================== FMC COUNTER PAGE ===========================
elif page == "عداد حركة الجنين":
    st.title("👣 عداد حركة الجنين (FMC)")
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
            st.session_state.fmc_start_time = datetime.datetime.now(); st.session_state.fmc_count = 0; st.rerun()
    else:
        minutes_elapsed = int((datetime.datetime.now() - st.session_state.fmc_start_time).total_seconds() // 60)
        met_col1, met_col2 = st.columns(2); met_col1.metric("الحركات", f"{st.session_state.fmc_count} / 10"); met_col2.metric("الوقت", f"{minutes_elapsed} دقيقة")
        st.progress(st.session_state.fmc_count / 10)
        if st.button("➕ تسجيل حركة", use_container_width=True, disabled=(st.session_state.fmc_count >= 10)):
            st.session_state.fmc_count += 1
            if st.session_state.fmc_count >= 10: st.balloons(); st.success(f"🎉 ممتاز! 10 حركات في {minutes_elapsed} دقيقة."); st.session_state.fmc_start_time = None
            st.rerun()
        if minutes_elapsed >= 120 and st.session_state.fmc_count < 10: st.error("‼️ مر ساعتان ولم يتم تسجيل 10 حركات. تواصلي مع طبيبكِ.")
        if st.button("🔄 إعادة البدء"): st.session_state.fmc_start_time = None; st.session_state.fmc_count = 0; st.rerun()

