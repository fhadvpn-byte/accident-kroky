import html
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import base64
import os
import json
import hashlib
import math
import tempfile
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path


def _select_images_dir():
    candidates = (
        Path.cwd() / "saved_accident_images",
        Path(tempfile.gettempdir()) / "bayyinah_images",
    )
    for folder in candidates:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".bayyinah_write_probe"
            probe.write_bytes(b"")
            probe.unlink()
            return folder
        except OSError:
            continue
    return candidates[-1]


SAVED_IMAGES_DIR = _select_images_dir()
ARABIC_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
]
GROQ_VISION_MODELS = (
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
)


def gregorian_to_hijri_str(gregorian_date):
    year = int(gregorian_date.year)
    month = int(gregorian_date.month)
    day = int(gregorian_date.day)
    if month < 3:
        year -= 1
        month += 12
    century = math.floor(year / 100)
    gregorian_shift = 2 - century + math.floor(century / 4)
    julian_day = (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + gregorian_shift
        - 1524
    )
    lunar = julian_day - 1948440 + 10632
    cycles = math.floor((lunar - 1) / 10631)
    lunar = lunar - 10631 * cycles + 354
    jump = (
        math.floor((10985 - lunar) / 5316) * math.floor((50 * lunar) / 17719)
    ) + (
        math.floor(lunar / 5670) * math.floor((43 * lunar) / 15238)
    )
    lunar = (
        lunar
        - (math.floor((30 - jump) / 15) * math.floor((17719 * jump) / 50))
        - (math.floor(jump / 16) * math.floor((15238 * jump) / 43))
        + 29
    )
    hijri_month = math.floor((24 * lunar) / 709)
    hijri_day = lunar - math.floor((709 * hijri_month) / 24)
    hijri_year = 30 * cycles + jump - 30
    return f"{int(hijri_year):04d}/{int(hijri_month):02d}/{int(hijri_day):02d}"


def get_today_hijri():
    return gregorian_to_hijri_str(date.today())


def _blank_parties():
    return [
        {"الطرف": "الطرف الأول", "الاسم": "", "الهوية": "", "المشاركة": "", "الحالة": "", "التأهيل": ""},
        {"الطرف": "الطرف الثاني", "الاسم": "", "الهوية": "", "المشاركة": "", "الحالة": "", "التأهيل": ""},
    ]


def _blank_vehicles():
    return [
        {"الطرف": "الطرف الأول", "نوع المركبة": "", "رقم اللوحة": "", "الرقم التسلسلي": "", "نوع الترخيص": "", "التأمين": ""},
        {"الطرف": "الطرف الثاني", "نوع المركبة": "", "رقم اللوحة": "", "الرقم التسلسلي": "", "نوع الترخيص": "", "التأمين": ""},
    ]


DRAFT_FILE_PATH = "bayyinah_autosave_draft.json"
DEFAULT_REPORT_STATE = {
    "accident_results": "",
    "technical_description": "",
    "legal_opinion": "",
    "selected_articles": [],
    "accident_nature": "حادث مروري اعتيادي",
    "rights_status": "اختر الحالة",
    "extra_procedure": "",
    "has_video": "لا فيديو",
    "video_clip_count": 1,
    "video_clips": [],
    "video_source": "كاميرا مراقبة أمنية (CCTV)",
    "video_clarity": "واضح وموثق بختم زمني (تاريخ ووقت)",
    "video_timestamp": "",
    "video_findings": [],
    "video_custom_notes": "",
    "video_injected_text": "",
    "auto_analyze_video": True,
    "show_page_numbers": False,
    "confirm_clear": False,
    "last_saved_time": "لم يتم الحفظ بعد",
}


def init_and_load_state():
    if "state_initialized" in st.session_state:
        return
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            with open(DRAFT_FILE_PATH, "r", encoding="utf-8") as draft_file:
                saved_data = json.load(draft_file)
            for key, default_val in DEFAULT_REPORT_STATE.items():
                st.session_state[key] = saved_data.get(key, default_val)
        except (OSError, json.JSONDecodeError, TypeError):
            for key, default_val in DEFAULT_REPORT_STATE.items():
                st.session_state.setdefault(key, default_val)
    else:
        for key, default_val in DEFAULT_REPORT_STATE.items():
            st.session_state.setdefault(key, default_val)
    if not isinstance(st.session_state.get("selected_articles"), list):
        st.session_state.selected_articles = []
    if not isinstance(st.session_state.get("video_findings"), list):
        st.session_state.video_findings = []
    for text_key in (
        "accident_results",
        "technical_description",
        "legal_opinion",
        "extra_procedure",
        "video_timestamp",
        "video_custom_notes",
    ):
        if not isinstance(st.session_state.get(text_key), str):
            st.session_state[text_key] = ""
    if not isinstance(st.session_state.get("show_page_numbers"), bool):
        st.session_state.show_page_numbers = False
    if not isinstance(st.session_state.get("auto_analyze_video"), bool):
        st.session_state.auto_analyze_video = True
    _normalize_loaded_video_state()
    st.session_state.law_selection_sig = tuple(st.session_state.get("selected_articles") or [])
    st.session_state["state_initialized"] = True


def save_current_work():
    data_to_save = {}
    for key in DEFAULT_REPORT_STATE:
        if key in st.session_state and key != "confirm_clear":
            data_to_save[key] = st.session_state[key]
    now_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d | %I:%M:%S %p")
    data_to_save["last_saved_time"] = now_str
    st.session_state["last_saved_time"] = now_str
    try:
        with open(DRAFT_FILE_PATH, "w", encoding="utf-8") as draft_file:
            json.dump(data_to_save, draft_file, ensure_ascii=False, indent=2)
        return True
    except OSError as error:
        st.error(f"حدث خطأ أثناء حفظ المسودة: {error}")
        return False


def clear_all_work():
    if os.path.exists(DRAFT_FILE_PATH):
        try:
            os.remove(DRAFT_FILE_PATH)
        except OSError:
            pass
    for key, default_val in DEFAULT_REPORT_STATE.items():
        st.session_state[key] = default_val
    st.session_state.law_selection_sig = ()
    st.session_state.pop("last_analyzed_video_sig", None)
    st.session_state["confirm_clear"] = False


def inject_bayyinah_blue_styles():
    st.markdown("""
    <style>
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div,
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[role="button"],
    .stMultiSelect div[role="button"] {
        background: linear-gradient(135deg, rgba(8, 56, 114, 0.88), rgba(4, 38, 84, 0.92)) !important;
        color: #ffffff !important;
        border: 1.5px solid #00d2ff !important;
        border-radius: 10px !important;
        box-shadow: 0 0 10px rgba(0, 210, 255, 0.2) !important;
    }
    .save-bar-container,
    [class*="st-key-save-bar"] {
        background: linear-gradient(90deg, rgba(5, 45, 95, 0.95), rgba(10, 75, 145, 0.95));
        border: 1px solid #00e1ff;
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 18px;
        box-shadow: 0 4px 15px rgba(0, 225, 255, 0.25);
        direction: rtl;
    }
    .video-evidence-box,
    [class*="st-key-video-evidence"] {
        background: linear-gradient(135deg, rgba(6, 52, 108, 0.9), rgba(3, 33, 74, 0.95));
        border: 1.5px solid #00d4ff;
        border-radius: 14px;
        padding: 16px;
        margin: 15px 0;
        box-shadow: 0 0 18px rgba(0, 212, 255, 0.22);
        direction: rtl;
    }
    </style>
    """, unsafe_allow_html=True)


def render_save_and_clear_toolbar():
    with st.container(key="save-bar"):
        col_status, col_save, col_clear = st.columns([3, 1.5, 1.5])
        with col_status:
            st.markdown(
                f"**🛡️ نظام حماية البيانات النشط:** آخر حفظ للعمل: `{st.session_state.get('last_saved_time', 'لم يتم الحفظ بعد')}`"
            )
        with col_save:
            if st.button("💾 حفظ العمل الحالي", use_container_width=True, type="primary"):
                if save_current_work():
                    st.toast("تم حفظ جميع بيانات التقرير والصفحات بنجاح", icon="💾")
        with col_clear:
            if not st.session_state.get("confirm_clear", False):
                if st.button("🗑️ مسح جميع الحقول", use_container_width=True):
                    st.session_state["confirm_clear"] = True
                    st.rerun()
            else:
                sub_c1, sub_c2 = st.columns(2)
                with sub_c1:
                    if st.button("⚠️ تأكيد المسح", use_container_width=True):
                        clear_all_work()
                        st.toast("تم مسح البيانات وبدء تقرير جديد", icon="🔄")
                        st.rerun()
                with sub_c2:
                    if st.button("إلغاء", use_container_width=True):
                        st.session_state["confirm_clear"] = False
                        st.rerun()


VIDEO_MARKER_START = "[بداية القرائن المرئية]"
VIDEO_MARKER_END = "[نهاية القرائن المرئية]"
VIDEO_SOURCE_OPTIONS = [
    "كاميرات الرصد الآلي / المدن الذكية",
    "كاميرا مراقبة أمنية (CCTV)",
    "كاميرا مركبة (داش كام - Dashcam)",
    "كاميرا منشأة تجارية / خاصة محيطة",
    "تصوير هاتف محمول موثق",
]
VIDEO_CLARITY_OPTIONS = [
    "واضح الدقة (بدون ختم زمني ظاهر)",
    "واضح وموثق بختم زمني (تاريخ ووقت)",
    "متوسط الوضوح ولكن يُظهر آلية الاصطدام",
    "زاوية بعيدة تُظهر اتجاهات المركبات فقط",
]
VIDEO_FINDING_OPTIONS = [
    "رصد لحظة الاصطدام وزاوية الدخول بدقة",
    "ثبوت انحراف المركبة المتسببة بشكل مفاجئ على مسار الطرف الآخر",
    "تجاوز السرعة النظامية وعدم ظهور إضاءة المكابح قبل الاصطدام",
    "ثبوت قطع الإشارة الضوئية الحمراء بالصوت والصورة",
    "ثبوت السير عكس اتجاه الحركة المرورية",
    "رصد قرائن تدل على تعمد الصدم أو المطاردة والمضايقة (شبهة جنائية)",
    "رصد هروب المركبة المتسببة من مسرح الحادث عقب الاصطدام مباشرة",
    "ثبوت هوية السائق الفعلي وقت الاصطدام قبل محاولة الاستبدال",
    "تأكيد التوقف النظامي للمركبة المتضررة قبل تعرضها للصدم",
]
VIDEO_CLIP_MIN = 1
VIDEO_CLIP_MAX = 10
VIDEO_HAS_OPTIONS = ["لا فيديو", "يوجد توثيق"]


def _blank_video_clip():
    return {
        "source": VIDEO_SOURCE_OPTIONS[0],
        "clarity": VIDEO_CLARITY_OPTIONS[0],
        "timestamp": "",
        "findings": [],
        "notes": "",
    }


def _normalize_video_clip(raw):
    clip = _blank_video_clip()
    if isinstance(raw, dict):
        if raw.get("source") in VIDEO_SOURCE_OPTIONS:
            clip["source"] = raw["source"]
        if raw.get("clarity") in VIDEO_CLARITY_OPTIONS:
            clip["clarity"] = raw["clarity"]
        clip["timestamp"] = str(raw.get("timestamp") or "").strip()
        findings = raw.get("findings") if isinstance(raw.get("findings"), list) else []
        clip["findings"] = [item for item in findings if item in VIDEO_FINDING_OPTIONS]
        clip["notes"] = str(raw.get("notes") or "").strip()
    return clip


def _clamp_clip_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = VIDEO_CLIP_MIN
    return max(VIDEO_CLIP_MIN, min(VIDEO_CLIP_MAX, count))


def _normalize_loaded_video_state():
    raw_has = str(st.session_state.get("has_video") or "")
    if raw_has in ("لا يوجد مقطع فيديو", "لا فيديو"):
        st.session_state.has_video = "لا فيديو"
    elif "توثيق" in raw_has or raw_has.startswith("نعم"):
        st.session_state.has_video = "يوجد توثيق"
    else:
        st.session_state.has_video = "لا فيديو"
    clips = st.session_state.get("video_clips")
    if not isinstance(clips, list) or not clips:
        legacy = _blank_video_clip()
        if st.session_state.get("video_source") in VIDEO_SOURCE_OPTIONS:
            legacy["source"] = st.session_state.video_source
        if st.session_state.get("video_clarity") in VIDEO_CLARITY_OPTIONS:
            legacy["clarity"] = st.session_state.video_clarity
        legacy["timestamp"] = str(st.session_state.get("video_timestamp") or "").strip()
        old_findings = st.session_state.get("video_findings")
        if isinstance(old_findings, list):
            legacy["findings"] = [item for item in old_findings if item in VIDEO_FINDING_OPTIONS]
        legacy["notes"] = str(st.session_state.get("video_custom_notes") or "").strip()
        clips = [legacy]
    clips = [_normalize_video_clip(item) for item in clips][:VIDEO_CLIP_MAX]
    if not clips:
        clips = [_blank_video_clip()]
    count = _clamp_clip_count(st.session_state.get("video_clip_count", len(clips)))
    while len(clips) < count:
        clips.append(_blank_video_clip())
    st.session_state.video_clips = clips[:count]
    st.session_state.video_clip_count = count


def _sync_video_clips(count):
    count = _clamp_clip_count(count)
    clips = [_normalize_video_clip(item) for item in (st.session_state.get("video_clips") or [])]
    while len(clips) < count:
        clips.append(_blank_video_clip())
    st.session_state.video_clips = clips[:count]
    return st.session_state.video_clips


def _store_clip_fields():
    count = _clamp_clip_count(st.session_state.get("video_clip_count"))
    clips = []
    for index in range(count):
        findings = st.session_state.get(f"clip_{index}_findings", [])
        if not isinstance(findings, list):
            findings = []
        clips.append(_normalize_video_clip({
            "source": st.session_state.get(f"clip_{index}_source"),
            "clarity": st.session_state.get(f"clip_{index}_clarity"),
            "timestamp": st.session_state.get(f"clip_{index}_timestamp", ""),
            "findings": findings,
            "notes": st.session_state.get(f"clip_{index}_notes", ""),
        }))
    st.session_state.video_clips = clips
    save_current_work()


def _active_video_clips():
    count = _clamp_clip_count(st.session_state.get("video_clip_count"))
    stored = _sync_video_clips(count)
    clips = []
    for index, clip in enumerate(stored):
        findings = st.session_state.get(f"clip_{index}_findings", clip["findings"])
        if not isinstance(findings, list):
            findings = []
        clips.append(_normalize_video_clip({
            "source": st.session_state.get(f"clip_{index}_source", clip["source"]),
            "clarity": st.session_state.get(f"clip_{index}_clarity", clip["clarity"]),
            "timestamp": st.session_state.get(f"clip_{index}_timestamp", clip["timestamp"]),
            "findings": findings,
            "notes": st.session_state.get(f"clip_{index}_notes", clip["notes"]),
        }))
    return clips


def _extract_marked_block(text):
    text = str(text or "")
    if VIDEO_MARKER_START in text and VIDEO_MARKER_END in text:
        return text.split(VIDEO_MARKER_START, 1)[1].split(VIDEO_MARKER_END, 1)[0].strip()
    return ""


def _strip_marked_block(text):
    text = str(text or "")
    if VIDEO_MARKER_START in text and VIDEO_MARKER_END in text:
        pre, rest = text.split(VIDEO_MARKER_START, 1)
        _, post = rest.split(VIDEO_MARKER_END, 1)
        return f"{pre.rstrip()}\n\n{post.lstrip()}".strip()
    return text.strip()


def _upsert_marked_block(text, block):
    base = _strip_marked_block(text)
    block = str(block or "").strip()
    if not block:
        return base
    marked = f"{VIDEO_MARKER_START}\n{block}\n{VIDEO_MARKER_END}"
    return f"{base}\n\n{marked}".strip() if base else marked


def _manual_evidence_blocks():
    clips = _active_video_clips()
    how_lines = []
    result_lines = []
    opinion_lines = []
    for index, clip in enumerate(clips, start=1):
        findings = "، ".join(clip["findings"]) if clip["findings"] else "رصد آلية وحركة المركبات لحظة وقوع الحادث"
        time_clause = f" والموثق زمنياً عند ({clip['timestamp']})" if clip["timestamp"] else ""
        notes = f"؛ كما أظهر التسجيل أن ({clip['notes']})" if clip["notes"] else ""
        how_lines.append(
            f"المقطع ({index}): تعززت المعاينة الفنية بالاطلاع على التسجيل المرئي المستخرج من ({clip['source']}) "
            f"وهو ({clip['clarity']}){time_clause}، حيث أظهر المقطع: {findings}{notes}."
        )
        result_lines.append(f"{index}- ثبت من المقطع المرئي رقم ({index}) ({clip['source']}): {findings}.")
        opinion_lines.append(
            f"• قرينة المقطع المرئي ({index}) من ({clip['source']}): ثبوت ({findings}){notes}."
        )
    return "\n".join(how_lines), "\n".join(result_lines), "\n".join(opinion_lines)


def insert_manual_video_evidence():
    how_block, results_block, opinion_block = _manual_evidence_blocks()
    st.session_state.technical_description = _upsert_marked_block(
        st.session_state.get("technical_description", ""),
        how_block,
    )
    st.session_state.accident_results = _upsert_marked_block(
        st.session_state.get("accident_results", ""),
        results_block,
    )
    st.session_state.legal_opinion = _upsert_marked_block(
        st.session_state.get("legal_opinion", ""),
        opinion_block,
    )
    st.session_state.video_injected_text = how_block
    save_current_work()


def remove_manual_video_evidence():
    st.session_state.technical_description = _strip_marked_block(st.session_state.get("technical_description", ""))
    st.session_state.accident_results = _strip_marked_block(st.session_state.get("accident_results", ""))
    st.session_state.legal_opinion = _strip_marked_block(st.session_state.get("legal_opinion", ""))
    st.session_state.video_injected_text = ""
    save_current_work()


def _gemini_secret_key():
    for env_key in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    try:
        value = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    except Exception:
        return ""
    return str(value or "").strip()


def _resolved_gemini_key():
    typed = str(st.session_state.get("gemini_api_key") or "").strip()
    if typed:
        return typed
    return _gemini_secret_key()


def _redact_secret(message, secret):
    text = str(message or "")
    if secret:
        text = text.replace(secret, "•••")
    return text


def _collect_uploaded_videos():
    """Collects all uploaded videos from both the bulk multi-file uploader and individual clip tabs."""
    clips = _active_video_clips()
    bulk_files = st.session_state.get("bulk_video_files") or []
    uploads = []
    for index, clip in enumerate(clips):
        uploaded = st.session_state.get(f"clip_file_{index}")
        if uploaded is None and index < len(bulk_files):
            uploaded = bulk_files[index]
        if uploaded is not None:
            uploads.append((index, clip, uploaded))
    return uploads


def _groq_text_fallback(prompt_text):
    """Fallback to Groq LLM if Gemini API key is not configured but GROQ_API_KEY exists."""
    import urllib.request
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        try:
            groq_key = str(st.secrets.get("GROQ_API_KEY") or "").strip()
        except Exception:
            groq_key = ""
    if not groq_key:
        return None
    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "أنت خبير تحقيق حوادث مرورية في المرور السعودي. أجب بكائن JSON صالح فقط بدون markdown "
                    "يحتوي على المفاتيح: technical_description (صياغة فنية رسمية مفصلة لكيفية وقوع الحادث) "
                    "و accident_results (نتائج الحادث في نقاط مرقمة) و legal_opinion (الرأي والمسؤولية النظامية)."
                ),
            },
            {"role": "user", "content": prompt_text},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def analyze_videos_with_gemini(uploads=None):
    if uploads is None:
        uploads = _collect_uploaded_videos()
    if not uploads:
        st.warning("⚠️ ارفع مقطع فيديو واحداً على الأقل قبل طلب التحليل الذكي.")
        return False

    api_key = _resolved_gemini_key()
    prompt_lines = [
        "أنت خبير معاينة وتحقيق حوادث مرورية معتمد في الإدارة العامة للمرور بالمملكة العربية السعودية.",
        "شاهد مقاطع الفيديو المرفقة وحلل حركة المركبات والمسارات ونقطة التصادم والخطأ المروري بدقة.",
        "أجب بكائن JSON صالح فقط دون أي نص خارجه ودون markdown، ويضم المفاتيح الثلاثة التالية:",
        "technical_description: فقرة عربية رسمية مفصلة تصف كيفية وقوع الحادث فنياً من بداية الخطر حتى نقطة التصادم وما أظهره كل مقطع.",
        "accident_results: نتائج الحادث في نقاط مرقمة (1- ... 2- ...)، كل نقطة في سطر مستقل.",
        "legal_opinion: خلاصة الرأي الفني والمسؤولية المرورية المستنتجة من المقاطع المرئية.",
        "لا تخترع وقائع غير ظاهرة، واستند إلى المشاهدات التالية لكل مقطع:",
    ]

    for index, clip, uploaded in uploads:
        findings_str = "، ".join(clip["findings"]) if clip["findings"] else "غير محدد"
        prompt_lines.append(
            f"- المقطع ({index + 1}) [{getattr(uploaded, 'name', 'video')}]: المصدر ({clip['source']})، "
            f"الوضوح ({clip['clarity']})، وقت اللقطة ({clip['timestamp'] or 'غير محدد'})، "
            f"المشاهدات الفنية ({findings_str})، ملاحظات الباحث ({clip['notes'] or 'لا يوجد'})."
        )

    raw = ""
    # 1) المحاولة الأولى: تحليل الفيديو مباشرة عبر Gemini Vision
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            parts = []
            remote_names = []
            temp_paths = []
            try:
                for index, clip, uploaded in uploads:
                    suffix = Path(getattr(uploaded, "name", "") or "").suffix.lower()
                    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
                        suffix = ".mp4"
                    mime = {
                        ".mp4": "video/mp4",
                        ".mov": "video/quicktime",
                        ".avi": "video/x-msvideo",
                        ".mkv": "video/x-matroska",
                    }.get(suffix, "video/mp4")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                        handle.write(uploaded.getvalue())
                        temp_path = handle.name
                    temp_paths.append(temp_path)
                    file_ref = genai.upload_file(temp_path, mime_type=mime)
                    deadline = time.time() + 180
                    state_name = getattr(getattr(file_ref, "state", None), "name", "")
                    while state_name == "PROCESSING" and time.time() < deadline:
                        time.sleep(2)
                        file_ref = genai.get_file(file_ref.name)
                        state_name = getattr(getattr(file_ref, "state", None), "name", "")
                    if state_name == "FAILED":
                        raise RuntimeError(f"تعذر معالجة المقطع {index + 1}")
                    remote_names.append(file_ref.name)
                    parts.append(file_ref)

                parts.insert(0, "\n".join(prompt_lines))
                for model_name in ("gemini-2.5-flash", "gemini-1.5-flash"):
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(parts)
                        raw = str(getattr(response, "text", "") or "").strip()
                        if raw:
                            break
                    except Exception:
                        continue
            finally:
                for path in temp_paths:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                for name in remote_names:
                    try:
                        genai.delete_file(name)
                    except Exception:
                        pass
        except Exception as error:
            st.warning(f"تعذر الاتصال بـ Gemini ({_redact_secret(error, api_key)})، جاري التحويل للمحرك البديل...")

    # 2) المحاولة البديلة: عبر Groq في حال عدم إدخال مفتاح Gemini
    if not raw:
        try:
            raw = _groq_text_fallback("\n".join(prompt_lines)) or ""
        except Exception:
            raw = ""

    if not raw:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API في القائمة الجانبية لتحليل مقاطع الفيديو بالذكاء الاصطناعي.")
        return False

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        parsed = _parse_model_json(raw)
        how_text = str(parsed.get("technical_description") or "").strip()
        results_text = str(parsed.get("accident_results") or "").strip()
        opinion_text = str(parsed.get("legal_opinion") or "").strip()
    except Exception:
        how_text = raw
        results_text = ""
        opinion_text = ""

    if not how_text and not results_text:
        st.error("لم يُرجع النموذج صياغة يمكن إدراجها.")
        return False

    if how_text:
        st.session_state.technical_description = _upsert_marked_block(
            st.session_state.get("technical_description", ""),
            how_text,
        )
        st.session_state.video_injected_text = how_text
    if results_text:
        st.session_state.accident_results = _upsert_marked_block(
            st.session_state.get("accident_results", ""),
            results_text,
        )
    if opinion_text:
        st.session_state.legal_opinion = _upsert_marked_block(
            st.session_state.get("legal_opinion", ""),
            opinion_text,
        )

    save_current_work()
    st.toast("✅ تم تحليل المقاطع بالذكاء الاصطناعي وصياغة كيفية وقوع الحادث تلقائياً", icon="🎥")
    return True


def render_video_evidence_engine():
    with st.container(key="video-evidence"):
        st.subheader("🎥 محرك القرائن الرقمية والتوثيق المرئي (يدعم تعدد المقاطع والتحليل الذكي)")
        if st.session_state.get("has_video") not in VIDEO_HAS_OPTIONS:
            st.session_state.has_video = "لا فيديو"
        has_video = st.radio(
            "هل يتوفر توثيق مرئي للحادث؟",
            options=VIDEO_HAS_OPTIONS,
            key="has_video",
            horizontal=True,
            on_change=save_current_work,
        )
        if has_video == "لا فيديو":
            st.info("ℹ️ لا يوجد تسجيل مرئي مرفق؛ يعتمد التقرير الفني والمسؤولية النظامية على الآثار المادية، والمعاينة الميدانية، وأقوال الأطراف.")
            return

        # رفع مقطع أو عدة مقاطع فيديو دفعة واحدة
        bulk_uploaded_videos = st.file_uploader(
            "📹 إرفاق مقاطع الفيديو للمعاينة والتحليل التلقائي (يمكنك اختيار مقطع واحد أو عدة مقاطع معاً MP4, MOV, AVI, MKV)",
            type=["mp4", "mov", "avi", "mkv"],
            accept_multiple_files=True,
            key="bulk_video_files",
        )

        if bulk_uploaded_videos and len(bulk_uploaded_videos) > st.session_state.get("video_clip_count", 1):
            st.session_state.video_clip_count = min(VIDEO_CLIP_MAX, len(bulk_uploaded_videos))
            _sync_video_clips(st.session_state.video_clip_count)

        current = _clamp_clip_count(st.session_state.get("video_clip_count"))
        add_col, remove_col, auto_col = st.columns([1.2, 1.2, 2])
        with add_col:
            if st.button("➕ إضافة مقطع آخر", use_container_width=True):
                st.session_state.video_clip_count = min(VIDEO_CLIP_MAX, current + 1)
                _sync_video_clips(st.session_state.video_clip_count)
                save_current_work()
                st.rerun()
        with remove_col:
            if st.button("➖ إنقاص مقطع", use_container_width=True, disabled=current <= VIDEO_CLIP_MIN):
                st.session_state.video_clip_count = max(VIDEO_CLIP_MIN, current - 1)
                _sync_video_clips(st.session_state.video_clip_count)
                for index in range(st.session_state.video_clip_count, VIDEO_CLIP_MAX):
                    for suffix in ("source", "clarity", "timestamp", "findings", "notes"):
                        st.session_state.pop(f"clip_{index}_{suffix}", None)
                    st.session_state.pop(f"clip_file_{index}", None)
                save_current_work()
                st.rerun()
        with auto_col:
            st.checkbox(
                "⚡ تحليل الفيديو تلقائياً بالذكاء الاصطناعي فور إرفاقه",
                key="auto_analyze_video",
                on_change=save_current_work,
            )

        count = st.number_input(
            "إجمالي عدد مقاطع الفيديو الموثقة",
            min_value=VIDEO_CLIP_MIN,
            max_value=VIDEO_CLIP_MAX,
            step=1,
            key="video_clip_count",
            on_change=_store_clip_fields,
        )
        clips = _sync_video_clips(int(count))
        for index, clip in enumerate(clips):
            st.session_state.setdefault(f"clip_{index}_source", clip["source"])
            st.session_state.setdefault(f"clip_{index}_clarity", clip["clarity"])
            st.session_state.setdefault(f"clip_{index}_timestamp", clip["timestamp"])
            st.session_state.setdefault(f"clip_{index}_findings", list(clip["findings"]))
            st.session_state.setdefault(f"clip_{index}_notes", clip["notes"])
            if st.session_state.get(f"clip_{index}_source") not in VIDEO_SOURCE_OPTIONS:
                st.session_state[f"clip_{index}_source"] = VIDEO_SOURCE_OPTIONS[0]
            if st.session_state.get(f"clip_{index}_clarity") not in VIDEO_CLARITY_OPTIONS:
                st.session_state[f"clip_{index}_clarity"] = VIDEO_CLARITY_OPTIONS[0]
            stored_findings = st.session_state.get(f"clip_{index}_findings")
            if not isinstance(stored_findings, list):
                stored_findings = []
            st.session_state[f"clip_{index}_findings"] = [
                item for item in stored_findings if item in VIDEO_FINDING_OPTIONS
            ]

        clip_tabs = st.tabs([f"🎬 المقطع ({index + 1})" for index in range(len(clips))])
        for index, tab in enumerate(clip_tabs):
            with tab:
                col_v1, col_v2, col_v3 = st.columns(3)
                with col_v1:
                    st.selectbox(
                        "مصدر مقطع الفيديو",
                        options=VIDEO_SOURCE_OPTIONS,
                        key=f"clip_{index}_source",
                        on_change=_store_clip_fields,
                    )
                with col_v2:
                    st.selectbox(
                        "درجة وضوح المقطع والختم الزمني",
                        options=VIDEO_CLARITY_OPTIONS,
                        key=f"clip_{index}_clarity",
                        on_change=_store_clip_fields,
                    )
                with col_v3:
                    st.text_input(
                        "وقت اللقطة في الفيديو (مثال: الدقيقة 01:24 أو 14:35:10)",
                        placeholder="الثواني 00:45 / الساعة 10:15 م",
                        key=f"clip_{index}_timestamp",
                        on_change=_store_clip_fields,
                    )
                st.multiselect(
                    "المشاهدات الفنية المستخلصة من مقطع الفيديو (تُدرج في الرأي والمسؤولية)",
                    options=VIDEO_FINDING_OPTIONS,
                    key=f"clip_{index}_findings",
                    on_change=_store_clip_fields,
                )
                st.text_area(
                    "تفاصيل إضافية رصدها باحث الحوادث في مقطع الفيديو",
                    placeholder="اكتب أي تفصيل دقيق ظهر في الفيديو (مثل: لون المركبة، حركة المشاة، حالة الطريق أثناء التصوير...)",
                    key=f"clip_{index}_notes",
                    height=80,
                    on_change=_store_clip_fields,
                )
                single_uploaded = st.file_uploader(
                    f"📹 إرفاق أو استبدال ملف الفيديو للمقطع ({index + 1}) - اختياري",
                    type=["mp4", "mov", "avi", "mkv"],
                    key=f"clip_file_{index}",
                )
                active_video_file = single_uploaded or (
                    bulk_uploaded_videos[index] if index < len(bulk_uploaded_videos) else None
                )
                if active_video_file is not None:
                    with st.expander(f"▶️ معاينة المقطع ({index + 1}): {getattr(active_video_file, 'name', '')}", expanded=False):
                        st.video(active_video_file)

        # التحليل التلقائي بالذكاء الاصطناعي فور رفع ملفات الفيديو
        current_uploads = _collect_uploaded_videos()
        if current_uploads and st.session_state.get("auto_analyze_video", True):
            upload_sig = tuple(
                f"{idx}_{getattr(f, 'name', '')}_{getattr(f, 'size', 0)}"
                for idx, _c, f in current_uploads
            )
            if st.session_state.get("last_analyzed_video_sig") != upload_sig and (
                _resolved_gemini_key() or os.getenv("GROQ_API_KEY")
            ):
                st.session_state.last_analyzed_video_sig = upload_sig
                with st.spinner("🤖 جاري التحليل التلقائي لمقاطع الفيديو بالذكاء الاصطناعي واستخلاص كيفية وقوع الحادث..."):
                    analyze_videos_with_gemini(current_uploads)

        if st.button("🤖 تحليل المقاطع بالذكاء الاصطناعي وكتابة (كيفية وقوع الحادث) تلقائياً", type="primary", use_container_width=True):
            with st.spinner("⏳ جاري رفع المقاطع وتحليل كيفية وقوع الحادث بالذكاء الاصطناعي..."):
                analyze_videos_with
