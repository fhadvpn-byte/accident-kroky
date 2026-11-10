import base64
from datetime import date, datetime
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import streamlit as st


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
    ) + (math.floor(lunar / 5670) * math.floor((43 * lunar) / 15238))
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
        {
            "الطرف": "الطرف الأول",
            "الاسم": "",
            "الهوية": "",
            "المشاركة": "",
            "الحالة": "",
            "التأهيل": "",
        },
        {
            "الطرف": "الطرف الثاني",
            "الاسم": "",
            "الهوية": "",
            "المشاركة": "",
            "الحالة": "",
            "التأهيل": "",
        },
    ]


def _blank_vehicles():
    return [
        {
            "الطرف": "الطرف الأول",
            "نوع المركبة": "",
            "رقم اللوحة": "",
            "الرقم التسلسلي": "",
            "نوع الترخيص": "",
            "التأمين": "",
        },
        {
            "الطرف": "الطرف الثاني",
            "نوع المركبة": "",
            "رقم اللوحة": "",
            "الرقم التسلسلي": "",
            "نوع الترخيص": "",
            "التأمين": "",
        },
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
    "auto_analyze_video": False,
    "show_page_numbers": False,
    "confirm_clear": False,
    "last_saved_time": "لم يتم الحفظ بعد",
}

VIDEO_MARKER_START = "[بداية القرائن المرئية]"
VIDEO_MARKER_END = "[نهاية القرائن المرئية]"
VIDEO_SOURCE_OPTIONS = [
    "كاميرا مراقبة أمنية (CCTV)",
    "كاميرا مركبة (داش كام - Dashcam)",
    "كاميرا منشأة تجارية / خاصة محيطة",
    "كاميرات الرصد الآلي / المدن الذكية",
    "تصوير هاتف محمول موثق",
]
VIDEO_CLARITY_OPTIONS = [
    "واضح وموثق بختم زمني (تاريخ ووقت)",
    "واضح الدقة (بدون ختم زمني ظاهر)",
    "متوسط الوضوح ولكن يُظهر آلية الاصطدام",
    "زاوية بعيدة تُظهر اتجاهات المركبات فقط",
]
VIDEO_FINDING_OPTIONS = [
