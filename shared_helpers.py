"""
ملف الدوال المشتركة (Helpers) - نسخة v30
(تم إصلاح خطأ NameError/SyntaxError في دالة build_sidebar)
"""

import datetime
import streamlit as st
import pandas as pd
import gspread
from gspread.exceptions import SpreadsheetNotFound, APIError
import google.generativeai as genai
from google.generativeai.types import generation_types
from PIL import Image
import io
import os
import re
import json
import uuid  # For generating unique record IDs
import base64  # For SVG logo
import platform  # For OS detection
import sys

# --- PDF Generation Modules ---
FPDF_EXISTS = False
ARABIC_FONT_PATH = "DejaVuSans.ttf"
try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    import arabic_reshaper
    from bidi.algorithm import get_display

    if os.path.exists(ARABIC_FONT_PATH):
        FPDF_EXISTS = True
except ImportError:
    pass

# --- Tesseract Configuration ---
TESSERACT_CMD_PATH_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_AVAILABLE = False
try:
    import pytesseract

    if platform.system() == "Windows":
        if os.path.exists(TESSERACT_CMD_PATH_WIN):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH_WIN
            TESSERACT_AVAILABLE = True
    else:
        TESSERACT_AVAILABLE = True
except ImportError:
    pass

# --- AI Configuration ---
MODEL_NAME = 'gemini-2.5-flash'
GEMINI_MODEL = None
USE_GEMINI = False
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
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
    else:
        pass
except Exception as e:
    st.error(f"فشل إعداد Gemini AI بشكل فادح: {e}")
    USE_GEMINI = False

# --- Google Sheet Configuration ---
GDRIVE_SHEET_NAME = "GDM_Research_Data_V2"


# --- Custom Exceptions ---
class GSheetError(Exception):
    """خطأ مخصص لمشاكل Google Sheets."""
    pass
class AIError(Exception): pass
class PDFError(Exception): pass
class OCRError(Exception): pass


# --- SVG Logo ---
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

@st.cache_data
def svg_to_data_uri(svg_text: str) -> str:
    """Converts SVG text to a base64 data URI."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode('utf-8')).decode('utf-8')

SVG_DATA_URI = svg_to_data_uri(SVG_LOGO)


# --- Knowledge Bases & Constants ---
@st.cache_data
def load_medical_kb():
    # ... (محتوى قاعدة المعرفة الطبية) ...
    csv_data = """
Disease_Name,Common_Symptoms,Key_Lab_Tests,Normal_Range,Risk_Signs,Intervention
Gestational Diabetes,"عطش شديد، تبول متكرر، تعب، غثيان، زيادة وزن سريعة، التهابات متكررة","FBS, OGTT, HbA1c","FBS: <95; 1h: <180; 2h: <155","سكر غير منضبط، انخفاض حركات الجنين، زيادة وزن سريع للجنين","حمية قليلة السكر (تجنب العصائر والحلويات، تقسيم الوجبات)، نشاط بدني منتظم (مشي نصف ساعة يومياً)، مراقبة سكر الدم بالمنزل (4 مرات يومياً)، متابعة دكتور سكر وغدد، قد تحتاج لأنسولين"
Preeclampsia,"صداع شديد لا يستجيب للمسكنات، زغللة في النظر، تورم مفاجئ بالوجه/اليدين، ألم أعلى يمين البطن، ارتفاع ضغط، **غثيان أو قيء مفاجئ (خاصة T3)**","BP, Urine Protein, LFTs, Platelets, Creatinine","BP: <140/90, Protein: Negative/Trace","ضغط مرتفع >140/90 أو >160/110، بروتين بول ++، انخفاض صفائح (<100k)، ارتفاع وظائف كبد (ALT/AST)، صداع مستمر، زغللة","**طوارئ طبية**. raحة تامة (يفضل على الجانب الأيسر)، متابعة لصيقة بالمستشفى، أدوية ضغط (مثل Labetalol)، مراقبة الجنين، قد تحتاج لولادة مبكرة فوراً"
HELLP Syndrome,"ألم شديد أعلى يمين البطن، **غثيان وقيء شديد**، صداع، زغللة (قد يحدث مع تسمم الحمل أو بدونه)","Platelets, LFTs (AST/ALT), LDH","Platelets >150k, LFTs normal","انخفاض صفائح شديد (<100k)، ارتفاع إنزيمات كبد (AST/ALT > 70)، علامات تكسر دم (LDH مرتفع)","**طوارئ طبية قصوى**. نقل دم/صفائح إذا لزم، أدوية ضغط، الولادة الفورية هي العلاج الوحيد بغض النظر عن عمر الحمل."
Anemia,"دوخة عند الوقوف، تعب شديد وإرهاق، شحوب (في جفن العين)، خفقان، ضيق تنفس بسيط","Hb, Ferritin, CBC","Hb: >11 (T1/T3), >10.5 (T2)","شحوب شديد، ضيق تنفس عند المجهود، Hb < 9","مكملات حديد/فوليك أسيد (مثل Ferrous Fumarate) حسب وصفة الطبيب، نظام غذائي غني بالحديد (لحوم حمراء، كبدة، سبانخ، عدس) وفيتامين سي (برتقال، ليمون) لزيادة الامتصاص"
UTI,"ألم أو حرقان أثناء التبول، تكرار التبول، إلحاح بولي، ألم فوق العانة، **غثيان/قيء (إذا وصلت للكلى)**","Urine Analysis, Urine Culture","WBCs <5, Nitrite Negative","حرارة، قشعريرة، ألم بالجانب (الكلى)، غثيان/قيء (علامات Pyelonephritis)","مضاد حيوي مناسب للحمل فوراً (حسب نتيجة المزرعة إن أمكن) مع إكمال الجرعة كاملة، شرب سوائل بكثرة (8-10 أكواب ماء يومياً)، تفريغ المثانة بانتظام"
Hyperemesis Gravidarum,"**غثيان وقيء شديد ومستمر** يمنع الأكل/الشرب، فقدان وزن >5% من وزن ما قبل الحمل","Ketones in Urine, Electrolytes, LFTs","Ketones: Negative","جفاف شديد (قلة بول، دوخة)، فقدان وزن ملحوظ، كيتون في البول، خلل أملاح (هايبوكاليميا)","تجنب الأطعمة الدسمة/الروائح القوية، وجبات صغيرة جداً وجافة (بسكويت مالح)، سوائل باردة، فيتامين B6، أدوية مضادة للقيء، قد تحتاج لسوائل وريدية بالمستشفى"
Preterm Labor Signs,"انقباضات رحمية منتظمة (>4/ساعة قبل الأسبوع 37)، آلام تشبه الدورة الشهرية، نزول ماء أو إفرازات دموية/مخاطية، ضغط شديد بالحوض","Cervical exam, Ultrasound (TVU)","Cervix closed & long (>2.5cm)","انقباضات منتظمة ومؤلمة، تغييرات بعنق الرحم (قصر/اتساع)","**طوارئ طبية**. راحة تامة، شرب سوائل، التوقف عن أي مجهود، التواصل مع الطبيب أو المستشفى **فوراً**، قد تحتاج لأدوية لإيقاف الانقباضات (Tocolytics) وحقنة الرئة للجنين"
Placenta Previa,"نزيف مهbli أحمر فاتح مفاجئ **بدون ألم** (غالبًا في الثلث الثاني أو الثالث)","Ultrasound (السونار هو التشخيص الوحيد)","-","نزيف غزير ومتكرر، انقباضات رحمية مصاحبة للنزيف","راحة تامة، تجنب العلاقة الزوجية والفحص المهBli تماماً، متابعة لصيقة بالسونار، الولادة تكون قيصرية دائماً. في حال النزيف الشديد: طوارئ"
Placental Abruption,"نزيف مهbli داكن (قد يكون داخلياً بدون نزول دم)، **ألم شديد مستمر بالبطن**، بطن صلبة (كالحجر)، قلة حركة الجنين","Clinical diagnosis, Ultrasound (قد لا يظهر)","-","ألم شديد، بطن صلبة كلوح الخشب، توقف حركة الجنين، علامات صدمة للأم","**طوارئ طبية قصوى**. التوجه للطوارئ فوراً. غالباً ما تتطلب ولادة عاجلة (قيصرية أو طبيعية حسب الحالة)"
Cholestasis of Pregnancy,"**حكة شديدة** (خاصة في راحة اليدين وباطن القدمين) تزداد سوءاً في الليل، **بدون طفح جلدي**","Bile Acids, LFTs","Bile Acids < 10 μmol/L","حكة لا تحتمل، اصفرار الجلد (يرقان)، بول داكن، ارتفاع شديد في أحماض الصفراء (>40)","متابعة طبية قريبة، أدوية (Ursodiol) لتقليل الحكة والأحماض، مراقبة وظائف الكبد وحالة الجنين، قد تستدعي ولادة مبكرة (37-38 أسبوع)"
DVT (Deep Vein Thrombosis),"تورم في ساق واحدة (عادة اليسرى)، ألم شديد بالساق، احمرار، سخونة في المنطقة المتورمة","Doppler Ultrasound (سونار دوبلر)","-","ألم شديد عند ثني القدم للأعلى (Homan's sign)، تاريخ مرضي بجلطات","**تقييم فوري**. راحة ورفع الساق، أدوية مسيلة للدم (مثل Enoxaparin) مناسبة للحمل، تجنب الجلوس لفترة طويلة"
Peripartum Cardiomyopathy (PPCM),"ضيق تنفس عند الاستلقاء (orthopnea)، سعال ليلي، تورم شديد بالقدمين والساقين، خفقان، تعب شديد","Echo (موجات صوتية على القلب), BNP","BNP < 100 pg/mL (قد يرتفع قليلاً طبيعياً في الحمل)","ارتفاع BNP، انخفاض كفاءة عضلة القلب (EF) في الإيكو","**طوارئ قلب فورية**. راحة تامة، أدوية مدرة للبول وأدوية دعم القلب (ACEI/ARBs ممنوعة أثناء الحمل)، متابعة لصيقة مع طبيب قلب"
Normal Pregnancy,"**غثيان صباحي خفيف (خاصة T1)**، تعب (T1/T3)، زيادة وزن طبيعية، حركة جنين طبيعية، آلام ظهر/حوض بسيطة","Routine Antenal Care","-","عدم وجود علامات خطر (نزيف، صداع شديد، انقباضات منتظمة، قلة حركة جنين)","استمرار بالمتابعة، غذاء صحي، فيتامينات الحمل، نشاط بدني معتدل"
"""
    return pd.read_csv(io.StringIO(csv_data))

@st.cache_data
def load_weekly_guide():
    # ... (محتوى الدليل الأسبوعي) ...
    return {
        6: {"f": "بحجم حبة العدس (~0.6 سم). القلب يبدأ بالنبض، وبدايات تشكل الدماغ والوجه.",
            "m": "التعب الشديد والغثيان الصباحي (الذي قد يحدث طوال اليوم) هما الأكثر شيوعاً بسبب ارتفاع الهرمونات.",
            "t": "ابدئي بتناول حمض الفوليك (400 ميكروجرام) يومياً فوراً. تناولي وجبات صغيرة وجافة (بسكويت مالح) قبل النهوض من السرير لتقليل الغثيان."},
        12: {
            "f": "بحجم الليمونة الكبيرة (~5.4 سم). الأعضاء الرئيسية كلها تكونت. يمكنه فتح وإغلاق يديه. خطر الإجهاض يقل بشكل كبير بعد هذا الأسبوع.",
            "m": "الغثيان يبدأ بالتحسن. الرحم يكبر ليخرج من الحوض. قد تشعرين ببعض الدوخة بسبب تغيرات ضغط الدم.",
            "t": "الوقت المناسب لفحوصات الثلث الأول الهامة (مثل Nuchal Translucency). ابدئي بتمارين قاع الحوض (كيجل)."},
        16: {
            "f": "بحجم الأفوكادو (~11.6 سم). الهيكل العظمي يبدأ بالتصلب. الجهاز العصبي يبدأ بالعمل. قد تشعرين بحركاته الأولى الخفيفة (الرفة).",
            "m": "بطنك يبرز بوضوح. قد تشعرين بزيادة في الطاقة وتقليل الغثيان ('شهر العسل' للحمل).",
            "t": "الوقت مناسب لبدء تمارين الحمل الخفيفة. احرصي على شرب كميات كافية من الماء وتناول الألياف لتجنب الإمساك."},
        20: {"f": "بحجم الموزة (~25 سم من الرأس للقدم). يمكنكِ الشعور بحركاته بوضوح الآن! تتطور حواسه (السمع واللمس).",
             "m": "منتصف الطريق! الرحم يصل لمستوى السرة. الفحص التفصيلي للجنين (Anomaly Scan) هام جداً.",
             "t": "تأكدي من إجراء الفحص التفصيلي بالموجات فوق الصوتية للكشف عن أي تشوهات خلقية محتملة."},
        24: {"f": "بحجم قطعة الشمام (~30 سم). رئتاه تتطوران وتنتجان مادة السرفاكتانت الهامة للتنفس. يستجيب للأصوات.",
             "m": "قد تعانين من آلام الظهر وتورم خفيف في القدمين. هذا هو وقت فحص سكري الحمل.",
             "t": "احرصي على إجراء فحص تحمل الجلوكوز (OGTT). حاولي رفع قدميك عند الجلوس لتقليل التورم."},
        28: {
            "f": "يزن حوالي 1 كجم وطوله (~37 سم). يفتح ويغلق عينيه ويميز الضوء. فرصته في النجاة جيدة جدًا إذا ولد الآن.",
            "m": "زيادة الوزن تصبح أسرع. بداية الثلث الثالث. قد تشعرين بحرقة المعدة وضيق التنفس.",
            "t": "ابدئي بمراقبة حركة الجنين يوميًا (FMC). ناقشي مع طبيبك أعراض الولادة المبكرة. هذا هو وقت أخذ حقنة Anti-D إذا كانت فصيلة دمك سالبة."},
        32: {"f": "يزن حوالي 1.7 كجم (~42 سم). معظم الأعضاء اكتملت ما عدا الرئتين. يتخذ وضعية الولادة غالبًا.",
             "m": "قد تشعرين بضيق في التنفس أكثر بسبب حجم الرحم. تقلصات براكستون هكس (التدريبية) قد تزداد.",
             "t": "ابدئي في تعلم تقنيات التنفس للولادة. جهزي حقيبة المستشفى الأساسية. زيارات الطبيب قد تصبح كل أسبوعين."},
        36: {"f": "يزن حوالي 2.6 كجم (~47 سم). يعتبر الآن 'كامل المدة المبكرة'. يكتسب دهوناً تحت الجلد.",
             "m": "قد ينزل رأس الجنين في الحوض مما يسهل التنفس لكن يزيد الضغط أسفل البطن. زيارات الطبيب تصبح أسبوعية.",
             "t": "تأكدي من جاهزية حقيبة المستشفى كاملة. ناقشي خطة الولادة بالتفصيل مع طبيبك. إجراء مسحة GBS (للبكتيريا العقدية)."},
        40: {"f": "اكتمل النمو! متوسط الوزن ~3.4 كجم (~51 سم). جاهز للخروج للعالم.",
             "m": "وصلتِ للموعد المتوقع! قد تشعرين بالإرهاق والترقب. الولادة قد تبدأ في أي لحظة.",
             "t": "الصبر والمراقبة. استمري بمتابعة حركة الجنين. راقbi علامات بدء المخاض (انقباضات منتظمة وقوية، نزول الماء، الإفرازات المخاطية الدموية)."}
    }

# --- استدعاء الدوال مرة واحدة وتخزينها كثوابت (Uppercase) ---
MEDICAL_KB = load_medical_kb()
WEEKLY_GUIDE = load_weekly_guide()


IOM_GUIDELINES = {"نقص الوزن": (12.5, 18), "وزن طبيعي": (11.5, 16), "زيادة الوزن": (7, 11.5), "سمنة": (5, 9)}
ALL_RISK_FACTORS = {
    # (Factor, (min_week, max_week))
    "العمر أكبر من 35 سنة": (0, 40),
    "العمر أقل من 18 سنة": (0, 40),
    "تاريخ عائلي لمرض السكري": (0, 40),
    "تاريخ عائلي لارتفاع ضغط الدم": (0, 40),
    "إصابة سابقة بسكري الحمل": (0, 40),
    "إصابة سابقة بتسمم الحمل": (0, 40),
    "متلازمة تكيس المبايض (PCOS)": (0, 40),
    "زيادة الوزن أو السمنة (BMI > 25)": (0, 40),
    "أمراض الكلى المزمنة": (0, 40),
    "أمراض المناعة الذاتية (مثل الذئبة)": (0, 40),
    "الحمل المتعدد (توأم أو أكثر)": (0, 40),
    "تاريخ مرضي بأمراض القلب": (0, 40),
    "خضوع لفحص سكري الحمل (OGTT)": (24, 28)  # Week-specific example
}

# --- بنية أعمدة Google Sheet (لضمان الترتيب وعدم التكرار) ---
GSHEET_LAB_HEADERS = [
    "systolic_bp", "diastolic_bp", "fasting_glucose", "ogtt_1h", "ogtt_2h",
    "hba1c", "hb", "platelets", "alt", "ast", "creatinine",
    "urine_protein", "urine_ketones", "bnp"
]
GSHEET_BASE_HEADERS = [
    "record_id", "timestamp", "patient_id", "patient_name", "age", "gravida", "para",
    "abortion", "past_medical_history", "current_medications",
    "gestational_week", "height_cm", "pre_pregnancy_weight_kg",
    "current_weight_kg", "weight_gain_kg", "pre_pregnancy_bmi",
    "pre_pregnancy_bmi_category", "risk_factors", "symptoms_text",
    "nausea_timing", "vomiting_frequency"
]
GSHEET_AI_HEADERS = [
    "ocr_results", "brief_summary", "final_ai_report", "urgency_assessment"
]

# يتم تجميعها بالترتيب الصحيح
GSHEET_ALL_HEADERS = GSHEET_BASE_HEADERS + GSHEET_LAB_HEADERS + GSHEET_AI_HEADERS


# --- Core Functions ---

@st.cache_resource(ttl=300)
def get_gsheet_connection():
    """
    يتصل بـ Google Sheet.
    يطلق GSheetError في حالة الفشل.
    """
    try:
        if "gcp_service_account" not in st.secrets:
            raise GSheetError("لم يتم العثور على معلومات اتصال Google Sheets في st.secrets.")

        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        spreadsheet = gc.open(GDRIVE_SHEET_NAME)
        return spreadsheet.sheet1
    except SpreadsheetNotFound:
        raise GSheetError(f"خطأ: لم يتم العثور على Google Sheet '{GDRIVE_SHEET_NAME}'. تأكد من الاسم والمشاركة.")
    except APIError as e:
        raise GSheetError(f"خطأ API Google Sheets: {e}. تأكد من الأذونات وتفعيل APIs.")
    except Exception as e:
        raise GSheetError(f"فشل الاتصال بـ Google Sheets: {e}")


def get_patient_history_df(worksheet, patient_id_input):
    """
    يجلب تاريخ المريض بكفاءة باستخدام get_all_records()
    ويقوم بالتحويلات اللازمة.
    """
    try:
        if worksheet is None:
            return pd.DataFrame()

        all_records = worksheet.get_all_records()
        if not all_records:
            return pd.DataFrame()

        df = pd.DataFrame(all_records)

        required_cols = ['patient_id', 'timestamp']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()

        df = df.replace('', pd.NA)

        search_id = str(patient_id_input).strip().lower()
        df['patient_id_str'] = df['patient_id'].astype(str).str.strip().str.lower()
        patient_df = df[df['patient_id_str'] == search_id].copy().drop(columns=['patient_id_str'])

        if patient_df.empty:
            return pd.DataFrame()

        patient_df['timestamp'] = pd.to_datetime(patient_df['timestamp'], errors='coerce')
        patient_df.dropna(subset=['timestamp'], inplace=True)

        numeric_cols = [
            'age', 'gravida', 'para', 'abortion', 'gestational_week', 'height_cm',
            'pre_pregnancy_weight_kg', 'current_weight_kg', 'weight_gain_kg',
            'pre_pregnancy_bmi', 'vomiting_frequency'
        ] + GSHEET_LAB_HEADERS

        for col in numeric_cols:
            if col in patient_df.columns:
                patient_df[col] = pd.to_numeric(patient_df[col], errors='coerce')

        return patient_df.sort_values(by='timestamp', ascending=True)

    except Exception as e:
        print(f"Error fetching/processing history: {e}")
        return pd.DataFrame()


def get_relevant_risk_factors(week):
    """Filters risk factors based on gestational week."""
    relevant_factors = []
    if not isinstance(week, (int, float)): week = 0
    for factor, (min_week, max_week) in ALL_RISK_FACTORS.items():
        if min_week <= week <= max_week:
            relevant_factors.append(factor)
    return relevant_factors


def calculate_bmi(weight_kg, height_cm):
    if not height_cm or height_cm <= 0 or not weight_kg or weight_kg <= 0: return 0, "غير محدد"
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
    if bmi < 18.5:
        category = "نقص الوزن"
    elif 18.5 <= bmi < 25:
        category = "وزن طبيعي"
    elif 25 <= bmi < 30:
        category = "زيادة الوزن"
    else:
        category = "سمنة"
    return bmi, category


def ocr_with_tesseract(image_bytes):
    """
    يقوم بـ OCR على الصورة.
    يطلق OCRError في حالة الفشل.
    """
    if not TESSERACT_AVAILABLE:
        raise OCRError("Tesseract غير مفعل أو غير مثبت بشكل صحيح.")
    try:
        text = pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)), lang='ara+eng')
        return text or "لم يتم قراءة نص."
    except Exception as e:
        raise OCRError(f"خطأ Tesseract: {e}")


def ai_generate_final_report(patient_info, labs, history_df, symptoms_text, ocr_text):
    """
    يُنشئ التقرير، يستخلص التحاليل، ويقيم الإلحاح باستخدام Gemini (وضع JSON).
    يُرجع dict يحتوي على النتائج.
    يطلق AIError في حالة الفشل.
    """
    if not GEMINI_MODEL:
        raise AIError("خدمة Gemini AI غير مفعلة أو لم يتم إعدادها (تحقق من API_KEY).")

    # 1. تلخيص التاريخ (نفس الكود السابق)
    history_summary = "لا يوجد سجل سابق."
    if not history_df.empty:
        prev = history_df.iloc[-1]
        prev_ts = safe_get(prev, 'timestamp', pd.NaT)
        history_summary = f"الزيارة السابقة ({prev_ts.strftime('%Y-%m-%d') if pd.notna(prev_ts) else '?'}): وزن={safe_get(prev, 'current_weight_kg', '?')} كجم, ضغط={safe_get(prev, 'systolic_bp', '?')}/{safe_get(prev, 'diastolic_bp', '?')}, سكر صائم={safe_get(prev, 'fasting_glucose', '?')}."
        current_weight_kg = patient_info.get('current_weight', 0);
        prev_weight_kg = safe_get(prev, 'current_weight_kg', current_weight_kg)
        weight_trend = current_weight_kg - prev_weight_kg if pd.notna(current_weight_kg) and pd.notna(
            prev_weight_kg) else 0
        current_bp_sys = labs.get('systolic_bp', 0);
        prev_bp_sys = safe_get(prev, 'systolic_bp', current_bp_sys)
        bp_trend = current_bp_sys - prev_bp_sys if pd.notna(current_bp_sys) and pd.notna(prev_bp_sys) else 0
        history_summary += f"\n   - التغير: وزن {weight_trend:+.1f} كجم, ضغط {bp_trend:+.0f} mmHg."

    manual_lab_summary = ", ".join(
        [f"{k.replace('_', ' ').title()}: {v}" for k, v in labs.items() if v is not None]) or "لا يوجد إدخال يدوي."

    # 2. بناء Prompt (لJSON)
    prompt = f"""
    مهمتك: تحليل حالة حمل كمستشار طبي ذكي وإرجاع كائن JSON منظم.

    قاعدة المعرفة: {MEDICAL_KB.to_string()}
    أعمدة التحاليل المستهدفة للاستخلاص: {', '.join(GSHEET_LAB_HEADERS)}

    بيانات الحالة الحالية:
    - المعلومات الأساسية: {patient_info}
    - الأعراض النصية: "{symptoms_text}"
    - تفاصيل الغثيان/القيء: أوقات الغثيان: "{patient_info.get('nausea_timing', 'لا يوجد')}", عدد مرات التقيؤ (آخر 24 ساعة): {patient_info.get('vomiting_frequency', 0)}
    - الأدوية الحالية: "{patient_info.get('current_medications', 'لا يوجد')}"
    - التحاليل اليدوية: "{manual_lab_summary}"
    - النص المستخرج من صورة التحاليل (قد يكون غير دقيق): "{ocr_text}"
    - ملخص الزيارة السابقة: {history_summary}

    المطلوب:
    قم بإرجاع كائن JSON فقط بالبنية التالية:
    {{
      "urgency": "(صنف الحالة: متابعة روتينية، استشارة قريبة، تقييم فوري)",
      "brief_summary": "(اكتب فقرة من 2-3 أسطر للمريضة بلغة بسيطة جدًا تطمئنها أو تحذرها بناءً على أهم نتيجة)",
      "detailed_report": "(اكتب التقرير الطبي المفصل بالكامل هنا، يشمل: الترحيب، التشخيص التفريقي، التشخيص النهائي (مع التعليق على الغثيان/القيء هل هو طبيعي أم لا)، مستوى الإلحاح وتفسيره، إرشادات وتدخلات عملية ومخصصة، علامات الخطر، وتأكيد المتابعة)",
      "extracted_labs": {{
        "(اسم التحليل من الأعمدة المستهدفة، مثلاً 'fasting_glucose')": (القيمة الرقمية المستخلصة، مثلاً 92),
        "(اسم تحليل آخر، مثلاً 'systolic_bp')": 125,
        "(اسم تحليل آخر، مثلاً 'hb')": 11.2
      }}
    }}

    تعليمات إضافية:
    1.  **الاستخلاص المنظم للتحاليل:** ادمج التحاليل اليدوية مع القيم الموثوقة من نص OCR. طابق الأسماء مع الأعمدة المستهدفة فقط. أرجع الأرقام فقط.
    2.  **التقرير المفصل:** كن شاملاً ومفيداً.
    """

    # 3. استدعاء الـ AI وتفسير الـ JSON
    try:
        response = GEMINI_MODEL.generate_content(prompt)

        cleaned_text = re.sub(r"```json\s*(.*?)\s*```", r"\1", response.text, flags=re.DOTALL).strip()
        ai_data = json.loads(cleaned_text)

        if not all(k in ai_data for k in ['urgency', 'brief_summary', 'detailed_report', 'extracted_labs']):
            raise AIError("استجابة AI ناقصة (لم يتم العثور على المفاتيح المطلوبة).")

        if not isinstance(ai_data['extracted_labs'], dict):
             ai_data['extracted_labs'] = {}

        return ai_data

    except json.JSONDecodeError as e:
        raise AIError(f"فشل في تحليل استجابة JSON من AI: {e}\nالاستجابة: {response.text}")
    except Exception as e:
        raise AIError(f"حدث خطأ أثناء استدعاء Gemini AI: {e}")


def save_record_to_gsheet(worksheet, record: dict):
    """
    يحفظ السجل في Google Sheet.
    يطلق GSheetError في حالة الفشل.
    """
    try:
        if worksheet is None:
            raise GSheetError("فشل الحفظ: اتصال Google Sheet غير موجود.")

        record_to_save = {}

        ai_labs = record.get('ai_extracted_labs', {})
        manual_labs = {k: record.get(k) for k in GSHEET_LAB_HEADERS if record.get(k) is not None}

        lab_values = {}
        for lab_header in GSHEET_LAB_HEADERS:
            ai_val = ai_labs.get(lab_header)
            manual_val = manual_labs.get(lab_header)
            final_val = ai_val if ai_val is not None else manual_val

            if final_val is None or final_val == "":
                final_val = "N/A"
            else:
                try:
                    fv = float(final_val)
                    final_val = int(fv) if fv == int(fv) else fv
                except (ValueError, TypeError):
                    final_val = str(final_val)

            lab_values[lab_header] = final_val

        final_row_dict = {}
        for header in GSHEET_ALL_HEADERS:
            if header in lab_values:
                final_row_dict[header] = lab_values[header]
            else:
                final_row_dict[header] = record.get(header, "N/A")

        final_row_dict['record_id'] = str(uuid.uuid4())
        final_row_dict['timestamp'] = datetime.datetime.now().isoformat()

        row_to_append = [final_row_dict.get(h, "N/A") for h in GSHEET_ALL_HEADERS]

        worksheet.append_rows([row_to_append], value_input_option='USER_ENTERED')

        return True

    except APIError as e:
        raise GSheetError(f"فشل الحفظ (API Error): {e}")
    except Exception as e:
        raise GSheetError(f"فشل الحفظ (Unexpected): {e}")


# --- Utility Functions ---
def safe_get(record, key, default):
    """Safely gets a value from a dictionary or Pandas Series, handling None and NA."""
    val = record.get(key)
    return default if pd.isna(val) or val is None else val


def get_urgency_color(urgency_text):
    urgency_lower = str(urgency_text).lower()
    if "فوري" in urgency_lower or "immediate" in urgency_lower or "urgent" in urgency_lower:
        return "error"
    elif "قريبة" in urgency_lower or "soon" in urgency_lower:
        return "warning"
    elif "روتيني" in urgency_lower or "routine" in urgency_lower:
        return "success"
    else:
        return "info"  # Default for unknown/N/A


def create_pdf_bytes(report_text, patient_info, labs):
    """
    ينشئ ملف PDF في الذاكرة.
    يطلق PDFError في حالة الفشل.
    """
    if not FPDF_EXISTS or not os.path.exists(ARABIC_FONT_PATH):
        raise PDFError(f"خطأ PDF: المكتبات أو ملف الخط '{ARABIC_FONT_PATH}' مفقود.")

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('DejaVu', '', ARABIC_FONT_PATH, uni=True)

        pdf.set_font('DejaVu', '', 16)
        title = f"تقرير المساعد الذكي للمريضة: {patient_info.get('name', 'N/A')}"
        reshaped_title = arabic_reshaper.reshape(title);
        bidi_title = get_display(reshaped_title)
        pdf.cell(0, 10, bidi_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5)

        pdf.set_font('DejaVu', '', 11)
        info_text = f"المعرف: {patient_info.get('id', 'N/A')} | العمر: {patient_info.get('age', 'N/A')} | أسبوع الحمل: {patient_info.get('week', 'N/A')}"
        reshaped_info = arabic_reshaper.reshape(str(info_text));
        bidi_info = get_display(reshaped_info)
        pdf.cell(0, 8, bidi_info, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        pdf.ln(5)

        pdf.set_font('DejaVu', '', 10)
        report_text_str = str(report_text or "")
        for line in report_text_str.split('\n'):
            line_stripped = line.strip()
            if line_stripped:
                reshaped_line = arabic_reshaper.reshape(line_stripped);
                bidi_line = get_display(reshaped_line)
                pdf.multi_cell(0, 7, bidi_line, align='R')
            else:
                pdf.ln(7)  # Add a blank line

        return pdf.output(dest='S').encode('latin-1')

    except Exception as e:
        raise PDFError(f"حدث خطأ غير متوقع أثناء إنشاء PDF: {e}")


# --- 💡💡 (تمت إضافة هذه الدالة الجديدة) 💡💡 ---
def apply_global_styles():
    """
    تطبق الـ CSS المخصص للتطبيق بالكامل.
    """
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
            body, .stApp, input, textarea, button, select, label, div[data-baseweb="select"] > div, .stDataFrame *, .stTable *, .stMarkdown p { 
                font-family: 'Cairo', sans-serif !important; 
                direction: rtl; 
                color: #000000 !important; /* **FIX**: Force BLACK text color */
            }
            /* **PINKER THEME** & Mobile Responsive */
            .stApp { background: linear-gradient(135deg, #FFF0F5 0%, #FFE4E1 100%); } /* Softer Pink Gradient */
            
            /* (تأكد أن هذا الـ class صحيح، قد يحتاج للتعديل) */
            /* هذا يضمن أن الصفحات الفرعية لها خلفية بيضاء شفافة */
            .main > div { 
                background-color: rgba(255, 255, 255, 0.95); 
                padding: 2rem; 
                border-radius: 25px; 
                box-shadow: 0 15px 50px rgba(255, 105, 180, 0.15); 
                border: 1px solid rgba(255, 255, 255, 0.3); 
            }
            
            h1, h2, h3 { color: #D81B60 !important; font-weight: 700; } /* Main Title Pink */
            h1 { text-align: center; margin-bottom: 2.5rem; }
            h3 { border-bottom: 2px solid #F8BBD0; padding-bottom: 0.6rem; margin-top: 2rem; margin-bottom: 1rem; display: flex; align-items: center;}
            h3::before { content: '⭐ '; margin-left: 10px; font-size: 1.1em; color: #FF69B4; }
            h3:contains("المعلومات الأساسية")::before { content: '👤 '; }
            h3:contains("القياسات الأساسية")::before { content: '📏 '; }
            h3:contains("عوامل الخطورة")::before { content: '❗ '; }
            h3:contains("الأعراض الحالية")::before { content: '❓ '; }
            h3:contains("نتائج التحاليل")::before { content: '🔬 '; }

            .stButton>button { 
                border-radius: 30px; border: none; color: white !important; /* Force white text on button */
                background: linear-gradient(45deg, #FF69B4, #D81B60); /* Pink Gradient */
                padding: 15px 40px; font-size: 1.1em; font-weight: 700; 
                box-shadow: 0 6px 20px rgba(216, 27, 96, 0.35); 
                transition: all 0.3s ease; cursor: pointer; 
            }
            .stButton>button:hover { 
                transform: translateY(-5px) scale(1.05); 
                box-shadow: 0 10px 30px rgba(216, 27, 96, 0.45); 
            }

            /* **DARK MODE FIX** */
            .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { 
                border-radius: 12px; border: 1px solid #F48FB1 !important;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.06); 
                transition: all 0.2s ease-in-out; padding: 10px 12px;
                background-color: #FFFFFF !important; /* Force white background */
                color: #333333 !important; /* Force dark text */
            }
            div[data-baseweb="popover"] li {
                color: #333333 !important;
            }

            .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { 
                border-color: #D81B60 !important; /* Darker Pink Focus */
                box-shadow: 0 0 0 4px rgba(255, 105, 180, 0.2) !important; 
                transform: scale(1.01); 
            }

            .stDataFrame, .stTable { border-radius: 10px; overflow: hidden; border: 1px solid #F8BBD0; box-shadow: 0 4px 10px rgba(0,0,0,0.05); color: #333333 !important;}
            .stDataFrame *, .stTable * { color: #333333 !important; } /* Force dark text in tables */

            .stSpinner > div { border-top-color: #D81B60 !important; border-left-color: #D81B60 !important; }
            .stMetric { background-color: #FCE4EC; padding: 1rem; border-radius: 15px; border: 1px solid #F8BBD0; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.05);}
            .stMetric label { color: #AD1457 !important; font-weight: bold; font-size: 0.9em;}
            .stMetric .st-ae { font-size: 1.8em; color: #880E4F !important; font-weight: 700;} 
            .stProgress > div > div { background-image: linear-gradient(45deg, #FF69B4, #D81B60); border-radius: 10px; }

            .stContainer { border: 1px solid #F8BBD0; border-radius: 15px; padding: 1.5rem; margin-bottom: 1.5rem; background-color: rgba(255, 255, 255, 0.65);}
            .stAlert { border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; }
            .stAlert [data-testid="stMarkdownContainer"] p { font-weight: bold; color: inherit !important; }

            /* **BLACK CHECKBOX FIX** */
            [data-testid="stCheckbox"] label { color: #000000 !important; }

            /* Mobile Responsive Fixes */
            @media (max-width: 768px) {
                .main > div { padding: 1rem 1rem; } 
                h1 { font-size: 1.6em; margin-bottom: 1.5rem; }
                h3 { font-size: 1.15em; }
                .stButton>button { padding: 12px 25px; font-size: 1em; }
                .stMetric { padding: 0.5rem; }
                .stMetric .st-ae { font-size: 1.5em; }
                .stMetric label { font-size: 0.8em; }
            }
            
            /* ستايل القائمة الجانبية الجديدة */
            [data-testid="stSidebar"] { 
                background: linear-gradient(180deg, #FFF0F5 0%, #FFE4E1 100%);
                border-right: 1px solid #F8BBD0;
            }
            [data-testid="stSidebar"] .st-emotion-cache-16txtl3 { /* عنوان القائمة */
                color: #D81B60 !important;
                font-family: 'Cairo', sans-serif !important;
                font-weight: 700;
            }
            
            /* 💡💡 (تم تعديل هذا الجزء لإصلاح اللون الأبيض) 💡💡 */
            [data-testid="stSidebar"] a { /* روابط الصفحات */
                font-family: 'Cairo', sans-serif !important;
                font-size: 1.05em;
                color: #AD1457 !important; /* <-- اللون الأساسي (أغمق) */
                border-radius: 10px;
                transition: all 0.2s ease;
            }
            [data-testid="stSidebar"] a:hover {
                background-color: #FCE4EC;
                color: #880E4F !important; /* <-- لون عند المرور (أغمق) */
            }
            [data-testid="stSidebar"] a[aria-current="page"] { /* الصفحة الحالية */
                background-color: #F48FB1;
                color: #880E4F !important; /* <-- لون الصفحة النشطة (أغمق) */
                font-weight: 700;
            }
        </style>
    """, unsafe_allow_html=True)


# --- 💡💡 (تمت إضافة دالة القائمة الجانبية الموحدة) 💡💡 ---
def build_sidebar():
    """
    تنشئ القائمة الجانبية المخصصة (العربية).
    يجب استدعاؤها في بداية كل صفحة.
    """
    
    # 💡 (الحل 1: تحديد اسم الملف الرئيسي ديناميكيًا)
    # هذا الكود يحدد ما إذا كنا في الصفحة الرئيسية أم لا
    try:
        # 💡 (الحل 2: الاعتماد على الرمز '/' الرسمي)
        main_page_path = "/" # <-- 💡💡💡 هذا هو المسار الصحيح للصفحة الرئيسية
    except Exception as e:
        print(f"Error getting main page path: {e}")
        main_page_path = "/" # الاعتماد على الرمز الافتراضي


    with st.sidebar:
        st.image(SVG_DATA_URI, width=250)
        st.title("مساعد الحمل الذكي")

        # --- 💡💡 (تم تعديل المسار الرئيسي هنا) 💡💡 ---
        st.page_link("app1.py", label="🏠 القائمة الرئيسية", icon="🏠")
        
        # --- 💡💡 (تم إصلاح الخطأ الإملائي هنا) 💡💡 ---
        st.page_link("pages/assessment_wizard.py", label="👩‍⚕️ التقييم الشامل", icon="👩‍⚕️")
        st.page_link("pages/chatbot_page.py", label="💬 الدردشة الذكية", icon="💬")
        st.page_link("pages/dashboard.py", label="📊 لوحة المتابعة", icon="📊")
        st.page_link("pages/weekly_guide.py", label="📅 دليل الحمل الأسبوعي", icon="📅")
        st.page_link("pages/fmc_counter.py", label="👣 عداد حركة الجنين", icon="👣")
