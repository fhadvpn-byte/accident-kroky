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

def _absorb_groq_env():
    if os.getenv("GROQ_API_KEY"):
        return
    roots = [Path("/agent"), Path("/agent").resolve().parent, Path("/home/ubuntu"), Path("/opt"), Path("/root")]
    skip = {".git", "node_modules", ".cache", "pkg", "go", ".nvm", "__pycache__", ".local"}
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            for name in filenames:
                if name != ".env" and not name.startswith(".env."):
                    continue
                path = Path(dirpath) / name
                if path in seen:
                    continue
                seen.add(path)
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key.strip() != "GROQ_API_KEY":
                        continue
                    value = value.strip().strip('"').strip("'")
                    if value:
                        os.environ["GROQ_API_KEY"] = value
                        return

def _arabic_font(size):
    for path in ARABIC_FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()

def _project_logo_path():
    root = Path(__file__).resolve().parent
    for name in ("traffic_logo.png", "logo.png", "traffic_logo.jpg", "logo.jpg", "logo.jpeg", "traffic_logo.jpeg", "logo.webp"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None

def _open_fixed_logo():
    path = _project_logo_path()
    if path is None:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except OSError:
        return None

def _save_upload_once(uploaded):
    try:
        SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    raw = uploaded.getvalue()
    digest = hashlib.sha256(raw).hexdigest()[:20]
    ext = Path(getattr(uploaded, "name", "") or "").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".jpg"
    dest = SAVED_IMAGES_DIR / f"{digest}{ext}"
    try:
        if not dest.exists():
            dest.write_bytes(raw)
    except OSError:
        return dest
    return dest

def persist_uploads(uploads):
    if not uploads:
        return []
    return [_save_upload_once(item) for item in uploads]

def list_saved_images():
    if not SAVED_IMAGES_DIR.exists():
        return []
    files = [
        path for path in SAVED_IMAGES_DIR.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    return sorted(files, key=lambda path: path.stat().st_mtime)

def _parse_model_json(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data

def _groq_vision(api_key, image_paths):
    import urllib.request
    prompt = (
        "أنت خبير تحقيق حوادث مرورية في الأمن العام السعودي. "
        "حلّل صور الحادث وأعد JSON فقط دون شرح. "
        "scenario يجب أن تكون واحدة من هذه القيم حرفياً: "
        "تجاوز واصطدام أمامي بزاوية | استدارة يوتيرن واصطدام جانبي | تصادم خلفي | تصادم تقاطع | "
        "انحراف واصطدام بجسم ثابت | انقلاب | دهس. "
        "road_type واحد من: مزدوج بجزيرة وسطية | مفرد مسارين | تقاطع | جبلي. "
        "lane_direction: يمين أو يسار لمسار الطرف الأول. "
        "vehicle1_type و vehicle1_color و vehicle2_type و vehicle2_color والألوان بصيغة #hex. "
        "collision_angle رقم من 20 إلى 70، و skid_length رقم من 40 إلى 220. "
        "how_it_happened صياغة عربية رسمية لكيفية الوقوع. "
        "keys أربع عبارات عربية لمفاتيح الكروكي. "
        "date_text و coordinates_text هما نص ختم الكاميرا أسفل الصورة (التاريخ والإحداثيات)، "
        "و camera_timestamp النص الكامل لذلك الختم، واتركها فارغة إن لم تُقرأ."
    )
    parts = [{"type": "text", "text": prompt}]
    for path in image_paths:
        image = Image.open(path)
        image.thumbnail((1280, 1280))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
        encoded = base64.b64encode(buffer.getvalue()).decode()
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
        })
    last_error = None
    for model in GROQ_VISION_MODELS:
        payload = json.dumps({
            "model": model,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": parts}],
        }).encode()
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode())
            content = body["choices"][0]["message"]["content"]
            return _parse_model_json(content)
        except Exception:
            last_error = "vision"
            continue
    raise RuntimeError(last_error or "vision")

def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

def _badge(draw, xy, number, font):
    draw.ellipse([xy[0], xy[1], xy[0] + 30, xy[1] + 30], fill="white", outline="#9b2226", width=3)
    draw.text((xy[0] + 9, xy[1] + 4), str(number), fill="#9b2226", font=font)

SKETCH_SCENARIOS = (
    "تجاوز واصطدام أمامي بزاوية",
    "استدارة يوتيرن واصطدام جانبي",
    "تصادم خلفي",
    "تصادم تقاطع",
    "انحراف واصطدام بجسم ثابت",
    "انقلاب",
    "دهس",
)
_COLOR_NAMES = {
    "أبيض": "#ffffff", "white": "#ffffff",
    "زيتوني": "#556b2f", "olive": "#556b2f",
    "أسود": "#222222", "اسود": "#222222", "black": "#222222",
    "أحمر": "#c1121f", "احمر": "#c1121f", "red": "#c1121f",
    "أزرق": "#1d4e89", "ازرق": "#1d4e89", "blue": "#1d4e89",
    "فضي": "#adb5bd", "رمادي": "#6c757d", "silver": "#adb5bd", "gray": "#6c757d",
    "أخضر": "#2d6a4f", "اخضر": "#2d6a4f", "green": "#2d6a4f",
    "بيج": "#d4a373", "بني": "#6f4e37", "برتقالي": "#e76f51", "أصفر": "#ffd60a", "اصفر": "#ffd60a",
}

def _match_scenario(value):
    text = str(value or "").strip()
    for name in SKETCH_SCENARIOS:
        if text == name or name in text or text in name:
            return name
    hints = (
        ("يوتيرن", SKETCH_SCENARIOS[1]),
        ("جانبي", SKETCH_SCENARIOS[1]),
        ("خلفي", SKETCH_SCENARIOS[2]),
        ("تقاطع", SKETCH_SCENARIOS[3]),
        ("جسم", SKETCH_SCENARIOS[4]),
        ("انحراف", SKETCH_SCENARIOS[4]),
        ("انقلاب", SKETCH_SCENARIOS[5]),
        ("دهس", SKETCH_SCENARIOS[6]),
        ("أمامي", SKETCH_SCENARIOS[0]),
        ("تجاوز", SKETCH_SCENARIOS[0]),
    )
    for hint, name in hints:
        if hint in text:
            return name
    return None

def _paint(color, fallback):
    text = str(color or "").strip()
    if text.startswith("#") and len(text) in (4, 7):
        return text
    return _COLOR_NAMES.get(text, fallback)

def _text_fill(color):
    raw = str(color or "").lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    try:
        red, green, blue = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except (ValueError, IndexError):
        return "white"
    return "#111111" if (red * 0.3 + green * 0.59 + blue * 0.11) > 165 else "white"

def _lane_is_left(lane_direction):
    text = str(lane_direction or "")
    return "يسر" in text or text.lower() in {"left", "l"}

def _clamp_number(value, low, high, fallback):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))

def _vehicle_field(data, index, field, fallback):
    direct = data.get(f"vehicle{index}_{field}") or data.get(f"car{index}_{field}")
    if direct:
        return str(direct)
    vehicles = data.get("vehicles") or []
    if index - 1 < len(vehicles) and isinstance(vehicles[index - 1], dict):
        item = vehicles[index - 1]
        if field == "type":
            return str(item.get("type") or item.get("name") or fallback)
        return str(item.get("color") or fallback)
    return fallback

def _store_analysis(data, road_name):
    st.session_state.ai_sketch = data
    scenario = _match_scenario(data.get("scenario") or data.get("collision_type"))
    if scenario:
        st.session_state.sketch_scenario = scenario
    if data.get("road_type"):
        st.session_state.sketch_road_type = str(data.get("road_type"))
    lane = str(data.get("lane_direction") or data.get("lane") or "")
    if "يسر" in lane or lane.lower() == "left":
        st.session_state.sketch_lane = "يسار"
    elif "يمن" in lane or lane.lower() == "right":
        st.session_state.sketch_lane = "يمين"
    st.session_state.sketch_v1_type = _vehicle_field(data, 1, "type", st.session_state.get("sketch_v1_type", "نيسان باترول"))
    st.session_state.sketch_v1_color = _paint(
        _vehicle_field(data, 1, "color", st.session_state.get("sketch_v1_color", "#556b2f")),
        "#556b2f",
    )
    st.session_state.sketch_v2_type = _vehicle_field(data, 2, "type", st.session_state.get("sketch_v2_type", "تويوتا هايلكس"))
    st.session_state.sketch_v2_color = _paint(
        _vehicle_field(data, 2, "color", st.session_state.get("sketch_v2_color", "#ffffff")),
        "#ffffff",
    )
    if data.get("collision_angle") is not None:
        st.session_state.collision_angle = int(_clamp_number(data.get("collision_angle"), 20, 70, 45))
    if data.get("skid_length") is not None:
        st.session_state.sketch_skid_length = int(_clamp_number(data.get("skid_length"), 40, 220, 140))
    st.session_state.sketch_swapped = False
    keys = data.get("keys") if isinstance(data.get("keys"), list) else []
    lane_label = st.session_state.get("sketch_lane", "يسار")
    fallbacks = [
        f"1 - {data.get('road_type') or road_name}",
        f"2 - {st.session_state.sketch_v1_type} في المسار {lane_label}",
        f"3 - {scenario or data.get('collision_point') or 'نقطة الاصطدام'}",
        "4 - آثار الكبح والفرامل",
    ]
    for index in range(4):
        text = str(keys[index]).strip() if index < len(keys) and str(keys[index]).strip() else fallbacks[index]
        if not text.startswith(f"{index + 1}"):
            text = f"{index + 1} - {text}"
        st.session_state[f"legend_key_{index + 1}"] = text
    how = str(data.get("how_it_happened") or "").strip()
    date_text = str(data.get("date_text") or "").strip()
    coordinates = str(data.get("coordinates_text") or "").strip()
    timestamp = str(data.get("camera_timestamp") or "").strip()
    if not date_text and timestamp:
        date_text = timestamp
    extras = []
    if date_text:
        extras.append(f"التاريخ المقروء أسفل الصورة: {date_text}")
        st.session_state.acc_date_override = date_text
    if coordinates:
        extras.append(f"الإحداثيات المقروءة أسفل الصورة: {coordinates}")
        st.session_state.acc_loc_override = coordinates
    articles = data.get("traffic_law_articles") or []
    if articles:
        extras.append("مواد نظام المرور: " + "، ".join(str(item) for item in articles))
    narrative = "\n".join(part for part in [how, *extras] if part)
    if narrative:
        st.session_state.acc_how_override = narrative

def _car_sprite(label, color, kind_name):
    text = str(kind_name or "")
    pickup = any(word in text for word in ("هايل", "وانيت", "غمار", "بيك", "داتسن"))
    suv = any(word in text for word in ("باترول", "رباعي", "جيب"))
    sprite = Image.new("RGBA", (96, 158), (0, 0, 0, 0))
    pen = ImageDraw.Draw(sprite)
    pen.rounded_rectangle([18, 8, 78, 148], radius=12, fill=color, outline="#222222", width=2)
    pen.polygon([(26, 16), (70, 16), (64, 42), (32, 42)], fill="#d7ecf5", outline="#243028")
    if pickup:
        pen.rectangle([24, 102, 72, 140], fill="#d7ecf5", outline="#333333")
        if "هايل" in text:
            pen.rectangle([18, 48, 26, 140], fill="#d00000")
            pen.rectangle([70, 48, 78, 140], fill="#d00000")
    if suv:
        pen.ellipse([36, 116, 60, 142], fill="#111111")
    for tire in ((2, 24), (78, 24), (2, 108), (78, 108)):
        pen.rounded_rectangle([tire[0], tire[1], tire[0] + 16, tire[1] + 30], radius=3, fill="#111111")
    pen.text((22, 62), str(label)[:8], fill=_text_fill(color), font=_arabic_font(14))
    return sprite

def _rolled_sprite(label, color):
    sprite = Image.new("RGBA", (176, 84), (0, 0, 0, 0))
    pen = ImageDraw.Draw(sprite)
    pen.rounded_rectangle([8, 34, 166, 76], radius=12, fill=color, outline="#222222", width=2)
    for x in (22, 58, 100, 136):
        pen.ellipse([x, 6, x + 24, 30], fill="#111111", outline="#333333")
    pen.text((48, 46), str(label)[:8], fill=_text_fill(color), font=_arabic_font(14))
    return sprite

def _road_x(y, frac):
    t = min(1.0, max(0.0, (y - 36) / (830 - 36)))
    left = 250 + (130 - 250) * t
    right = 470 + (590 - 470) * t
    return left + (right - left) * frac

def _rotated_anchor(size, anchor, angle):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    mark = ImageDraw.Draw(layer)
    x, y = anchor
    mark.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 0, 0, 255))
    turned = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    width, height = turned.size
    total_x = total_y = count = 0
    for index, pixel in enumerate(turned.getdata()):
        if pixel[0] > 200 and pixel[3] > 120 and pixel[1] < 90:
            total_x += index % width
            total_y += index // width
            count += 1
    if not count:
        return turned.size, (width / 2, height / 2)
    return turned.size, (total_x / count, total_y / count)

def _place_front(base, sprite, front_xy, rotation):
    rotation = float(rotation or 0)
    anchor = (sprite.size[0] / 2, 14)
    if abs(rotation) < 0.1:
        base.paste(sprite, (int(front_xy[0] - anchor[0]), int(front_xy[1] - anchor[1])), sprite)
        return
    _, (ax, ay) = _rotated_anchor(sprite.size, anchor, rotation)
    turned = sprite.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
    base.paste(turned, (int(front_xy[0] - ax), int(front_xy[1] - ay)), turned)

def _impact(draw, x, y, radius=68):
    box = [x - radius, y - radius, x + radius, y + radius]
    for start in range(0, 360, 28):
        draw.arc(box, start, start + 16, fill="#d00000", width=4)
    for dx, dy, color in (
        (-16, 6, "#adb5bd"), (8, 14, "#f8f9fa"), (18, -4, "#4cc9f0"),
        (-6, 22, "#6c757d"), (16, 24, "#dee2e6"), (-22, 18, "#90e0ef"),
    ):
        draw.ellipse([x + dx, y + dy, x + dx + 8, y + dy + 8], fill=color, outline="#495057")

def _skid(draw, x, y, length, dx=0):
    end_y = min(820, y + length)
    draw.line([(x, y), (x + dx, end_y)], fill="#111111", width=5)
    draw.line([(x + 34, y), (x + 34 + dx, end_y)], fill="#111111", width=5)

def _compass(draw, font):
    draw.rectangle([600, 28, 690, 112], fill="white", outline="#1b4332", width=2)
    draw.polygon([(645, 36), (630, 68), (660, 68)], fill="#1b4332")
    draw.text((620, 74), "شمال", fill="#1b4332", font=font)

def _person(draw, x, y):
    draw.ellipse([x - 9, y - 30, x + 9, y - 12], fill="#f4a261", outline="#222222", width=2)
    draw.line([(x, y - 12), (x, y + 16)], fill="#222222", width=4)
    draw.line([(x - 14, y), (x + 14, y)], fill="#222222", width=4)
    draw.line([(x, y + 16), (x - 12, y + 38)], fill="#222222", width=4)
    draw.line([(x, y + 16), (x + 12, y + 38)], fill="#222222", width=4)

def _open_board(road_type):
    mountainous = "جبل" in str(road_type)
    img = Image.new("RGB", (720, 860), "#d8f3dc" if mountainous else "#e9ecef")
    draw = ImageDraw.Draw(img)
    if mountainous:
        draw.polygon([(0, 0), (210, 0), (150, 210), (0, 300)], fill="#1b4332")
        draw.polygon([(0, 180), (170, 250), (80, 520), (0, 600)], fill="#2d6a4f")
        draw.polygon([(0, 480), (150, 620), (40, 860), (0, 860)], fill="#40916c")
        draw.polygon([(720, 0), (500, 0), (560, 230), (720, 340)], fill="#1b4332")
        draw.polygon([(720, 200), (540, 280), (620, 560), (720, 640)], fill="#2d6a4f")
        draw.polygon([(720, 500), (560, 640), (680, 860), (720, 860)], fill="#40916c")
    else:
        draw.rectangle([0, 0, 720, 860], fill="#c7d0c3")
    return img, draw

def _straight_road(draw, road_type):
    draw.polygon([(250, 36), (470, 36), (590, 830), (130, 830)], fill="#3a3f45")
    left_top, left_bottom = (250, 36), (130, 830)
    right_top, right_bottom = (470, 36), (590, 830)
    draw.line([_lerp(left_top, left_bottom, 0.02), _lerp(left_top, left_bottom, 0.98)], fill="#ffd60a", width=5)
    draw.line([_lerp(right_top, right_bottom, 0.02), _lerp(right_top, right_bottom, 0.98)], fill="#ffd60a", width=5)
    median = "جزيرة" in str(road_type) or "مزدوج" in str(road_type)
    if median:
        island = [
            _lerp(left_top, right_top, 0.42), _lerp(left_top, right_top, 0.58),
            _lerp(left_bottom, right_bottom, 0.58), _lerp(left_bottom, right_bottom, 0.42),
        ]
        draw.polygon(island, fill="#2d6a4f")
        for frac in (0.40, 0.60):
            draw.line([_lerp(left_top, right_top, frac), _lerp(left_bottom, right_bottom, frac)], fill="white", width=4)
    else:
        for frac in (0.47, 0.53):
            draw.line([_lerp(left_top, right_top, frac), _lerp(left_bottom, right_bottom, frac)], fill="white", width=4)

def _cross_road(draw):
    draw.rectangle([210, 20, 510, 840], fill="#3a3f45")
    draw.rectangle([20, 330, 700, 530], fill="#3a3f45")
    draw.rectangle([214, 20, 228, 330], fill="#ffd60a")
    draw.rectangle([492, 20, 506, 330], fill="#ffd60a")
    draw.rectangle([214, 530, 228, 840], fill="#ffd60a")
    draw.rectangle([492, 530, 506, 840], fill="#ffd60a")
    draw.rectangle([20, 334, 210, 348], fill="#ffd60a")
    draw.rectangle([510, 334, 700, 348], fill="#ffd60a")
    draw.rectangle([20, 512, 210, 526], fill="#ffd60a")
    draw.rectangle([510, 512, 700, 526], fill="#ffd60a")
    for x in range(250, 470, 28):
        draw.line([(x, 40), (x + 14, 40)], fill="white", width=3)
        draw.line([(x, 820), (x + 14, 820)], fill="white", width=3)
    for y in range(360, 510, 28):
        draw.line([(40, y), (40, y + 14)], fill="white", width=3)
        draw.line([(680, y), (680, y + 14)], fill="white", width=3)

def _lane_x(y, left_lane, primary):
    if left_lane:
        frac = 0.27 if primary else 0.73
    else:
        frac = 0.73 if primary else 0.27
    return _road_x(y, frac)

def generate_ai_vision_sketch(
    scenario,
    road_type,
    lane_direction,
    vehicle1_type,
    vehicle1_color,
    vehicle2_type,
    vehicle2_color,
    collision_angle,
    skid_length,
):
    font = _arabic_font(18)
    name = _match_scenario(scenario) or SKETCH_SCENARIOS[0]
    angle = _clamp_number(collision_angle, 15, 80, 45)
    skid = _clamp_number(skid_length, 40, 220, 140)
    left_lane = _lane_is_left(lane_direction)
    color1 = _paint(vehicle1_color, "#556b2f")
    color2 = _paint(vehicle2_color, "#ffffff")
    car1 = _car_sprite(vehicle1_type, color1, vehicle1_type)
    car2 = _car_sprite(vehicle2_type, color2, vehicle2_type)
    img, draw = _open_board(road_type)
    if name == "تصادم تقاطع":
        _cross_road(draw)
        contact = (360, 430)
        _place_front(img, car1, (contact[0] - 70, contact[1] + 20), 0)
        side = -90 if left_lane else 90
        _place_front(img, car2, (contact[0] + (80 if left_lane else -80), contact[1]), side + (angle - 45) * 0.3)
        _skid(draw, contact[0] - 88, contact[1] + 150, skid, -8)
        _impact(draw, contact[0], contact[1])
        _badge(draw, (250, 80), 1, font)
        _badge(draw, (250, 620), 2, font)
        _badge(draw, (430, 360), 3, font)
        _badge(draw, (250, 740), 4, font)
    else:
        _straight_road(draw, road_type)
        if name == "استدارة يوتيرن واصطدام جانبي":
            contact_y = 470
            contact_x = _lane_x(contact_y, left_lane, True)
            turn = (70 + (angle - 45)) if left_lane else -(70 + (angle - 45))
            _place_front(img, car2, (contact_x, contact_y - 10), turn)
            _place_front(img, car1, (contact_x, contact_y + 78), 0)
            arc_box = [contact_x - 40, 180, contact_x + 220, 460] if left_lane else [contact_x - 220, 180, contact_x + 40, 460]
            draw.arc(arc_box, 200 if left_lane else 20, 330 if left_lane else 150, fill="#f4a261", width=5)
            _skid(draw, contact_x - 18, contact_y + 200, skid)
            _impact(draw, contact_x, contact_y + 20, 60)
            _badge(draw, (int(_road_x(100, 0.2)), 80), 1, font)
            _badge(draw, (int(contact_x - 70), contact_y + 120), 2, font)
            _badge(draw, (int(contact_x + 50), contact_y - 40), 3, font)
            _badge(draw, (int(contact_x - 20), min(790, contact_y + 200 + skid * 0.4)), 4, font)
        elif name == "تصادم خلفي":
            lane_x = _lane_x(420, left_lane, True)
            _place_front(img, car2, (lane_x, 300), 0)
            _place_front(img, car1, (lane_x, 470), (angle - 45) * 0.15)
            _skid(draw, lane_x - 18, 610, skid)
            _impact(draw, lane_x, 455, 48)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(lane_x + 60), 330), 2, font)
            _badge(draw, (int(lane_x - 80), 430), 3, font)
            _badge(draw, (int(lane_x + 50), min(790, 640 + skid * 0.35)), 4, font)
        elif name == "انحراف واصطدام بجسم ثابت":
            contact_y = 430
            contact_x = _road_x(contact_y, 0.08 if left_lane else 0.92)
            barrier = (int(contact_x - 30), contact_y - 20)
            draw.rectangle([barrier[0], barrier[1], barrier[0] + 42, barrier[1] + 86], fill="#6c757d", outline="#222222", width=2)
            draw.line([(barrier[0] + 6, barrier[1] + 10), (barrier[0] + 36, barrier[1] + 74)], fill="#ffd60a", width=4)
            draw.line([(barrier[0] + 36, barrier[1] + 10), (barrier[0] + 6, barrier[1] + 74)], fill="#ffd60a", width=4)
            yaw = -angle if left_lane else angle
            _place_front(img, car1, (contact_x + (20 if left_lane else -20), contact_y + 30), yaw)
            other_x = _lane_x(260, left_lane, False)
            _place_front(img, car2, (other_x, 230), 180)
            _skid(draw, _lane_x(560, left_lane, True), 560, skid, -40 if left_lane else 40)
            _impact(draw, contact_x, contact_y + 10, 54)
            _badge(draw, (int(_road_x(90, 0.2)), 70), 1, font)
            _badge(draw, (int(other_x - 40), 250), 2, font)
            _badge(draw, (barrier[0] - 10, barrier[1] + 90), 3, font)
            _badge(draw, (int(_lane_x(700, left_lane, True)), 730), 4, font)
        elif name == "انقلاب":
            lane_x = _lane_x(480, left_lane, True)
            rolled = _rolled_sprite(vehicle1_type, color1)
            img.paste(rolled, (int(lane_x - 90), 390), rolled)
            other_x = _lane_x(300, left_lane, False)
            _place_front(img, car2, (other_x, 260), 180)
            _skid(draw, lane_x - 10, 500, skid, 20 if left_lane else -20)
            _impact(draw, lane_x, 430, 58)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(other_x + 40), 280), 2, font)
            _badge(draw, (int(lane_x + 70), 400), 3, font)
            _badge(draw, (int(lane_x - 50), min(790, 560 + skid * 0.3)), 4, font)
        elif name == "دهس":
            lane_x = _lane_x(430, left_lane, True)
            zebra_y = 390
            x0 = _road_x(zebra_y, 0.08)
            x1 = _road_x(zebra_y, 0.92)
            step = x0
            while step < x1:
                draw.rectangle([step, zebra_y, step + 16, zebra_y + 46], fill="white")
                step += 30
            _person(draw, lane_x, zebra_y + 8)
            _place_front(img, car1, (lane_x, zebra_y + 70), 0)
            shoulder_x = _road_x(260, 0.04 if left_lane else 0.96)
            _place_front(img, car2, (shoulder_x, 240), 90 if left_lane else -90)
            _skid(draw, lane_x - 16, zebra_y + 200, skid)
            _impact(draw, lane_x, zebra_y + 16, 46)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(lane_x + 56), zebra_y + 90), 2, font)
            _badge(draw, (int(lane_x - 70), zebra_y - 10), 3, font)
            _badge(draw, (int(lane_x + 40), min(790, zebra_y + 230 + skid * 0.25)), 4, font)
        else:
            contact_y = 450
            contact_x = _lane_x(contact_y, left_lane, True)
            _place_front(img, car1, (contact_x, contact_y), 0)
            yaw = -(180 - angle) if left_lane else (180 - angle)
            _place_front(img, car2, (contact_x, contact_y - 6), yaw)
            _skid(draw, contact_x - 18, contact_y + 150, skid)
            _impact(draw, contact_x, contact_y)
            _badge(draw, (int(_road_x(90, 0.18)), 70), 1, font)
            _badge(draw, (int(contact_x - 70), contact_y + 80), 2, font)
            _badge(draw, (int(contact_x + 46), contact_y - 36), 3, font)
            _badge(draw, (int(contact_x + 10), min(790, contact_y + 170 + skid * 0.25)), 4, font)
    _compass(draw, font)
    return img.convert("RGB")

_absorb_groq_env()
try:
    SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
_bayyinah_logo_path = Path(__file__).resolve().parent / "bayyinah_logo.png"

def _bayyinah_logo_ready():
    if not _bayyinah_logo_path.is_file():
        return False
    try:
        with Image.open(_bayyinah_logo_path) as logo_image:
            logo_image.verify()
        return True
    except OSError:
        return False

st.set_page_config(
    page_title="منظومة البَيِّنَةُ الذكية للحوادث المرورية",
    page_icon=str(_bayyinah_logo_path) if _bayyinah_logo_ready() else "🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)
# تنسيق واجهة البرنامج باللون الأخضر الرسمي
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        direction: rtl;
        text-align: right;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    section[data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {
        background: #0a192f !important;
        color: #e2eafc;
    }
    [data-testid="stHeader"] {
        background: #0a192f !important;
    }
    h1, h2, h3,
    [data-testid="stHeading"],
    [data-testid="stHeading"] h1,
    [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3,
    [data-testid="stHeading"] span,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stCaptionContainer"] p {
        color: #e2eafc !important;
        font-family: 'Tajawal', sans-serif;
    }
    .glow-container,
    [class*="st-key-glow"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(0, 242, 254, 0.45);
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.28), inset 0 0 12px rgba(79, 172, 254, 0.08);
    }
    .bayyinah-hero {
        direction: rtl;
        display: flex;
        align-items: center;
        gap: 22px;
        background:
            linear-gradient(145deg, #071422 0%, #0a192f 58%, #102a43 100%) padding-box,
            linear-gradient(120deg, #00f2fe, #4facfe) border-box;
        border: 2px solid transparent;
        border-radius: 18px;
        padding: 18px 22px;
        margin: 4px 0 16px;
        box-shadow: 0 0 22px rgba(0, 242, 254, 0.45), 0 0 48px rgba(79, 172, 254, 0.28);
    }
    .bayyinah-logo-ring {
        width: 112px;
        height: 112px;
        flex: 0 0 112px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        line-height: 1.25;
        font-weight: 700;
        font-size: 14px;
        color: #e8f7ff;
        background: radial-gradient(circle at 40% 35%, #16365c, #071422 72%);
        border: 2px solid #4facfe;
        box-shadow: 0 0 16px #00f2fe, 0 0 34px rgba(79, 172, 254, 0.75);
    }
    .bayyinah-logo-ring img {
        width: 94px;
        height: 94px;
        border-radius: 50%;
        object-fit: cover;
    }
    .logo-fallback { display: none; font-weight: 700; line-height: 1.25; }
    .bayyinah-logo-ring.show-fallback .logo-fallback { display: block; }
    .bh-word {
        color: #ffffff;
        font-size: 34px;
        font-weight: 700;
        letter-spacing: 1px;
        text-shadow: 0 0 14px rgba(0, 242, 254, 0.85);
        line-height: 1.1;
    }
    .bh-1 { color: #00f2fe; font-size: 22px; font-weight: 700; text-shadow: 0 0 12px rgba(0, 242, 254, 0.75); }
    .bh-2 { color: #ffffff; font-size: 18px; font-weight: 700; letter-spacing: 3px; margin-top: 2px; }
    .bh-3 { color: #e2eafc; font-size: 22px; font-weight: 700; margin-top: 2px; }
    .bh-4 { color: #b7d4f0; font-size: 15px; font-weight: 700; margin-top: 4px; }
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    [data-testid="stDataEditor"],
    [data-testid="stFileUploader"] section,
    [data-testid="stAlert"],
    iframe[title="st.iframe"] {
        border-radius: 14px !important;
        box-shadow: 0 0 16px rgba(0, 242, 254, 0.22) !important;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input {
        background: #112240 !important;
        color: #f8f9fa !important;
        border-radius: 10px !important;
        border: 1px solid rgba(79, 172, 254, 0.55) !important;
        box-shadow: 0 0 10px rgba(0, 242, 254, 0.12);
    }
    [data-baseweb="select"] > div {
        background: #112240 !important;
        color: #f8f9fa !important;
        border-radius: 10px !important;
        border-color: rgba(79, 172, 254, 0.55) !important;
    }
    .stTabs [data-baseweb="tab-list"],
    .stTabs [role="tablist"] {
        gap: 8px;
        background: transparent;
        flex-wrap: wrap !important;
        overflow: visible !important;
    }
    .stTabs [data-baseweb="tab"],
    .stTabs [data-testid="stTab"] {
        background: #12263f !important;
        color: #d6f4ff !important;
        border-radius: 10px !important;
        padding: 10px 16px;
        font-weight: 500 !important;
        border: 1px solid rgba(0, 242, 254, 0.45) !important;
        box-shadow: 0 0 10px rgba(79, 172, 254, 0.28);
    }
    .stTabs [data-testid="stTab"]:hover {
        background: #1d4f86 !important;
        color: #ffffff !important;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.7);
    }
    .stTabs [data-testid="stTab"]:hover {
        transform: scale(1.04);
    }
    .stTabs [aria-selected="true"],
    .stTabs [data-testid="stTab"][aria-selected="true"] {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #0a192f !important;
        font-weight: 700 !important;
        border-color: #00f2fe !important;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.8);
    }
    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span,
    .stTabs [aria-selected="true"] div {
        color: #0a192f !important;
        font-weight: 700 !important;
    }
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]):hover p,
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]):hover span {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]) p,
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]) span,
    .stTabs [data-testid="stTab"]:not([aria-selected="true"]) div {
        color: #d6f4ff !important;
        font-weight: 500 !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #00f2fe !important; }
    .stTabs [data-baseweb="tab-border"] { background-color: rgba(79, 172, 254, 0.35) !important; }
    div.stButton > button,
    div.stDownloadButton > button,
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #0a192f !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-family: 'Tajawal', sans-serif !important;
        box-shadow: 0 0 14px rgba(0, 242, 254, 0.4);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover,
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(90deg, #00f2fe, #4facfe) !important;
        color: #0a192f !important;
        transform: scale(1.05);
        box-shadow: 0 0 22px rgba(0, 242, 254, 0.9);
    }
    div.stButton > button p,
    div.stDownloadButton > button p,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-primary"] p {
        color: #0a192f !important;
    }
    [class*="st-key-adopt-hidden"],
    [class*="st-key-adopt_sketch_form"],
    [class*="st-key-adopted_sketch_data"],
    [class*="st-key-adopt_submit"],
    [data-testid="stForm"]:has([class*="st-key-adopted_sketch_data"]) {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        border: 0 !important;
        visibility: hidden !important;
    }
    iframe[title="st.iframe"] {
        background: #0d2137 !important;
        border-radius: 14px;
        border: 1px solid rgba(0, 242, 254, 0.35) !important;
    }
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarHeader"] button,
    button[kind="headerNoPadding"] {
        background-color: rgba(0, 229, 255, 0.18) !important;
        border: 2px solid #00e5ff !important;
        border-radius: 10px !important;
        box-shadow: 0 0 15px #00e5ff, 0 0 25px rgba(0, 229, 255, 0.6), inset 0 0 8px rgba(0, 229, 255, 0.45) !important;
        z-index: 999999 !important;
    }
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="stExpandSidebarButton"] svg,
    [data-testid="stSidebarCollapseButton"] button svg,
    [data-testid="stSidebarHeader"] button svg,
    button[kind="headerNoPadding"] svg {
        fill: #00e5ff !important;
        stroke: #00e5ff !important;
        width: 24px !important;
        height: 24px !important;
    }
    @media screen and (max-width: 768px) {
        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .main,
        .block-container,
        .main .block-container {
            margin-left: 0 !important;
            margin-right: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            transform: none !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }
        .main .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 2rem !important;
        }
        [data-testid="stSidebar"][aria-expanded="false"],
        [data-testid="stSidebar"][data-collapsed="true"] {
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            box-shadow: none !important;
            transform: none !important;
            overflow: hidden !important;
        }
        [data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarResizeHandle"] {
            display: none !important;
            width: 0 !important;
            background: none !important;
            box-shadow: none !important;
        }
        iframe {
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }
        .stTabs [data-baseweb="tab-list"],
        .stTabs [role="tablist"] {
            flex-wrap: wrap !important;
        }
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 1.1rem !important; }
        h3 { font-size: 1rem !important; }
    }
    @media print {
        section[data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stSidebarCollapsedControl"],
        .stButton, .stDownloadButton, button {
            display: none !important;
        }
    }
</style>
""", unsafe_allow_html=True)
if 'parties' not in st.session_state:
    st.session_state.parties = [
        {"الطرف": "الطرف الأول", "الاسم": "", "الهوية": "", "المشاركة": "سائق", "الحالة": "مصاب", "التأهيل": "مؤهل"},
        {"الطرف": "الطرف الثاني", "الاسم": "", "الهوية": "", "المشاركة": "سائق", "الحالة": "متوفي", "التأهيل": "مؤهل"}
    ]
if 'vehicles' not in st.session_state:
    st.session_state.vehicles = [
        {"الطرف": "الطرف الأول", "نوع المركبة": "", "رقم اللوحة": "", "الرقم التسلسلي": "", "نوع الترخيص": "خصوصي", "التأمين": "مؤمنة"},
        {"الطرف": "الطرف الثاني", "نوع المركبة": "", "رقم اللوحة": "", "الرقم التسلسلي": "", "نوع الترخيص": "خصوصي", "التأمين": "غير مؤمنة"}
    ]
with st.sidebar:
    if _bayyinah_logo_ready():
        try:
            st.image(str(_bayyinah_logo_path), width=148)
        except OSError:
            pass
    st.markdown("### بَيِّنَةُ الذكي للحوادث")
    with st.container(key="glow-dept"):
        st.header("⚙️ الإعدادات الثابتة للقسم")
        dept_region = st.text_input("إدارة مرور منطقة", "إدارة مرور منطقة جازان")
        dept_branch = st.text_input("القسم / الشعبة", "قسم مرور محافظة العارضة")
    with st.container(key="glow-officers"):
        st.subheader("👮‍♂️ بيانات معدي التقرير (الصفحة 3)")
        officer_1_name = st.text_input("اسم مباشر/إجراء الحوادث", "")
        officer_1_rank = st.text_input("رتبة مباشر الحوادث", "رقيب")
        officer_2_name = st.text_input("اسم مشرف الحوادث", "فهد أحمد مجرشي")
        officer_2_rank = st.text_input("رتبة مشرف الحوادث", "رقيب أول")
        manager_name = st.text_input("اسم مدير القسم / الشعبة", "")
        manager_rank = st.text_input("رتبة المدير", "مقدم")
app_logo_b64 = ""
if _bayyinah_logo_ready():
    try:
        with Image.open(_bayyinah_logo_path) as app_logo:
            _hero_buf = io.BytesIO()
            app_logo.save(_hero_buf, format="PNG")
            app_logo_b64 = base64.b64encode(_hero_buf.getvalue()).decode()
    except OSError:
        app_logo_b64 = ""
if app_logo_b64:
    _hero_ring = f'<div class="bayyinah-logo-ring"><img src="data:image/png;base64,{app_logo_b64}" alt="بَيِّنَة"/></div>'
else:
    _hero_ring = '<div class="bayyinah-logo-ring"></div>'
st.html(f"""
<div class="glow-container bayyinah-hero">
  {_hero_ring}
  <div>
    <div class="bh-word">بَيِّنَة</div>
    <div class="bh-1">منظومة الذكاء الاصطناعي السيادي</div>
    <div class="bh-2">VISION 2030</div>
    <div class="bh-3">بَيِّنَة الذكي للحوادث المرورية</div>
    <div class="bh-4">منصة التحليل</div>
  </div>
</div>
""", unsafe_allow_javascript=False)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ الصفحة (1): البيانات والأطراف",
    "2️⃣ الصفحة (2): الوصف ومواد المرور (حسم)",
    "3️⃣ الصفحة (3): الإجراءات والتوقيعات",
    "4️⃣ الصفحة (4): استوديو الكروكي",
    "5️⃣ الملحق والطباعة النهائية (PDF)"
])
with tab1:
    st.subheader("معلومات الحادث الأساسية")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        acc_num = st.text_input("رقم الحادث", "6004894074")
        if "acc_date_value" not in st.session_state:
            st.session_state.acc_date_value = "1448/04/21"
        if st.session_state.get("acc_date_override"):
            st.session_state.acc_date_value = st.session_state.pop("acc_date_override")
        acc_date = st.text_input("تاريخ الحادث (هجري)", key="acc_date_value")
    with col2:
        acc_time = st.text_input("الوقت", "4:50 مساءً")
        if "acc_loc_value" not in st.session_state:
            st.session_state.acc_loc_value = "العارضة"
        if st.session_state.get("acc_loc_override"):
            st.session_state.acc_loc_value = st.session_state.pop("acc_loc_override")
        acc_loc = st.text_input("موقع الحادث", key="acc_loc_value")
    with col3:
        acc_type = st.selectbox("نوع الحادث", ["تصادم مركبتين", "دهس مشاة", "انقلاب", "تصادم متعدد", "اصطدام بجسم ثابت"])
        acc_weather = st.selectbox("الطقس", ["صحو", "غائم", "ممطر", "غبار / عوالق ترابية", "ضباب"])
    with col4:
        acc_injuries = st.number_input("عدد الإصابات", min_value=0, value=1)
        acc_deaths = st.number_input("عدد الوفيات", min_value=0, value=1)
    
    acc_cause = st.text_input("سبب الحادث الرئيسي (المختصر)", "عدم إعطاء الأفضلية والشروع في الدوران")
    st.divider()
    st.subheader("جدول معلومات أطراف الحادث")
    parties_df = st.data_editor(
        pd.DataFrame(st.session_state.parties),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "المشاركة": st.column_config.SelectboxColumn("نوع المشاركة", options=["سائق", "راكب", "مشاة"]),
            "الحالة": st.column_config.SelectboxColumn("الحالة الصحية", options=["سليم", "مصاب", "متوفي"]),
        }
    )
    st.divider()
    st.subheader("جدول معلومات المركبات")
    vehicles_df = st.data_editor(
        pd.DataFrame(st.session_state.vehicles),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "نوع الترخيص": st.column_config.SelectboxColumn("نوع الترخيص", options=["خصوصي", "نقل خاص", "نقل عام", "دراجة آلية"]),
            "التأمين": st.column_config.SelectboxColumn("التأمين", options=["مؤمنة", "غير مؤمنة"]),
        }
    )
with tab2:
    st.subheader("📚 محرك المواد النظامية وفروعها (من المادة 50 إلى 62 - قاعدة حسم)")
    
    traffic_law_dict = {
        "المادة (50/9/5/1) - تجاوز السرعة داخل الأحياء": "عدم التقيد بالسرعة النظامية المقررة داخل الأحياء السكنية (أكثر من 50 كم/س).",
        "المادة (50/2/3) - عدم خفض السرعة": "عدم تخفيف السرعة عند الاقتراب من التقاطعات والمنحنيات وأماكن المشاة.",
        "المادة (52/1) - التجاوز الخاطئ": "التجاوز الخاطئ من الأكتان أو الجهة اليمنى الممنوعة.",
        "المادة (55/1) - عدم إعطاء الأفضلية": "عدم إعطاء الأفضلية للمركبات القادمة ذات الأولوية في التقاطعات والميادين.",
        "المادة (55/7/3) - عبور المشاة الخاطئ": "عبور المشاة للطريق من غير الأماكن المخصصة وعدم إعطاء الأفضلية للمركبات.",
        "المادة (60/2/1) - الإهمال وقلة الاحتراز": "عدم أخذ الحيطة والحذر والإهمال وقلة الاحتراز أثناء القيادة.",
        "المادة (50/2/24/4) - الشروع في الدوران (يوتيرن)": "قلة الاحتراز المتمثل في الشروع في الدوران للخلف قبل التأكد من خلو الطريق.",
        "جدول (4) فقرة (14) - أفضلية الدوران": "عدم إعطاء الأفضلية عند إجراء الدوران للمركبات القادمة من الاتجاهات الأخرى.",
        "المادة (61/1) - الوقوف المباغت": "الوقوف الخاطئ أو التوقف المفاجئ دون إعطاء تنبيه كافٍ للمخلفات خلفه.",
        "المادة (62/2) - الرجوع للخلف غير الآمن": "الرجوع بالمركبة للخلف دون التأكد من خلو الطريق وتأمين حركة المرور."
    }
    selected_law_keys = st.multiselect(
        "اختر المواد النظامية وفروعها المطبقة على الحادث:",
        options=list(traffic_law_dict.keys()),
        default=["المادة (50/2/24/4) - الشروع في الدوران (يوتيرن)", "جدول (4) فقرة (14) - أفضلية الدوران"]
    )
    laws_list_for_report = []
    for key in selected_law_keys:
        desc = traffic_law_dict[key]
        laws_list_for_report.append(f"{key}: {desc}")
    default_results = "1- وفاة السائق الثاني ومرافقيه\n2- إصابة السائق الأول\n3- تلفيات جسيمة بالمركبات"
    acc_results = st.text_area("نتائج الحادث (نقاط مرقمة)", value=default_results, height=90)
    
    default_desc = (
        "بالوصول لموقع الحادث وتتبع الآثار على الطبيعة اتضح لنا أن المركبة الأولى كانت قادمة باتجاه السير النظامي "
        "والمركبة الثانية قامت بالشروع في الاستدارة والدوران للخلف (يوتيرن) دون التأكد من خلو الطريق، "
        "مما أدى لاصطدام مقدمة الأولى بالجانب الأيمن للثانية، ونقطة الاصطدام بمسار المركبة الأولى الصحيح."
    )
    if "acc_how_text" not in st.session_state:
        st.session_state.acc_how_text = default_desc
    if st.session_state.get("acc_how_override"):
        st.session_state.acc_how_text = st.session_state.pop("acc_how_override")
    acc_how = st.text_area("كيفية وقوع الحادث (الصياغة الفنية الدقيقة)", key="acc_how_text", height=120)
    st.divider()
    st.subheader("الرأي والمسؤولية النظامية")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        resp_summary = st.text_input("صدر قرار الإدانة", value="تقع مسؤولية الحادث بنسبة ١٠٠٪ على الطرف الثاني")
    with col_r2:
        custom_laws = st.text_area("المواد النظامية المعتمدة للتقرير:", value="\n".join(laws_list_for_report), height=120)
with tab3:
    st.subheader("الحقوق والإجراءات المتخذة")
    rights_status = st.selectbox("الحقوق الخاصة والعامة", ["لا زالت قائمة", "انتهت بالتنازل", "محالة للمحكمة المختصة"])
    
    default_actions = [
        "تم مباشرة الحادث فور تلقي البلاغ",
        "تم استدعاء الجهات المساندة لاتخاذ اللازم",
        "تم متابعة نقل الجثامين والمصابين للمستشفى",
        "تم تفتيش المركبات بشكل دقيق",
        "تم تسجيل الحادث وتصويره"
    ]
    selected_actions = st.multiselect("الإجراءات المتخذة:", default_actions, default=default_actions)
    extra_action = st.text_input("إجراء إضافي خاص:")
    if extra_action:
        selected_actions.append(extra_action)
with tab4:
    st.subheader("🎨 محرر الكروكي التفاعلي (Fabric.js)")
    _fabric_html = r'''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #0a192f; color: #e2eafc; font-family: Tajawal, sans-serif; }
  html, body { overflow-x: hidden; max-width: 100%; }
  .editor { background: #0b1220; border: 1px solid rgba(43, 147, 72, 0.65); border-radius: 14px; overflow: hidden; max-width: 100%; box-shadow: 0 0 16px rgba(0, 242, 254, 0.18); }
  header { background: #2b9348; color: #fff; display: flex; gap: 8px; align-items: center; padding: 8px 12px; flex-wrap: wrap; }
  header strong { margin-left: auto; font-size: 16px; color: #fff; }
  header button { background: #ffffff; color: #14301c; border: 0; border-radius: 8px; padding: 6px 10px; font-size: 16px; cursor: pointer; font-family: inherit; font-weight: 700; }
  header button:hover { transform: scale(1.06); }
  .stage { display: flex; justify-content: center; padding: 12px 8px 4px; background: #0b1220; }
  .canvas-wrap { background: #111; border: 1px solid #2b9348; border-radius: 8px; width: 600px; height: 550px; max-width: 100%; overflow: hidden; }
  .canvas-wrap .canvas-container,
  .canvas-wrap canvas { display: block !important; visibility: visible !important; opacity: 1 !important; max-width: 100%; }
  .label { margin: 6px 12px 2px; color: #e2eafc; font-size: 13px; font-weight: 700; }
  .carousel, .palette { display: flex; flex-wrap: wrap; gap: 5px; overflow: visible; padding: 4px 8px 8px; }
  .carousel button, .palette button { background: #f8f9fa; color: #0a192f; border: 2px solid #2b9348; border-radius: 12px; padding: 8px 12px; cursor: pointer; font-family: inherit; font-weight: 700; transition: transform 0.2s ease; }
  @media (max-width: 768px) {
    .carousel button, .palette button { padding: 6px 8px; font-size: 12px; }
  }
  .carousel button:hover, .palette button:hover { transform: scale(1.05); }
  .carousel button.active { background: #2b9348; color: #fff; border-color: #2b9348; }
  #adopt { display: block; width: calc(100% - 24px); margin: 6px 12px 12px; background: #2b9348; color: #fff; border: 0; border-radius: 10px; padding: 12px; font-size: 18px; font-weight: 700; cursor: pointer; font-family: inherit; }
</style>
</head>
<body>
<div class="editor">
<header>
  <strong>محرر الكروكي التنظيمي</strong>
  <button type="button" id="del" title="حذف المحدد">🗑️</button>
  <button type="button" id="rr" title="تدوير يمين">↻</button>
  <button type="button" id="rl" title="تدوير يسار">↺</button>
  <button type="button" id="clear" title="مسح اللوحة">🔄</button>
  <button type="button" id="zin" title="تكبير">🔍+</button>
  <button type="button" id="zout" title="تصغير">🔍-</button>
</header>
<div class="stage"><div class="canvas-wrap"><canvas id="c" width="600" height="550"></canvas></div></div>
<div class="label">قوالب الطريق</div>
<div class="carousel" id="roads"></div>
<div class="label">مكتبة المركبات والرموز</div>
<div class="palette" id="palette"></div>
<button type="button" id="adopt">💾 اعتماد الكروكي في التقرير</button>
</div>
<script>
const ROADS = [
  ["تقاطع T بجزيرة", "t"],
  ["تقاطع رباعي", "cross"],
  ["مزدوج بجزيرة", "dual"],
  ["مفرد مسارين", "single"],
  ["دوار", "round"],
  ["طريق جبلي منحني", "curve"],
  ["يوتيرن (U-Turn)", "uturn"]
];
const ITEMS = [
  ["سيدان أخضر", "sedan-green"],
  ["سيدان أبيض", "sedan-white"],
  ["دفع رباعي", "suv"],
  ["وانيت غمارتين", "pickup"],
  ["شاحنة", "truck"],
  ["دراجة", "moto"],
  ["آثار فرامل", "skid"],
  ["نقطة اصطدام", "hit"],
  ["سهم اتجاه", "arrow"],
  ["1", "b1"], ["2", "b2"], ["3", "b3"], ["4", "b4"],
  ["شمال", "north"]
];
let canvas;
let currentRoad = "t";

function mark(obj) {
  obj.set({ selectable: false, evented: false, hoverCursor: "default", name: "road-bg" });
  return obj;
}
function box(x, y, w, h, fill) {
  return mark(new fabric.Rect({ left: x, top: y, width: w, height: h, fill: fill }));
}
function rule(x1, y1, x2, y2, color, width) {
  return mark(new fabric.Line([x1, y1, x2, y2], { stroke: color, strokeWidth: width }));
}
function disk(x, y, r, fill, stroke, sw) {
  return mark(new fabric.Circle({
    left: x, top: y, radius: r, fill: fill, stroke: stroke || null, strokeWidth: sw || 0,
    originX: "center", originY: "center"
  }));
}
const SAND = "#dfd3c3";
const ASPH = "#343a40";
const YEL = "#f0c400";
function vDashes(x, y0, y1) {
  const out = [];
  for (let y = y0; y < y1 - 2; y += 18) out.push(rule(x, y, x, Math.min(y1, y + 10), "#ffffff", 2));
  return out;
}
function hDashes(y, x0, x1) {
  const out = [];
  for (let x = x0; x < x1 - 2; x += 18) out.push(rule(x, y, Math.min(x1, x + 10), y, "#ffffff", 2));
  return out;
}
function roadT() {
  const parts = [
    box(0, 0, 600, 550, SAND),
    box(168, 0, 264, 550, ASPH),
    box(0, 178, 168, 194, ASPH),
    box(18, 262, 110, 26, SAND),
    rule(168, 0, 168, 178, YEL, 4),
    rule(168, 372, 168, 550, YEL, 4),
    rule(432, 0, 432, 550, YEL, 4),
    rule(292, 0, 292, 550, YEL, 3),
    rule(304, 0, 304, 550, YEL, 3),
    rule(0, 178, 168, 178, YEL, 4),
    rule(0, 372, 168, 372, YEL, 4),
    rule(18, 262, 128, 262, YEL, 3),
    rule(18, 288, 128, 288, YEL, 3)
  ];
  parts.push.apply(parts, vDashes(230, 8, 170));
  parts.push.apply(parts, vDashes(230, 380, 542));
  parts.push.apply(parts, vDashes(368, 8, 170));
  parts.push.apply(parts, vDashes(368, 380, 542));
  parts.push.apply(parts, hDashes(220, 8, 158));
  parts.push.apply(parts, hDashes(330, 8, 158));
  return parts;
}
function roadCross() {
  const parts = [
    box(0, 0, 600, 550, SAND),
    box(168, 0, 264, 550, ASPH),
    box(0, 178, 600, 194, ASPH),
    box(18, 262, 110, 26, SAND),
    box(472, 262, 110, 26, SAND),
    rule(168, 0, 168, 178, YEL, 4),
    rule(168, 372, 168, 550, YEL, 4),
    rule(432, 0, 432, 178, YEL, 4),
    rule(432, 372, 432, 550, YEL, 4),
    rule(292, 0, 292, 178, YEL, 3),
    rule(304, 0, 304, 178, YEL, 3),
    rule(292, 372, 292, 550, YEL, 3),
    rule(304, 372, 304, 550, YEL, 3),
    rule(0, 178, 168, 178, YEL, 4),
    rule(432, 178, 600, 178, YEL, 4),
    rule(0, 372, 168, 372, YEL, 4),
    rule(432, 372, 600, 372, YEL, 4),
    rule(18, 262, 128, 262, YEL, 3),
    rule(18, 288, 128, 288, YEL, 3),
    rule(472, 262, 582, 262, YEL, 3),
    rule(472, 288, 582, 288, YEL, 3)
  ];
  parts.push.apply(parts, vDashes(230, 8, 170));
  parts.push.apply(parts, vDashes(230, 380, 542));
  parts.push.apply(parts, vDashes(368, 8, 170));
  parts.push.apply(parts, vDashes(368, 380, 542));
  parts.push.apply(parts, hDashes(220, 8, 158));
  parts.push.apply(parts, hDashes(220, 442, 592));
  parts.push.apply(parts, hDashes(330, 8, 158));
  parts.push.apply(parts, hDashes(330, 442, 592));
  return parts;
}
function roadDual() {
  const parts = [
    box(0, 0, 600, 550, SAND),
    box(120, 0, 360, 550, ASPH),
    box(282, 0, 36, 550, SAND),
    rule(120, 0, 120, 550, YEL, 4),
    rule(480, 0, 480, 550, YEL, 4),
    rule(282, 0, 282, 550, YEL, 3),
    rule(318, 0, 318, 550, YEL, 3)
  ];
  parts.push.apply(parts, vDashes(201, 8, 542));
  parts.push.apply(parts, vDashes(399, 8, 542));
  return parts;
}
function roadSingle() {
  const parts = [
    box(0, 0, 600, 550, SAND),
    box(190, 0, 220, 550, ASPH),
    rule(190, 0, 190, 550, YEL, 4),
    rule(410, 0, 410, 550, YEL, 4)
  ];
  parts.push.apply(parts, vDashes(300, 8, 542));
  return parts;
}
function roadRound() {
  const parts = [
    box(0, 0, 600, 550, SAND),
    box(250, 0, 100, 550, ASPH),
    box(0, 225, 600, 100, ASPH),
    disk(300, 275, 118, ASPH),
    disk(300, 275, 54, SAND, YEL, 4),
    rule(250, 0, 250, 160, YEL, 4),
    rule(350, 0, 350, 160, YEL, 4),
    rule(250, 390, 250, 550, YEL, 4),
    rule(350, 390, 350, 550, YEL, 4),
    rule(0, 225, 180, 225, YEL, 4),
    rule(0, 325, 180, 325, YEL, 4),
    rule(420, 225, 600, 225, YEL, 4),
    rule(420, 325, 600, 325, YEL, 4)
  ];
  parts.push.apply(parts, vDashes(300, 8, 150));
  parts.push.apply(parts, vDashes(300, 400, 542));
  parts.push.apply(parts, hDashes(275, 8, 170));
  parts.push.apply(parts, hDashes(275, 430, 592));
  return parts;
}
function roadCurve() {
  const d = "M 150 8 C 230 130, 120 230, 270 330 S 430 470, 470 544";
  return [
    box(0, 0, 600, 550, SAND),
    mark(new fabric.Path(d, { fill: "", stroke: YEL, strokeWidth: 118, strokeLineCap: "butt" })),
    mark(new fabric.Path(d, { fill: "", stroke: ASPH, strokeWidth: 104, strokeLineCap: "butt" })),
    mark(new fabric.Path(d, { fill: "", stroke: "#ffffff", strokeWidth: 2, strokeDashArray: [12, 10] }))
  ];
}
function roadUturn() {
  const parts = [
    box(0, 0, 600, 550, SAND),
    box(130, 0, 150, 550, ASPH),
    box(320, 0, 150, 550, ASPH),
    box(280, 200, 40, 150, ASPH),
    mark(new fabric.Path("M 280 200 L 246 168 L 246 228 Z", { fill: ASPH })),
    mark(new fabric.Path("M 320 200 L 354 168 L 354 228 Z", { fill: ASPH })),
    mark(new fabric.Path("M 280 350 L 246 382 L 246 322 Z", { fill: ASPH })),
    mark(new fabric.Path("M 320 350 L 354 382 L 354 322 Z", { fill: ASPH })),
    rule(130, 0, 130, 550, YEL, 4),
    rule(470, 0, 470, 550, YEL, 4),
    rule(280, 0, 280, 168, YEL, 3),
    rule(320, 0, 320, 168, YEL, 3),
    rule(280, 382, 280, 550, YEL, 3),
    rule(320, 382, 320, 550, YEL, 3)
  ];
  parts.push.apply(parts, vDashes(205, 8, 542));
  parts.push.apply(parts, vDashes(395, 8, 542));
  return parts;
}
const BUILDERS = { t: roadT, cross: roadCross, dual: roadDual, single: roadSingle, round: roadRound, curve: roadCurve, uturn: roadUturn };

function applyRoad(kind) {
  currentRoad = kind;
  canvas.getObjects().slice().forEach(function(obj) {
    if (obj.name === "road-bg") canvas.remove(obj);
  });
  const parts = BUILDERS[kind]();
  parts.forEach(function(obj) { canvas.add(obj); });
  parts.slice().reverse().forEach(function(obj) { canvas.sendToBack(obj); });
  document.querySelectorAll("#roads button").forEach(function(btn) {
    btn.classList.toggle("active", btn.dataset.kind === kind);
  });
  canvas.requestRenderAll();
}
function place(obj) {
  obj.set({
    left: 300, top: 275, originX: "center", originY: "center",
    cornerColor: "#38b000", borderColor: "#38b000", transparentCorners: false,
    cornerSize: 9, borderScaleFactor: 2, hasRotatingPoint: true,
    rotatingPointOffset: 22, centeredRotation: true
  });
  canvas.add(obj);
  canvas.setActiveObject(obj);
  canvas.requestRenderAll();
}
function sedan(fill) {
  return '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="76" viewBox="0 0 36 76">' +
    '<path d="M13 7 C16 3 20 3 23 7 C28 9 31 13 31 18 L30 58 C30 67 25 72 18 72 C11 72 6 67 6 58 L5 18 C5 13 8 9 13 7 Z" fill="' + fill + '" stroke="#1c1c1c" stroke-width="0.8"/>' +
    '<path d="M18 8 L18 16" stroke="#222" stroke-width="0.5" fill="none"/>' +
    '<path d="M13 15 H23" stroke="#222" stroke-width="0.45" fill="none" opacity="0.7"/>' +
    '<path d="M10 9 L14.2 14.2 L12.4 14.2 L9 10.2 Z" fill="#fff4d6" stroke="#8a8a8a" stroke-width="0.3"/>' +
    '<path d="M26 9 L21.8 14.2 L23.6 14.2 L27 10.2 Z" fill="#fff4d6" stroke="#8a8a8a" stroke-width="0.3"/>' +
    '<path d="M11 18 L25 18 L23.4 29 L12.6 29 Z" fill="#1d2d44"/>' +
    '<rect x="12" y="30.5" width="12" height="15" rx="1.4" fill="' + fill + '" stroke="#222" stroke-width="0.45"/>' +
    '<path d="M7.6 31 L12 31.6 L12 45 L8.2 43.2 Z" fill="#1d2d44"/>' +
    '<path d="M28.4 31 L24 31.6 L24 45 L27.8 43.2 Z" fill="#1d2d44"/>' +
    '<path d="M12.2 47 C14.4 54 21.6 54 23.8 47 C21.4 51.2 14.6 51.2 12.2 47 Z" fill="#1d2d44"/>' +
    '<rect x="1.2" y="20" width="5.2" height="3.2" rx="1" fill="#2b2b2b"/>' +
    '<rect x="29.6" y="20" width="5.2" height="3.2" rx="1" fill="#2b2b2b"/>' +
    '<rect x="4.2" y="14" width="2.8" height="8" rx="1" fill="#111"/>' +
    '<rect x="29" y="14" width="2.8" height="8" rx="1" fill="#111"/>' +
    '<rect x="4.2" y="54" width="2.8" height="8" rx="1" fill="#111"/>' +
    '<rect x="29" y="54" width="2.8" height="8" rx="1" fill="#111"/>' +
    '</svg>';
}
function suvSvg() {
  return '<svg xmlns="http://www.w3.org/2000/svg" width="44" height="80" viewBox="0 0 44 80">' +
    '<path d="M14 8 C18 3 26 3 30 8 C35 10 38 15 38 20 L37 60 C37 70 31 76 22 76 C13 76 7 70 7 60 L6 20 C6 15 9 10 14 8 Z" fill="#6b705c" stroke="#1c1c1c" stroke-width="0.8"/>' +
    '<path d="M22 9 L22 17" stroke="#222" stroke-width="0.5" fill="none"/>' +
    '<path d="M16 16 H28" stroke="#222" stroke-width="0.45" fill="none" opacity="0.7"/>' +
    '<path d="M12 10 L17 15.5 L15 15.5 L10.6 11.2 Z" fill="#fff4d6" stroke="#8a8a8a" stroke-width="0.3"/>' +
    '<path d="M32 10 L27 15.5 L29 15.5 L33.4 11.2 Z" fill="#fff4d6" stroke="#8a8a8a" stroke-width="0.3"/>' +
    '<path d="M13 19 L31 19 L29 31 L15 31 Z" fill="#1d2d44"/>' +
    '<rect x="15" y="32" width="14" height="16" rx="1.5" fill="#6b705c" stroke="#222" stroke-width="0.45"/>' +
    '<path d="M9 32 L15 33 L15 48 L9.6 46 Z" fill="#1d2d44"/>' +
    '<path d="M35 32 L29 33 L29 48 L34.4 46 Z" fill="#1d2d44"/>' +
    '<path d="M15 50 C18 57 26 57 29 50 C26 54 18 54 15 50 Z" fill="#1d2d44"/>' +
    '<circle cx="22" cy="68" r="4.3" fill="#222" stroke="#111" stroke-width="0.6"/>' +
    '<circle cx="22" cy="68" r="1.7" fill="#6b705c"/>' +
    '<rect x="2" y="22" width="6" height="3.4" rx="1" fill="#2b2b2b"/>' +
    '<rect x="36" y="22" width="6" height="3.4" rx="1" fill="#2b2b2b"/>' +
    '<rect x="5" y="15" width="3.2" height="9" rx="1" fill="#111"/>' +
    '<rect x="35.8" y="15" width="3.2" height="9" rx="1" fill="#111"/>' +
    '<rect x="5" y="52" width="3.2" height="9" rx="1" fill="#111"/>' +
    '<rect x="35.8" y="52" width="3.2" height="9" rx="1" fill="#111"/>' +
    '</svg>';
}
function pickupSvg() {
  return '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="86" viewBox="0 0 40 86">' +
    '<path d="M12 6 C16 2 24 2 28 6 C32 8 34 12 34 16 L34 78 C34 82 30 84 20 84 C10 82 6 82 6 78 L6 16 C6 12 8 8 12 6 Z" fill="#f8f9fa" stroke="#222" stroke-width="0.8"/>' +
    '<path d="M20 7 L20 14" stroke="#333" stroke-width="0.5" fill="none"/>' +
    '<path d="M11 9 L15.5 14 L13.8 14 L10 10.2 Z" fill="#fff4d6" stroke="#888" stroke-width="0.3"/>' +
    '<path d="M29 9 L24.5 14 L26.2 14 L30 10.2 Z" fill="#fff4d6" stroke="#888" stroke-width="0.3"/>' +
    '<path d="M11 16 L29 16 L27 26 L13 26 Z" fill="#1d2d44"/>' +
    '<rect x="12" y="27" width="16" height="16" rx="1.2" fill="#f8f9fa" stroke="#333" stroke-width="0.4"/>' +
    '<path d="M8 28 L12 28.5 L12 42 L8.4 40.5 Z" fill="#1d2d44"/>' +
    '<path d="M32 28 L28 28.5 L28 42 L31.6 40.5 Z" fill="#1d2d44"/>' +
    '<path d="M13 43 C16 48 24 48 27 43 C24 46 16 46 13 43 Z" fill="#1d2d44"/>' +
    '<rect x="9" y="50" width="22" height="28" rx="1.5" fill="#e9ecef" stroke="#666" stroke-width="0.6"/>' +
    '<path d="M11 56 H29 M11 62 H29 M11 68 H29 M11 74 H29" stroke="#8d99ae" stroke-width="0.7" fill="none"/>' +
    '<rect x="1" y="18" width="5.4" height="3.2" rx="1" fill="#2b2b2b"/>' +
    '<rect x="33.6" y="18" width="5.4" height="3.2" rx="1" fill="#2b2b2b"/>' +
    '<rect x="4" y="12" width="3" height="8" rx="1" fill="#111"/>' +
    '<rect x="33" y="12" width="3" height="8" rx="1" fill="#111"/>' +
    '<rect x="4" y="64" width="3" height="8" rx="1" fill="#111"/>' +
    '<rect x="33" y="64" width="3" height="8" rx="1" fill="#111"/>' +
    '</svg>';
}
function truckSvg() {
  return '<svg xmlns="http://www.w3.org/2000/svg" width="42" height="108" viewBox="0 0 42 108">' +
    '<path d="M12 4 C16 1 26 1 30 4 C34 6 36 10 36 14 L36 40 L6 40 L6 14 C6 10 8 6 12 4 Z" fill="#ced4da" stroke="#222" stroke-width="0.8"/>' +
    '<path d="M11 8 L16 13 L14.2 13 L10 9 Z" fill="#fff4d6" stroke="#888" stroke-width="0.3"/>' +
    '<path d="M31 8 L26 13 L27.8 13 L32 9 Z" fill="#fff4d6" stroke="#888" stroke-width="0.3"/>' +
    '<path d="M10 15 L32 15 L30 28 L12 28 Z" fill="#1d2d44"/>' +
    '<path d="M8 22 L12 22.4 L12 34 L8.5 32.5 Z" fill="#1d2d44"/>' +
    '<path d="M34 22 L30 22.4 L30 34 L33.5 32.5 Z" fill="#1d2d44"/>' +
    '<rect x="7" y="46" width="28" height="56" rx="2" fill="#6c757d" stroke="#222" stroke-width="0.8"/>' +
    '<path d="M12 50 V98 M18 50 V98 M24 50 V98 M30 50 V98" stroke="#495057" stroke-width="0.7" fill="none"/>' +
    '<rect x="2" y="16" width="5" height="3" rx="1" fill="#222"/>' +
    '<rect x="35" y="16" width="5" height="3" rx="1" fill="#222"/>' +
    '<rect x="4" y="30" width="4" height="8" rx="1" fill="#111"/>' +
    '<rect x="34" y="30" width="4" height="8" rx="1" fill="#111"/>' +
    '<rect x="4" y="78" width="4" height="10" rx="1" fill="#111"/>' +
    '<rect x="34" y="78" width="4" height="10" rx="1" fill="#111"/>' +
    '</svg>';
}
function motoSvg() {
  return '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="90" viewBox="0 0 36 90">' +
    '<circle cx="18" cy="16" r="12" fill="#111"/>' +
    '<circle cx="18" cy="74" r="12" fill="#111"/>' +
    '<rect x="12" y="24" width="12" height="42" rx="4" fill="#e76f51" stroke="#111"/>' +
    '</svg>';
}
function addSvg(svg) {
  fabric.loadSVGFromString(svg, function(objects, options) {
    const item = fabric.util.groupSVGElements(objects, options);
    place(item);
  });
}
function addBadge(num) {
  const circle = new fabric.Circle({ radius: 16, fill: "#ffffff", stroke: "#9b2226", strokeWidth: 3, originX: "center", originY: "center" });
  const text = new fabric.Text(String(num), { fontSize: 18, fill: "#9b2226", originX: "center", originY: "center", fontFamily: "Tajawal, sans-serif" });
  place(new fabric.Group([circle, text]));
}
function addNorth() {
  const plate = new fabric.Rect({ width: 54, height: 54, fill: "#ffffff", stroke: "#1b4332", strokeWidth: 2, originX: "center", originY: "center" });
  const tri = new fabric.Triangle({ width: 22, height: 18, fill: "#1b4332", left: 0, top: -12, originX: "center", originY: "center" });
  const text = new fabric.Text("شمال", { fontSize: 14, fill: "#1b4332", left: 0, top: 12, originX: "center", originY: "center", fontFamily: "Tajawal, sans-serif" });
  place(new fabric.Group([plate, tri, text]));
}
function addItem(kind) {
  if (kind === "sedan-green") addSvg(sedan("#38b000"));
  else if (kind === "sedan-white") addSvg(sedan("#f8f9fa"));
  else if (kind === "suv") addSvg(suvSvg());
  else if (kind === "pickup") addSvg(pickupSvg());
  else if (kind === "truck") addSvg(truckSvg());
  else if (kind === "moto") addSvg(motoSvg());
  else if (kind === "skid") {
    place(new fabric.Group([
      new fabric.Line([0, 0, 0, 100], { stroke: "#111111", strokeWidth: 5 }),
      new fabric.Line([22, 0, 22, 100], { stroke: "#111111", strokeWidth: 5 })
    ]));
  } else if (kind === "hit") {
    place(new fabric.Circle({ radius: 28, fill: "rgba(208,0,0,0.08)", stroke: "#d00000", strokeWidth: 4, strokeDashArray: [8, 6] }));
  } else if (kind === "arrow") {
    place(new fabric.Path("M 16 0 L 32 26 L 22 26 L 22 72 L 10 72 L 10 26 L 0 26 Z", { fill: "#1b4332" }));
  } else if (kind === "b1") addBadge(1);
  else if (kind === "b2") addBadge(2);
  else if (kind === "b3") addBadge(3);
  else if (kind === "b4") addBadge(4);
  else if (kind === "north") addNorth();
}
function rotateActive(delta) {
  const obj = canvas.getActiveObject();
  if (!obj || obj.name === "road-bg") return;
  obj.rotate(((obj.angle || 0) + delta + 360) % 360);
  canvas.requestRenderAll();
}
function pushToParent(dataUrl) {
  try {
    const doc = window.parent.document;
    const areas = Array.prototype.slice.call(doc.querySelectorAll("textarea"));
    const area = areas.find(function(el) {
      return (el.getAttribute("aria-label") || "").indexOf("adopt_payload") !== -1;
    });
    if (!area) return;
    const proto = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, "value");
    proto.set.call(area, dataUrl);
    area.dispatchEvent(new Event("input", { bubbles: true }));
    area.dispatchEvent(new Event("change", { bubbles: true }));
    const root = area.closest("[class*='st-key-adopt-hidden']") || area.closest("form");
    const btn = root ? root.querySelector("button") : null;
    if (btn) setTimeout(function() { btn.click(); }, 120);
  } catch (err) {}
}
function adopt() {
  const dataUrl = canvas.toDataURL({ format: "png", multiplier: 1 });
  pushToParent(dataUrl);
}
function boot() {
  fabric.Object.prototype.borderColor = "#38b000";
  fabric.Object.prototype.cornerColor = "#38b000";
  fabric.Object.prototype.transparentCorners = false;
  fabric.Object.prototype.cornerSize = 9;
  fabric.Object.prototype.borderScaleFactor = 2;
  fabric.Object.prototype.hasRotatingPoint = true;
  fabric.Object.prototype.rotatingPointOffset = 22;
  canvas = new fabric.Canvas("c", {
    width: 600, height: 550, backgroundColor: "#dfd3c3", preserveObjectStacking: true, selection: true
  });
  const roads = document.getElementById("roads");
  ROADS.forEach(function(pair) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pair[0];
    btn.dataset.kind = pair[1];
    btn.onclick = function() { applyRoad(pair[1]); };
    roads.appendChild(btn);
  });
  const palette = document.getElementById("palette");
  ITEMS.forEach(function(pair) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = pair[0];
    btn.onclick = function() { addItem(pair[1]); };
    palette.appendChild(btn);
  });
  document.getElementById("del").onclick = function() {
    const obj = canvas.getActiveObject();
    if (obj && obj.name !== "road-bg") canvas.remove(obj);
    canvas.discardActiveObject();
    canvas.requestRenderAll();
  };
  document.getElementById("rr").onclick = function() { rotateActive(15); };
  document.getElementById("rl").onclick = function() { rotateActive(-15); };
  document.getElementById("clear").onclick = function() {
    canvas.getObjects().slice().forEach(function(obj) {
      if (obj.name !== "road-bg") canvas.remove(obj);
    });
    canvas.discardActiveObject();
    canvas.requestRenderAll();
  };
  document.getElementById("zin").onclick = function() {
    const zoom = Math.min(2.4, canvas.getZoom() * 1.15);
    canvas.zoomToPoint(new fabric.Point(300, 275), zoom);
  };
  document.getElementById("zout").onclick = function() {
    const zoom = Math.max(0.5, canvas.getZoom() / 1.15);
    canvas.zoomToPoint(new fabric.Point(300, 275), zoom);
  };
  document.getElementById("adopt").onclick = adopt;
  applyRoad("t");
  fitBoard();
  window.addEventListener("resize", fitBoard);
}
function fitBoard() {
  if (!canvas) return;
  const viewW = window.innerWidth || document.documentElement.clientWidth || 600;
  const wrap = document.querySelector(".canvas-wrap");
  if (viewW >= 768) {
    canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    canvas.setWidth(600);
    canvas.setHeight(550);
    if (wrap) {
      wrap.style.width = "600px";
      wrap.style.height = "550px";
    }
  } else {
    const avail = Math.max(220, viewW - 24);
    const scale = Math.min(1, avail / 600);
    const w = Math.round(600 * scale);
    const h = Math.round(550 * scale);
    canvas.setViewportTransform([scale, 0, 0, scale, 0, 0]);
    canvas.setWidth(w);
    canvas.setHeight(h);
    if (wrap) {
      wrap.style.width = w + "px";
      wrap.style.height = h + "px";
      wrap.style.minHeight = "0";
    }
  }
  canvas.allowTouchScrolling = false;
  canvas.calcOffset();
  canvas.requestRenderAll();
}
if (window.fabric) boot();
else document.body.insertAdjacentHTML("beforeend", "<p>تعذر تحميل Fabric.js</p>");
</script>
</body>
</html>
'''
    st.components.v1.html(_fabric_html, height=980, scrolling=False)

    def _store_adopted_sketch(payload):
        if not isinstance(payload, str) or "base64," not in payload:
            return False
        try:
            raw = base64.b64decode(payload.split(",", 1)[1])
        except Exception:
            return False
        if not raw.startswith(b"\x89PNG"):
            return False
        try:
            SAVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            (SAVED_IMAGES_DIR / "adopted_sketch.png").write_bytes(raw)
        except OSError:
            return False
        return True

    with st.container(key="adopt-hidden"):
        with st.form("adopt_sketch_form", clear_on_submit=True, border=False):
            adopted_payload = st.text_area(
                "adopt_payload",
                key="adopted_sketch_data",
                label_visibility="collapsed",
            )
            adopted_submitted = st.form_submit_button("حفظ", key="adopt_submit")
    if adopted_submitted:
        _store_adopted_sketch(adopted_payload)
    road_name_sign = st.text_input("اسم الطريق الرئيسي", "طريق العارضة العام - جازان")
    key_1 = st.text_input("مدلول رقم (1)", f"1 - {road_name_sign}")
    key_2 = st.text_input("مدلول رقم (2)", "2 - اتجاه سير المركبة الأولى")
    key_3 = st.text_input("مدلول رقم (3)", "3 - نقطة الاصطدام")
    key_4 = st.text_input("مدلول رقم (4)", "4 - آثار الفرامل والاتجاهات")
    adopted_path = SAVED_IMAGES_DIR / "adopted_sketch.png"
    sketch_img = Image.open(adopted_path).convert("RGB") if adopted_path.is_file() else None
def convert_gallery_image(uploaded_file):
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGB")
            image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=82)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return None

with tab5:
    st.subheader("📸 إرفاق صور موقع الحادث والمركبات للتقرير الرسمي")
    _max_accident_photos = 10
    if "gallery_photos" not in st.session_state:
        st.session_state.gallery_photos = list(st.session_state.get("accident_photos_data") or [])
    if "uploaded_ids" not in st.session_state:
        st.session_state.uploaded_ids = set(st.session_state.get("processed_file_keys") or set())
        for entry in st.session_state.gallery_photos:
            if entry.get("id"):
                st.session_state.uploaded_ids.add(entry["id"])
    gallery_uploads = st.file_uploader(
        "📸 اضغط هنا لاختيار صور الحادث من معرض الجوال (حتى 10 صور)",
        type=None,
        accept_multiple_files=True,
        key="mobile_gallery_uploader",
    )
    st.components.v1.html(
        """
<script>
(function () {
  var MAX = 10;
  var EDGE = 1200;
  var QUALITY = 0.78;
  var doc;
  try { doc = window.parent.document; } catch (err) { return; }
  if (!doc || !doc.body) return;
  function compress(file) {
    return new Promise(function (resolve) {
      if (!file || !file.type || file.type.indexOf("image/") !== 0) {
        resolve(null);
        return;
      }
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        var scale = Math.min(1, EDGE / Math.max(img.width || 1, img.height || 1));
        var canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          URL.revokeObjectURL(url);
          if (!blob) { resolve(file); return; }
          var base = (file.name || "photo").split(".").slice(0, -1).join(".") || "photo";
          resolve(new File([blob], base + ".jpg", {type: "image/jpeg", lastModified: Date.now()}));
        }, "image/jpeg", QUALITY);
      };
      img.onerror = function () {
        URL.revokeObjectURL(url);
        resolve(file);
      };
      img.src = url;
    });
  }
  function bind(input) {
    input.setAttribute("accept", "image/*");
    if (input.dataset.bayyinahGallery === "1") return;
    input.dataset.bayyinahGallery = "1";
    input.addEventListener("change", function (event) {
      if (input.dataset.bayyinahPass === "send") {
        input.dataset.bayyinahPass = "";
        return;
      }
      var files = Array.prototype.slice.call(input.files || []);
      if (!files.length) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      Promise.all(files.slice(0, MAX).map(compress)).then(function (out) {
        var transfer = new DataTransfer();
        out.forEach(function (file) { if (file) transfer.items.add(file); });
        input.dataset.bayyinahPass = "send";
        input.files = transfer.files;
        input.dispatchEvent(new Event("change", {bubbles: true}));
      });
    }, true);
  }
  function scan() {
    var root = doc.querySelector('[class*="st-key-mobile_gallery_uploader"]') || doc;
    root.querySelectorAll('input[type="file"]').forEach(bind);
  }
  if (!doc.body.dataset.bayyinahGalleryObserver) {
    doc.body.dataset.bayyinahGalleryObserver = "1";
    new MutationObserver(scan).observe(doc.body, {childList: true, subtree: true});
  }
  scan();
})();
</script>
        """,
        height=0,
    )
    gallery_photos = st.session_state.gallery_photos
    uploaded_ids = set(st.session_state.uploaded_ids)
    photo_limit_hit = False
    if gallery_uploads:
        for item in gallery_uploads:
            uid = f"{getattr(item, 'name', '')}_{getattr(item, 'size', 0)}"
            if uid in uploaded_ids:
                continue
            if len(gallery_photos) >= _max_accident_photos:
                photo_limit_hit = True
                continue
            image_b64 = convert_gallery_image(item)
            if not image_b64:
                continue
            number = len(gallery_photos) + 1
            gallery_photos.append({
                "id": uid,
                "b64": image_b64,
                "caption": f"صورة ({number}): موقع التصادم واتجاه المركبات",
            })
            uploaded_ids.add(uid)
    st.session_state.gallery_photos = gallery_photos
    st.session_state.uploaded_ids = uploaded_ids
    if photo_limit_hit:
        st.warning("تم الوصول للحد الأقصى (10 صور).")
    pending_remove = None
    for row_start in range(0, len(gallery_photos), 2):
        cols = st.columns(2)
        for offset, entry in enumerate(gallery_photos[row_start:row_start + 2]):
            number = row_start + offset + 1
            cap_key = f"annex_cap_{entry['id']}"
            if cap_key not in st.session_state:
                st.session_state[cap_key] = entry.get("caption") or f"صورة ({number}): موقع التصادم واتجاه المركبات"
            with cols[offset]:
                preview_b64 = entry["b64"].split(",", 1)[-1]
                st.image(base64.b64decode(preview_b64), width=320)
                if st.button("🗑️ حذف هذه الصورة", key=f"del_photo_{entry['id']}"):
                    pending_remove = entry["id"]
                entry["caption"] = st.text_input("تعليق الصورة", key=cap_key)
    if pending_remove:
        st.session_state.gallery_photos = [
            entry for entry in gallery_photos if entry["id"] != pending_remove
        ]
        st.rerun()
    
    def img_to_b64(img_obj):
        buf = io.BytesIO()
        img_obj.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    sketch_b64 = img_to_b64(sketch_img) if sketch_img is not None else ""
    sketch_figure = (
        f'<img src="data:image/png;base64,{sketch_b64}" style="max-width:100%; height:440px; border:1px solid #ccc;">'
        if sketch_b64 else ""
    )
    logo_b64 = ""
    _fixed_logo_path = Path(__file__).resolve().parent / "traffic_logo.png"
    if _fixed_logo_path.is_file():
        try:
            logo_b64 = img_to_b64(Image.open(_fixed_logo_path).convert("RGBA"))
        except OSError:
            logo_b64 = ""
    def build_header():
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" alt="شعار المرور">' if logo_b64 else '<div class="logo-fallback">الأمن العام<br>المرور</div>'
        return f"""
        <div class="header-Title">بسم الله الرحمن الرحيم</div>
        <div class="header-box">
            <div class="header-right">
                المملكة العربية السعودية<br>وزارة الداخلية<br>الأمن العام<br>الإدارة العامة للمرور<br>{dept_region}<br>{dept_branch}
            </div>
            <div class="header-logo">{logo_html}</div>
            <div class="header-center">
                الرقم: ...........................<br>
                التاريخ: ..........................<br>
                المشفوعات: ....................<br>
                الموضوع: .......................
            </div>
        </div>
        """
    parties_rows = ""
    for _, row in parties_df.iterrows():
        parties_rows += f"<tr><td>{row['الطرف']}</td><td>{row['الاسم']}</td><td>{row['الهوية']}</td><td>{row['المشاركة']}</td><td>{row['الحالة']}</td><td>{row['التأهيل']}</td></tr>"
    vehicles_rows = ""
    for _, row in vehicles_df.iterrows():
        vehicles_rows += f"<tr><td>{row['الطرف']}</td><td>{row['نوع المركبة']}</td><td>{row['رقم اللوحة']}</td><td>{row['الرقم التسلسلي']}</td><td>{row['نوع الترخيص']}</td><td>{row['التأمين']}</td></tr>"
    results_html = "<br>".join([line for line in acc_results.split("\n") if line.strip()])
    laws_html = "".join([f"<li>{line}</li>" for line in laws_list_for_report if line.strip()])
    actions_html = "".join([f"<tr><td>{i+1}- {act}</td></tr>" for i, act in enumerate(selected_actions)])
    photo_cards = ""
    for number, entry in enumerate(st.session_state.gallery_photos, start=1):
        safe_caption = html.escape(entry.get("caption") or "")
        photo_cards += f"""
        <div class="photo-card">
            <img src="{entry['b64']}" alt="صورة {number}">
            <div class="photo-meta">{number}<br>{safe_caption}</div>
        </div>
        """
    photos_pages_html = ""
    if photo_cards:
        photos_pages_html = f"""
        <div class="page report-page photo-annex">
            {build_header()}
            <div class="section-badge">ملحق الصور الفوتوغرافية لموقع الحادث</div>
            <div class="photo-grid">{photo_cards}</div>
            <div class="page-num">5</div>
        </div>
        """
    full_report_html = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@500;700&display=swap');
        html, body {{ height: 100%; margin: 0; }}
        body {{
            font-family: 'Tajawal', sans-serif; background: #e5e7eb; margin: 0;
            display: flex; flex-direction: column; overflow: hidden;
        }}
        .report-viewport {{
            flex: 1 1 auto; width: 100%; min-width: 0; max-width: 100%;
            overflow: auto; -webkit-overflow-scrolling: touch;
            container-type: inline-size; container-name: report;
        }}
        .report-sheet {{
            width: 210mm; min-width: 750px; margin: 12px auto 20px auto;
        }}
        .page {{
            background: white; width: 210mm; min-width: 750px; min-height: 297mm; margin: 0 auto 20px auto;
            padding: 15mm 18mm; box-sizing: border-box; position: relative;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); page-break-after: always;
        }}
        .photo-annex {{ page-break-before: always; }}
        .photo-grid {{ display: flex; flex-wrap: wrap; justify-content: space-between; }}
        .photo-card {{ width: 48%; margin-bottom: 18px; text-align: center; }}
        .photo-card img {{
            width: auto; max-width: 100%; max-height: 350px; height: auto; object-fit: contain;
            border: 2px solid #1b4332; border-radius: 6px; background: #fff;
        }}
        .photo-card .photo-meta {{ margin-top: 6px; font-weight: bold; font-size: 14px; line-height: 1.6; }}
        .logo-fallback {{
            border: 2px solid #1b4332; border-radius: 50%; width: 80px; height: 80px;
            display: flex; align-items: center; justify-content: center; margin: auto;
            font-weight: bold; color: #1b4332; line-height: 1.25; text-align: center;
        }}
        .header-logo img {{
            height: 110px; width: auto; max-width: 120px; object-fit: contain;
            display: block; margin: 0 auto;
        }}
        .header-Title {{ text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 6px; }}
        .header-box {{
            position: relative; display: flex; justify-content: space-between; align-items: center;
            min-height: 128px; border-bottom: 3px double #1b4332; padding-bottom: 10px;
            margin-bottom: 18px; font-size: 14px; font-weight: bold; line-height: 1.6;
        }}
        .header-right {{ width: 36%; text-align: right; }}
        .header-center {{ width: 36%; text-align: center; }}
        .header-logo {{
            position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
            display: flex; justify-content: center; align-items: center; margin: 0;
        }}
        .section-badge {{
            background: #d8f3dc; border: 1.5px solid #1b4332; border-radius: 6px;
            padding: 5px 25px; font-weight: bold; font-size: 17px; display: table; margin: 14px auto; text-align: center; color: #1b4332;
        }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 14px; }}
        th, td {{ border: 1.5px solid #444; padding: 7px 6px; text-align: center; font-weight: bold; }}
        th {{ background-color: #d8f3dc; color: #1b4332; }}
        .box-content {{
            border: 1.5px solid #444; padding: 14px; font-size: 15px; font-weight: bold;
            line-height: 1.9; text-align: right; margin-bottom: 16px; min-height: 110px;
        }}
        .page-num {{ position: absolute; bottom: 12mm; left: 50%; transform: translateX(-50%); font-weight: bold; font-size: 16px; }}
        .road-sign {{
            background: #2d6a4f; color: white; border: 3px solid white; outline: 3px solid #2d6a4f;
            border-radius: 8px; padding: 10px 18px; font-weight: bold; font-size: 16px; display: inline-block; margin-bottom: 25px;
        }}
        .table-scroll {{ width: 100%; max-width: 100%; }}
        @media screen and (max-width: 768px) {{
            html, body {{ width: 100%; max-width: 100%; overflow-x: hidden; }}
            .report-viewport {{ overflow-x: hidden; overflow-y: auto; width: 100%; max-width: 100%; }}
            .report-sheet {{
                width: 100%; min-width: 0; max-width: 100%;
                margin: 0 auto 12px auto; zoom: 1;
            }}
            .page {{
                width: 100%; min-width: 0; max-width: 100%;
                overflow: hidden; font-size: 12px;
            }}
            .report-page {{
                width: 100%;
                box-sizing: border-box;
                background: #fff;
                color: #000;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 15px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
            }}
            .header-Title {{ font-size: 14px; }}
            .header-box {{ font-size: 11px; min-height: 88px; }}
            .header-logo img {{ height: 64px; max-width: 70px; }}
            .section-badge {{ font-size: 13px; padding: 4px 10px; }}
            .box-content {{ font-size: 12px; min-height: 0; padding: 8px; }}
            .table-scroll {{
                width: 100%; max-width: 100%;
                overflow-x: auto; -webkit-overflow-scrolling: touch;
            }}
            .table-scroll table {{ min-width: 600px; width: 600px; font-size: 11px; }}
            th, td {{ font-size: 11px; padding: 4px 3px; }}
        }}
        @media print {{
            @page {{ size: A4; margin: 8mm; }}
            html, body {{ height: auto; display: block; overflow: visible; background: white; padding: 0; }}
            button, .no-print, .stButton, .stDownloadButton,
            [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {{
                display: none !important;
            }}
            .report-viewport {{ overflow: visible; height: auto; }}
            .report-sheet {{ width: auto; min-width: 0; margin: 0; zoom: 1; }}
            .page, .report-page {{
                box-shadow: none; margin: 0 auto; width: 100%; max-width: 194mm; max-height: 278mm;
                min-width: 0; min-height: 0; zoom: 1; overflow: hidden; page-break-after: always;
            }}
            .report-sheet > .report-page:last-child {{ page-break-after: auto; break-after: auto; }}
            .table-scroll {{ overflow: visible; max-width: none; }}
            table, .table-scroll table {{
                width: 99.6% !important; min-width: 0 !important; border-collapse: collapse;
                border: 1px solid #000;
            }}
            th, td {{ border: 1px solid #000 !important; }}
            .header-logo img {{ height: 110px; max-width: 120px; }}
        }}
    </style>
    </head>
    <body>
        <div class="no-print" style="text-align:center; margin:0; padding:12px;">
            <button onclick="window.print()" style="background:linear-gradient(90deg,#0e7490,#2563eb); color:white; font-family:'Tajawal'; font-size:18px; font-weight:bold; padding:12px 35px; border:1px solid #4facfe; border-radius:10px; cursor:pointer; box-shadow:0 0 14px rgba(0,242,254,0.45);">
                🖨️ طباعة التقرير الرسمي أو حفظه كـ PDF
            </button>
        </div>
        <div class="report-viewport">
        <div class="report-sheet">
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">تقرير حادث مروري</div>
            <div class="section-badge" style="font-size:15px;">معلومات الحادث</div>
            <div class="table-scroll"><table>
                <tr>
                    <th>رقم الحادث</th><th>تاريخ الحادث</th><th>الوقت</th><th>موقع الحادث</th>
                    <th>نوع الحادث</th><th>عدد الإصابات</th><th>عدد الوفيات</th><th>الطقس</th><th>سبب الحادث</th>
                </tr>
                <tr>
                    <td>{acc_num}</td><td>{acc_date}</td><td>{acc_time}</td><td>{acc_loc}</td>
                    <td>{acc_type}</td><td>{acc_injuries}</td><td>{acc_deaths}</td><td>{acc_weather}</td><td>{acc_cause}</td>
                </tr>
            </table></div>
            <div class="section-badge" style="font-size:15px;">معلومات أطراف الحادث</div>
            <div class="table-scroll"><table>
                <tr><th>الأطراف</th><th>الاسم</th><th>الهوية / الإقامة</th><th>نوع المشاركة</th><th>الحالة الصحية</th><th>تأهيل للقيادة</th></tr>
                {parties_rows}
            </table></div>
            <div class="section-badge" style="font-size:15px;">معلومات المركبات</div>
            <div class="table-scroll"><table>
                <tr><th>الأطراف</th><th>نوع المركبة</th><th>رقم اللوحة</th><th>الرقم التسلسلي</th><th>نوع الترخيص</th><th>التأمين</th></tr>
                {vehicles_rows}
            </table></div>
            <div class="page-num">1</div>
        </div>
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">نتائج الحادث</div>
            <div class="box-content">نتج عن الحادث :<br>{results_html}</div>
            <div class="section-badge">كيفية وقوع الحادث</div>
            <div class="box-content">{acc_how}</div>
            <div class="section-badge">الرأي والمسؤولية</div>
            <div class="box-content">
                {resp_summary}<br>وذلك للأسباب التالية:
                <ul style="margin-top:8px;">{laws_html}</ul>
            </div>
            <div class="page-num">2</div>
        </div>
        <div class="page report-page">
            {build_header()}
            <div class="table-scroll"><table>
                <tr><th style="font-size:16px;">الحقوق الخاصة والعامة</th></tr>
                <tr><td style="padding:14px; font-size:16px;">{rights_status}</td></tr>
            </table></div>
            <div class="table-scroll"><table style="margin-top:25px;">
                <tr><th style="font-size:16px;">الإجراءات المتخذة</th></tr>
                {actions_html}
            </table></div>
            <div class="table-scroll"><table style="margin-top:35px;">
                <tr><th colspan="3" style="font-size:16px;">معد التقرير</th></tr>
                <tr><th>إجراء الحوادث</th><th>مشرف الحوادث</th><th>مدير {dept_branch}</th></tr>
                <tr><td>الاسم: {officer_1_name}</td><td>الاسم: {officer_2_name}</td><td>الاسم: {manager_name}</td></tr>
                <tr><td>الرتبة: {officer_1_rank}</td><td>الرتبة: {officer_2_rank}</td><td>الرتبة: {manager_rank}</td></tr>
                <tr style="height:65px;"><td>التوقيع:</td><td>التوقيع:</td><td>التوقيع:</td></tr>
            </table></div>
            <div class="page-num">3</div>
        </div>
        <div class="page report-page">
            {build_header()}
            <div class="section-badge">كروكي الحادث</div>
            <div style="text-align:center; font-weight:bold; font-size:18px; margin-bottom:15px;">رسم كروكي {road_name_sign}</div>
            <div style="display:flex; justify-content:space-around; align-items:center; margin-top:20px;">
                <div style="text-align:center; width:35%;">
                    <div class="road-sign">{road_name_sign}</div>
                    <div style="font-size:75px; line-height:1; margin:20px 0;">✥</div>
                    <div style="font-weight:bold;">اتجاهات الطريق</div>
                </div>
                <div style="width:55%; text-align:center;">
                    {sketch_figure}
                </div>
            </div>
            <div style="margin-top:30px; font-weight:bold; font-size:16px; line-height:2; padding-right:30px;">
                <div>{key_1}</div>
                <div>{key_2}</div>
                <div>{key_3}</div>
                <div>{key_4}</div>
            </div>
            <div class="page-num">4</div>
        </div>
        {photos_pages_html}
        </div>
        </div>
    </body>
    </html>
    """
    st.divider()
    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        st.download_button(
            label="📥 تحميل التقرير الرسمي الكامل (HTML/PDF)",
            data=full_report_html.encode("utf-8"),
            file_name=f"Accident_Report_{acc_num}.html",
            mime="text/html",
            use_container_width=True
        )
    with col_btn2:
        st.info("💡 بعد تحميل الملف وفتحه، اضغط على زر (طباعة التقرير الرسمي أو حفظه كـ PDF) في أعلى الصفحة.")
    st.subheader("معاينة حية للتقرير قبل الطباعة:")
    st.components.v1.html(full_report_html, height=850, scrolling=True)
st.markdown("""
<style>
@media screen and (max-width: 768px) {
  html body section.stSidebar[data-testid="stSidebar"][data-collapsed="true"],
  html body section[data-testid="stSidebar"][aria-expanded="false"] {
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    transform: none !important;
    overflow: hidden !important;
  }
}
</style>
""", unsafe_allow_html=True)
