#!/usr/bin/env python3
"""
DraveMotion - een portable animatie- & videosuite (een Dravenlock product).

Fundament (v0.17):
  * Project met een tijdlijn met meerdere SPOREN (tracks)
  * Cliptypes: tekenscene (frame-by-frame), videoclip, fotoclip, audioclip, TEKST
  * MEDIA BESTANDEN (assets): importeer losse media of een hele MAP (bv. een
    soundpool); (sub)mappen worden uitklapbare groepen. Sleep items op de
    tijdlijn, dubbelklik om te plaatsen, of RECHTSKLIK op een clip om te knippen.
  * TRANSFORM + KEYFRAMES per clip: positie (X/Y), schaal, rotatie en opaciteit,
    desgewenst geanimeerd over tijd met keyframes.
  * EFFECTEN per clip: helderheid, contrast, verzadiging, vervaging + kleurfilter
    (grijs/sepia/negatief).
  * TRANSITIES per clip-rand: fade, schuiven, vegen, zoom, dip naar zwart/wit;
    overlappende clips lopen in elkaar over (crossfade). Audio: volume + fades.
  * SNELHEID / TIMELAPSE per videoclip (slow motion t/m versneld).
  * Compositor: voegt op elk tijdstip alle sporen + transforms + effecten samen
  * Preview met afspelen / scrubben + audio live mee
  * Undo / redo, clips dupliceren, timeline-zoom, projectinstellingen
  * Export naar MP4 (gebundelde ffmpeg), GIF en PNG-reeks
  * Volledig PORTABLE: alle config, cache en projecten in de app-map zelf.
    Nooit %APPDATA% of de systeem-temp. Klaar om als 1 .exe te bundelen.

Starten:
    pip install -r requirements.txt
    python draveanimate.py
"""

import os
import sys
import io
import re
import json
import math
import base64
import shutil
import subprocess
import urllib.request
import urllib.parse
from collections import deque


# --------------------------------------------------------------------------- #
#  PORTABLE INFRASTRUCTUUR  (moet voor imageio/cv2 staan)
# --------------------------------------------------------------------------- #
try:
    from uitspraak import uitspraak as _uitspraak
except Exception:
    try:
        from .uitspraak import uitspraak as _uitspraak
    except Exception:  # zonder uitspraak.py gewoon de tekst zelf
        def _uitspraak(t, taal="nl"):
            return t


def app_dir():
    """De map waarin de app draait: naast de .exe (frozen) of naast dit script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = app_dir()
CACHE_DIR = os.path.join(APP_DIR, "cache")
PROJECTS_DIR = os.path.join(APP_DIR, "projecten")
MEDIA_DIR = os.path.join(APP_DIR, "media")
BIN_DIR = os.path.join(APP_DIR, "bin")
CONFIG_PATH = os.path.join(APP_DIR, "draveanimate_config.json")
APP_VERSION = "0.40.3"
APP_NAME = "DraveMotion"
AUTHOR_NAME = "Dravenlock"
WEBSITE_URL = "https://dravenlock.nl/"
DONATE_URL = "https://paypal.me/roger076"
DOWNLOAD_PAGE_URL = "https://github.com/mbrv4ever/DraveMotion/releases/latest"
UPDATE_CHECK_URL = "https://dravenlock.nl/downloads/DraveMotion/version.txt"
SERVICE_EMAIL = "service@dravenlock.nl"

for _d in (CACHE_DIR, PROJECTS_DIR, MEDIA_DIR):
    try:
        os.makedirs(_d, exist_ok=True)
    except OSError:
        pass

# Houd imageio/ffmpeg-cache binnen de app-map (portable, nooit %APPDATA%).
os.environ["IMAGEIO_USERDIR"] = CACHE_DIR
_ff_local = os.path.join(BIN_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
if os.path.exists(_ff_local):
    os.environ["IMAGEIO_FFMPEG_EXE"] = _ff_local


def resource_path(rel):
    """Pad naar een GEBUNDELDE (alleen-lezen) resource, bv. een logo."""
    base = getattr(sys, "_MEIPASS", APP_DIR)
    return os.path.join(base, rel)


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except OSError:
        pass


# =========================================================================== #
#  TAAL  (neemt de computertaal over; Nederlands is de basis/terugval)
# =========================================================================== #
SUPPORTED_LANGS = ["nl", "en"]          # uitbreidbaar (de, fr, …)
_CURRENT_LANG = None

# Engelse vertalingen, met de Nederlandse tekst als sleutel.
# Ontbreekt een sleutel, dan valt de app automatisch terug op het Nederlands.
TRANSLATIONS = {
    "en": {
        "een Dravenlock product": "a Dravenlock product",
        # --- werkbalk ---
        "📖 Snelgids": "📖 Quick guide", "✉️ Contact": "✉️ Contact",
        "🔄 Updates": "🔄 Updates", "ⓘ Info": "ⓘ Info", "⤓ Exporteren…": "⤓ Export…",
        # --- linkerpaneel ---
        "Project": "Project", "Toevoegen": "Add", "Media bestanden": "Media files", "Spoor": "Track",
        "Nieuw": "New", "Openen…": "Open…", "Opslaan…": "Save…", "Instellingen…": "Settings…",
        "✎ Nieuwe tekenscène": "✎ New drawing scene", "T  Tekst / titel": "T  Text / title",
        "▤  End credits / aftiteling": "▤  End credits", "🦴  Stok-poppetje": "🦴  Stick figure",
        "🎬  Teken-studio + poppetje": "🎬  Draw studio + figure",
        "🧍  Poppetje met skelet": "🧍  Figure with skeleton",
        "🎞 Importeer video…": "🎞 Import video…", "🖼 Importeer foto…": "🖼 Import photo…",
        "🎵 Importeer audio…": "🎵 Import audio…",
        "🔊  Stem (tekst-naar-spraak)…": "🔊  Voice (text-to-speech)…",
        "📂 Map laden…": "📂 Load folder…", "Uit lijst verwijderen": "Remove from list",
        "+ Spoor": "+ Track",
        # --- tijdlijn-knoppen ---
        "▶ Afspelen": "▶ Play", "⏸ Pauze": "⏸ Pause", "⏹ Stop": "⏹ Stop",
        "↶ Ongedaan": "↶ Undo", "↷ Opnieuw": "↷ Redo", "⧉ Dupliceer": "⧉ Duplicate",
        "🗑 Verwijder": "🗑 Delete", "FPS": "FPS",
        # --- clip-paneel ---
        "Geselecteerde clip": "Selected clip", "— geen clip —": "— no clip —",
        "Start (s)": "Start (s)", "Duur / trim (s)": "Length / trim (s)", "Transform": "Transform",
        "X (px)": "X (px)", "Y (px)": "Y (px)", "Schaal %": "Scale %", "Rotatie °": "Rotation °",
        "Opaciteit %": "Opacity %",
        # --- introscherm ---
        "2D-animatieprogramma én videobewerker in één":
            "A 2D animation tool and video editor in one",
        "📖 Open de Snelgids": "📖 Open the quick guide",
        "Nieuw hier? Lees even de Snelgids voor een vliegende start —\n"
        "of begin meteen met een tekenscène of het importeren van media.":
            "New here? Read the quick guide for a flying start —\n"
            "or jump right in with a drawing scene or by importing media.",
        # --- info / over ---
        "Een portable animatie- &amp; videosuite.": "A portable animation &amp; video suite.",
        "Sneltoetsen:": "Shortcuts:",
        # --- contact ---
        "Contact opnemen": "Contact", "Soort bericht:": "Type of message:",
        "Vraag": "Question", "Klacht": "Complaint", "Idee": "Idea", "Bug / fout": "Bug / error",
        "Anders": "Other", "Je naam:": "Your name:",
        "Je e-mailadres (zodat de maker je kan antwoorden):":
            "Your e-mail (so the author can reply):", "Je bericht:": "Your message:",
        "📋 Kopieer e-mailadres": "📋 Copy e-mail address", "Sluiten": "Close",
        "✉️ Versturen": "✉️ Send",
        # --- updates ---
        "Updates": "Updates", "Controleren op updates…": "Checking for updates…",
        # --- instellingen ---
        "Taal": "Language", "Automatisch (computertaal)": "Automatic (system language)",
        "Nederlands": "Dutch", "English": "English", "Projectinstellingen": "Project settings",
        "De taal verandert nadat je DraveMotion opnieuw start.":
            "The language changes after you restart DraveMotion.",
        "Beeld": "Image", "Breedte": "Width", "Hoogte": "Height", "Achtergrond": "Background",
        "Annuleer": "Cancel", "Toepassen": "Apply",
        # --- export ---
        "Exporteren": "Export", "Kies een exportformaat:": "Choose an export format:",
        "PNG-reeks": "PNG sequence",
    },
}


def current_lang():
    global _CURRENT_LANG
    if _CURRENT_LANG is None:
        choice = load_config().get("language", "auto")
        if choice in SUPPORTED_LANGS:
            _CURRENT_LANG = choice
        else:  # auto: neem de computertaal over
            try:
                sys_nl = (QLocale.system().language() == QLocale.Dutch)
            except Exception:
                sys_nl = True
            _CURRENT_LANG = "nl" if sys_nl else "en"
    return _CURRENT_LANG


def t(s):
    """Vertaal een Nederlandse tekst naar de huidige taal (NL = terugval)."""
    lang = current_lang()
    if lang == "nl":
        return s
    return TRANSLATIONS.get(lang, {}).get(s, s)


# --------------------------------------------------------------------------- #
#  Afhankelijkheden
# --------------------------------------------------------------------------- #
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QDialog, QWidget, QHBoxLayout, QVBoxLayout,
        QGridLayout, QPushButton, QLabel, QSlider, QColorDialog, QFileDialog,
        QListWidget, QListWidgetItem, QScrollArea, QSpinBox, QDoubleSpinBox,
        QMessageBox, QFrame, QToolButton, QSizePolicy, QComboBox, QPlainTextEdit,
        QCheckBox, QAbstractItemView, QProgressDialog, QTreeWidget, QTreeWidgetItem,
        QStyle, QInputDialog, QFontComboBox, QShortcut, QLineEdit, QTabWidget,
    )
    from PyQt5.QtGui import (
        QImage, QPainter, QColor, QPen, QPixmap, QIcon, QFont, QBrush, QDrag,
        QPolygonF, QKeySequence, QFontMetrics, QTransform, QDesktopServices,
    )
    from PyQt5.QtCore import (
        Qt, QTimer, QPoint, QPointF, QSize, QBuffer, QIODevice, QRectF, QRect, QMimeData,
        QThread, pyqtSignal, QUrl, QLocale,
    )
except ImportError:
    print("PyQt5 ontbreekt. Installeer met:  pip install -r requirements.txt")
    sys.exit(1)

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

try:
    import cv2
    HAVE_CV2 = HAVE_NUMPY  # cv2 zonder numpy is zinloos
except ImportError:
    HAVE_CV2 = False

try:
    import imageio_ffmpeg
    HAVE_FFMPEG = True
except ImportError:
    HAVE_FFMPEG = False

try:
    import importlib.util as _ilu
    HAVE_TTS = _ilu.find_spec("neuvoice") is not None
except Exception:  # noqa: BLE001
    HAVE_TTS = False

try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    HAVE_QTMM = True
except ImportError:
    HAVE_QTMM = False


# Tekengereedschappen
PEN, ERASER, LINE, FILL = "pen", "eraser", "line", "fill"

# Mime-type voor slepen vanuit de mediabak naar de tijdlijn
ASSET_MIME = "application/x-drave-asset"

# Overgangstypes (key -> label) en kleurfilters
TRANS_KEYS = ["fade", "slide_l", "slide_r", "slide_u", "slide_d",
              "wipe_l", "wipe_r", "zoom", "dip_black", "dip_white"]
TRANS_LABELS = ["Vervagen (fade)", "Schuif \u2190 links", "Schuif \u2192 rechts",
                "Schuif \u2191 omhoog", "Schuif \u2193 omlaag", "Veeg \u2190 links",
                "Veeg \u2192 rechts", "Zoom", "Dip naar zwart", "Dip naar wit"]
FILTER_KEYS = ["none", "gray", "sepia", "negative"]
FILTER_LABELS = ["Geen", "Grijswaarden", "Sepia", "Negatief"]


def _trans_index(key):
    return TRANS_KEYS.index(key) if key in TRANS_KEYS else 0


def _filter_index(key):
    return FILTER_KEYS.index(key) if key in FILTER_KEYS else 0


# Herkende media-extensies (voor losse import en map-import)
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma", ".aif", ".aiff"}


def kind_for_ext(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AUDIO_EXTS:
        return "audio"
    return None


# =========================================================================== #
#  BEELD-HELPERS  (QImage <-> PIL / numpy)
# =========================================================================== #
def _qimage_png_bytes(qimg):
    buf = QBuffer()
    buf.open(QIODevice.ReadWrite)
    qimg.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return data


def qimage_to_b64(qimg):
    return base64.b64encode(_qimage_png_bytes(qimg)).decode("ascii")


def b64_to_qimage(s):
    img = QImage()
    img.loadFromData(base64.b64decode(s), "PNG")
    return img.convertToFormat(QImage.Format_ARGB32)


def qimage_to_pil(qimg):
    return Image.open(io.BytesIO(_qimage_png_bytes(qimg))).convert("RGB")


def qimage_to_rgb_array(qimg):
    """QImage -> HxWx3 uint8 (RGB), zonder stride-padding."""
    img = qimg.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(h * bpl)
    arr = np.frombuffer(ptr, np.uint8).reshape((h, bpl))
    return arr[:, : w * 3].reshape((h, w, 3)).copy()


def bgr_array_to_qimage(frame):
    """OpenCV-frame (BGR ndarray) -> QImage (RGB)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


def qimage_to_rgba_array(qimg):
    """QImage -> HxWx4 uint8 (RGBA), zonder stride-padding."""
    img = qimg.convertToFormat(QImage.Format_RGBA8888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(h * bpl)
    arr = np.frombuffer(ptr, np.uint8).reshape((h, bpl))
    return arr[:, : w * 4].reshape((h, w, 4)).copy()


def rgba_array_to_qimage(arr):
    """HxWx4 uint8 (RGBA) -> QImage."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w, _ = arr.shape
    return QImage(arr.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()


DEFAULT_EFFECTS = {"brightness": 0.0, "contrast": 0.0, "saturation": 0.0, "blur": 0.0}


def effects_active(fx, filt="none"):
    return filt != "none" or any(abs(fx.get(k, 0.0)) > 1e-6 for k in DEFAULT_EFFECTS)


def apply_effects(qimg, fx, filt="none"):
    """Pas helderheid/contrast/verzadiging/filter/vervaging toe; behoudt alpha."""
    if qimg is None or qimg.isNull() or not HAVE_NUMPY or not effects_active(fx, filt):
        return qimg
    arr = qimage_to_rgba_array(qimg).astype(np.float32)
    rgb = arr[..., :3]
    a = arr[..., 3:]
    b = fx.get("brightness", 0.0) / 100.0 * 128.0      # -128..+128
    if b:
        rgb = rgb + b
    c = fx.get("contrast", 0.0) / 100.0                # -1..+1 -> factor 0..2
    if c:
        rgb = (rgb - 128.0) * (1.0 + c) + 128.0
    s = fx.get("saturation", 0.0) / 100.0              # -1..+1
    if s:
        lum = (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 +
               rgb[..., 2] * 0.114)[..., None]
        rgb = lum + (rgb - lum) * (1.0 + s)
    if filt == "gray":
        lum = (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114)
        rgb = np.repeat(lum[..., None], 3, axis=-1)
    elif filt == "sepia":
        r, g, bl = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        rgb = np.stack([0.393 * r + 0.769 * g + 0.189 * bl,
                        0.349 * r + 0.686 * g + 0.168 * bl,
                        0.272 * r + 0.534 * g + 0.131 * bl], axis=-1)
    elif filt == "negative":
        rgb = 255.0 - rgb
    out = np.concatenate([np.clip(rgb, 0, 255), a], axis=-1).astype(np.uint8)
    bl = int(fx.get("blur", 0.0))
    if bl > 0 and HAVE_CV2:
        k = bl * 2 + 1
        out = cv2.GaussianBlur(out, (k, k), 0)
    return rgba_array_to_qimage(out)


def fade_factor(fade_in, fade_out, t_local, dur):
    """Extra opaciteit (0..1) voor een eenvoudige fade-in/uit (fallback)."""
    f = 1.0
    if fade_in > 0 and t_local < fade_in:
        f *= max(0.0, t_local / fade_in)
    if fade_out > 0 and t_local > dur - fade_out:
        f *= max(0.0, (dur - t_local) / fade_out)
    return max(0.0, min(1.0, f))


def _apply_transition(ttype, p, W, H, mods):
    """p: 0 = volledig weg, 1 = volledig aanwezig. Vult 'mods' aan."""
    if ttype == "fade":
        mods["op"] *= p
    elif ttype == "slide_l":
        mods["dx"] += -(1.0 - p) * W
    elif ttype == "slide_r":
        mods["dx"] += (1.0 - p) * W
    elif ttype == "slide_u":
        mods["dy"] += -(1.0 - p) * H
    elif ttype == "slide_d":
        mods["dy"] += (1.0 - p) * H
    elif ttype == "zoom":
        mods["smul"] *= max(0.0, p)
    elif ttype in ("wipe_l", "wipe_r", "wipe_u", "wipe_d"):
        if mods["wipe"] is None or p < mods["wipe"][1]:
            mods["wipe"] = (ttype, p)
    elif ttype == "dip_black":
        mods["overlay"] = ("#000000", 1.0 - p)
    elif ttype == "dip_white":
        mods["overlay"] = ("#ffffff", 1.0 - p)


def draw_clip_with_transition(painter, src, W, H, clip, t_local):
    """Teken een clip met transform + in/uit-transitie (fade, schuif, veeg, zoom, dip)."""
    if src is None or src.isNull():
        return
    sw, sh = src.width(), src.height()
    if sw == 0 or sh == 0:
        return
    tf = clip.transform
    base = min(W / sw, H / sh)
    scale_pct = max(0.0, tf.scale.value_at(t_local) / 100.0)
    cx = W / 2.0 + tf.x.value_at(t_local)
    cy = H / 2.0 + tf.y.value_at(t_local)
    op = max(0.0, min(1.0, tf.opacity.value_at(t_local) / 100.0))
    rot = tf.rotation.value_at(t_local)
    dur = clip.duration()
    mods = {"op": 1.0, "dx": 0.0, "dy": 0.0, "smul": 1.0, "wipe": None, "overlay": None}
    fin = getattr(clip, "fade_in", 0.0)
    fout = getattr(clip, "fade_out", 0.0)
    if fin > 0 and t_local < fin:
        _apply_transition(getattr(clip, "trans_in", "fade"),
                          max(0.0, min(1.0, t_local / fin)), W, H, mods)
    if fout > 0 and t_local > dur - fout:
        _apply_transition(getattr(clip, "trans_out", "fade"),
                          max(0.0, min(1.0, (dur - t_local) / fout)), W, H, mods)
    op *= mods["op"]
    scale = base * scale_pct * mods["smul"]
    tw, th = sw * scale, sh * scale
    if op > 0.0 and tw > 0.0 and th > 0.0:
        painter.save()
        painter.setOpacity(op)
        painter.translate(cx + mods["dx"], cy + mods["dy"])
        if rot:
            painter.rotate(rot)
        if mods["wipe"] is not None:
            d, frac = mods["wipe"]
            frac = max(0.0, min(1.0, frac))
            left, top = -tw / 2.0, -th / 2.0
            if d == "wipe_l":
                painter.setClipRect(QRectF(left, top, tw * frac, th))
            elif d == "wipe_r":
                painter.setClipRect(QRectF(left + tw * (1.0 - frac), top, tw * frac, th))
            elif d == "wipe_u":
                painter.setClipRect(QRectF(left, top, tw, th * frac))
            elif d == "wipe_d":
                painter.setClipRect(QRectF(left, top + th * (1.0 - frac), tw, th * frac))
        painter.drawImage(QRectF(-tw / 2.0, -th / 2.0, tw, th), src)
        painter.restore()
    if mods["overlay"] is not None:
        col, a = mods["overlay"]
        a = max(0.0, min(1.0, a))
        if a > 0.0:
            painter.save(); painter.setOpacity(a)
            painter.fillRect(QRectF(0, 0, W, H), QColor(col)); painter.restore()


def draw_fitted(painter, src, w, h):
    """Teken src binnen (w,h) met behoud van verhouding, gecentreerd."""
    if src is None or src.isNull():
        return
    sw, sh = src.width(), src.height()
    if sw == 0 or sh == 0:
        return
    scale = min(w / sw, h / sh)
    tw, th = sw * scale, sh * scale
    x, y = (w - tw) / 2.0, (h - th) / 2.0
    painter.drawImage(QRectF(x, y, tw, th), src)


def draw_clip(painter, src, W, H, tf, t_local, extra_opacity=1.0):
    """Teken src binnen (W,H) met behoud van verhouding + de transform van de clip."""
    if src is None or src.isNull():
        return
    sw, sh = src.width(), src.height()
    if sw == 0 or sh == 0:
        return
    base = min(W / sw, H / sh)                      # passend maken (fit)
    sc = max(0.0, tf.scale.value_at(t_local) / 100.0)
    scale = base * sc
    tw, th = sw * scale, sh * scale
    cx = W / 2.0 + tf.x.value_at(t_local)
    cy = H / 2.0 + tf.y.value_at(t_local)
    op = max(0.0, min(1.0, tf.opacity.value_at(t_local) / 100.0)) * extra_opacity
    if op <= 0.0:
        return
    rot = tf.rotation.value_at(t_local)
    painter.save()
    painter.setOpacity(op)
    painter.translate(cx, cy)
    if rot:
        painter.rotate(rot)
    painter.drawImage(QRectF(-tw / 2.0, -th / 2.0, tw, th), src)
    painter.restore()


# =========================================================================== #
#  KEYFRAMES + TRANSFORM
# =========================================================================== #
class Keyable:
    """Een animeerbare scalair-eigenschap met optionele keyframes (lokale tijd)."""

    def __init__(self, default):
        self.default = float(default)
        self.keys = []  # [[t_local, value], ...] gesorteerd op t

    def is_animated(self):
        return len(self.keys) > 0

    def value_at(self, t):
        if not self.keys:
            return self.default
        if t <= self.keys[0][0]:
            return self.keys[0][1]
        if t >= self.keys[-1][0]:
            return self.keys[-1][1]
        for i in range(len(self.keys) - 1):
            t0, v0 = self.keys[i]
            t1, v1 = self.keys[i + 1]
            if t0 <= t <= t1:
                f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return v0 + (v1 - v0) * f
        return self.keys[-1][1]

    def key_at(self, t, tol=1e-3):
        for k in self.keys:
            if abs(k[0] - t) <= tol:
                return k
        return None

    def set_key(self, t, value):
        t = round(float(t), 3)
        k = self.key_at(t)
        if k is not None:
            k[1] = float(value)
        else:
            self.keys.append([t, float(value)])
            self.keys.sort(key=lambda kk: kk[0])

    def remove_key(self, t):
        self.keys = [k for k in self.keys if abs(k[0] - t) > 1e-3]

    def to_dict(self):
        return {"default": self.default, "keys": self.keys}

    @classmethod
    def from_dict(cls, d):
        k = cls(d.get("default", 0.0))
        k.keys = [[float(a), float(b)] for a, b in d.get("keys", [])]
        return k


class Transform:
    def __init__(self):
        self.x = Keyable(0.0)          # px-verschuiving (0 = gecentreerd)
        self.y = Keyable(0.0)
        self.scale = Keyable(100.0)    # procent
        self.rotation = Keyable(0.0)   # graden
        self.opacity = Keyable(100.0)  # procent

    def props(self):
        return {"x": self.x, "y": self.y, "scale": self.scale,
                "rotation": self.rotation, "opacity": self.opacity}

    def key_times(self):
        ts = set()
        for k in self.props().values():
            for kk in k.keys:
                ts.add(round(kk[0], 3))
        return sorted(ts)

    def to_dict(self):
        return {name: k.to_dict() for name, k in self.props().items()}

    @classmethod
    def from_dict(cls, d):
        t = cls()
        for name in t.props():
            if name in d:
                setattr(t, name, Keyable.from_dict(d[name]))
        return t


# =========================================================================== #
#  TEKEN-ENGINE  (frame-by-frame)
# =========================================================================== #
class AnimationModel:
    def __init__(self, width=640, height=360, fps=12):
        self.width, self.height, self.fps = width, height, fps
        self.frames = [self._blank()]
        self.current = 0

    def _blank(self):
        img = QImage(self.width, self.height, QImage.Format_ARGB32)
        img.fill(QColor("white"))
        return img

    @property
    def frame(self):
        return self.frames[self.current]

    def add_frame(self, duplicate=False):
        src = self.frame.copy() if duplicate else self._blank()
        self.frames.insert(self.current + 1, src)
        self.current += 1

    def delete_frame(self):
        if len(self.frames) <= 1:
            self.frames[0] = self._blank()
            return
        del self.frames[self.current]
        self.current = min(self.current, len(self.frames) - 1)

    def move_to(self, i):
        self.current = max(0, min(i, len(self.frames) - 1))

    def to_dict(self):
        return {"width": self.width, "height": self.height, "fps": self.fps,
                "frames": [qimage_to_b64(f) for f in self.frames]}

    @classmethod
    def from_dict(cls, d):
        m = cls(d["width"], d["height"], d.get("fps", 12))
        m.frames = [b64_to_qimage(s) for s in d["frames"]]
        m.current = 0
        return m


class Canvas(QWidget):
    """Tekenoppervlak met onion skin + undo (gebruikt in de scene-editor)."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.disp_scale = 1.0
        self.guide = None          # hulplijn (bv. poppetje) om overheen te tekenen
        self.setFixedSize(model.width, model.height)
        self.setCursor(Qt.CrossCursor)
        self.tool, self.color, self.brush, self.onion = PEN, QColor("black"), 4, False
        self._drawing, self._last, self._line_start = False, QPoint(), QPoint()
        self._line_base = None
        self._undo = deque(maxlen=40)
        self.on_change = None

    def set_display_scale(self, s):
        self.disp_scale = max(0.1, float(s))
        self.setFixedSize(int(self.model.width * self.disp_scale),
                          int(self.model.height * self.disp_scale))
        self.update()

    def set_guide(self, img):
        self.guide = img; self.update()

    def _snapshot(self):
        self._undo.append((self.model.current, self.model.frame.copy()))

    def undo(self):
        if not self._undo:
            return
        i, img = self._undo.pop()
        if i < len(self.model.frames):
            self.model.frames[i] = img
            self.model.current = i
        self.update()
        self._notify()

    def _notify(self):
        if self.on_change:
            self.on_change()

    def clear_frame(self):
        self._snapshot()
        self.model.frame.fill(QColor("white"))
        self.update()
        self._notify()

    def _pen(self):
        col = QColor("white") if self.tool == ERASER else self.color
        size = self.brush * 2 if self.tool == ERASER else self.brush
        return QPen(col, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def _clamp(self, p):
        return QPoint(max(0, min(p.x(), self.model.width - 1)),
                      max(0, min(p.y(), self.model.height - 1)))

    def _pos(self, ev):
        s = self.disp_scale
        return self._clamp(QPoint(int(ev.x() / s), int(ev.y() / s)))

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        pos = self._pos(ev)
        self._snapshot()
        if self.tool == FILL:
            self._flood_fill(pos.x(), pos.y(), self.color)
            self.update(); self._notify(); return
        if self.tool == LINE:
            self._drawing, self._line_start = True, pos
            self._line_base = self.model.frame.copy(); return
        self._drawing, self._last = True, pos
        p = QPainter(self.model.frame); p.setPen(self._pen()); p.drawPoint(pos); p.end()
        self.update()

    def mouseMoveEvent(self, ev):
        if not self._drawing:
            return
        pos = self._pos(ev)
        if self.tool == LINE:
            self.model.frames[self.model.current] = self._line_base.copy()
            p = QPainter(self.model.frame); p.setPen(self._pen())
            p.drawLine(self._line_start, pos); p.end(); self.update(); return
        p = QPainter(self.model.frame); p.setPen(self._pen())
        p.drawLine(self._last, pos); p.end()
        self._last = pos; self.update()

    def mouseReleaseEvent(self, ev):
        if self._drawing:
            self._drawing, self._line_base = False, None
            self._notify()

    def _flood_fill(self, x, y, color):
        img = self.model.frame
        target, repl = img.pixel(x, y), color.rgba()
        if target == repl:
            return
        w, h = img.width(), img.height()
        stack, seen, cap, n = [(x, y)], set(), w * h, 0
        while stack and n < cap:
            cx, cy = stack.pop()
            if (cx, cy) in seen or cx < 0 or cy < 0 or cx >= w or cy >= h:
                continue
            if img.pixel(cx, cy) != target:
                continue
            seen.add((cx, cy)); img.setPixel(cx, cy, repl); n += 1
            stack += [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.scale(self.disp_scale, self.disp_scale)
        W, H = self.model.width, self.model.height
        p.fillRect(0, 0, W, H, QColor("white"))
        if self.onion:
            if self.model.current > 0:
                p.setOpacity(0.30); p.drawImage(0, 0, self.model.frames[self.model.current - 1])
            if self.model.current < len(self.model.frames) - 1:
                p.setOpacity(0.30); p.drawImage(0, 0, self.model.frames[self.model.current + 1])
            p.setOpacity(1.0)
        p.drawImage(0, 0, self.model.frame)
        if self.guide is not None and not self.guide.isNull():
            p.setOpacity(0.35); p.drawImage(0, 0, self.guide); p.setOpacity(1.0)
        p.setPen(QColor("#cccccc")); p.drawRect(0, 0, W - 1, H - 1)
        p.end()


# =========================================================================== #
#  TIJDLIJN-MODEL  (clips, sporen, project, compositor)
# =========================================================================== #
class Clip:
    KIND = "clip"

    def __init__(self, name, start=0.0):
        self.name = name
        self.start = float(start)
        self.transform = Transform()
        self.fade_in = 0.0
        self.fade_out = 0.0
        self.trans_in = "fade"
        self.trans_out = "fade"
        self.effects = dict(DEFAULT_EFFECTS)
        self.filter = "none"

    def duration(self):
        return 1.0

    def image_at(self, t_local):
        return None

    def to_dict(self):
        return {"kind": self.KIND, "name": self.name, "start": self.start,
                "transform": self.transform.to_dict(),
                "fade_in": self.fade_in, "fade_out": self.fade_out,
                "trans_in": self.trans_in, "trans_out": self.trans_out,
                "effects": dict(self.effects), "filter": self.filter}


class DrawnSceneClip(Clip):
    KIND = "scene"

    def __init__(self, model=None, name="Tekenscene", start=0.0):
        super().__init__(name, start)
        self.model = model or AnimationModel()

    def duration(self):
        return max(1, len(self.model.frames)) / float(self.model.fps)

    def image_at(self, t_local):
        idx = int(t_local * self.model.fps)
        idx = max(0, min(idx, len(self.model.frames) - 1))
        return self.model.frames[idx]

    def to_dict(self):
        d = super().to_dict(); d["model"] = self.model.to_dict(); return d

    @classmethod
    def from_dict(cls, d):
        return cls(AnimationModel.from_dict(d["model"]), d["name"], d["start"])


class ImageClip(Clip):
    KIND = "image"

    def __init__(self, path, name=None, start=0.0, dur=3.0):
        super().__init__(name or os.path.basename(path), start)
        self.path = path
        self._dur = float(dur)
        self._img = self._load(path)
        # ---- praat mee met de stem (eenvoudige modus, auto-mond) ----
        self.talk = False
        self.mouth_x = 0.5
        self.mouth_y = 0.62
        self.mouth_size = 0.06

    @staticmethod
    def _load(path):
        """Laad een afbeelding; render SVG scherp op een nette grootte."""
        if path and path.lower().endswith(".svg"):
            try:
                from PyQt5.QtSvg import QSvgRenderer
                rend = QSvgRenderer(path)
                if rend.isValid():
                    sz = rend.defaultSize()
                    w, h = sz.width(), sz.height()
                    if w <= 0 or h <= 0:
                        w = h = 512
                    scale = 1.0
                    if min(w, h) < 512:
                        scale = 512.0 / min(w, h)
                    img = QImage(int(w * scale), int(h * scale), QImage.Format_ARGB32)
                    img.fill(Qt.transparent)
                    pr = QPainter(img); rend.render(pr); pr.end()
                    return img
            except Exception:  # noqa: BLE001
                pass
        return QImage(path)

    def duration(self):
        return self._dur

    def set_duration(self, d):
        self._dur = max(0.1, float(d))

    def image_at(self, t_local):
        return self._img if not self._img.isNull() else None

    def render_talk(self, t_local, amt):
        if self._img.isNull():
            return None
        img = self._img.copy()
        draw_auto_mouth(img, self.mouth_x, self.mouth_y, self.mouth_size, amt)
        return img

    def to_dict(self):
        d = super().to_dict(); d["path"] = self.path; d["dur"] = self._dur
        d.update(talk=bool(self.talk), mouth_x=self.mouth_x, mouth_y=self.mouth_y,
                 mouth_size=self.mouth_size)
        return d

    @classmethod
    def from_dict(cls, d):
        c = cls(d["path"], d["name"], d["start"], d.get("dur", 3.0))
        c.talk = bool(d.get("talk", False))
        c.mouth_x = float(d.get("mouth_x", 0.5))
        c.mouth_y = float(d.get("mouth_y", 0.62))
        c.mouth_size = float(d.get("mouth_size", 0.06))
        return c


class VideoClip(Clip):
    KIND = "video"

    def __init__(self, path, name=None, start=0.0, in_point=0.0, out_point=None):
        super().__init__(name or os.path.basename(path), start)
        self.path = path
        self._cap = None
        self.src_fps = 25.0
        self.src_frames = 0
        self.src_dur = 0.0
        self.speed = 1.0  # afspeelsnelheid (>1 = sneller/timelapse, <1 = slow motion)
        self.volume = 100.0  # procent (geluid uit de video)
        if HAVE_CV2:
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                self.src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                self.src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                self.src_dur = (self.src_frames / self.src_fps) if self.src_fps else 0.0
            cap.release()
        self.in_point = float(in_point)
        self.out_point = float(out_point) if out_point is not None else self.src_dur

    def _capture(self):
        if self._cap is None and HAVE_CV2:
            self._cap = cv2.VideoCapture(self.path)
        return self._cap

    def duration(self):
        return max(0.1, (self.out_point - self.in_point) / max(0.01, self.speed))

    def image_at(self, t_local):
        cap = self._capture()
        if cap is None or not cap.isOpened():
            return None
        frame_idx = int((self.in_point + t_local * self.speed) * self.src_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            return None
        return bgr_array_to_qimage(frame)

    def to_dict(self):
        d = super().to_dict()
        d.update(path=self.path, in_point=self.in_point, out_point=self.out_point,
                 speed=self.speed, volume=self.volume)
        return d

    @classmethod
    def from_dict(cls, d):
        c = cls(d["path"], d["name"], d["start"], d.get("in_point", 0.0),
                d.get("out_point"))
        c.speed = d.get("speed", 1.0) or 1.0
        c.volume = d.get("volume", 100.0)
        return c


def ffmpeg_exe():
    """Pad naar de ffmpeg-binary, of None.

    Zoekt in deze volgorde, zodat het werkt of ffmpeg nu IN de .exe is gebundeld
    (onefile -> uitgepakt in sys._MEIPASS) óf los naast de app staat:
      1) in de .exe gebundeld (root of bin/),
      2) los in bin/ naast de app,
      3) IMAGEIO_FFMPEG_EXE,
      4) imageio_ffmpeg (los pip-pakket).
    """
    names = ["ffmpeg.exe", "ffmpeg"] if os.name == "nt" else ["ffmpeg"]
    cand = []
    for n in names:
        cand.append(resource_path(n))                       # gebundeld in de root
        cand.append(resource_path(os.path.join("bin", n)))  # gebundeld in bin/
    cand.append(_ff_local)                                   # los in bin/ naast de app
    for c in cand:
        if c and os.path.exists(c):
            return c
    env = os.environ.get("IMAGEIO_FFMPEG_EXE")
    if env and os.path.exists(env):
        return env
    if not HAVE_FFMPEG:
        return None
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def probe_duration(path, fallback=5.0):
    """Lees de mediaduur (s) uit met ffmpeg; val terug op fallback."""
    ff = ffmpeg_exe()
    if not ff:
        return fallback
    try:
        out = subprocess.run([ff, "-i", path], capture_output=True, text=True).stderr
        for line in out.splitlines():
            if "Duration:" in line:
                hms = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = hms.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:  # noqa: BLE001
        pass
    return fallback


class AudioClip(Clip):
    KIND = "audio"

    def __init__(self, path, name=None, start=0.0, in_point=0.0, out_point=None):
        super().__init__(name or os.path.basename(path), start)
        self.path = path
        self.src_dur = probe_duration(path)
        self.in_point = float(in_point)
        self.out_point = float(out_point) if out_point is not None else self.src_dur
        self.volume = 100.0  # procent

    def duration(self):
        return max(0.1, self.out_point - self.in_point)

    def image_at(self, t_local):
        return None  # audio levert geen beeld; alleen hoorbaar in de export

    def to_dict(self):
        d = super().to_dict()
        d.update(path=self.path, in_point=self.in_point, out_point=self.out_point,
                 volume=self.volume)
        return d

    @classmethod
    def from_dict(cls, d):
        c = cls(d["path"], d["name"], d["start"], d.get("in_point", 0.0),
                d.get("out_point"))
        c.volume = d.get("volume", 100.0)
        return c


class TextClip(Clip):
    KIND = "text"

    def __init__(self, text="Titel", name=None, start=0.0, dur=3.0,
                 size=64, color="#ffffff", bg=None, box_w=640, box_h=360,
                 font="Arial", text_width=None, bg_opacity=100):
        super().__init__(name or "Tekst", start)
        self.text = text
        self._dur = float(dur)
        self.size = int(size)
        self.color = color
        self.bg = bg  # None of hex-string voor een vlak achtergrondkader
        self.bg_opacity = int(bg_opacity)  # 0 = transparant, 100 = vol
        self.box_w, self.box_h = int(box_w), int(box_h)
        self.font = font
        self.text_width = int(text_width) if text_width else int(box_w)
        self._cache, self._sig = None, None

    def duration(self):
        return self._dur

    def set_duration(self, d):
        self._dur = max(0.1, float(d))

    def _text_font(self):
        f = QFont(self.font or "Arial", self.size); f.setBold(True)
        return f

    def content_rect(self):
        """Strakke rechthoek (in beeldcoördinaten) waar de tekst staat, met marge."""
        fm = QFontMetrics(self._text_font())
        tw = max(20, min(int(self.text_width), self.box_w))
        band = QRect(int((self.box_w - tw) / 2), 0, tw, self.box_h)
        br = fm.boundingRect(band, Qt.AlignCenter | Qt.TextWordWrap, self.text or " ")
        pad = max(8, int(self.size * 0.18))
        r = QRectF(br.x() - pad, br.y() - pad,
                   br.width() + 2 * pad, br.height() + 2 * pad)
        # binnen het beeld houden
        x = max(0.0, r.x()); y = max(0.0, r.y())
        w = min(r.width(), self.box_w - x); h = min(r.height(), self.box_h - y)
        return QRectF(x, y, max(2.0, w), max(2.0, h))

    def _render(self):
        sig = (self.text, self.size, self.color, self.bg, self.bg_opacity,
               self.box_w, self.box_h, self.font, self.text_width)
        if self._cache is not None and self._sig == sig:
            return self._cache
        # beeld op projectgrootte (geen vervorming); tekst in een gecentreerde band
        img = QImage(self.box_w, self.box_h, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        tw = max(20, min(int(self.text_width), self.box_w))
        rect = QRectF((self.box_w - tw) / 2.0, 0, tw, self.box_h)
        if self.bg:
            col = QColor(self.bg)
            col.setAlpha(max(0, min(255, int(round(self.bg_opacity * 255 / 100)))))
            p.fillRect(self.content_rect(), col)   # strak achter de tekst, met dekking
        p.setFont(self._text_font())
        p.setPen(QColor(self.color))
        p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)
        p.end()
        self._cache, self._sig = img, sig
        return img

    def image_at(self, t_local):
        return self._render()

    def to_dict(self):
        d = super().to_dict()
        d.update(text=self.text, dur=self._dur, size=self.size, color=self.color,
                 bg=self.bg, bg_opacity=self.bg_opacity, box_w=self.box_w, box_h=self.box_h,
                 font=self.font, text_width=self.text_width)
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("text", "Titel"), d.get("name"), d["start"], d.get("dur", 3.0),
                   d.get("size", 64), d.get("color", "#ffffff"), d.get("bg"),
                   d.get("box_w", 640), d.get("box_h", 360),
                   d.get("font", "Arial"), d.get("text_width"), d.get("bg_opacity", 100))


class EndCreditsClip(Clip):
    """Aftiteling: titel + gelabelde regels (auteur, muziek, copyright, dank, extra),
    optioneel rollend van onder naar boven."""
    KIND = "credits"

    def __init__(self, title="Aftiteling", author="", copyright="", song="",
                 thanks="", extra="", name=None, start=0.0, dur=10.0,
                 size=44, color="#ffffff", font="Arial", scroll=True,
                 box_w=1280, box_h=720):
        super().__init__(name or "Aftiteling", start)
        self.title = title
        self.author = author
        self.copyright = copyright
        self.song = song
        self.thanks = thanks
        self.extra = extra
        self._dur = float(dur)
        self.size = int(size)
        self.color = color
        self.font = font
        self.scroll = bool(scroll)
        self.box_w, self.box_h = int(box_w), int(box_h)

    def duration(self):
        return self._dur

    def set_duration(self, d):
        self._dur = max(0.1, float(d))

    def _lines(self):
        out = []
        if self.title.strip():
            out.append(("title", self.title.strip()))

        def block(label, value):
            v = (value or "").strip()
            if not v:
                return
            out.append(("blank", ""))
            out.append(("label", label))
            for ln in v.splitlines():
                out.append(("value", ln))

        block("Auteur", self.author)
        block("Muziek", self.song)
        block("Met dank aan", self.thanks)
        if (self.copyright or "").strip():
            out.append(("blank", ""))
            out.append(("value", "© " + self.copyright.strip()))
        if (self.extra or "").strip():
            out.append(("blank", ""))
            for ln in self.extra.splitlines():
                out.append(("plain", ln))
        return out

    def _fonts(self):
        title_f = QFont(self.font or "Arial", max(8, int(self.size * 1.5))); title_f.setBold(True)
        label_f = QFont(self.font or "Arial", max(8, int(self.size * 0.7)))
        value_f = QFont(self.font or "Arial", self.size); value_f.setBold(True)
        return title_f, label_f, value_f

    def image_at(self, t_local):
        W, H = self.box_w, self.box_h
        img = QImage(W, H, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        title_f, label_f, value_f = self._fonts()
        gap = max(4, int(self.size * 0.35))
        items = []
        for kind, txt in self._lines():
            if kind == "blank":
                items.append((kind, txt, None, gap)); continue
            f = title_f if kind == "title" else (label_f if kind == "label" else value_f)
            items.append((kind, txt, f, QFontMetrics(f).height()))
        total = sum(h for _, _, _, h in items) + gap * max(1, len(items))
        if self.scroll and self._dur > 0:
            fr = max(0.0, min(1.0, t_local / self._dur))
            y = H - fr * (H + total)
        else:
            y = (H - total) / 2.0
        for kind, txt, fnt, h in items:
            if kind == "blank":
                y += h; continue
            p.setFont(fnt)
            p.setPen(QColor("#9aa0a8") if kind == "label" else QColor(self.color))
            p.drawText(QRectF(0, y, W, h), Qt.AlignHCenter | Qt.AlignVCenter, txt)
            y += h + gap
        p.end()
        return img

    def to_dict(self):
        d = super().to_dict()
        d.update(title=self.title, author=self.author, copyright=self.copyright,
                 song=self.song, thanks=self.thanks, extra=self.extra,
                 dur=self._dur, size=self.size, color=self.color, font=self.font,
                 scroll=self.scroll, box_w=self.box_w, box_h=self.box_h)
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("title", "Aftiteling"), d.get("author", ""),
                   d.get("copyright", ""), d.get("song", ""), d.get("thanks", ""),
                   d.get("extra", ""), d.get("name"), d["start"], d.get("dur", 10.0),
                   d.get("size", 44), d.get("color", "#ffffff"),
                   d.get("font", "Arial"), d.get("scroll", True),
                   d.get("box_w", 1280), d.get("box_h", 720))


class StickFigureClip(Clip):
    """Vector-poppetje met skelet; per frame een houding (frame-voor-frame)."""
    KIND = "figure"

    # gewrichten in een vierkante 0..1-ruimte (y omlaag); rust-houding
    REST = {
        "head": (0.50, 0.12), "neck": (0.50, 0.24), "hip": (0.50, 0.56),
        "l_elbow": (0.40, 0.40), "l_hand": (0.33, 0.52),
        "r_elbow": (0.60, 0.40), "r_hand": (0.67, 0.52),
        "l_knee": (0.45, 0.74), "l_foot": (0.43, 0.94),
        "r_knee": (0.55, 0.74), "r_foot": (0.57, 0.94),
    }
    BONES = [("neck", "hip"),
             ("neck", "l_elbow"), ("l_elbow", "l_hand"),
             ("neck", "r_elbow"), ("r_elbow", "r_hand"),
             ("hip", "l_knee"), ("l_knee", "l_foot"),
             ("hip", "r_knee"), ("r_knee", "r_foot")]
    JOINTS = list(REST.keys())

    def __init__(self, frames=None, name=None, start=0.0, fps=12,
                 color="#e6e6e6", line_w=4):
        super().__init__(name or "Stok-poppetje", start)
        self.fps = int(fps)
        self.color = color
        self.line_w = int(line_w)
        self.frames = frames if frames else [dict(self.REST)]

    def duration(self):
        return max(0.1, len(self.frames) / max(1, self.fps))

    def pose_at(self, idx):
        if not self.frames:
            return dict(self.REST)
        return self.frames[max(0, min(idx, len(self.frames) - 1))]

    @staticmethod
    def render_pose(pose, W, H, color="#e6e6e6", line_w=4, square=True):
        img = QImage(W, H, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        if square:
            s = min(W, H); ox = (W - s) / 2.0; oy = (H - s) / 2.0
            def P(name):
                jx, jy = pose.get(name, StickFigureClip.REST[name])
                return QPointF(ox + jx * s, oy + jy * s)
            rr = 0.055 * s
        else:
            s = min(W, H)
            def P(name):
                jx, jy = pose.get(name, StickFigureClip.REST[name])
                return QPointF(jx * W, jy * H)
            rr = 0.055 * s
        lw = max(2, int(line_w * s / 360.0))
        pen = QPen(QColor(color), lw); pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        for a, b in StickFigureClip.BONES:
            p.drawLine(P(a), P(b))
        hc = P("head")
        p.drawLine(P("neck"), QPointF(hc.x(), hc.y() + rr))
        p.drawEllipse(hc, rr, rr)
        p.end()
        return img

    def image_at(self, t_local):
        idx = int(t_local * self.fps)
        return self.render_pose(self.pose_at(idx), 1280, 1280,
                                self.color, self.line_w)

    def to_dict(self):
        d = super().to_dict()
        d.update(fps=self.fps, color=self.color, line_w=self.line_w,
                 frames=[{k: [round(v[0], 4), round(v[1], 4)] for k, v in f.items()}
                         for f in self.frames])
        return d

    @classmethod
    def from_dict(cls, d):
        frames = []
        for f in d.get("frames", []):
            frames.append({k: (float(v[0]), float(v[1])) for k, v in f.items()})
        return cls(frames or None, d.get("name"), d["start"],
                   d.get("fps", 12), d.get("color", "#e6e6e6"), d.get("line_w", 4))


class StudioClip(Clip):
    """Gecombineerde animatie: per frame een tekening (raster) + een skelet-mal.

    Elk frame heeft altijd een houding (pose) die in het Tekenen-tabblad als
    lichte hulplijn dient. self.bake[i] bepaalt of dat skelet ook in het
    eindbeeld (de video) getekend wordt; zet je het uit, dan blijft alleen je
    eigen tekening over.
    """
    KIND = "studio"

    def __init__(self, model=None, poses=None, bake=None, name=None, start=0.0,
                 fig_color="#000000", fig_line_w=6):
        super().__init__(name or "Studio", start)
        self.model = model or AnimationModel()
        n = len(self.model.frames)
        raw = list(poses) if poses else [dict(StickFigureClip.REST)]
        self.poses, self.bake = [], []
        for i in range(n):
            p = raw[i] if i < len(raw) else None
            if p is None:                      # legacy/leeg -> pose als mal, niet bakken
                self.poses.append(dict(StickFigureClip.REST)); self.bake.append(False)
            else:
                self.poses.append({k: (float(v[0]), float(v[1])) for k, v in p.items()})
                self.bake.append(True)
        if bake is not None:
            for i in range(min(n, len(bake))):
                self.bake[i] = bool(bake[i])
        self.fig_color = fig_color
        self.fig_line_w = int(fig_line_w)

    def duration(self):
        return max(0.1, len(self.model.frames) / max(1, self.model.fps))

    def composite(self, idx):
        idx = max(0, min(idx, len(self.model.frames) - 1))
        base = self.model.frames[idx].copy()
        if idx < len(self.bake) and self.bake[idx]:
            fig = StickFigureClip.render_pose(self.poses[idx], base.width(), base.height(),
                                              self.fig_color, self.fig_line_w, square=False)
            p = QPainter(base); p.drawImage(0, 0, fig); p.end()
        return base

    def image_at(self, t_local):
        return self.composite(int(t_local * self.model.fps))

    def to_dict(self):
        d = super().to_dict()
        d.update(model=self.model.to_dict(), fig_color=self.fig_color,
                 fig_line_w=self.fig_line_w, bake=list(self.bake),
                 poses=[{k: [round(v[0], 4), round(v[1], 4)] for k, v in p.items()}
                        for p in self.poses])
        return d

    @classmethod
    def from_dict(cls, d):
        model = AnimationModel.from_dict(d["model"])
        poses = []
        for p in d.get("poses", []):
            poses.append(None if p is None else
                         {k: (float(v[0]), float(v[1])) for k, v in p.items()})
        return cls(model, poses or None, d.get("bake"), d.get("name"), d["start"],
                   d.get("fig_color", "#000000"), d.get("fig_line_w", 6))


def bone_transform(r1, r2, p1, p2, stretch=True):
    """Legt het rust-bot (r1->r2) op het pose-bot (p1->p2).
    stretch=True: rekt alleen in de lengte mee (dikte blijft gelijk).
    stretch=False: vast formaat, alleen draaien om het begin-gewricht."""
    sx, sy = r2[0] - r1[0], r2[1] - r1[1]
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ls = math.hypot(sx, sy) or 1e-6
    ld = math.hypot(dx, dy)
    ang_s = math.degrees(math.atan2(sy, sx))
    ang_d = math.degrees(math.atan2(dy, dx))
    t = QTransform()
    t.translate(p1[0], p1[1])
    if stretch:
        # draai naar de pose-richting, rek alleen langs de bot-as (dikte = 1)
        t.rotate(ang_d)
        t.scale((ld / ls) if ls else 1.0, 1.0)
        t.rotate(-ang_s)
    else:
        # alleen draaien, formaat blijft gelijk
        t.rotate(ang_d - ang_s)
    t.translate(-r1[0], -r1[1])
    return t


# botten waaraan je een lichaamsdeel kunt tekenen (incl. hoofd)
RIG_BONES = list(StickFigureClip.BONES) + [("neck", "head")]
RIG_LABELS = {
    ("neck", "hip"): "Romp", ("neck", "head"): "Hoofd / nek",
    ("neck", "l_elbow"): "Linkerbovenarm", ("l_elbow", "l_hand"): "Linkeronderarm",
    ("neck", "r_elbow"): "Rechterbovenarm", ("r_elbow", "r_hand"): "Rechteronderarm",
    ("hip", "l_knee"): "Linkerdijbeen", ("l_knee", "l_foot"): "Linkeronderbeen",
    ("hip", "r_knee"): "Rechterdijbeen", ("r_knee", "r_foot"): "Rechteronderbeen",
}

# Kant-en-klare skeletten (gewrichten met rust-positie 0..1, + botten als paren).
SKELETON_TEMPLATES = {
    "Mens": (dict(StickFigureClip.REST), list(RIG_BONES)),
    "Viervoeter (hond)": (
        {"head": (0.16, 0.40), "neck": (0.28, 0.42), "shoulder": (0.40, 0.45),
         "hip": (0.66, 0.45), "tail": (0.82, 0.38),
         "f_knee": (0.40, 0.68), "f_foot": (0.40, 0.92),
         "b_knee": (0.66, 0.68), "b_foot": (0.66, 0.92)},
        [("head", "neck"), ("neck", "shoulder"), ("shoulder", "hip"), ("hip", "tail"),
         ("shoulder", "f_knee"), ("f_knee", "f_foot"),
         ("hip", "b_knee"), ("b_knee", "b_foot")]),
    "Vogel": (
        {"head": (0.30, 0.30), "neck": (0.38, 0.38), "body": (0.50, 0.52),
         "tail": (0.72, 0.56), "wing": (0.54, 0.30),
         "knee": (0.50, 0.74), "foot": (0.50, 0.93)},
        [("head", "neck"), ("neck", "body"), ("body", "tail"), ("body", "wing"),
         ("body", "knee"), ("knee", "foot")]),
    "Eigen (leeg)": ({}, []),
}


def bone_label(bone, index):
    return RIG_LABELS.get(bone, f"Deel {index + 1}")


def skin_to_parts(rig, flat, overlap=None):
    """Verdeel één tekening (flat, in rust-pose) over de botten op basis van het
    dichtstbijzijnde bot. Met 'overlap' (pixels) horen pixels rond een gewricht bij
    meerdere botten tegelijk, zodat de naad bij het buigen gevuld blijft. Vereist numpy."""
    if not HAVE_NUMPY or not rig.bones:
        return False
    W, H = rig.width, rig.height
    if overlap is None:
        overlap = max(6.0, 0.03 * min(W, H))
    overlap = float(max(0.0, overlap))
    im = flat.convertToFormat(QImage.Format_RGBA8888)
    ptr = im.constBits(); ptr.setsize(H * W * 4)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(H, W, 4).copy()
    mask = arr[:, :, 3] > 10
    if not mask.any():
        return False
    ys, xs = np.mgrid[0:H, 0:W]
    xs = xs.astype(np.float32); ys = ys.astype(np.float32)
    dists = []
    for bone in rig.bones:
        ax, ay = rig._pt(bone[0], rig.joints)
        bx, by = rig._pt(bone[1], rig.joints)
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-6:
            d = np.hypot(xs - ax, ys - ay)
        else:
            t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / L2, 0.0, 1.0)
            d = np.hypot(xs - (ax + t * dx), ys - (ay + t * dy))
        dists.append(d.astype(np.float32))
    D = np.stack(dists, axis=0)          # (nbones, H, W)
    best = D.min(axis=0)                 # dichtstbijzijnde afstand per pixel
    for i, pt in enumerate(rig.parts):
        # pixel hoort bij dit bot als het (bijna) het dichtst is — de overlap-band
        # zorgt dat grenspixels bij meerdere botten horen (zachte naad)
        sel = mask & (D[i] <= best + overlap)
        out = np.zeros((H, W, 4), np.uint8)
        if sel.any():
            out[sel] = arr[sel]
        qi = QImage(out.tobytes(), W, H, QImage.Format_RGBA8888).convertToFormat(QImage.Format_ARGB32)
        pt["image"] = qi.copy()
        pt["art"] = bool(sel.any())
    return True


def audio_envelope(path, fps):
    """Leest een audiobestand (mp3/wav/…) en geeft per frame een luidheid 0..1 terug.
    Decodeert met ffmpeg (werkt dus ook met mp3) en valt terug op de wave-module."""
    if not HAVE_NUMPY:
        return []
    sr = 22050
    data = None
    ff = ffmpeg_exe()
    if ff:
        try:
            pr = subprocess.run([ff, "-v", "quiet", "-i", path, "-f", "s16le",
                                 "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
            if pr.stdout:
                data = np.frombuffer(pr.stdout, dtype="<i2").astype("float32") / 32768.0
        except Exception:  # noqa: BLE001
            data = None
    if data is None or data.size == 0:
        try:
            import wave
            import contextlib
            with contextlib.closing(wave.open(path, "r")) as wf:
                sr = wf.getframerate() or 22050
                ch = wf.getnchannels() or 1
                sw = wf.getsampwidth() or 2
                raw = wf.readframes(wf.getnframes())
            dt = {1: "int8", 2: "<i2", 4: "<i4"}.get(sw, "<i2")
            data = np.frombuffer(raw, dtype=dt).astype("float32")
            if ch > 1:
                data = data[: (data.size // ch) * ch].reshape(-1, ch).mean(axis=1)
            mx = float(np.max(np.abs(data))) if data.size else 0.0
            if mx > 1e-9:
                data = data / mx
        except Exception:  # noqa: BLE001
            return []
    if data is None or data.size == 0:
        return []
    dur = data.size / float(sr)
    n = max(1, int(math.ceil(dur * fps)))
    env = []
    for i in range(n):
        a = int(i / fps * sr)
        b = int((i + 1) / fps * sr)
        seg = data[a:b]
        env.append(float(np.sqrt(np.mean(seg * seg))) if seg.size else 0.0)
    mx = max(env) if env else 0.0
    if mx > 1e-9:
        env = [min(1.0, e / mx) for e in env]
    return env


ENV_FPS = 50          # resolutie van de luidheid-curve voor live lip-sync (50 = elke 20 ms)
_ENV_CACHE = {}


def voice_envelope(path):
    """Gecachete luidheid-curve (0..1) van een stembestand, op ENV_FPS."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        key = (path, 0)
    if key not in _ENV_CACHE:
        if len(_ENV_CACHE) > 40:
            _ENV_CACHE.clear()
        _ENV_CACHE[key] = audio_envelope(path, ENV_FPS)
    return _ENV_CACHE[key]


def draw_auto_mouth(img, mx, my, size_frac, amt):
    """Teken een eenvoudige mond op `img`: dichte streep of open (rode) ovaal,
    op genormaliseerde positie (mx,my), grootte size_frac×min(B,H). amt 0..1 stuurt open/dicht."""
    W, H = img.width(), img.height()
    cx, cy = mx * W, my * H
    r = max(3.0, size_frac * min(W, H))
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    if amt >= 0.5:
        p.setPen(QPen(QColor("#3a1414"), max(2, int(r * 0.28))))
        p.setBrush(QColor("#8a3030"))
        p.drawEllipse(QPointF(cx, cy), r, r * 0.78)
    else:
        pen = QPen(QColor("#3a1414"), max(2, int(r * 0.42))); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen); p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.end()


class RigClip(Clip):
    """Poppetje met skelet (rigging): je tekent elk lichaamsdeel één keer (op het rust-skelet);
    per frame poseer je alleen het skelet en de getekende delen bewegen mee (rigging)."""
    KIND = "rig"

    def __init__(self, parts=None, frames=None, name=None, start=0.0,
                 width=640, height=360, fps=12, joints=None, bones=None):
        super().__init__(name or "Poppetje met skelet", start)
        self.width, self.height, self.fps = int(width), int(height), int(fps)
        self.joints = dict(joints) if joints is not None else dict(StickFigureClip.REST)
        self.bones = list(bones) if bones is not None else list(RIG_BONES)
        # parts: per bot een transparant laag-image (in rust-pose getekend) + has_art vlag
        self.parts = parts if parts is not None else self._blank_parts()
        self.frames = frames if frames else [dict(self.joints)]
        self.stretch = True   # delen meerekken in de lengte (dikte blijft gelijk)
        # ---- mond / lip-sync ----
        self.mouth_closed = None   # QImage of None (in rust-coördinaten, hele canvas)
        self.mouth_open = None     # QImage of None
        self.mouth_bone = None     # (j1, j2) waarop de mond meebeweegt, of None (vast)
        self.mouth = []            # per frame 0..1 (mond open), uitgelijnd met frames
        self.talk = False          # eenvoudige modus: praat mee met het Stem-spoor
        self.talk_dur = None        # als 'talk' aan: vrij instelbare lengte (sec) op de tijdlijn

    @property
    def rest(self):
        return self.joints

    def _blank_image(self):
        img = QImage(self.width, self.height, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        return img

    def _blank_parts(self):
        return [{"bone": bone, "image": self._blank_image(), "art": False}
                for bone in self.bones]

    # ---- skelet aanpassen (vrij gewrichten/botten) ---------------------- #
    def new_joint_id(self):
        n = 1
        while f"j{n}" in self.joints:
            n += 1
        return f"j{n}"

    def add_joint(self, x, y, jid=None):
        jid = jid or self.new_joint_id()
        self.joints[jid] = (x, y)
        for f in self.frames:
            f.setdefault(jid, (x, y))
        return jid

    def add_bone(self, j1, j2):
        if j1 == j2 or (j1, j2) in self.bones or (j2, j1) in self.bones:
            return False
        self.bones.append((j1, j2))
        self.parts.append({"bone": (j1, j2), "image": self._blank_image(), "art": False})
        return True

    def rename_joint(self, old, new):
        new = (new or "").strip()
        if old not in self.joints or not new or new in self.joints:
            return False
        self.joints = {(new if k == old else k): v for k, v in self.joints.items()}
        self.bones = [tuple(new if x == old else x for x in b) for b in self.bones]
        for pt in self.parts:
            pt["bone"] = tuple(new if x == old else x for x in pt["bone"])
        for f in self.frames:
            if old in f:
                f[new] = f.pop(old)
        return True

    def delete_bone(self, bone):
        if bone in self.bones:
            self.bones.remove(bone)
        self.parts = [pt for pt in self.parts if pt["bone"] != bone]

    def split_bone(self, bone, x, y):
        """Voeg een gewricht toe midden in een bot: het bot wordt in twee botten gesplitst."""
        if bone not in self.bones:
            return None
        j1, j2 = bone
        jid = self.add_joint(x, y)
        self.delete_bone(bone)
        self.add_bone(j1, jid)
        self.add_bone(jid, j2)
        return jid

    def delete_joint(self, jid):
        self.joints.pop(jid, None)
        for b in [b for b in self.bones if jid in b]:
            self.delete_bone(b)
        for f in self.frames:
            f.pop(jid, None)

    def sync(self):
        """Zorg dat parts en frames overeenkomen met de huidige joints/bones."""
        have = {pt["bone"]: pt for pt in self.parts}
        self.parts = []
        for bone in self.bones:
            self.parts.append(have.get(bone) or
                              {"bone": bone, "image": self._blank_image(), "art": False})
        for f in self.frames:
            for jid, pos in self.joints.items():
                f.setdefault(jid, pos)
            for jid in [k for k in f if k not in self.joints]:
                f.pop(jid, None)

    def load_template(self, name):
        joints, bones = SKELETON_TEMPLATES.get(name, ({}, []))
        self.joints = {k: tuple(v) for k, v in joints.items()}
        self.bones = [tuple(b) for b in bones]
        self.parts = self._blank_parts()
        self.frames = [dict(self.joints)]

    def duration(self):
        if getattr(self, "talk", False) and getattr(self, "talk_dur", None):
            return max(0.1, float(self.talk_dur))
        return max(0.1, len(self.frames) / max(1, self.fps))

    def pose_at(self, idx):
        return self.frames[max(0, min(idx, len(self.frames) - 1))]

    def _pt(self, name, pose):
        jx, jy = pose.get(name, self.joints.get(name, (0.5, 0.5)))
        return (jx * self.width, jy * self.height)

    def render_pose(self, pose, fallback_skeleton=True, mouth_amt=0.0):
        img = QImage(self.width, self.height, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        any_art = any(pt["art"] for pt in self.parts)
        for pt in self.parts:
            j1, j2 = pt["bone"]
            r1, r2 = self._pt(j1, self.joints), self._pt(j2, self.joints)
            q1, q2 = self._pt(j1, pose), self._pt(j2, pose)
            if pt["art"]:
                p.setTransform(bone_transform(r1, r2, q1, q2, getattr(self, "stretch", True)))
                p.drawImage(0, 0, pt["image"])
                p.resetTransform()
            elif fallback_skeleton and not any_art:
                # nog niets getekend: laat het stok-skelet zien zodat je iets ziet
                pen = QPen(QColor("#000000"), max(2, int(min(self.width, self.height) / 90)))
                pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
                p.drawLine(QPointF(*q1), QPointF(*q2))
                if "head" in (j1, j2):
                    hp = q2 if j2 == "head" else q1
                    rr = 0.055 * min(self.width, self.height)
                    p.drawEllipse(QPointF(*hp), rr, rr)
        self._draw_mouth(p, pose, mouth_amt)
        p.end()
        return img

    def _draw_mouth(self, p, pose, amt):
        mc = getattr(self, "mouth_closed", None)
        mo = getattr(self, "mouth_open", None)
        if mc is None and mo is None:
            return
        if amt >= 0.5:
            mimg = mo if mo is not None else mc
        else:
            mimg = mc if mc is not None else None
        if mimg is None:
            return
        mb = getattr(self, "mouth_bone", None)
        if mb and mb[0] in self.joints and mb[1] in self.joints:
            r1, r2 = self._pt(mb[0], self.joints), self._pt(mb[1], self.joints)
            q1, q2 = self._pt(mb[0], pose), self._pt(mb[1], pose)
            p.setTransform(bone_transform(r1, r2, q1, q2, False))  # rigide: volgt, blijft even groot
            p.drawImage(0, 0, mimg); p.resetTransform()
        else:
            p.drawImage(0, 0, mimg)

    def render_frame(self, idx):
        """Render frame `idx` inclusief de juiste mondstand (open/dicht)."""
        idx = max(0, min(int(idx), len(self.frames) - 1))
        pose = self.frames[idx]
        m = getattr(self, "mouth", [])
        amt = m[idx] if idx < len(m) else 0.0
        return self.render_pose(pose, mouth_amt=amt)

    def render_talk(self, t_local, amt):
        """Render de houding van dit moment, maar met de mond gestuurd door de stem (amt 0..1)."""
        idx = max(0, min(int(t_local * self.fps), len(self.frames) - 1))
        return self.render_pose(self.frames[idx], mouth_amt=amt)

    def ensure_default_mouth(self):
        """Maak automatisch een eenvoudige open/dichte mond bij het hoofd, als er nog geen is."""
        if self.mouth_open is not None or self.mouth_closed is not None:
            return True
        if "head" not in self.joints:
            return False
        W, H = self.width, self.height
        hx, hy = self.joints["head"]
        cx, cy = hx * W, (hy + 0.02) * H
        r = 0.06 * min(W, H)
        mc = self._blank_image()
        p = QPainter(mc); p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#3a1414"), max(2, int(r * 0.20))); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen); p.drawLine(QPointF(cx - r * 0.5, cy), QPointF(cx + r * 0.5, cy)); p.end()
        mo = self._blank_image()
        p = QPainter(mo); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#3a1414"), max(2, int(r * 0.14))))
        p.setBrush(QColor("#8a3030"))
        p.drawEllipse(QPointF(cx, cy), r * 0.5, r * 0.40); p.end()
        self.mouth_closed, self.mouth_open = mc, mo
        if not self.mouth_bone:
            for b in self.bones:
                if "head" in b:
                    self.mouth_bone = b; break
        return True

    def apply_lipsync(self, audio_path, threshold=0.18, body_pose=None):
        """Maak frames die de mond per frame open/dicht zetten op basis van de luidheid
        van het audiobestand. Het lichaam blijft in de meegegeven (of huidige) houding."""
        env = audio_envelope(audio_path, self.fps)
        if not env:
            return 0
        if body_pose:
            base = dict(body_pose)
        elif self.frames:
            base = dict(self.frames[0])
        else:
            base = dict(self.joints)
        self.frames = [dict(base) for _ in env]
        self.mouth = [1.0 if e >= threshold else 0.0 for e in env]
        return len(env)

    def image_at(self, t_local):
        return self.render_frame(int(t_local * self.fps))

    def flatten_parts(self):
        """Voeg alle deel-tekeningen samen tot één beeld in rust-pose."""
        flat = QImage(self.width, self.height, QImage.Format_ARGB32)
        flat.fill(Qt.transparent)
        p = QPainter(flat)
        for pt in self.parts:
            p.drawImage(0, 0, pt["image"])
        p.end()
        return flat

    def to_dict(self):
        d = super().to_dict()
        d.update(width=self.width, height=self.height, fps=self.fps,
                 stretch=bool(getattr(self, "stretch", True)),
                 joints={k: [round(v[0], 4), round(v[1], 4)] for k, v in self.joints.items()},
                 bones=[list(b) for b in self.bones],
                 parts=[{"bone": list(pt["bone"]),
                         "image": qimage_to_b64(pt["image"]), "art": pt["art"]}
                        for pt in self.parts],
                 frames=[{k: [round(v[0], 4), round(v[1], 4)] for k, v in f.items()}
                         for f in self.frames],
                 mouth_bone=(list(self.mouth_bone) if getattr(self, "mouth_bone", None) else None),
                 talk=bool(getattr(self, "talk", False)),
                 talk_dur=(float(self.talk_dur) if getattr(self, "talk_dur", None) else None),
                 mouth=[round(float(m), 3) for m in getattr(self, "mouth", [])],
                 mouth_closed=(qimage_to_b64(self.mouth_closed)
                               if getattr(self, "mouth_closed", None) is not None else None),
                 mouth_open=(qimage_to_b64(self.mouth_open)
                             if getattr(self, "mouth_open", None) is not None else None))
        return d

    @classmethod
    def from_dict(cls, d):
        joints = None
        if "joints" in d:
            joints = {k: (float(v[0]), float(v[1])) for k, v in d["joints"].items()}
        bones = [tuple(b) for b in d["bones"]] if "bones" in d else None
        c = cls(parts=[], frames=None, name=d.get("name"), start=d["start"],
                width=d.get("width", 640), height=d.get("height", 360),
                fps=d.get("fps", 12), joints=joints, bones=bones)
        parts = []
        for pt in d.get("parts", []):
            parts.append({"bone": tuple(pt["bone"]),
                          "image": b64_to_qimage(pt["image"]),
                          "art": bool(pt.get("art", True))})
        c.parts = parts or c._blank_parts()
        c.frames = [{k: (float(v[0]), float(v[1])) for k, v in f.items()}
                    for f in d.get("frames", [])] or [dict(c.joints)]
        c.stretch = bool(d.get("stretch", True))
        mb = d.get("mouth_bone")
        c.mouth_bone = tuple(mb) if mb else None
        c.mouth = [float(x) for x in d.get("mouth", [])]
        c.mouth_closed = b64_to_qimage(d["mouth_closed"]) if d.get("mouth_closed") else None
        c.mouth_open = b64_to_qimage(d["mouth_open"]) if d.get("mouth_open") else None
        c.talk = bool(d.get("talk", False))
        c.talk_dur = d.get("talk_dur")
        return c


CLIP_TYPES = {c.KIND: c for c in
              (DrawnSceneClip, ImageClip, VideoClip, AudioClip, TextClip,
               EndCreditsClip, StickFigureClip, StudioClip, RigClip)}


class Track:
    def __init__(self, name="Spoor", kind="media"):
        self.name = name
        self.kind = kind
        self.clips = []

    def add(self, clip):
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start)

    def remove(self, clip):
        if clip in self.clips:
            self.clips.remove(clip)

    def end(self):
        return max((c.start + c.duration() for c in self.clips), default=0.0)

    def clip_at(self, t):
        for c in self.clips:
            if c.start <= t < c.start + c.duration():
                return c, t - c.start
        return None, 0.0

    def active_clips(self, t):
        """Alle clips die op tijdstip t actief zijn (kan overlappen -> crossfade)."""
        return [c for c in self.clips if c.start <= t < c.start + c.duration()]

    def to_dict(self):
        return {"name": self.name, "kind": self.kind,
                "clips": [c.to_dict() for c in self.clips]}

    @classmethod
    def from_dict(cls, d):
        t = cls(d["name"], d.get("kind", "media"))
        for cd in d["clips"]:
            cls_ = CLIP_TYPES.get(cd["kind"])
            if cls_:
                clip = cls_.from_dict(cd)
                clip.transform = Transform.from_dict(cd.get("transform", {}))
                clip.fade_in = float(cd.get("fade_in", 0.0))
                clip.fade_out = float(cd.get("fade_out", 0.0))
                clip.trans_in = cd.get("trans_in", "fade")
                clip.trans_out = cd.get("trans_out", "fade")
                clip.effects = {**DEFAULT_EFFECTS, **cd.get("effects", {})}
                clip.filter = cd.get("filter", "none")
                t.clips.append(clip)
        return t


class Project:
    def __init__(self, width=640, height=360, fps=24):
        self.width, self.height, self.fps = width, height, fps
        self.background = QColor("black")
        self.tracks = [Track("Spoor 1"), Track("Spoor 2"),
                       Track("Audio 1", kind="audio")]

    def duration(self):
        return max((t.end() for t in self.tracks), default=0.0)

    def voice_amplitude_at(self, t):
        """Hoogste luidheid (0..1) van alle stemmen op het Stem-spoor op tijdstip t."""
        amt = 0.0
        for tr in self.tracks:
            if tr.kind != "voice":
                continue
            for c in tr.clips:
                if c.start <= t < c.start + c.duration() and isinstance(c, AudioClip):
                    env = voice_envelope(c.path)
                    if env:
                        i = int((t - c.start) * ENV_FPS)
                        if 0 <= i < len(env):
                            amt = max(amt, env[i])
        return amt

    def render_frame(self, t):
        """Voeg alle sporen + transforms + effecten samen op tijdstip t -> QImage."""
        canvas = QImage(self.width, self.height, QImage.Format_RGB888)
        canvas.fill(self.background)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        talk_amt = None
        for track in self.tracks:  # onderste spoor eerst, bovenste wint
            for clip in track.active_clips(t):  # overlap -> crossfade/overgang
                t_local = t - clip.start
                if getattr(clip, "talk", False) and hasattr(clip, "render_talk"):
                    if talk_amt is None:
                        talk_amt = self.voice_amplitude_at(t)
                    img = clip.render_talk(t_local, talk_amt)
                else:
                    img = clip.image_at(t_local)
                if img is None:
                    continue
                img = apply_effects(img, clip.effects, getattr(clip, "filter", "none"))
                draw_clip_with_transition(p, img, self.width, self.height,
                                          clip, t_local)
        p.end()
        return canvas

    def to_dict(self):
        return {"app": "DraveMotion", "version": APP_VERSION,
                "width": self.width, "height": self.height, "fps": self.fps,
                "background": self.background.name(),
                "tracks": [t.to_dict() for t in self.tracks]}

    @classmethod
    def from_dict(cls, d):
        pr = cls(d["width"], d["height"], d.get("fps", 24))
        pr.background = QColor(d.get("background", "#000000"))
        pr.tracks = [Track.from_dict(t) for t in d["tracks"]] or [Track("Spoor 1")]
        return pr


# =========================================================================== #
#  EXPORT
# =========================================================================== #
_AUDIO_PROBE = {}


def video_has_audio(path):
    """True als het bestand een audiospoor heeft (gecachet per pad)."""
    if path in _AUDIO_PROBE:
        return _AUDIO_PROBE[path]
    ff = ffmpeg_exe()
    has = False
    if ff:
        try:
            out = subprocess.run([ff, "-i", path], capture_output=True, text=True).stderr
            has = "Audio:" in out
        except Exception:  # noqa: BLE001
            has = False
    _AUDIO_PROBE[path] = has
    return has


def _atempo_chain(speed):
    """Bouw een atempo-keten (elke factor binnen 0.5–2.0) voor willekeurige snelheid."""
    parts = []
    r = float(speed)
    while r > 2.0:
        parts.append(2.0); r /= 2.0
    while r < 0.5:
        parts.append(0.5); r /= 0.5
    parts.append(r)
    return ",".join(f"atempo={p:.4f}" for p in parts)


def collect_audio_clips(project):
    out = []
    for tr in project.tracks:
        for c in tr.clips:
            if isinstance(c, AudioClip):
                out.append(c)
            elif isinstance(c, VideoClip) and video_has_audio(c.path):
                out.append(c)   # geluid uit de video meenemen
    return out


def build_audio_mixdown(clips, out_path, total_dur, acodec="aac"):
    """Mix alle audio (losse audio + geluid uit video's) tot 1 bestand via ffmpeg."""
    ff = ffmpeg_exe()
    if not ff or not clips:
        return None
    inputs, filters, labels = [], [], []
    for i, c in enumerate(clips):
        inputs += ["-i", c.path]
        delay = max(0, int(round(c.start * 1000)))
        spd = getattr(c, "speed", 1.0) or 1.0
        src_dur = max(0.1, c.out_point - c.in_point)
        final_dur = src_dur / spd
        chain = (f"[{i}:a]atrim=start={c.in_point}:end={c.out_point},"
                 f"asetpts=PTS-STARTPTS")
        if abs(spd - 1.0) > 1e-3:
            chain += "," + _atempo_chain(spd)
        vol = getattr(c, "volume", 100.0) / 100.0
        if abs(vol - 1.0) > 1e-3:
            chain += f",volume={vol:.3f}"
        fin = getattr(c, "fade_in", 0.0)
        if fin > 0:
            chain += f",afade=t=in:st=0:d={fin:.3f}"
        fout = getattr(c, "fade_out", 0.0)
        if fout > 0:
            chain += f",afade=t=out:st={max(0.0, final_dur - fout):.3f}:d={fout:.3f}"
        chain += f",adelay={delay}|{delay}[a{i}]"
        filters.append(chain)
        labels.append(f"[a{i}]")
    if len(clips) == 1:
        fc = filters[0].replace("[a0]", "[aout]")
    else:
        fc = ";".join(filters) + ";" + "".join(labels) + \
            f"amix=inputs={len(clips)}:normalize=0[aout]"
    cmd = [ff, "-y", *inputs, "-filter_complex", fc, "-map", "[aout]",
           "-t", f"{total_dur:.3f}", "-c:a", acodec, out_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return out_path if res.returncode == 0 and os.path.exists(out_path) else None


def export_video(project, path, progress=None):
    if not HAVE_FFMPEG:
        raise RuntimeError("imageio-ffmpeg ontbreekt; MP4-export niet beschikbaar.")
    w, h, fps = project.width, project.height, project.fps
    total = max(1, int(round(project.duration() * fps)))
    audio = collect_audio_clips(project)

    # 1) beeld renderen (naar tijdelijk bestand als er audio bijkomt)
    video_path = os.path.join(CACHE_DIR, "_render_video.mp4") if audio else path
    # macro_block_size=1 behoudt de exacte (even) projectafmeting i.p.v. afronden naar 16
    writer = imageio_ffmpeg.write_frames(
        video_path, (w, h), fps=fps, macro_block_size=1, quality=7,
        ffmpeg_log_level="error")
    writer.send(None)
    for i in range(total):
        writer.send(qimage_to_rgb_array(project.render_frame(i / fps)).tobytes())
        if progress:
            progress(i + 1, total)
    writer.close()
    if not audio:
        return

    # 2) audio mixen en in de MP4 muxen
    mix = build_audio_mixdown(audio, os.path.join(CACHE_DIR, "_render_audio.m4a"),
                              project.duration())
    ff = ffmpeg_exe()
    if mix and ff:
        subprocess.run([ff, "-y", "-i", video_path, "-i", mix,
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        "-c:a", "aac", "-shortest", path],
                       capture_output=True, text=True)
    else:  # audio mislukt -> lever toch het beeld
        import shutil
        shutil.copyfile(video_path, path)


def export_gif(project, path, progress=None):
    if not HAVE_PIL:
        raise RuntimeError("Pillow ontbreekt.")
    fps = project.fps
    total = max(1, int(round(project.duration() * fps)))
    frames = []
    for i in range(total):
        frames.append(qimage_to_pil(project.render_frame(i / fps)))
        if progress:
            progress(i + 1, total)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=int(1000 / fps), loop=0)


def export_png_sequence(project, folder, progress=None, prefix="frame"):
    fps = project.fps
    total = max(1, int(round(project.duration() * fps)))
    safe = "".join(ch for ch in prefix if ch.isalnum() or ch in "-_") or "frame"
    for i in range(total):
        project.render_frame(i / fps).save(
            os.path.join(folder, f"{safe}_{i:04d}.png"), "PNG")
        if progress:
            progress(i + 1, total)
    return total


# =========================================================================== #
#  HUISSTIJL  (donker, zilver, hoog contrast - EN 301 549 / WCAG)
# =========================================================================== #
DRAVENLOCK_QSS = """
QMainWindow, QDialog, QWidget { background-color:#0e0e11; color:#d4d4d4; }
QLabel { color:#d4d4d4; }
QLabel#title { color:#f2f2f2; font-size:22px; font-weight:600; }
QLabel#subtitle { color:#9aa0a8; font-family:"Consolas","DejaVu Sans Mono",monospace; font-size:11px; }
QLabel#section { color:#a8a8b0; font-size:11px; font-weight:600; letter-spacing:1px; }
QLabel#mono { color:#8e8e96; font-family:"Consolas","DejaVu Sans Mono",monospace; }
QMessageBox QLabel, QInputDialog QLabel { font-size:14pt; }
QMessageBox QPushButton, QInputDialog QPushButton { font-size:12pt; padding:8px 22px; min-width:90px; }
QToolTip { font-size:12pt; color:#e9e9ee; background:#23232a; border:1px solid #4a4a56; padding:4px; }

#panel, #header { background-color:#16161b; border:1px solid #2a2a31; border-radius:10px; }

QPushButton, QToolButton, QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QPlainTextEdit {
    background-color:#23232a; color:#d6d6d6;
    border:1px solid #3a3a44; border-radius:8px; padding:8px 10px;
}
QPushButton:hover, QToolButton:hover, QComboBox:hover { background-color:#2d2d36; border-color:#4a4a56; }
QPushButton:pressed { background-color:#34343f; }
QToolButton:checked { background-color:#27384b; border:2px solid #6fa3d6; color:#ffffff; }
QPushButton:focus, QToolButton:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QListWidget:focus, QSlider:focus, QLineEdit:focus, QPlainTextEdit:focus { border:2px solid #6fa3d6; }
QPushButton#cta { background-color:#27384b; border:1px solid #6fa3d6; color:#eaf3fc; }
QPushButton#cta:hover { background-color:#2f4661; }
QPushButton:disabled, QDoubleSpinBox:disabled, QToolButton:disabled { color:#666; border-color:#2a2a31; }

QListWidget { background-color:#1b1b21; border:1px solid #2a2a31; border-radius:8px; color:#d4d4d4; }
QListWidget::item { padding:3px; }
QListWidget::item:selected { background-color:#27384b; border:1px solid #6fa3d6; color:#fff; }

QScrollArea { border:none; }
QSlider::groove:horizontal { height:6px; background:#46464f; border-radius:3px; }
QSlider::handle:horizontal { background:#d0d0d0; width:20px; margin:-8px 0; border-radius:10px; }
QStatusBar { background-color:#121216; color:#c8c8c8; }
QToolTip { background-color:#23232a; color:#eaeaea; border:1px solid #6fa3d6; padding:4px; }

QTabWidget::pane { border:1px solid #2a2a31; border-radius:8px; top:-1px; }
QTabBar { qproperty-drawBase:0; background:transparent; }
QTabBar::tab {
    background-color:#1b1b21; color:#cfd2d6; border:1px solid #2a2a31;
    border-top-left-radius:8px; border-top-right-radius:8px;
    padding:8px 22px; margin-right:3px; min-width:120px; font-weight:bold;
}
QTabBar::tab:selected { background-color:#27384b; color:#ffffff; border:1px solid #6fa3d6; border-bottom:none; }
QTabBar::tab:hover:!selected { background-color:#23232a; color:#ffffff; }
"""


def split_clip(clip, t_abs):
    """Splits een clip op absolute tijd t_abs in twee losse clips (links, rechts)."""
    local = t_abs - clip.start
    total = clip.duration()
    d = clip.to_dict()

    def clone():
        c = CLIP_TYPES[clip.KIND].from_dict(d)
        c.transform = Transform.from_dict(d.get("transform", {}))
        c.effects = {**DEFAULT_EFFECTS, **d.get("effects", {})}
        c.filter = d.get("filter", "none")
        c.trans_in = d.get("trans_in", "fade")
        c.trans_out = d.get("trans_out", "fade")
        return c

    left, right = clone(), clone()
    # een schone knip: linkerdeel houdt fade-in, rechterdeel houdt fade-out
    left.fade_in, left.fade_out = clip.fade_in, 0.0
    right.fade_in, right.fade_out = 0.0, clip.fade_out

    if isinstance(clip, (ImageClip, TextClip, EndCreditsClip)):
        left.start = clip.start; left.set_duration(local)
        right.start = t_abs; right.set_duration(total - local)
    elif isinstance(clip, DrawnSceneClip):
        fps = clip.model.fps
        k = max(1, min(len(clip.model.frames) - 1, int(round(local * fps))))
        left.model.frames = [f.copy() for f in clip.model.frames[:k]]
        right.model.frames = [f.copy() for f in clip.model.frames[k:]]
        left.model.current = right.model.current = 0
        left.start = clip.start
        right.start = clip.start + k / fps
    elif isinstance(clip, StickFigureClip):
        fps = clip.fps
        k = max(1, min(len(clip.frames) - 1, int(round(local * fps))))
        left.frames = [dict(f) for f in clip.frames[:k]]
        right.frames = [dict(f) for f in clip.frames[k:]]
        left.start = clip.start
        right.start = clip.start + k / fps
    elif isinstance(clip, StudioClip):
        fps = clip.model.fps
        k = max(1, min(len(clip.model.frames) - 1, int(round(local * fps))))
        left.model.frames = [f.copy() for f in clip.model.frames[:k]]
        right.model.frames = [f.copy() for f in clip.model.frames[k:]]
        left.poses = [dict(p) for p in clip.poses[:k]]
        right.poses = [dict(p) for p in clip.poses[k:]]
        left.bake = list(clip.bake[:k]); right.bake = list(clip.bake[k:])
        left.model.current = right.model.current = 0
        left.start = clip.start
        right.start = clip.start + k / fps
    elif isinstance(clip, RigClip):
        fps = clip.fps
        k = max(1, min(len(clip.frames) - 1, int(round(local * fps))))
        # de getekende delen worden gedeeld (gekopieerd), de frames verdeeld
        left.parts = [{"bone": pt["bone"], "image": pt["image"].copy(), "art": pt["art"]}
                      for pt in clip.parts]
        right.parts = [{"bone": pt["bone"], "image": pt["image"].copy(), "art": pt["art"]}
                       for pt in clip.parts]
        left.frames = [dict(f) for f in clip.frames[:k]]
        right.frames = [dict(f) for f in clip.frames[k:]]
        left.start = clip.start
        right.start = clip.start + k / fps
    elif isinstance(clip, (VideoClip, AudioClip)):
        spd = getattr(clip, "speed", 1.0)
        src_split = clip.in_point + local * spd
        left.in_point, left.out_point, left.start = clip.in_point, src_split, clip.start
        right.in_point, right.out_point, right.start = src_split, clip.out_point, t_abs
    return left, right


def make_logo(size=44):
    """Laadt logo.png uit de app-map indien aanwezig, anders een DA-monogram."""
    for cand in (resource_path("logo.png"), os.path.join(APP_DIR, "logo.png")):
        if os.path.exists(cand):
            pm = QPixmap(cand)
            if not pm.isNull():
                return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#1b1b21")))
    p.setPen(QPen(QColor("#6fa3d6"), 2))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 9, 9)
    p.setPen(QColor("#e6e6e6"))
    f = QFont("Arial", int(size * 0.42)); f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "DA")
    p.end()
    return pm


ASSET_GLYPH = {"video": "🎞", "audio": "🎵", "image": "🖼", "scene": "✎", "text": "T", "credits": "▤", "figure": "🦴", "studio": "🎬", "rig": "🧍"}
ASSET_COLOR = {"video": "#4a3f63", "audio": "#5a4a2e", "image": "#3f5a45",
               "scene": "#3b5266", "text": "#444a55", "credits": "#52426b", "figure": "#3f5a5a", "studio": "#5a3f55", "rig": "#3f4a5a"}


def asset_icon(kind, path=None, size=40):
    """Maakt een pictogram voor een asset in de mediabak."""
    if kind == "image" and path:
        pm = QPixmap(path)
        if not pm.isNull():
            return QIcon(pm.scaled(size, size, Qt.KeepAspectRatioByExpanding,
                                   Qt.SmoothTransformation))
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(ASSET_COLOR.get(kind, "#444"))); p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, 8, 8)
    p.setPen(QColor("#eaeaea"))
    f = QFont("Arial", int(size * 0.42)); f.setBold(True); p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, ASSET_GLYPH.get(kind, "?"))
    p.end()
    return QIcon(pm)


def section(text):
    lbl = QLabel(t(text).upper()); lbl.setObjectName("section"); return lbl


# =========================================================================== #
#  SCENE-EDITOR  (de tekenstudio als dialoog)
# =========================================================================== #
class DrawingStudio(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scene bewerken - DraveMotion")
        self.model = model
        self.canvas = Canvas(model)
        self.canvas.on_change = self._refresh_item
        self.play_timer = QTimer(self); self.play_timer.timeout.connect(self._tick)
        self.playing = False
        self._build()
        self._refresh_timeline()
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint |
                            Qt.WindowMinimizeButtonHint)
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)
        QTimer.singleShot(0, self.showMaximized)

    def _build(self):
        root = QHBoxLayout(self)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Gereedschap"))
        self._tool_btns = {}
        tips = {PEN: "Vrij tekenen", ERASER: "Wissen", LINE: "Rechte lijn", FILL: "Vullen"}
        for k, label in [(PEN, "✏  Pen"), (ERASER, "⌫  Gum"), (LINE, "／  Lijn"), (FILL, "🪣  Vullen")]:
            b = QToolButton(); b.setText(label); b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setMinimumWidth(150); b.setMinimumHeight(34); b.setToolTip(tips[k])
            b.clicked.connect(lambda _, key=k: self._set_tool(key))
            tools.addWidget(b); self._tool_btns[k] = b
        self._tool_btns[PEN].setChecked(True)
        self.color_btn = QPushButton("Kleur"); self.color_btn.clicked.connect(self._pick_color)
        self._refresh_color(); tools.addWidget(self.color_btn)
        self.brush_lbl = QLabel("Lijndikte / penseel: 4 px")
        tools.addWidget(self.brush_lbl)
        self.brush = QSlider(Qt.Horizontal); self.brush.setRange(1, 60); self.brush.setValue(4)
        self.brush.valueChanged.connect(self._set_brush)
        tools.addWidget(self.brush)
        self.onion = QPushButton("Vorig frame tonen: uit"); self.onion.setCheckable(True)
        self.onion.setToolTip("Onion skin: toont het vorige frame lichtjes (als schaduw) "
                              "zodat je je tekening erop kunt uitlijnen voor een vloeiende animatie.")
        self.onion.clicked.connect(self._toggle_onion); tools.addWidget(self.onion)
        clr = QPushButton("Frame wissen"); clr.clicked.connect(self.canvas.clear_frame); tools.addWidget(clr)
        undo = QPushButton("Ongedaan (Ctrl+Z)"); undo.clicked.connect(self.canvas.undo); tools.addWidget(undo)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(250)
        root.addWidget(tp)
        scroll = QScrollArea(); scroll.setWidget(self.canvas); scroll.setAlignment(Qt.AlignCenter)
        root.addWidget(scroll, 1)
        right = QVBoxLayout(); right.addWidget(section("Frames"))
        self.tl = QListWidget(); self.tl.setViewMode(QListWidget.IconMode)
        self.tl.setIconSize(QSize(92, 64)); self.tl.setResizeMode(QListWidget.Adjust)
        self.tl.setMovement(QListWidget.Static); self.tl.setSpacing(4)
        self.tl.currentRowChanged.connect(self._select); right.addWidget(self.tl, 1)
        for label, fn in [("＋ Frame toevoegen", lambda: self._add(False)),
                          ("⧉ Frame dupliceren", lambda: self._add(True)),
                          ("🗑 Frame verwijderen", self._del)]:
            b = QPushButton(label); b.setMinimumHeight(32); b.clicked.connect(fn)
            right.addWidget(b)
        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Afspelen"); self.play_btn.clicked.connect(self._toggle_play)
        play_row.addWidget(self.play_btn); play_row.addWidget(QLabel("FPS"))
        self.fps = QSpinBox(); self.fps.setRange(1, 60); self.fps.setValue(self.model.fps)
        self.fps.valueChanged.connect(lambda v: setattr(self.model, "fps", v))
        play_row.addWidget(self.fps); right.addLayout(play_row)
        guide_b = QPushButton("📖 Snelgids"); guide_b.setMinimumHeight(32)
        guide_b.clicked.connect(lambda: open_quick_guide(self)); right.addWidget(guide_b)
        done = QPushButton("Klaar"); done.setObjectName("cta"); done.setMinimumHeight(36)
        done.clicked.connect(self.accept)
        right.addWidget(done)
        rp = QWidget(); rp.setObjectName("panel"); rp.setLayout(right); rp.setFixedWidth(280)
        root.addWidget(rp)

    def _set_tool(self, k):
        self.canvas.tool = k
        for key, b in self._tool_btns.items():
            b.setChecked(key == k)

    def _set_brush(self, v):
        self.canvas.brush = v
        self.brush_lbl.setText(f"Lijndikte / penseel: {v} px")

    def _pick_color(self):
        c = QColorDialog.getColor(self.canvas.color, self, "Kies kleur")
        if c.isValid():
            self.canvas.color = c; self._refresh_color()

    def _refresh_color(self):
        c = self.canvas.color
        fg = "white" if c.lightness() < 128 else "black"
        self.color_btn.setStyleSheet(f"background-color:{c.name()};color:{fg};")
        self.color_btn.setText(f"Kleur ({c.name()})")

    def _toggle_onion(self):
        self.canvas.onion = self.onion.isChecked()
        self.onion.setText("Vorig frame tonen: aan" if self.canvas.onion else "Vorig frame tonen: uit")
        self.canvas.update()

    def _add(self, dup): self.model.add_frame(duplicate=dup); self._refresh_timeline(); self.canvas.update()
    def _del(self): self.model.delete_frame(); self._refresh_timeline(); self.canvas.update()

    def _select(self, row):
        if row >= 0:
            self.model.move_to(row); self.canvas.update()

    def _refresh_timeline(self):
        self.tl.blockSignals(True); self.tl.clear()
        for i, f in enumerate(self.model.frames):
            self.tl.addItem(QListWidgetItem(QIcon(QPixmap.fromImage(f)), str(i + 1)))
        self.tl.setCurrentRow(self.model.current); self.tl.blockSignals(False)

    def _refresh_item(self):
        i = self.model.current
        if 0 <= i < self.tl.count():
            self.tl.item(i).setIcon(QIcon(QPixmap.fromImage(self.model.frames[i])))

    def _toggle_play(self):
        if self.playing:
            self.play_timer.stop(); self.playing = False; self.play_btn.setText("▶ Afspelen")
        elif len(self.model.frames) > 1:
            self.playing = True; self.play_btn.setText("⏸ Pauze")
            self.play_timer.start(int(1000 / self.model.fps))

    def _tick(self):
        self.model.move_to((self.model.current + 1) % len(self.model.frames))
        self.tl.blockSignals(True); self.tl.setCurrentRow(self.model.current); self.tl.blockSignals(False)
        self.canvas.update()

    def keyPressEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier and ev.key() == Qt.Key_Z:
            self.canvas.undo()
        else:
            super().keyPressEvent(ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        avail_w = max(200, self.width() - 220 - 280 - 80)
        avail_h = max(200, self.height() - 80)
        scale = min(avail_w / self.model.width, avail_h / self.model.height)
        scale = max(1.0, min(scale, 4.0))
        if abs(self.canvas.disp_scale - scale) > 0.02:
            self.canvas.set_display_scale(scale)


# =========================================================================== #
#  POPPETJE / SKELET-ANIMATIE
# =========================================================================== #
class PoseCanvas(QWidget):
    """Canvas om gewrichten van het poppetje te verslepen.

    square=True : gewrichten in een gecentreerde vierkante ruimte (los poppetje).
    square=False: vol-frame mapping (x*W, y*H) zodat het skelet over een tekening valt.
    """

    def __init__(self, parent=None, square=True):
        super().__init__(parent)
        self.setFixedSize(560, 560)
        self.square = square
        self.pose = None
        self.prev = None
        self.bg = None            # optionele achtergrond (de tekening van dit frame)
        self.handles_only = False  # alleen gewricht-bolletjes tonen (over een gerenderd poppetje)
        self.color = "#e6e6e6"
        self.line_w = 4
        self.onion = True
        self._sel = None
        self.on_change = None
        # skelet-definitie (standaard het mens-poppetje, maar instelbaar voor eigen skeletten)
        self.joint_ids = list(StickFigureClip.JOINTS)
        self.bones = list(StickFigureClip.BONES)
        self.rest = dict(StickFigureClip.REST)

    def set_skeleton(self, joint_ids, bones, rest):
        self.joint_ids = list(joint_ids)
        self.bones = list(bones)
        self.rest = dict(rest)

    def _rest_of(self, n):
        return self.rest.get(n, (0.5, 0.5))

    def set_pose(self, pose, prev, bg=None):
        self.pose = pose; self.prev = prev; self.bg = bg; self.update()

    def _map(self, jx, jy):
        if self.square:
            s = min(self.width(), self.height())
            ox = (self.width() - s) / 2.0; oy = (self.height() - s) / 2.0
            return ox + jx * s, oy + jy * s
        return jx * self.width(), jy * self.height()

    def _unmap(self, x, y):
        if self.square:
            s = min(self.width(), self.height())
            ox = (self.width() - s) / 2.0; oy = (self.height() - s) / 2.0
            return (x - ox) / s, (y - oy) / s
        return x / self.width(), y / self.height()

    def _draw_fig(self, p, pose, color, ghost=False):
        s = min(self.width(), self.height())
        lw = max(2, int(self.line_w * s / 360.0))
        pen = QPen(QColor(color), lw); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
        p.setOpacity(0.30 if ghost else 1.0)
        p.setPen(pen); p.setBrush(Qt.NoBrush)

        def P(n):
            jx, jy = pose.get(n, self._rest_of(n)); x, y = self._map(jx, jy); return QPointF(x, y)
        for a, b in self.bones:
            p.drawLine(P(a), P(b))
        if "head" in self.joint_ids and "neck" in self.joint_ids:
            hc = P("head"); r = 0.055 * s
            p.drawLine(P("neck"), QPointF(hc.x(), hc.y() + r))
            p.drawEllipse(hc, r, r)
        p.setOpacity(1.0)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#15151b" if self.bg else "#0e0e12"))
        if self.bg is not None and not self.bg.isNull():
            p.drawImage(self.rect(), self.bg)
        p.setPen(QPen(QColor("#2a2a31"), 1)); p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        if self.onion and self.prev and not self.handles_only:
            self._draw_fig(p, self.prev, "#6f9ad6", ghost=True)
        if self.pose:
            if not self.handles_only:
                self._draw_fig(p, self.pose, self.color)
            for n in self.joint_ids:
                jx, jy = self.pose.get(n, self._rest_of(n))
                cx, cy = self._map(jx, jy)
                sel = (n == self._sel)
                p.setBrush(QColor("#7fd4ff") if sel else QColor("#cfd2d6"))
                p.setPen(QPen(QColor("#0b0b0d"), 1))
                rr = 8 if sel else 6
                p.drawEllipse(QPointF(cx, cy), rr, rr)
        p.end()

    def _nearest(self, x, y):
        if not self.pose:
            return None
        best = None; bd = 20 ** 2
        for n in self.joint_ids:
            jx, jy = self.pose.get(n, self._rest_of(n))
            px, py = self._map(jx, jy)
            d = (x - px) ** 2 + (y - py) ** 2
            if d < bd:
                bd = d; best = n
        return best

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.pose:
            self._sel = self._nearest(ev.x(), ev.y()); self.update()

    def mouseMoveEvent(self, ev):
        if self._sel and self.pose and (ev.buttons() & Qt.LeftButton):
            jx, jy = self._unmap(ev.x(), ev.y())
            jx = min(1.0, max(0.0, jx)); jy = min(1.0, max(0.0, jy))
            self.pose[self._sel] = (jx, jy)
            if self.on_change:
                self.on_change()
            self.update()

    def mouseReleaseEvent(self, _ev):
        self._sel = None; self.update()


class PoseStudio(QDialog):
    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle("Stok-poppetje - DraveMotion")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint |
                            Qt.WindowMinimizeButtonHint)
        self.resize(900, 800)
        self.setMinimumSize(720, 640)
        QTimer.singleShot(0, self.showMaximized)
        self.frames = [dict(f) for f in clip.frames] or [dict(StickFigureClip.REST)]
        self.idx = 0
        self.playing = False
        lay = QVBoxLayout(self)
        lay.addWidget(section("Houding (sleep de gewrichten)"))
        center = QHBoxLayout(); center.addStretch(1)
        self.canvas = PoseCanvas()
        self.canvas.color = clip.color; self.canvas.line_w = clip.line_w
        center.addWidget(self.canvas); center.addStretch(1)
        lay.addLayout(center)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Vorige"); self.prev_btn.clicked.connect(self._prev)
        self.next_btn = QPushButton("Volgende ▶"); self.next_btn.clicked.connect(self._next)
        self.frame_lbl = QLabel(); self.frame_lbl.setObjectName("mono")
        self.add_btn = QPushButton("＋ Nieuw frame"); self.add_btn.setToolTip("Kopie van dit frame toevoegen")
        self.add_btn.clicked.connect(self._add)
        self.del_btn = QPushButton("🗑 Frame"); self.del_btn.clicked.connect(self._del)
        self.play_btn = QPushButton("▶ Speel"); self.play_btn.clicked.connect(self._toggle_play)
        for w in (self.prev_btn, self.next_btn, self.frame_lbl, self.add_btn, self.del_btn, self.play_btn):
            nav.addWidget(w)
        lay.addLayout(nav)

        opt = QHBoxLayout()
        self.onion_chk = QCheckBox("Vorig frame tonen (onion skin)")
        self.onion_chk.setToolTip("Toont het skelet van het vorige frame lichtjes, "
                                  "zodat je vloeiend kunt animeren.")
        self.onion_chk.setChecked(True)
        self.onion_chk.toggled.connect(lambda v: setattr(self.canvas, "onion", v) or self.canvas.update())
        opt.addWidget(self.onion_chk)
        opt.addWidget(QLabel("FPS"))
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 30); self.fps_spin.setValue(clip.fps)
        opt.addWidget(self.fps_spin)
        opt.addWidget(QLabel("Lijndikte"))
        self.lw_spin = QSpinBox(); self.lw_spin.setRange(1, 20); self.lw_spin.setValue(clip.line_w)
        self.lw_spin.valueChanged.connect(self._set_lw)
        opt.addWidget(self.lw_spin)
        self.color_btn = QPushButton(); self.color_btn.clicked.connect(self._pick_color)
        self._color = QColor(clip.color); self._refresh_color()
        opt.addWidget(self.color_btn); opt.addStretch(1)
        lay.addLayout(opt)

        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
        row = QHBoxLayout()
        guide_b = QPushButton("📖 Snelgids"); guide_b.clicked.connect(lambda: open_quick_guide(self))
        row.addWidget(guide_b); row.addStretch(1)
        cancel = QPushButton("Annuleer"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        ok = QPushButton("Klaar"); ok.setObjectName("cta"); ok.clicked.connect(self._accept); row.addWidget(ok)
        lay.addLayout(row)
        self._load()

    def _load(self):
        prev = self.frames[self.idx - 1] if self.idx > 0 else None
        self.canvas.set_pose(self.frames[self.idx], prev)
        self.frame_lbl.setText(f"Frame {self.idx + 1}/{len(self.frames)}")
        self.del_btn.setEnabled(len(self.frames) > 1)

    def _prev(self):
        if self.idx > 0:
            self.idx -= 1; self._load()

    def _next(self):
        if self.idx < len(self.frames) - 1:
            self.idx += 1; self._load()

    def _add(self):
        self.frames.insert(self.idx + 1, dict(self.frames[self.idx]))
        self.idx += 1; self._load()

    def _del(self):
        if len(self.frames) > 1:
            self.frames.pop(self.idx)
            self.idx = min(self.idx, len(self.frames) - 1); self._load()

    def _toggle_play(self):
        if self.playing:
            self._timer.stop(); self.playing = False; self.play_btn.setText("▶ Speel")
        elif len(self.frames) > 1:
            self.playing = True; self.play_btn.setText("⏸ Stop")
            self._timer.start(int(1000 / max(1, self.fps_spin.value())))

    def _tick(self):
        self.idx = (self.idx + 1) % len(self.frames); self._load()

    def _set_lw(self, v):
        self.canvas.line_w = v; self.canvas.update()

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Lijnkleur")
        if c.isValid():
            self._color = c; self.canvas.color = c.name(); self._refresh_color(); self.canvas.update()

    def _refresh_color(self):
        fg = "white" if self._color.lightness() < 128 else "black"
        self.color_btn.setStyleSheet(f"background-color:{self._color.name()};color:{fg};")
        self.color_btn.setText(self._color.name())

    def _accept(self):
        self._timer.stop()
        self.clip.frames = self.frames
        self.clip.fps = self.fps_spin.value()
        self.clip.line_w = self.lw_spin.value()
        self.clip.color = self._color.name()
        self.accept()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # canvas zo groot mogelijk maken (vierkant) binnen het venster
        s = max(360, min(self.height() - 240, self.width() - 80))
        if abs(self.canvas.width() - s) > 4:
            self.canvas.setFixedSize(s, s)


# =========================================================================== #
#  STUDIO  —  tekenen + poppetje in één venster (tabbladen)
# =========================================================================== #
class StudioEditor(QDialog):
    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle("Teken-studio + poppetje - DraveMotion")
        src = clip.model
        self.model = AnimationModel(src.width, src.height, src.fps)
        self.model.frames = [f.copy() for f in src.frames]
        self.model.current = 0
        self.poses = [dict(p) for p in clip.poses]
        self.bake = list(clip.bake)
        while len(self.poses) < len(self.model.frames):
            self.poses.append(dict(StickFigureClip.REST)); self.bake.append(False)
        self.poses = self.poses[:len(self.model.frames)]
        self.bake = self.bake[:len(self.model.frames)]
        self._fig_color = QColor(clip.fig_color)
        self._fig_line_w = clip.fig_line_w
        self.playing = False
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
        self._build()
        self._refresh_strip()
        self._load()
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint |
                            Qt.WindowMinimizeButtonHint)
        self.resize(1320, 840)
        self.setMinimumSize(1040, 680)
        QTimer.singleShot(0, self.showMaximized)

    # ---- opbouw ---------------------------------------------------------- #
    def _build(self):
        root = QHBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_draw_tab(), "✏  Tekenen")
        self.tabs.addTab(self._build_pose_tab(), "🦴  Poppetje")
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)
        root.addWidget(self._build_right_panel())

    def _build_draw_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Tekengereedschap"))
        self.canvas = Canvas(self.model); self.canvas.on_change = self._refresh_item
        self._tool_btns = {}
        tips = {PEN: "Vrij tekenen", ERASER: "Wissen", LINE: "Rechte lijn", FILL: "Vullen"}
        for k, label in [(PEN, "✏  Pen"), (ERASER, "⌫  Gum"), (LINE, "／  Lijn"), (FILL, "🪣  Vullen")]:
            b = QToolButton(); b.setText(label); b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setMinimumWidth(150); b.setMinimumHeight(34); b.setToolTip(tips[k])
            b.clicked.connect(lambda _, key=k: self._set_tool(key))
            tools.addWidget(b); self._tool_btns[k] = b
        self._tool_btns[PEN].setChecked(True)
        self.color_btn = QPushButton("Kleur"); self.color_btn.clicked.connect(self._pick_pen_color)
        self._refresh_pen_color(); tools.addWidget(self.color_btn)
        self.brush_lbl = QLabel("Lijndikte / penseel: 4 px"); tools.addWidget(self.brush_lbl)
        self.brush = QSlider(Qt.Horizontal); self.brush.setRange(1, 60); self.brush.setValue(4)
        self.brush.valueChanged.connect(self._set_brush); tools.addWidget(self.brush)
        self.donion = QPushButton("Vorig frame tonen: uit"); self.donion.setCheckable(True)
        self.donion.setToolTip("Onion skin: toont het vorige frame lichtjes (als schaduw) "
                               "zodat je je tekening erop kunt uitlijnen voor een vloeiende animatie.")
        self.donion.clicked.connect(self._toggle_draw_onion); tools.addWidget(self.donion)
        clr = QPushButton("Frame wissen"); clr.clicked.connect(self.canvas.clear_frame); tools.addWidget(clr)
        undo = QPushButton("Ongedaan (Ctrl+Z)"); undo.clicked.connect(self.canvas.undo); tools.addWidget(undo)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(250)
        lay.addWidget(tp)
        sc = QScrollArea(); sc.setWidget(self.canvas); sc.setAlignment(Qt.AlignCenter)
        lay.addWidget(sc, 1)
        return w

    def _build_pose_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Stok-poppetje"))
        self.skel_btn = QPushButton("Skelet in beeld: aan")
        self.skel_btn.setToolTip("Bepaalt of dít skelet ook echt in de video getekend wordt. "
                                 "Zet je het uit, dan dient het skelet alleen als hulplijn om "
                                 "in het Tekenen-tabblad je eigen figuur overheen te tekenen.")
        self.skel_btn.clicked.connect(self._toggle_skeleton); tools.addWidget(self.skel_btn)
        self.fig_color_btn = QPushButton(); self.fig_color_btn.clicked.connect(self._pick_fig_color)
        self._refresh_fig_color(); tools.addWidget(self.fig_color_btn)
        tools.addWidget(QLabel("Skelet-lijndikte"))
        self.fig_lw = QSpinBox(); self.fig_lw.setRange(1, 30); self.fig_lw.setValue(self._fig_line_w)
        self.fig_lw.valueChanged.connect(self._set_fig_lw); tools.addWidget(self.fig_lw)
        self.ponion = QCheckBox("Vorig frame tonen"); self.ponion.setChecked(True)
        self.ponion.setToolTip("Toont het skelet van het vorige frame lichtjes (onion skin), "
                               "zodat je vloeiend kunt animeren.")
        self.ponion.toggled.connect(lambda v: setattr(self.pcanvas, "onion", v) or self.pcanvas.update())
        tools.addWidget(self.ponion)
        tip = QLabel("Tip: sleep de bolletjes (gewrichten) in de juiste houding. "
                     "Ga daarna naar Tekenen om je eigen figuur er overheen te tekenen.")
        tip.setWordWrap(True); tools.addWidget(tip)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(250)
        lay.addWidget(tp)
        self.pcanvas = PoseCanvas(square=False)
        self.pcanvas.color = self._fig_color.name(); self.pcanvas.line_w = self._fig_line_w
        self.pcanvas.on_change = self._refresh_item
        self.pcanvas.setFixedSize(self.model.width, self.model.height)
        sc = QScrollArea(); sc.setWidget(self.pcanvas); sc.setAlignment(Qt.AlignCenter)
        lay.addWidget(sc, 1)
        return w

    def _build_right_panel(self):
        right = QVBoxLayout(); right.addWidget(section("Frames"))
        self.strip = QListWidget(); self.strip.setViewMode(QListWidget.IconMode)
        self.strip.setIconSize(QSize(96, 64)); self.strip.setResizeMode(QListWidget.Adjust)
        self.strip.setMovement(QListWidget.Static); self.strip.setSpacing(4)
        self.strip.currentRowChanged.connect(self._select); right.addWidget(self.strip, 1)
        for label, fn in [("＋ Frame toevoegen", lambda: self._add(False)),
                          ("⧉ Frame dupliceren", lambda: self._add(True)),
                          ("🗑 Frame verwijderen", self._del)]:
            b = QPushButton(label); b.setMinimumHeight(32); b.clicked.connect(fn); right.addWidget(b)
        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Afspelen"); self.play_btn.clicked.connect(self._toggle_play)
        play_row.addWidget(self.play_btn); play_row.addWidget(QLabel("FPS"))
        self.fps = QSpinBox(); self.fps.setRange(1, 60); self.fps.setValue(self.model.fps)
        self.fps.valueChanged.connect(lambda v: setattr(self.model, "fps", v))
        play_row.addWidget(self.fps); right.addLayout(play_row)
        guide_b = QPushButton("📖 Snelgids"); guide_b.setMinimumHeight(32)
        guide_b.clicked.connect(lambda: open_quick_guide(self)); right.addWidget(guide_b)
        row = QHBoxLayout()
        cancel = QPushButton("Annuleer"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        done = QPushButton("Klaar"); done.setObjectName("cta"); done.setMinimumHeight(36)
        done.clicked.connect(self._accept); row.addWidget(done)
        right.addLayout(row)
        rp = QWidget(); rp.setObjectName("panel"); rp.setLayout(right); rp.setFixedWidth(300)
        return rp

    # ---- frames + weergave ---------------------------------------------- #
    def _thumb(self, i):
        return QPixmap.fromImage(self._composite(i))

    def _composite(self, i):
        base = self.model.frames[i].copy()
        if i < len(self.bake) and self.bake[i]:
            fig = StickFigureClip.render_pose(self.poses[i], base.width(), base.height(),
                                              self._fig_color.name(), self._fig_line_w,
                                              square=False)
            p = QPainter(base); p.drawImage(0, 0, fig); p.end()
        return base

    def _guide_image(self, i):
        """Lichtblauwe skelet-mal om in het Tekenen-tabblad overheen te tekenen."""
        return StickFigureClip.render_pose(self.poses[i], self.model.width, self.model.height,
                                           "#3d7fb0", max(2, self._fig_line_w), square=False)

    def _refresh_strip(self):
        self.strip.blockSignals(True); self.strip.clear()
        for i in range(len(self.model.frames)):
            self.strip.addItem(QListWidgetItem(QIcon(self._thumb(i)), str(i + 1)))
        self.strip.setCurrentRow(self.model.current); self.strip.blockSignals(False)

    def _refresh_item(self):
        i = self.model.current
        if 0 <= i < self.strip.count():
            self.strip.item(i).setIcon(QIcon(self._thumb(i)))

    def _load(self):
        i = self.model.current
        prev = self.poses[i - 1] if i > 0 else None
        self.pcanvas.set_pose(self.poses[i], prev, bg=self.model.frames[i])
        self.canvas.set_guide(self._guide_image(i))
        self.canvas.update()
        self.skel_btn.setText("Skelet in beeld: aan" if self.bake[i]
                              else "Skelet in beeld: uit")

    def _select(self, row):
        if row < 0:
            return
        self.model.move_to(row); self._load()

    def _add(self, dup):
        cur = self.model.current
        self.model.add_frame(dup)              # current -> cur+1
        self.poses.insert(cur + 1, dict(self.poses[cur]))
        self.bake.insert(cur + 1, self.bake[cur])
        self._refresh_strip(); self._load()

    def _del(self):
        cur = self.model.current
        n0 = len(self.model.frames)
        self.model.delete_frame()
        if len(self.model.frames) < n0:
            self.poses.pop(min(cur, len(self.poses) - 1))
            self.bake.pop(min(cur, len(self.bake) - 1))
        self.model.current = min(self.model.current, len(self.model.frames) - 1)
        self._refresh_strip(); self._load()

    def _toggle_skeleton(self):
        i = self.model.current
        self.bake[i] = not self.bake[i]
        self._refresh_item(); self._load()

    # ---- gereedschap (tekenen) ------------------------------------------ #
    def _set_tool(self, k):
        self.canvas.tool = k
        for key, b in self._tool_btns.items():
            b.setChecked(key == k)

    def _set_brush(self, v):
        self.canvas.brush = v; self.brush_lbl.setText(f"Lijndikte / penseel: {v} px")

    def _pick_pen_color(self):
        c = QColorDialog.getColor(self.canvas.color, self, "Kies kleur")
        if c.isValid():
            self.canvas.color = c; self._refresh_pen_color()

    def _refresh_pen_color(self):
        c = self.canvas.color
        fg = "white" if c.lightness() < 128 else "black"
        self.color_btn.setStyleSheet(f"background-color:{c.name()};color:{fg};")
        self.color_btn.setText(f"Kleur ({c.name()})")

    def _toggle_draw_onion(self):
        self.canvas.onion = self.donion.isChecked()
        self.donion.setText("Vorig frame tonen: aan" if self.canvas.onion else "Vorig frame tonen: uit")
        self.canvas.update()

    # ---- gereedschap (poppetje) ----------------------------------------- #
    def _pick_fig_color(self):
        c = QColorDialog.getColor(self._fig_color, self, "Skelet-kleur")
        if c.isValid():
            self._fig_color = c; self.pcanvas.color = c.name()
            self._refresh_fig_color(); self.pcanvas.update(); self._refresh_item()

    def _refresh_fig_color(self):
        fg = "white" if self._fig_color.lightness() < 128 else "black"
        self.fig_color_btn.setStyleSheet(f"background-color:{self._fig_color.name()};color:{fg};")
        self.fig_color_btn.setText(f"Skelet-kleur ({self._fig_color.name()})")

    def _set_fig_lw(self, v):
        self._fig_line_w = v; self.pcanvas.line_w = v; self.pcanvas.update(); self._refresh_item()

    # ---- tab-wissel + afspelen ------------------------------------------ #
    def _tab_changed(self, _i):
        self._load()

    def _toggle_play(self):
        if self.playing:
            self._timer.stop(); self.playing = False; self.play_btn.setText("▶ Afspelen")
        elif len(self.model.frames) > 1:
            self.playing = True; self.play_btn.setText("⏸ Pauze")
            self._timer.start(int(1000 / max(1, self.fps.value())))

    def _tick(self):
        self.model.move_to((self.model.current + 1) % len(self.model.frames))
        self.strip.blockSignals(True); self.strip.setCurrentRow(self.model.current)
        self.strip.blockSignals(False); self._load()

    def _accept(self):
        self._timer.stop()
        self.clip.model.frames = self.model.frames
        self.clip.model.fps = self.fps.value()
        self.clip.model.current = 0
        self.clip.poses = self.poses
        self.clip.bake = self.bake
        self.clip.fig_color = self._fig_color.name()
        self.clip.fig_line_w = self._fig_line_w
        self.accept()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # beide canvassen zo groot mogelijk maken (aspect behouden, max ~4x)
        avail_w = max(200, self.width() - 250 - 300 - 90)
        avail_h = max(200, self.height() - 150)
        scale = min(avail_w / self.model.width, avail_h / self.model.height)
        scale = max(1.0, min(scale, 4.0))
        if abs(self.canvas.disp_scale - scale) > 0.02:
            self.canvas.set_display_scale(scale)
        pw = int(self.model.width * scale); ph = int(self.model.height * scale)
        if abs(self.pcanvas.width() - pw) > 4:
            self.pcanvas.setFixedSize(pw, ph)


# =========================================================================== #
#  RIG-STUDIO  —  beweegbaar poppetje (1x tekenen, daarna poseren)
# =========================================================================== #
class PartCanvas(QWidget):
    """Tekenen op één lichaamsdeel (transparante laag), met rust-skelet als hulplijn."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target = None; self.guide = None; self.context = None
        self.W, self.H = 640, 360
        self.disp_scale = 1.0
        self.tool, self.color, self.brush = PEN, QColor("black"), 6
        self._drawing, self._last = False, QPoint()
        self._undo = deque(maxlen=30)
        self.on_change = None
        self.setCursor(Qt.CrossCursor)

    def set_target(self, img, W, H):
        self.target, self.W, self.H = img, W, H
        self.set_display_scale(self.disp_scale)

    def set_display_scale(self, s):
        self.disp_scale = max(0.1, float(s))
        self.setFixedSize(int(self.W * self.disp_scale), int(self.H * self.disp_scale))
        self.update()

    def _pos(self, ev):
        s = self.disp_scale
        return QPoint(max(0, min(int(ev.x() / s), self.W - 1)),
                     max(0, min(int(ev.y() / s), self.H - 1)))

    def _snapshot(self):
        if self.target is not None:
            self._undo.append(self.target.copy())

    def undo(self):
        if self._undo and self.target is not None:
            img = self._undo.pop()
            p = QPainter(self.target)
            p.setCompositionMode(QPainter.CompositionMode_Source)
            p.drawImage(0, 0, img); p.end()
            self.update(); self._notify()

    def clear_part(self):
        if self.target is None:
            return
        self._snapshot(); self.target.fill(Qt.transparent); self.update(); self._notify()

    def _notify(self):
        if self.on_change:
            self.on_change()

    def _pen(self):
        col = self.color if self.tool == PEN else QColor("black")
        size = self.brush if self.tool == PEN else self.brush * 2
        return QPen(col, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def _paint(self, a, b):
        if self.target is None:
            return
        p = QPainter(self.target)
        if self.tool == ERASER:
            p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.setPen(self._pen())
        p.drawLine(a, b) if a != b else p.drawPoint(a)
        p.end()

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton or self.target is None:
            return
        self._snapshot(); pos = self._pos(ev)
        self._drawing, self._last = True, pos
        self._paint(pos, pos); self.update()

    def mouseMoveEvent(self, ev):
        if not self._drawing:
            return
        pos = self._pos(ev); self._paint(self._last, pos); self._last = pos; self.update()

    def mouseReleaseEvent(self, _ev):
        if self._drawing:
            self._drawing = False; self._notify()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.scale(self.disp_scale, self.disp_scale)
        p.fillRect(0, 0, self.W, self.H, QColor("white"))
        if self.context is not None and not self.context.isNull():
            p.setOpacity(0.30); p.drawImage(0, 0, self.context); p.setOpacity(1.0)
        if self.guide is not None and not self.guide.isNull():
            p.setOpacity(0.85); p.drawImage(0, 0, self.guide); p.setOpacity(1.0)
        if self.target is not None:
            p.drawImage(0, 0, self.target)
        p.setPen(QColor("#cccccc")); p.drawRect(0, 0, self.W - 1, self.H - 1)
        p.end()


def _dist_point_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class SkeletonCanvas(QWidget):
    """Bouw vrij een skelet: gewrichten plaatsen/verslepen en botten verbinden."""

    def __init__(self, rig, parent=None):
        super().__init__(parent)
        self.rig = rig
        self.bg = None              # lichte achtergrond: de getekende/geladen figuur
        self.disp_scale = 1.0
        self.mode = "move"          # move | joint | bone | delete
        self._drag = None
        self._pending = None
        self._press_joint = None
        self._moved = False
        self._cursor = None         # voor de elastiek-lijn bij 'bot maken'
        self.on_struct = None       # na toevoegen/verwijderen
        self.on_move = None         # na verslepen (licht)
        self.on_rename = None       # dubbelklik op een gewricht
        self.before_edit = None     # vóór een wijziging (voor undo)
        self.setMouseTracking(True)
        self.set_display_scale(1.0)

    def _hit_r(self):
        return max(20, int(min(self.width(), self.height()) / 22))

    def set_display_scale(self, s):
        self.disp_scale = max(0.1, float(s))
        self.setFixedSize(int(self.rig.width * self.disp_scale),
                          int(self.rig.height * self.disp_scale))
        self.update()

    def _jp(self, jid):
        jx, jy = self.rig.joints[jid]
        return (jx * self.width(), jy * self.height())

    def _nearest_joint(self, x, y, r=None):
        r = r or self._hit_r()
        best, bd = None, r * r
        for jid in self.rig.joints:
            px, py = self._jp(jid)
            d = (x - px) ** 2 + (y - py) ** 2
            if d < bd:
                bd, best = d, jid
        return best

    def _nearest_bone(self, x, y, r=12):
        best, bd = None, r
        for bone in self.rig.bones:
            ax, ay = self._jp(bone[0]); bx, by = self._jp(bone[1])
            d = _dist_point_seg(x, y, ax, ay, bx, by)
            if d < bd:
                bd, best = d, bone
        return best

    def _edit(self):
        if self.before_edit:
            self.before_edit()

    def _connect(self, a, b):
        if a is None or b is None or a == b:
            return
        self._edit()
        self.rig.add_bone(a, b)
        self._pending = None; self._press_joint = None
        if self.on_struct:
            self.on_struct()

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        x, y = ev.x(), ev.y()
        if self.mode == "move":
            self._drag = self._nearest_joint(x, y)
            if self._drag:
                self._edit()
        elif self.mode == "joint":
            self._edit()
            bone = self._nearest_bone(x, y, r=max(10, self._hit_r() // 2))
            if bone is not None:
                # klik óp een bot -> nieuw gewricht ertussen (bot splitsen)
                self.rig.split_bone(bone, x / self.width(), y / self.height())
            else:
                self.rig.add_joint(x / self.width(), y / self.height())
            if self.on_struct:
                self.on_struct()
        elif self.mode == "bone":
            jp = self._nearest_joint(x, y)
            self._press_joint = jp; self._moved = False
            if jp is not None:
                if self._pending is None:
                    self._pending = jp            # begin verbinding (klik of sleep)
                elif jp != self._pending:
                    self._connect(self._pending, jp)   # 2e klik: meteen verbinden
            self._cursor = (x, y)
        elif self.mode == "delete":
            self._edit()
            j = self._nearest_joint(x, y)
            if j is not None:
                self.rig.delete_joint(j)
            else:
                b = self._nearest_bone(x, y)
                if b:
                    self.rig.delete_bone(b)
            if self.on_struct:
                self.on_struct()
        self.update()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            j = self._nearest_joint(ev.x(), ev.y())
            if j is not None and self.on_rename:
                self.on_rename(j)

    def mouseMoveEvent(self, ev):
        self._cursor = (ev.x(), ev.y())
        if self.mode == "move" and self._drag and (ev.buttons() & Qt.LeftButton):
            jx = min(1.0, max(0.0, ev.x() / self.width()))
            jy = min(1.0, max(0.0, ev.y() / self.height()))
            self.rig.joints[self._drag] = (jx, jy)
            for f in self.rig.frames:        # rust en (ongeposeerde) frames gelijk houden
                f[self._drag] = (jx, jy)
            if self.on_move:
                self.on_move()
            self.update()
        elif self.mode == "bone":
            if ev.buttons() & Qt.LeftButton:
                self._moved = True
            if self._pending is not None:
                self.update()

    def mouseReleaseEvent(self, ev):
        if self._drag:
            self._drag = None
            if self.on_struct:
                self.on_struct()
        elif self.mode == "bone" and self._pending is not None and self._moved:
            jr = self._nearest_joint(ev.x(), ev.y())
            if jr is not None and jr != self._pending:
                self._connect(self._pending, jr)   # sleep-verbinding
            self._moved = False
            self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#15151b"))
        if self.bg is not None and not self.bg.isNull():
            p.setOpacity(0.45)
            p.drawImage(self.rect(), self.bg)
            p.setOpacity(1.0)
        p.setPen(QPen(QColor("#2a2a31"), 1)); p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        lw = max(3, int(min(self.width(), self.height()) / 80))
        p.setPen(QPen(QColor("#9fb3c6"), lw, Qt.SolidLine, Qt.RoundCap))
        for bone in self.rig.bones:
            a = self._jp(bone[0]); b = self._jp(bone[1])
            p.drawLine(QPointF(*a), QPointF(*b))
        # hoofd-ring zodat een mal herkenbaar is
        if "head" in self.rig.joints:
            hx, hy = self._jp("head")
            rr = 0.06 * min(self.width(), self.height())
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor("#9fb3c6"), lw))
            p.drawEllipse(QPointF(hx, hy), rr, rr)
        f = QFont("Arial", max(8, int(min(self.width(), self.height()) / 55)))
        for jid in self.rig.joints:
            px, py = self._jp(jid)
            pend = (jid == self._pending)
            p.setBrush(QColor("#7fd4ff") if pend else QColor("#e2e6ea"))
            p.setPen(QPen(QColor("#0b0b0d"), 1))
            p.drawEllipse(QPointF(px, py), 8, 8)
            p.setPen(QColor("#8aa0b4")); p.setFont(f)
            p.drawText(QPointF(px + 11, py - 8), jid)
        # elastiek-lijn terwijl je een bot maakt
        if self.mode == "bone" and self._pending is not None and self._cursor:
            sx, sy = self._jp(self._pending)
            pen = QPen(QColor("#7fd4ff"), max(2, int(min(self.width(), self.height()) / 110)))
            pen.setStyle(Qt.DashLine); p.setPen(pen)
            p.drawLine(QPointF(sx, sy), QPointF(*self._cursor))
        p.end()


class RigStudio(QDialog):
    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle("Poppetje met skelet (rigging) - DraveMotion")
        # werk op een kopie
        self.work = RigClip(
            parts=[{"bone": pt["bone"], "image": pt["image"].copy(), "art": pt["art"]}
                   for pt in clip.parts],
            frames=[dict(f) for f in clip.frames] or [dict(clip.rest)],
            width=clip.width, height=clip.height, fps=clip.fps,
            joints=dict(clip.joints), bones=list(clip.bones))
        self.work.stretch = bool(getattr(clip, "stretch", True))
        self.work.mouth_bone = clip.mouth_bone if getattr(clip, "mouth_bone", None) else None
        self.work.mouth = list(getattr(clip, "mouth", []))
        self.work.mouth_closed = (clip.mouth_closed.copy()
                                  if getattr(clip, "mouth_closed", None) is not None else None)
        self.work.mouth_open = (clip.mouth_open.copy()
                                if getattr(clip, "mouth_open", None) is not None else None)
        self._mouth_target = "open"
        self._mouth_audio = None
        self.cur_part = 0
        self.idx = 0
        self.playing = False
        self._undo_stack = []
        self._redo_stack = []
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
        self._build()
        self._load_part(); self._refresh_strip(); self._load_frame()
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint |
                            Qt.WindowMinimizeButtonHint)
        self.resize(1320, 840); self.setMinimumSize(1040, 680)
        QTimer.singleShot(0, self.showMaximized)

    # ---- opbouw ---------------------------------------------------------- #
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8); outer.setSpacing(8)
        self._banner = QWidget()
        self._banner.setStyleSheet("background:#3a2e12; border:1px solid #6b531f; border-radius:6px;")
        self._banner.setMaximumHeight(72)
        brow = QHBoxLayout(self._banner); brow.setContentsMargins(10, 4, 6, 4)
        btxt = QLabel("⚠  Tip: laad een vaste afbeelding (PNG/SVG) met ‘📂 Afbeelding/SVG laden…’, "
                      "leg het skelet er netjes overheen, klik ‘🪄 Verdeel over de botten’, en "
                      "poseer dan per frame op het tabblad ‘Animeren’.")
        btxt.setWordWrap(True)
        btxt.setStyleSheet("color:#ffd98a; font-weight:bold; background:transparent; border:0;")
        hide = QToolButton(); hide.setText("✕"); hide.setToolTip("Deze balk verbergen")
        hide.setStyleSheet("color:#ffd98a; background:transparent; border:0; font-weight:bold;")
        hide.clicked.connect(lambda: self._banner.setVisible(False))
        brow.addWidget(btxt, 1); brow.addWidget(hide, 0, Qt.AlignTop)
        outer.addWidget(self._banner)
        row = QHBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_skeleton_tab(), "🦿  Skelet")
        self.tabs.addTab(self._build_draw_tab(), "✏  Tekenen (delen)")
        self.tabs.addTab(self._build_anim_tab(), "🦴  Animeren")
        self.tabs.addTab(self._build_mouth_tab(), "👄  Mond / lip-sync")
        self.tabs.currentChanged.connect(self._tab_changed)
        row.addWidget(self.tabs, 1)
        row.addWidget(self._build_right_panel())
        outer.addLayout(row)

    def _build_skeleton_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Skelet bouwen"))
        tools.addWidget(QLabel("Begin met een mal:"))
        self.tmpl_combo = QComboBox()
        for nm in SKELETON_TEMPLATES:
            self.tmpl_combo.addItem(nm)
        load = QPushButton("Mal laden"); load.clicked.connect(self._load_template)
        tools.addWidget(self.tmpl_combo); tools.addWidget(load)
        loadimg = QPushButton("📂  Afbeelding/SVG laden…")
        loadimg.setMinimumHeight(34); loadimg.clicked.connect(self._load_figure_image)
        loadimg.setToolTip("Laad een kant-en-klare tekening als figuur. Daarna verdeel je hem over "
                           "de botten op het tabblad ‘Tekenen (delen)’.")
        tools.addWidget(loadimg)
        tools.addWidget(QLabel("Gereedschap:"))
        self._skel_btns = {}
        for key, label in [("move", "✋ Verplaatsen"), ("joint", "● Gewricht plaatsen"),
                           ("bone", "／ Bot maken"), ("delete", "🗑 Verwijderen")]:
            b = QPushButton(label); b.setCheckable(True); b.setMinimumHeight(32)
            b.clicked.connect(lambda _, k=key: self._set_skel_mode(k))
            tools.addWidget(b); self._skel_btns[key] = b
        self._skel_btns["move"].setChecked(True)
        ub = QPushButton("↶  Ongedaan"); ub.setMinimumHeight(32)
        ub.clicked.connect(self._undo); tools.addWidget(ub)
        rb = QPushButton("↷  Opnieuw"); rb.setMinimumHeight(32)
        rb.clicked.connect(self._redo); tools.addWidget(rb)
        wis = QPushButton("Wis hele skelet"); wis.clicked.connect(self._clear_skeleton)
        tools.addWidget(wis)
        tip = QLabel("Gewricht plaatsen: klik op een leeg plekje, of klik <b>óp een bot</b> om er "
                     "een extra gewricht in te zetten (bijv. een schouder of pols, zodat de arm "
                     "daar kan buigen). Bot maken: <b>sleep</b> van "
                     "het ene gewricht naar het andere (of klik ze na elkaar aan). Verplaatsen: "
                     "sleep een gewricht. Verwijderen: klik op een gewricht of bot. Dubbelklik een "
                     "gewricht om het een naam te geven.")
        tip.setWordWrap(True); tools.addWidget(tip)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(300)
        lay.addWidget(tp)
        self.skelcv = SkeletonCanvas(self.work)
        self.skelcv.on_struct = self._skeleton_changed
        self.skelcv.on_move = lambda: (self.skelcv.update(), self._refresh_item())
        self.skelcv.on_rename = self._rename_joint
        self.skelcv.before_edit = self._push_undo
        sc = QScrollArea(); sc.setWidget(self.skelcv); sc.setAlignment(Qt.AlignCenter)
        lay.addWidget(sc, 1)
        return w

    def _build_draw_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Lichaamsdeel"))
        self.active_part_lbl = QLabel("Je tekent nu: —")
        self.active_part_lbl.setWordWrap(True)
        self.active_part_lbl.setStyleSheet("font-weight:bold; color:#7fb4ff;")
        tools.addWidget(self.active_part_lbl)
        self.part_list = QListWidget()
        self._fill_part_list()
        self.part_list.setCurrentRow(0)
        self.part_list.currentRowChanged.connect(self._select_part)
        self.part_list.setMaximumHeight(210); tools.addWidget(self.part_list)
        self._pen_btn = QPushButton("✏  Pen"); self._pen_btn.setCheckable(True); self._pen_btn.setChecked(True)
        self._pen_btn.clicked.connect(lambda: self._set_part_tool(PEN)); tools.addWidget(self._pen_btn)
        self._gum_btn = QPushButton("⌫  Gum"); self._gum_btn.setCheckable(True)
        self._gum_btn.clicked.connect(lambda: self._set_part_tool(ERASER)); tools.addWidget(self._gum_btn)
        self.pcolor_btn = QPushButton(); self.pcolor_btn.clicked.connect(self._pick_part_color)
        self._part_color = QColor("black"); self._refresh_part_color(); tools.addWidget(self.pcolor_btn)
        self.pbrush_lbl = QLabel("Lijndikte: 6 px"); tools.addWidget(self.pbrush_lbl)
        self.pbrush = QSlider(Qt.Horizontal); self.pbrush.setRange(1, 60); self.pbrush.setValue(6)
        self.pbrush.valueChanged.connect(self._set_part_brush); tools.addWidget(self.pbrush)
        wis = QPushButton("Dit deel wissen"); wis.clicked.connect(self._clear_part); tools.addWidget(wis)
        undo = QPushButton("Ongedaan"); undo.clicked.connect(lambda: self.partcv.undo() or self._after_draw()); tools.addWidget(undo)
        loadimg = QPushButton("📂  Afbeelding/SVG laden…")
        loadimg.setMinimumHeight(36); loadimg.clicked.connect(self._load_figure_image)
        loadimg.setToolTip("Laad een kant-en-klare tekening (bijv. een SVG) als je figuur. "
                           "Daarna kun je ‘Verdeel over de botten’ gebruiken.")
        tools.addWidget(loadimg)
        dist = QPushButton("🪄  Verdeel over de botten")
        dist.setMinimumHeight(40); dist.clicked.connect(self._distribute)
        tools.addWidget(dist)
        self.overlap_lbl = QLabel("Zachte naad (overlap): 14 px")
        tools.addWidget(self.overlap_lbl)
        self.overlap_slider = QSlider(Qt.Horizontal)
        self.overlap_slider.setRange(0, 60); self.overlap_slider.setValue(14)
        self.overlap_slider.valueChanged.connect(
            lambda v: self.overlap_lbl.setText(f"Zachte naad (overlap): {v} px"))
        self.overlap_slider.setToolTip("Hoe groter, hoe meer de delen elkaar bij de gewrichten "
                                       "overlappen. Dat vult de naad bij het buigen. Zet weer op "
                                       "‘Verdeel’ na het wijzigen.")
        tools.addWidget(self.overlap_slider)
        tip = QLabel("Aanrader: laad een vaste afbeelding (PNG/SVG) met ‘📂 Afbeelding/SVG "
                     "laden…’, en klik daarna op ‘🪄 Verdeel over de botten’. Je tekening wordt "
                     "dan automatisch over de botten verdeeld, zodat alles meebeweegt als je "
                     "animeert.\n\nLiever zelf tekenen? Kies hierboven een lichaamsdeel en teken "
                     "dat op zijn bot (het oplichtende bot hoort bij het gekozen deel).")
        tip.setWordWrap(True); tools.addWidget(tip)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(300)
        lay.addWidget(tp)
        self.partcv = PartCanvas(); self.partcv.on_change = self._after_draw
        sc = QScrollArea(); sc.setWidget(self.partcv); sc.setAlignment(Qt.AlignCenter)
        lay.addWidget(sc, 1)
        return w

    def _build_anim_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Animeren"))
        reset = QPushButton("Houding terug naar rust"); reset.clicked.connect(self._reset_pose)
        tools.addWidget(reset)
        self.stretch_chk = QCheckBox("Delen meerekken met de botten")
        self.stretch_chk.setChecked(bool(getattr(self.work, "stretch", True)))
        self.stretch_chk.setToolTip("Aan: een deel rekt mee in de lengte als je een gewricht "
                                    "verder weg sleept (dikte blijft gelijk).\nUit: delen houden "
                                    "hun vaste formaat en draaien alleen.")
        self.stretch_chk.toggled.connect(self._toggle_stretch)
        tools.addWidget(self.stretch_chk)
        tip = QLabel("Sleep de bolletjes (gewrichten) om de houding te zetten. "
                     "Je getekende delen bewegen mee. Voeg rechts frames toe voor de animatie.")
        tip.setWordWrap(True); tools.addWidget(tip)
        self.anim_hint = QLabel("")
        self.anim_hint.setWordWrap(True)
        self.anim_hint.setStyleSheet(
            "background:#3a2a10; color:#ffcf6b; border:1px solid #6b5012;"
            "border-radius:6px; padding:8px; font-weight:bold;")
        self.anim_hint.setVisible(False)
        tools.addWidget(self.anim_hint)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(300)
        lay.addWidget(tp)
        self.posecv = PoseCanvas(square=False); self.posecv.handles_only = True
        self.posecv.on_change = self._after_pose
        self.posecv.setFixedSize(self.work.width, self.work.height)
        sc = QScrollArea(); sc.setWidget(self.posecv); sc.setAlignment(Qt.AlignCenter)
        lay.addWidget(sc, 1)
        return w

    def _build_mouth_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Mond / lip-sync"))
        tools.addWidget(QLabel("Teken twee mondstanden op de juiste plek in je figuur:"))
        self.mouth_target_combo = QComboBox()
        self.mouth_target_combo.addItems(["Mond open", "Mond dicht"])
        self.mouth_target_combo.currentIndexChanged.connect(self._set_mouth_target)
        tools.addWidget(self.mouth_target_combo)
        self.mouth_target_lbl = QLabel("Je tekent nu: mond open")
        self.mouth_target_lbl.setStyleSheet("font-weight:bold; color:#7fb4ff;")
        self.mouth_target_lbl.setWordWrap(True); tools.addWidget(self.mouth_target_lbl)
        self._mpen_btn = QPushButton("✏  Pen"); self._mpen_btn.setCheckable(True); self._mpen_btn.setChecked(True)
        self._mpen_btn.clicked.connect(lambda: self._set_mouth_tool(PEN)); tools.addWidget(self._mpen_btn)
        self._mgum_btn = QPushButton("⌫  Gum"); self._mgum_btn.setCheckable(True)
        self._mgum_btn.clicked.connect(lambda: self._set_mouth_tool(ERASER)); tools.addWidget(self._mgum_btn)
        self.mcolor_btn = QPushButton(); self.mcolor_btn.clicked.connect(self._pick_mouth_color)
        self._mouth_color = QColor("black"); tools.addWidget(self.mcolor_btn)
        self.mbrush_lbl = QLabel("Lijndikte: 6 px"); tools.addWidget(self.mbrush_lbl)
        self.mbrush = QSlider(Qt.Horizontal); self.mbrush.setRange(1, 60); self.mbrush.setValue(6)
        self.mbrush.valueChanged.connect(self._set_mouth_brush); tools.addWidget(self.mbrush)
        wis = QPushButton("Deze mondstand wissen"); wis.clicked.connect(self._clear_mouth); tools.addWidget(wis)
        undo = QPushButton("Ongedaan"); undo.clicked.connect(lambda: self.mouthcv.undo()); tools.addWidget(undo)
        tools.addWidget(section("Meebewegen"))
        tools.addWidget(QLabel("Mond volgt bot:"))
        self.mouth_bone_combo = QComboBox()
        self.mouth_bone_combo.currentIndexChanged.connect(self._set_mouth_bone)
        tools.addWidget(self.mouth_bone_combo)
        tools.addWidget(section("Stem → mond"))
        self.mouth_thr_lbl = QLabel("Gevoeligheid: 18%"); tools.addWidget(self.mouth_thr_lbl)
        self.mouth_thr = QSlider(Qt.Horizontal); self.mouth_thr.setRange(2, 60); self.mouth_thr.setValue(18)
        self.mouth_thr.valueChanged.connect(lambda v: self.mouth_thr_lbl.setText(f"Gevoeligheid: {v}%"))
        self.mouth_thr.setToolTip("Lager = mond gaat al bij zacht geluid open; hoger = alleen bij hard geluid.")
        tools.addWidget(self.mouth_thr)
        aud = QPushButton("📂  Kies audiobestand…"); aud.setMinimumHeight(34)
        aud.clicked.connect(self._pick_mouth_audio); tools.addWidget(aud)
        self.mouth_audio_lbl = QLabel("Nog geen audio gekozen."); self.mouth_audio_lbl.setWordWrap(True)
        tools.addWidget(self.mouth_audio_lbl)
        gen = QPushButton("👄  Genereer mond-animatie"); gen.setObjectName("cta"); gen.setMinimumHeight(40)
        gen.clicked.connect(self._gen_lipsync); tools.addWidget(gen)
        tip = QLabel("Zo werkt het:\n1) Teken een open én een dichte mond op de juiste plek.\n"
                     "2) Kies bij ‘Mond volgt bot’ bijv. het hoofd, zodat de mond meebeweegt.\n"
                     "3) Kies je stem-/audiobestand en klik ‘Genereer’. De mond gaat open waar het "
                     "geluid luid is.\n4) Zet hetzelfde geluid op de tijdlijn op dezelfde starttijd.")
        tip.setWordWrap(True); tools.addWidget(tip)
        tools.addStretch(1)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(300)
        lay.addWidget(tp)
        self.mouthcv = PartCanvas(); self.mouthcv.on_change = self._after_mouth_draw
        sc = QScrollArea(); sc.setWidget(self.mouthcv); sc.setAlignment(Qt.AlignCenter)
        lay.addWidget(sc, 1)
        self._refresh_mouth_color()
        return w

    # ---- mond / lip-sync ------------------------------------------------- #
    def _refresh_mouth_bones(self):
        self.mouth_bone_combo.blockSignals(True)
        self.mouth_bone_combo.clear()
        self.mouth_bone_combo.addItem("(vast — beweegt niet mee)", None)
        if not self.work.mouth_bone:
            for bone in self.work.bones:
                if "head" in bone:
                    self.work.mouth_bone = bone; break
        sel = 0
        for i, bone in enumerate(self.work.bones):
            self.mouth_bone_combo.addItem(bone_label(bone, i), bone)
            if self.work.mouth_bone and tuple(self.work.mouth_bone) == tuple(bone):
                sel = i + 1
        self.mouth_bone_combo.setCurrentIndex(sel)
        self.mouth_bone_combo.blockSignals(False)

    def _set_mouth_bone(self, idx):
        self.work.mouth_bone = self.mouth_bone_combo.itemData(idx)
        self.mouthcv.guide = self._rest_guide(self.work.mouth_bone); self.mouthcv.update()

    def _set_mouth_target(self, idx):
        self._mouth_target = "open" if idx == 0 else "closed"
        self._load_mouth()

    def _load_mouth(self):
        self._refresh_mouth_bones()
        if not self.work.bones:
            self.mouthcv.set_target(None, self.work.width, self.work.height)
            self.mouthcv.guide = self._rest_guide(None); self.mouthcv.context = None
            self.mouthcv.update()
            self.mouth_target_lbl.setText("Maak eerst een skelet (tabblad ‘Skelet’).")
            return
        t = self._mouth_target
        img = self.work.mouth_open if t == "open" else self.work.mouth_closed
        if img is None:
            img = self.work._blank_image()
            if t == "open":
                self.work.mouth_open = img
            else:
                self.work.mouth_closed = img
        self.mouthcv.set_target(img, self.work.width, self.work.height)
        self.mouthcv.color = self._mouth_color
        self.mouthcv.guide = self._rest_guide(self.work.mouth_bone)
        self.mouthcv.context = self.work.render_pose(self.work.joints, fallback_skeleton=True)
        self.mouthcv.update()
        self.mouth_target_lbl.setText("Je tekent nu: mond " + ("open" if t == "open" else "dicht"))

    def _set_mouth_tool(self, tool):
        self.mouthcv.tool = tool
        self._mpen_btn.setChecked(tool == PEN); self._mgum_btn.setChecked(tool == ERASER)

    def _set_mouth_brush(self, v):
        self.mouthcv.brush = v; self.mbrush_lbl.setText(f"Lijndikte: {v} px")

    def _pick_mouth_color(self):
        c = QColorDialog.getColor(self._mouth_color, self, "Mondkleur")
        if c.isValid():
            self._mouth_color = c; self.mouthcv.color = c; self._refresh_mouth_color()

    def _refresh_mouth_color(self):
        fg = "white" if self._mouth_color.lightness() < 128 else "black"
        self.mcolor_btn.setStyleSheet(f"background-color:{self._mouth_color.name()};color:{fg};")
        self.mcolor_btn.setText(f"Kleur ({self._mouth_color.name()})")

    def _clear_mouth(self):
        self.mouthcv.clear_part()

    def _after_mouth_draw(self):
        self.mouthcv.context = self.work.render_pose(self.work.joints, fallback_skeleton=True)

    def _pick_mouth_audio(self):
        start = MEDIA_DIR if os.path.isdir(MEDIA_DIR) else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Kies audiobestand", start,
            "Audio (*.mp3 *.wav *.m4a *.ogg *.flac);;Alle bestanden (*.*)")
        if path:
            self._mouth_audio = path
            self.mouth_audio_lbl.setText("Gekozen: " + os.path.basename(path))

    def _gen_lipsync(self):
        if not self._mouth_audio:
            QMessageBox.information(self, "Lip-sync", "Kies eerst een audiobestand."); return
        if self.work.mouth_open is None and self.work.mouth_closed is None:
            QMessageBox.information(self, "Lip-sync", "Teken eerst minstens een open mond."); return
        self._push_undo()
        thr = self.mouth_thr.value() / 100.0
        base = self.work.frames[self.idx] if self.work.frames else None
        n = self.work.apply_lipsync(self._mouth_audio, threshold=thr, body_pose=base)
        if n <= 0:
            QMessageBox.warning(self, "Lip-sync",
                "Kon geen geluid uit dit bestand lezen. Probeer een ander bestand (mp3 of wav).")
            return
        self.idx = 0
        self._refresh_strip(); self._load_frame()
        QMessageBox.information(self, "Klaar",
            f"{n} frames gemaakt en gekoppeld aan het geluid "
            f"(≈{n / max(1, self.work.fps):.1f} s). Klik rechts op ▶ Afspelen om de mond te zien "
            "bewegen.\n\nZet daarna hetzelfde audiobestand op de tijdlijn, op dezelfde starttijd "
            "als dit poppetje, zodat beeld en geluid gelijk lopen.")

    def _build_right_panel(self):
        right = QVBoxLayout(); right.addWidget(section("Frames (houdingen)"))
        self.strip = QListWidget(); self.strip.setViewMode(QListWidget.IconMode)
        self.strip.setIconSize(QSize(96, 64)); self.strip.setResizeMode(QListWidget.Adjust)
        self.strip.setMovement(QListWidget.Static); self.strip.setSpacing(4)
        self.strip.currentRowChanged.connect(self._select_frame); right.addWidget(self.strip, 1)
        for label, fn in [("＋ Frame toevoegen", lambda: self._add(True)),
                          ("🗑 Frame verwijderen", self._del)]:
            b = QPushButton(label); b.setMinimumHeight(32); b.clicked.connect(fn); right.addWidget(b)
        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Afspelen"); self.play_btn.clicked.connect(self._toggle_play)
        play_row.addWidget(self.play_btn); play_row.addWidget(QLabel("FPS"))
        self.fps = QSpinBox(); self.fps.setRange(1, 60); self.fps.setValue(self.work.fps)
        self.fps.valueChanged.connect(lambda v: setattr(self.work, "fps", v))
        play_row.addWidget(self.fps); right.addLayout(play_row)
        guide_b = QPushButton("📖 Snelgids"); guide_b.setMinimumHeight(32)
        guide_b.clicked.connect(lambda: open_quick_guide(self)); right.addWidget(guide_b)
        row = QHBoxLayout()
        cancel = QPushButton("Annuleer"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        done = QPushButton("Klaar"); done.setObjectName("cta"); done.setMinimumHeight(36)
        done.clicked.connect(self._accept); row.addWidget(done)
        right.addLayout(row)
        rp = QWidget(); rp.setObjectName("panel"); rp.setLayout(right); rp.setFixedWidth(300)
        return rp

    # ---- tekenen (delen) ------------------------------------------------- #
    def _rest_guide(self, sel_bone):
        W, H = self.work.width, self.work.height
        img = QImage(W, H, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
        base = max(3, int(min(W, H) / 70))
        for bone in self.work.bones:
            j1, j2 = bone
            a = self.work._pt(j1, self.work.joints); b = self.work._pt(j2, self.work.joints)
            sel = (bone == sel_bone)
            p.setPen(QPen(QColor("#1f6fd0") if sel else QColor("#5d7387"),
                         base + (4 if sel else 0), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(*a), QPointF(*b))
        if "head" in self.work.joints:
            hx, hy = self.work.joints["head"]
            rr = 0.06 * min(W, H)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor("#5d7387"), base))
            p.drawEllipse(QPointF(hx * W, hy * H), rr, rr)
        for jid, (jx, jy) in self.work.joints.items():
            p.setBrush(QColor("#dfe3e7")); p.setPen(QPen(QColor("#20262c"), 1))
            p.drawEllipse(QPointF(jx * W, jy * H), base * 0.8, base * 0.8)
        p.end()
        return img

    def _fill_part_list(self):
        self.part_list.blockSignals(True); self.part_list.clear()
        for i, pt in enumerate(self.work.parts):
            self.part_list.addItem(bone_label(pt["bone"], i))
        self.part_list.blockSignals(False)

    # ---- skelet bouwen --------------------------------------------------- #
    def _set_skel_mode(self, k):
        self.skelcv.mode = k
        self.skelcv._pending = None; self.skelcv._press_joint = None; self.skelcv._moved = False
        for key, b in self._skel_btns.items():
            b.setChecked(key == k)

    def _load_template(self):
        self._push_undo()
        self.work.load_template(self.tmpl_combo.currentText())
        self.cur_part = 0; self.idx = 0
        self._skeleton_changed()

    def _clear_skeleton(self):
        self._push_undo()
        self.work.joints = {}; self.work.bones = []
        self.work.parts = []; self.work.frames = [dict()]
        self.cur_part = 0; self.idx = 0
        self._skeleton_changed()

    def _rename_joint(self, jid):
        new, ok = QInputDialog.getText(self, "Gewricht hernoemen",
                                       f"Nieuwe naam voor '{jid}':", text=jid)
        if ok and new.strip() and new.strip() != jid:
            self._push_undo()
            if self.work.rename_joint(jid, new.strip()):
                self._skeleton_changed()

    # ---- undo / redo ----------------------------------------------------- #
    def _snap(self):
        return {"joints": dict(self.work.joints),
                "bones": [tuple(b) for b in self.work.bones],
                "parts": [{"bone": pt["bone"], "image": pt["image"].copy(), "art": pt["art"]}
                          for pt in self.work.parts],
                "frames": [dict(f) for f in self.work.frames],
                "mouth": list(getattr(self.work, "mouth", [])),
                "mouth_bone": self.work.mouth_bone,
                "mouth_closed": (self.work.mouth_closed.copy()
                                 if self.work.mouth_closed is not None else None),
                "mouth_open": (self.work.mouth_open.copy()
                               if self.work.mouth_open is not None else None),
                "cur_part": self.cur_part, "idx": self.idx}

    def _push_undo(self):
        self._undo_stack.append(self._snap())
        if len(self._undo_stack) > 25:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore(self, snap):
        self.work.joints = dict(snap["joints"])
        self.work.bones = [tuple(b) for b in snap["bones"]]
        self.work.parts = [{"bone": pt["bone"], "image": pt["image"].copy(), "art": pt["art"]}
                           for pt in snap["parts"]]
        self.work.frames = [dict(f) for f in snap["frames"]]
        self.work.mouth = list(snap.get("mouth", []))
        self.work.mouth_bone = snap.get("mouth_bone")
        self.work.mouth_closed = (snap["mouth_closed"].copy()
                                  if snap.get("mouth_closed") is not None else None)
        self.work.mouth_open = (snap["mouth_open"].copy()
                                if snap.get("mouth_open") is not None else None)
        self.cur_part = min(snap["cur_part"], max(0, len(self.work.parts) - 1))
        self.idx = min(snap["idx"], max(0, len(self.work.frames) - 1))
        self._fill_part_list()
        if self.work.parts:
            self.part_list.blockSignals(True); self.part_list.setCurrentRow(self.cur_part)
            self.part_list.blockSignals(False)
        self._load_part(); self._refresh_strip(); self._load_frame(); self.skelcv.update()

    def _undo(self):
        if self._undo_stack:
            self._redo_stack.append(self._snap())
            self._restore(self._undo_stack.pop())

    def _redo(self):
        if self._redo_stack:
            self._undo_stack.append(self._snap())
            self._restore(self._redo_stack.pop())

    def _update_skel_bg(self):
        """Toon de getekende/geladen figuur licht achter het skelet, om op uit te lijnen."""
        if not hasattr(self, "skelcv"):
            return
        self.skelcv.bg = (self.work.flatten_parts()
                          if any(pt["art"] for pt in self.work.parts) else None)
        self.skelcv.update()

    def _skeleton_changed(self):
        self.work.sync()
        self.cur_part = min(self.cur_part, max(0, len(self.work.parts) - 1))
        self._fill_part_list()
        if self.work.parts:
            self.part_list.setCurrentRow(self.cur_part)
        self.skelcv.update()
        self._load_part(); self._refresh_strip(); self._load_frame(); self._update_skel_bg()

    def _select_part(self, row):
        if row < 0:
            return
        self.cur_part = row
        self._load_part()

    def _load_part(self):
        if not self.work.parts:
            self.partcv.set_target(None, self.work.width, self.work.height)
            self.partcv.guide = self._rest_guide(None)
            self.partcv.context = None; self.partcv.update()
            self.active_part_lbl.setText("Je tekent nu: — (maak eerst een skelet)")
            return
        self.cur_part = min(self.cur_part, len(self.work.parts) - 1)
        pt = self.work.parts[self.cur_part]
        self.active_part_lbl.setText("Je tekent nu: " + bone_label(pt["bone"], self.cur_part))
        self.partcv.set_target(pt["image"], self.work.width, self.work.height)
        self.partcv.guide = self._rest_guide(pt["bone"])
        self.partcv.context = self.work.render_pose(self.work.joints, fallback_skeleton=False)
        self.partcv.update()

    def _load_figure_image(self):
        if not self.work.parts:
            QMessageBox.information(self, "Tekening laden",
                                    "Maak eerst een skelet in het tabblad ‘Skelet’.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Teken-afbeelding laden", PROJECTS_DIR,
            "Afbeeldingen (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;Alle (*)")
        if not path:
            return
        img = ImageClip._load(path)
        if img.isNull():
            QMessageBox.warning(self, "Laden mislukt", "Kon deze afbeelding niet lezen.")
            return
        self._push_undo()
        W, H = self.work.width, self.work.height
        scaled = img.scaled(W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        canvas = self.work._blank_image()
        p = QPainter(canvas)
        ox = (W - scaled.width()) // 2; oy = (H - scaled.height()) // 2
        p.drawImage(ox, oy, scaled); p.end()
        # zet de hele tekening op één deel, de rest leeg -> klaar voor ‘Verdeel’
        for pt in self.work.parts:
            pt["image"] = self.work._blank_image(); pt["art"] = False
        self.work.parts[0]["image"] = canvas; self.work.parts[0]["art"] = True
        self.cur_part = 0
        self._fill_part_list()
        self.part_list.blockSignals(True); self.part_list.setCurrentRow(0)
        self.part_list.blockSignals(False)
        self._load_part(); self._refresh_strip(); self._update_skel_bg()
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(0)   # naar ‘Skelet’ om over de figuur uit te lijnen
        QMessageBox.information(self, "Tekening geladen",
            "Je tekening staat nu op het poppetje en je ziet hem licht achter het skelet.\n\n"
            "1) Sleep hier op ‘Skelet’ de gewrichten zodat het skelet mooi óver je figuur ligt "
            "(hoofd op hoofd, handen op handen, voeten op voeten).\n"
            "2) Ga dan naar ‘Tekenen (delen)’ en klik op ‘🪄 Verdeel over de botten’.\n"
            "3) Op ‘Animeren’ beweegt je figuur dan mee als je een gewricht versleept.")

    def _distribute(self):
        if not HAVE_NUMPY:
            QMessageBox.information(self, "Verdelen",
                                    "Hiervoor is numpy nodig (zit in de meegeleverde installatie).")
            return
        if not self.work.bones:
            QMessageBox.information(self, "Verdelen",
                                    "Maak eerst een skelet met botten in het tabblad ‘Skelet’.")
            return
        if not any(pt["art"] for pt in self.work.parts):
            QMessageBox.information(self, "Verdelen", "Teken eerst je figuur.")
            return
        self._push_undo()
        flat = self.work.flatten_parts()
        if skin_to_parts(self.work, flat, overlap=self.overlap_slider.value()):
            self._fill_part_list()
            if self.work.parts:
                self.part_list.blockSignals(True); self.part_list.setCurrentRow(self.cur_part)
                self.part_list.blockSignals(False)
            self._load_part(); self._refresh_strip(); self._update_skel_bg()
            n_art = sum(1 for pt in self.work.parts if pt["art"])
            if n_art <= 1:
                QMessageBox.warning(self, "Bijna verdeeld",
                    "De tekening is wel verwerkt, maar bijna alles kwam op één bot terecht — "
                    "dan beweegt het figuur bij het animeren als één geheel.\n\n"
                    "Dit gebeurt als het skelet niet goed óver de tekening ligt. Ga naar het "
                    "tabblad ‘Skelet’, leg de botten netjes door de armen, benen en romp van je "
                    "figuur, en klik daarna opnieuw op ‘Verdeel’.")
            else:
                QMessageBox.information(self, "Klaar",
                    "De tekening is over %d delen verdeeld. Ga naar ‘Animeren’ en versleep een "
                    "gewricht — de delen bewegen nu mee.\n\nTip: bij een sterke knik kan er bij een "
                    "gewricht een kleine naad ontstaan; dat hoort bij deze manier van rigging." % n_art)
        else:
            QMessageBox.warning(self, "Verdelen lukte niet",
                "De tekening kon niet verdeeld worden. Controleer dat:\n"
                "• er een skelet met botten is (tabblad ‘Skelet’);\n"
                "• je figuur zichtbare, ondoorzichtige kleuren heeft (geen lege/transparante "
                "tekening).\n\nLaad je figuur opnieuw via ‘📂 Afbeelding/SVG laden…’ en probeer "
                "het nog eens.")

    def _set_part_tool(self, t):
        self.partcv.tool = t
        self._pen_btn.setChecked(t == PEN); self._gum_btn.setChecked(t == ERASER)

    def _set_part_brush(self, v):
        self.partcv.brush = v; self.pbrush_lbl.setText(f"Lijndikte: {v} px")

    def _pick_part_color(self):
        c = QColorDialog.getColor(self._part_color, self, "Tekenkleur")
        if c.isValid():
            self._part_color = c; self.partcv.color = c; self._refresh_part_color()

    def _refresh_part_color(self):
        fg = "white" if self._part_color.lightness() < 128 else "black"
        self.pcolor_btn.setStyleSheet(f"background-color:{self._part_color.name()};color:{fg};")
        self.pcolor_btn.setText(f"Kleur ({self._part_color.name()})")

    def _clear_part(self):
        self.partcv.clear_part(); self._after_draw()

    def _after_draw(self):
        # markeer dat dit deel tekening bevat + ververs context/strip
        if not self.work.parts:
            return
        self.work.parts[self.cur_part]["art"] = True
        self.partcv.context = self.work.render_pose(self.work.joints, fallback_skeleton=False)
        self._refresh_strip(); self._update_skel_bg()

    # ---- animeren (poseren) --------------------------------------------- #
    def _select_frame(self, row):
        if row < 0:
            return
        self.idx = row; self._load_frame()

    def _load_frame(self):
        pose = self.work.frames[self.idx]
        self.posecv.set_skeleton(list(self.work.joints), self.work.bones, self.work.joints)
        self.posecv.set_pose(pose, None, bg=self.work.render_frame(self.idx))
        hint = getattr(self, "anim_hint", None)
        if hint is not None:
            n_art = sum(1 for pt in self.work.parts if pt.get("art"))
            if n_art <= 1:
                hint.setText("⚠ Je figuur is nog niet over de botten verdeeld, dus hij beweegt "
                             "niet mee. Ga naar het tabblad ‘Tekenen (delen)’ en klik op "
                             "‘🪄 Verdeel over de botten’.")
                hint.setVisible(True)
            else:
                hint.setVisible(False)

    def _after_pose(self):
        # tijdens slepen: render het poppetje live opnieuw als achtergrond
        self.posecv.bg = self.work.render_frame(self.idx)
        self._refresh_item()

    def _toggle_stretch(self, on):
        self.work.stretch = bool(on)
        self._load_frame(); self._refresh_strip()

    def _reset_pose(self):
        self.work.frames[self.idx] = dict(self.work.joints); self._load_frame(); self._refresh_item()

    def _add(self, dup):
        src = self.work.frames[self.idx]
        self.work.frames.insert(self.idx + 1, dict(src))
        self.idx += 1; self._refresh_strip(); self._load_frame()

    def _del(self):
        if len(self.work.frames) > 1:
            self.work.frames.pop(self.idx)
            self.idx = min(self.idx, len(self.work.frames) - 1)
        self._refresh_strip(); self._load_frame()

    def _toggle_play(self):
        if self.playing:
            self._timer.stop(); self.playing = False; self.play_btn.setText("▶ Afspelen")
        elif len(self.work.frames) > 1:
            self.playing = True; self.play_btn.setText("⏸ Pauze")
            self._timer.start(int(1000 / max(1, self.fps.value())))

    def _tick(self):
        self.idx = (self.idx + 1) % len(self.work.frames)
        self.strip.blockSignals(True); self.strip.setCurrentRow(self.idx)
        self.strip.blockSignals(False); self._load_frame()

    # ---- frames-strip ---------------------------------------------------- #
    def _thumb(self, i):
        base = QImage(self.work.width, self.work.height, QImage.Format_ARGB32)
        base.fill(QColor("white"))
        p = QPainter(base); p.drawImage(0, 0, self.work.render_frame(i)); p.end()
        return QPixmap.fromImage(base)

    def _refresh_strip(self):
        self.strip.blockSignals(True); self.strip.clear()
        for i in range(len(self.work.frames)):
            self.strip.addItem(QListWidgetItem(QIcon(self._thumb(i)), str(i + 1)))
        self.strip.setCurrentRow(self.idx); self.strip.blockSignals(False)

    def _refresh_item(self):
        if 0 <= self.idx < self.strip.count():
            self.strip.item(self.idx).setIcon(QIcon(self._thumb(self.idx)))

    def _tab_changed(self, i):
        if i == 0:
            self._update_skel_bg(); self.skelcv.update()
        elif i == 1:
            self._load_part()
        elif i == 2:
            self._load_frame()
        else:
            self._load_mouth()

    def _accept(self):
        self._timer.stop()
        self.work.sync()
        self.clip.joints = self.work.joints
        self.clip.bones = self.work.bones
        self.clip.parts = self.work.parts
        self.clip.frames = self.work.frames
        self.clip.stretch = bool(getattr(self.work, "stretch", True))
        self.clip.mouth = self.work.mouth
        self.clip.mouth_bone = self.work.mouth_bone
        self.clip.mouth_closed = self.work.mouth_closed
        self.clip.mouth_open = self.work.mouth_open
        self.clip.fps = self.fps.value()
        self.clip.width, self.clip.height = self.work.width, self.work.height
        self.accept()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        avail_w = max(200, self.width() - 250 - 300 - 90)
        avail_h = max(200, self.height() - 150)
        scale = max(1.0, min(min(avail_w / self.work.width, avail_h / self.work.height), 4.0))
        if abs(self.partcv.disp_scale - scale) > 0.02:
            self.partcv.set_display_scale(scale)
        if abs(getattr(self.mouthcv, "disp_scale", -1) - scale) > 0.02:
            self.mouthcv.set_display_scale(scale)
        if abs(self.skelcv.disp_scale - scale) > 0.02:
            self.skelcv.set_display_scale(scale)
        pw, ph = int(self.work.width * scale), int(self.work.height * scale)
        if abs(self.posecv.width() - pw) > 4:
            self.posecv.setFixedSize(pw, ph)


class _MouthCanvas(QWidget):
    """Toont de afbeelding; klik (of sleep) om de mondpositie te zetten. Toont een rode
    voorbeeld-mond (open) op de gekozen plek."""

    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setMinimumSize(420, 420)
        self.setCursor(Qt.CrossCursor)
        self._ox = self._oy = 0
        self._sw = self._sh = 0

    def paintEvent(self, _ev):
        img = self.clip._img
        p = QPainter(self)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor("#15151a"))
        if img.isNull():
            p.end(); return
        scaled = img.scaled(W, H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._ox = (W - scaled.width()) // 2
        self._oy = (H - scaled.height()) // 2
        self._sw, self._sh = scaled.width(), scaled.height()
        p.drawImage(self._ox, self._oy, scaled)
        cx = self._ox + self.clip.mouth_x * self._sw
        cy = self._oy + self.clip.mouth_y * self._sh
        r = max(3.0, self.clip.mouth_size * min(self._sw, self._sh))
        p.setPen(QPen(QColor("#3a1414"), max(2, int(r * 0.28))))
        p.setBrush(QColor("#8a3030"))
        p.drawEllipse(QPointF(cx, cy), r, r * 0.78)
        p.setPen(QPen(QColor("#7fb4ff"), 1))
        p.drawLine(int(cx - 10), int(cy), int(cx + 10), int(cy))
        p.drawLine(int(cx), int(cy - 10), int(cx), int(cy + 10))
        p.end()

    def _set_from(self, ev):
        if self._sw <= 0 or self._sh <= 0:
            return
        mx = (ev.x() - self._ox) / self._sw
        my = (ev.y() - self._oy) / self._sh
        self.clip.mouth_x = min(1.0, max(0.0, mx))
        self.clip.mouth_y = min(1.0, max(0.0, my))
        self.update()

    def mousePressEvent(self, ev):
        self._set_from(ev)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            self._set_from(ev)


class MouthPlaceDialog(QDialog):
    """Eenvoudige modus: klik waar de mond op je figuur zit en stel de grootte in."""

    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle("Mond plaatsen - DraveMotion")
        lay = QVBoxLayout(self)
        info = QLabel("Klik (of sleep) op je figuur waar de mond zit. Stel daarna de grootte in. "
                      "De rode ovaal laat zien hoe de mond er ‘open’ uitziet als er gepraat wordt.")
        info.setWordWrap(True); lay.addWidget(info)
        self.view = _MouthCanvas(clip); lay.addWidget(self.view, 1)
        row = QHBoxLayout(); row.addWidget(QLabel("Grootte:"))
        self.size_slider = QSlider(Qt.Horizontal); self.size_slider.setRange(2, 20)
        self.size_slider.setValue(int(round(clip.mouth_size * 100)))
        self.size_slider.valueChanged.connect(self._set_size)
        row.addWidget(self.size_slider, 1); lay.addLayout(row)
        brow = QHBoxLayout()
        cancel = QPushButton("Annuleer"); cancel.clicked.connect(self.reject)
        ok = QPushButton("Klaar"); ok.setObjectName("cta"); ok.setMinimumHeight(34)
        ok.clicked.connect(self.accept)
        brow.addWidget(cancel); brow.addWidget(ok); lay.addLayout(brow)
        self.resize(780, 720)

    def _set_size(self, v):
        self.clip.mouth_size = v / 100.0
        self.view.update()


# =========================================================================== #
#  TEKST-NAAR-SPRAAK  (NeuVoice, lokaal via ONNX)
# =========================================================================== #
NEUVOICE_VOICES = ["Alina", "Cem", "Cole", "Giray", "Leon", "Lina", "Linda",
                   "Mustafa", "Sarp", "Selin", "Sema", "Soras"]
NEUVOICE_LANGS = [
    ("Nederlands", "nl"), ("Engels", "en"), ("Duits", "de"), ("Frans", "fr"),
    ("Spaans", "es"), ("Italiaans", "it"), ("Portugees", "pt"), ("Turks", "tr"),
    ("Japans", "ja"), ("Koreaans", "ko"), ("Chinees/overig (na)", "na"),
    ("Russisch", "ru"), ("Pools", "pl"), ("Oekraïens", "uk"), ("Arabisch", "ar"),
    ("Hindi", "hi"), ("Vietnamees", "vi"), ("Indonesisch", "id"), ("Grieks", "el"),
    ("Zweeds", "sv"), ("Deens", "da"), ("Fins", "fi"), ("Noors", "na"),
    ("Tsjechisch", "cs"), ("Slowaaks", "sk"), ("Sloveens", "sl"), ("Kroatisch", "hr"),
    ("Hongaars", "hu"), ("Roemeens", "ro"), ("Bulgaars", "bg"),
    ("Ests", "et"), ("Lets", "lv"), ("Litouws", "lt"),
]
NEUVOICE_TAGS = ["<happy>", "<sad>", "<laugh>", "<breath>"]


_TTS_HELPER = r'''
import sys, json
with open(sys.argv[1], "r", encoding="utf-8") as f:
    a = json.load(f)
import numpy as np, soundfile as sf
from neuvoice import TTS
tts = TTS(auto_download=True)
style = tts.get_voice_style(a["voice"])
out = tts.synthesize(a["text"], voice_style=style, lang=a["lang"],
                     speed=a["speed"], total_steps=a["steps"])
wav = out[0] if isinstance(out, (tuple, list)) else out
samples = np.asarray(wav, dtype="float32").flatten()
peak = float(np.max(np.abs(samples))) if samples.size else 0.0
if peak > 1e-6:
    samples = (samples / peak) * 0.98
sr = int(getattr(tts, "sample_rate", 24000) or 24000)
sf.write(a["out"], samples, sr, subtype="PCM_16")
print("DUR", (samples.size / float(sr)) if samples.size else 0.0)
print("N", samples.size, "SR", sr)
'''


class _TtsWorker(QThread):
    """Genereert spraak in een APART, schoon Python-proces zodat onnxruntime niet botst
    met de al-geladen bibliotheken (PyQt5/opencv/numpy), en het scherm niet bevriest."""
    status = pyqtSignal(str)
    done = pyqtSignal(object, float)      # pad naar wav, duur
    failed = pyqtSignal(str)

    def __init__(self, studio, text, voice, lang, speed, steps):
        super().__init__(studio)
        self.studio = studio
        self.text, self.voice, self.lang = text, voice, lang
        self.speed, self.steps = speed, steps

    def run(self):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            out_wav = os.path.join(CACHE_DIR, "tts_laatste.wav")
            try:
                if os.path.exists(out_wav):
                    os.remove(out_wav)
            except OSError:
                pass
            params = {"text": _uitspraak(self.text, self.lang), "voice": self.voice, "lang": self.lang,
                      "speed": self.speed, "steps": self.steps, "out": out_wav}
            jpath = os.path.join(CACHE_DIR, "tts_params.json")
            with open(jpath, "w", encoding="utf-8") as f:
                json.dump(params, f)
            self.status.emit("Model laden / genereren (de eerste keer kan dit even duren)…")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            proc = subprocess.run([sys.executable, "-c", _TTS_HELPER, jpath],
                                  capture_output=True, text=True, creationflags=flags)
            # de WAV is het bewijs van succes; een leeg/te klein bestand telt niet
            ok = os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000
            if not ok:
                msg = (proc.stderr or proc.stdout or "").strip()
                if not msg:
                    msg = ("De stem-engine leverde geen audio op. Controleer of de tekst niet leeg "
                           "is en of de gekozen taal bij de tekst past.")
                self.failed.emit(msg); return
            dur = 0.0
            for line in (proc.stdout or "").splitlines():
                if line.startswith("DUR"):
                    try:
                        dur = float(line.split()[1])
                    except (IndexError, ValueError):
                        pass
            self.done.emit(out_wav, dur)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class TtsStudio(QDialog):
    """Eigen scherm voor tekst-naar-spraak met NeuVoice."""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._worker = None
        self._player = QMediaPlayer(self) if HAVE_QTMM else None
        self._pending = None      # ("preview", None) of ("save", naam)
        self.setWindowTitle("Stem (tekst-naar-spraak) - DraveMotion")
        self._build()
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint |
                            Qt.WindowMinimizeButtonHint)
        self.resize(1180, 760); self.setMinimumSize(900, 620)
        QTimer.singleShot(0, self.showMaximized)

    # ---- opbouw ---------------------------------------------------------- #
    def _build(self):
        outer = QVBoxLayout(self)
        banner = QLabel("🔊  Tekst naar spraak (NeuVoice, draait lokaal). Schrijf of laad je "
                        "tekst, kies een stem en instellingen, beluister, en sla op in je media "
                        "bestanden. De eerste keer wordt het stemmodel gedownload — dat kan even duren.")
        banner.setWordWrap(True)
        banner.setStyleSheet("background:#16303a; color:#9fe0ff; border:1px solid #1f5b6b; "
                             "padding:6px 10px; border-radius:6px; font-weight:bold;")
        outer.addWidget(banner)
        if not HAVE_TTS:
            warn = QLabel("⚠  NeuVoice is niet geïnstalleerd. Sluit de app en voer in de map uit: "
                          "  py -m pip install neuvoice   (of gebruik herstel.bat). Daarna werkt dit scherm.")
            warn.setWordWrap(True)
            warn.setStyleSheet("background:#3a2e12; color:#ffd98a; border:1px solid #6b531f; "
                               "padding:6px 10px; border-radius:6px; font-weight:bold;")
            outer.addWidget(warn)

        row = QHBoxLayout()
        # links: tekst
        left = QVBoxLayout()
        left.addWidget(section("Tekst / script"))
        bar = QHBoxLayout()
        load = QPushButton("📂  Tekstbestand laden…"); load.clicked.connect(self._load_text)
        bar.addWidget(load); bar.addStretch(1)
        bar.addWidget(QLabel("Emotie invoegen:"))
        for tag in NEUVOICE_TAGS:
            b = QPushButton(tag); b.setToolTip(f"Voegt {tag} in op de cursor; bepaalt de toon")
            b.clicked.connect(lambda _, t=tag: self._insert_tag(t)); bar.addWidget(b)
        left.addLayout(bar)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Typ hier je tekst. Tip: zet <happy>, <sad>, <laugh> "
                                          "of <breath> in de zin om de toon te sturen.")
        f = self.text_edit.font(); f.setPointSize(13); self.text_edit.setFont(f)
        left.addWidget(self.text_edit, 1)
        row.addLayout(left, 1)

        # rechts: instellingen
        tools = QVBoxLayout(); tools.setSpacing(6)
        tools.addWidget(section("Stem & instellingen"))
        tools.addWidget(QLabel("Stem:"))
        self.voice_combo = QComboBox(); self.voice_combo.addItems(NEUVOICE_VOICES)
        self.voice_combo.setCurrentText("Leon"); tools.addWidget(self.voice_combo)
        tools.addWidget(QLabel("Taal:"))
        self.lang_combo = QComboBox()
        for label, code in NEUVOICE_LANGS:
            self.lang_combo.addItem(label, code)
        tools.addWidget(self.lang_combo)
        self.speed_lbl = QLabel("Snelheid: 1.05×")
        tools.addWidget(self.speed_lbl)
        self.speed = QSlider(Qt.Horizontal); self.speed.setRange(70, 200); self.speed.setValue(105)
        self.speed.valueChanged.connect(lambda v: self.speed_lbl.setText(f"Snelheid: {v/100:.2f}×"))
        tools.addWidget(self.speed)
        self.steps_lbl = QLabel("Kwaliteit (stappen): 5")
        tools.addWidget(self.steps_lbl)
        self.steps = QSlider(Qt.Horizontal); self.steps.setRange(1, 100); self.steps.setValue(5)
        self.steps.setToolTip("Hoger = mooier maar trager. 5 is een goede start; 20–30 voor extra kwaliteit.")
        self.steps.valueChanged.connect(lambda v: self.steps_lbl.setText(f"Kwaliteit (stappen): {v}"))
        tools.addWidget(self.steps)
        tools.addSpacing(8)
        self.listen_btn = QPushButton("▶  Beluister"); self.listen_btn.setMinimumHeight(40)
        self.listen_btn.clicked.connect(self._preview); tools.addWidget(self.listen_btn)
        self.save_btn = QPushButton("💾  Opslaan in mediabak (MP3)…"); self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self._save); tools.addWidget(self.save_btn)
        self.voice_btn = QPushButton("🎬  Zet direct op het Stem-spoor"); self.voice_btn.setObjectName("cta")
        self.voice_btn.setMinimumHeight(40)
        self.voice_btn.setToolTip("Maakt de stem én zet hem meteen op het Stem-spoor in de tijdlijn, "
                                  "klaar om een poppetje te laten meepraten.")
        self.voice_btn.clicked.connect(self._to_voice_track); tools.addWidget(self.voice_btn)
        self.status_lbl = QLabel("Klaar."); self.status_lbl.setWordWrap(True)
        self.status_lbl.setObjectName("mono"); tools.addWidget(self.status_lbl)
        tip = QLabel("De toon stuur je via de stemkeuze en de emotie-tags in de tekst. "
                     "Het opgeslagen bestand komt in ‘Media bestanden’ onder ‘Stemmen (TTS)’ en "
                     "kun je naar de tijdlijn slepen.")
        tip.setWordWrap(True); tools.addWidget(tip)
        tools.addStretch(1)
        close = QPushButton("Sluiten"); close.clicked.connect(self.accept); tools.addWidget(close)
        tp = QWidget(); tp.setObjectName("panel"); tp.setLayout(tools); tp.setFixedWidth(300)
        row.addWidget(tp)
        outer.addLayout(row, 1)

    # ---- tekst ----------------------------------------------------------- #
    def _load_text(self):
        path, _ = QFileDialog.getOpenFileName(self, "Tekstbestand laden", PROJECTS_DIR,
                                              "Tekst (*.txt *.md);;Alle (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                self.text_edit.setPlainText(fh.read())
            self.status_lbl.setText(f"Geladen: {os.path.basename(path)}")
        except OSError as e:
            QMessageBox.warning(self, "Laden mislukt", str(e))

    def _insert_tag(self, tag):
        cur = self.text_edit.textCursor()
        cur.insertText(tag + " ")
        self.text_edit.setTextCursor(cur)
        self.text_edit.setFocus()

    # ---- genereren ------------------------------------------------------- #
    def _params(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Geen tekst", "Schrijf of laad eerst wat tekst.")
            return None
        if not HAVE_TTS:
            QMessageBox.information(self, "NeuVoice ontbreekt",
                                    "Installeer NeuVoice (py -m pip install neuvoice) en open dit "
                                    "scherm opnieuw.")
            return None
        return (text, self.voice_combo.currentText(), self.lang_combo.currentData(),
                self.speed.value() / 100.0, self.steps.value())

    def _busy(self, on, msg=""):
        self.listen_btn.setEnabled(not on); self.save_btn.setEnabled(not on)
        self.voice_btn.setEnabled(not on)
        if msg:
            self.status_lbl.setText(msg)

    def _start(self, action, name=None):
        p = self._params()
        if not p:
            return
        self._pending = (action, name)
        self._busy(True, "Bezig…")
        self._worker = _TtsWorker(self, *p)
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _preview(self):
        self._start("preview")

    def _save(self):
        name, ok = QInputDialog.getText(self, "Opslaan als", "Bestandsnaam (zonder extensie):",
                                        text="stem")
        if not ok or not name.strip():
            return
        safe = "".join(c for c in name.strip() if c.isalnum() or c in " _-").strip() or "stem"
        self._start("save", safe)

    def _to_voice_track(self):
        name, ok = QInputDialog.getText(self, "Naar Stem-spoor",
                                        "Naam voor de stem (zonder extensie):", text="stem")
        if not ok or not name.strip():
            return
        safe = "".join(c for c in name.strip() if c.isalnum() or c in " _-").strip() or "stem"
        self._start("voice", safe)

    def _on_failed(self, msg):
        self._busy(False, "Mislukt.")
        low = msg.lower()
        if ("onnxruntime" in low or "dll load failed" in low or "_pybind11_state" in low
                or "initialisatieroutine" in low):
            QMessageBox.warning(
                self, "Stem-engine kon niet starten",
                "De stem-engine (onnxruntime) kon niet starten op deze pc.\n\n"
                "Heb je de nieuwste Microsoft Visual C++ (x64) al? Dan ligt het meestal aan de "
                "onnxruntime-versie.\n\n"
                "Makkelijkste oplossing:\n"
                "• Sluit DraveMotion.\n"
                "• Dubbelklik in de app-map op  stem-herstel.bat\n"
                "  Dat zoekt automatisch een werkende versie.\n"
                "• Start DraveMotion daarna opnieuw.\n\n"
                "(Heb je de Visual C++ runtime nog niet: installeer eerst\n"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe en herstart.)")
        else:
            QMessageBox.warning(self, "Genereren mislukt", msg)

    def _on_done(self, wav_path, dur):
        action, name = self._pending or ("preview", None)
        if not wav_path or not os.path.exists(wav_path):
            self._busy(False, "Mislukt."); QMessageBox.warning(self, "Opslaan mislukt",
                                                               "Er is geen audiobestand gemaakt."); return
        if action == "preview":
            self._busy(False, f"Klaar — {dur:.1f}s. Afspelen…")
            self._play(wav_path)
            return
        # opslaan als mp3 in de media-map
        out = os.path.join(MEDIA_DIR, name + ".mp3")
        ff = ffmpeg_exe()
        final = out
        if ff:
            try:
                subprocess.run([ff, "-y", "-i", wav_path, "-codec:a", "libmp3lame",
                                "-q:a", "2", out], capture_output=True, check=True)
            except Exception:  # noqa: BLE001
                final = os.path.join(MEDIA_DIR, name + ".wav")
                shutil.copyfile(wav_path, final)
        else:
            final = os.path.join(MEDIA_DIR, name + ".wav")
            shutil.copyfile(wav_path, final)
        self.app._add_asset("audio", final, os.path.basename(final), group="Stemmen (TTS)")
        self._busy(False, f"Opgeslagen: {os.path.basename(final)} ({dur:.1f}s)")
        if action == "voice":
            try:
                self.app.add_voice_clip(final)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Stem-spoor", f"Kon niet op het Stem-spoor zetten: {e}")
                return
            QMessageBox.information(self, "Op het Stem-spoor",
                f"‘{os.path.basename(final)}’ staat nu op het Stem-spoor in de tijdlijn "
                f"(≈{dur:.1f}s).\n\nZet je poppetje op dezelfde plek in de tijd en vink bij het "
                "poppetje ‘🗣 Praat mee met de stem’ aan — dan beweegt de mond mee.")
        else:
            QMessageBox.information(self, "Opgeslagen",
                                    f"‘{os.path.basename(final)}’ staat nu in Media bestanden onder "
                                    f"‘Stemmen (TTS)’. Sleep het naar de tijdlijn.")

    def _play(self, path):
        # Windows: winsound speelt WAV betrouwbaar af (QtMultimedia doet vaak niets).
        if os.name == "nt":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)  # stop vorige
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:  # noqa: BLE001
                pass
        if self._player:
            self._player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
            self._player.play()
        else:
            self.status_lbl.setText("Afspelen lukt hier niet automatisch; het bestand is wel klaar "
                                    "(staat in de map ‘media’ als je opslaat).")

    def closeEvent(self, ev):
        if os.name == "nt":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:  # noqa: BLE001
                pass
        if self._worker and self._worker.isRunning():
            self._worker.wait(50)
        super().closeEvent(ev)


# =========================================================================== #
#  TEKST-EDITOR
# =========================================================================== #
class TextEditDialog(QDialog):
    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle("Tekst bewerken - DraveMotion")
        self.resize(440, 380)
        lay = QVBoxLayout(self)
        lay.addWidget(section("Tekst"))
        self.edit = QPlainTextEdit(clip.text)
        self.edit.setMinimumHeight(120)
        lay.addWidget(self.edit)
        grid = QGridLayout()
        grid.addWidget(QLabel("Lettertype"), 0, 0)
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(getattr(clip, "font", "Arial")))
        grid.addWidget(self.font_combo, 0, 1)
        grid.addWidget(QLabel("Tekengrootte"), 1, 0)
        self.size = QSpinBox(); self.size.setRange(8, 400); self.size.setValue(clip.size)
        grid.addWidget(self.size, 1, 1)
        grid.addWidget(QLabel("Breedte (px)"), 2, 0)
        self.width = QSpinBox(); self.width.setRange(20, max(20, clip.box_w))
        self.width.setSingleStep(10)
        self.width.setValue(min(getattr(clip, "text_width", clip.box_w), clip.box_w))
        grid.addWidget(self.width, 2, 1)
        lbl_col = QLabel("Tekstkleur (letters)")
        grid.addWidget(lbl_col, 3, 0)
        self.color_btn = QPushButton(); self.color_btn.clicked.connect(self._pick_color)
        self.color_btn.setToolTip("Kleur van de letters")
        self._color = QColor(clip.color); self._refresh_color()
        grid.addWidget(self.color_btn, 3, 1)
        self.bg_chk = QCheckBox("Achtergrond achter tekst")
        self.bg_chk.setToolTip("Zet een gekleurd vlak strak achter de tekst")
        self.bg_chk.setChecked(clip.bg is not None)
        grid.addWidget(self.bg_chk, 4, 0)
        self.bg_btn = QPushButton(); self.bg_btn.clicked.connect(self._pick_bg)
        self.bg_btn.setToolTip("Kleur van de achtergrond achter de tekst")
        self._bg = QColor(clip.bg) if clip.bg else QColor("#000000")
        self._refresh_bg()
        grid.addWidget(self.bg_btn, 4, 1)
        grid.addWidget(QLabel("Achtergrond dekking"), 5, 0)
        opa_row = QHBoxLayout()
        self.bg_opacity = QSlider(Qt.Horizontal)
        self.bg_opacity.setRange(0, 100)
        self.bg_opacity.setValue(int(getattr(clip, "bg_opacity", 100)))
        self.bg_opacity.setToolTip("0% = volledig doorzichtig, 100% = vol")
        self.bg_opacity_lbl = QLabel(f"{self.bg_opacity.value()}%")
        self.bg_opacity_lbl.setObjectName("mono"); self.bg_opacity_lbl.setFixedWidth(48)
        self.bg_opacity.valueChanged.connect(
            lambda v: self.bg_opacity_lbl.setText(f"{v}%"))
        opa_row.addWidget(self.bg_opacity, 1); opa_row.addWidget(self.bg_opacity_lbl)
        grid.addLayout(opa_row, 5, 1)
        lay.addLayout(grid)
        hint = QLabel("Tip: versleep de tekst in het voorbeeld om hem te verplaatsen.")
        hint.setObjectName("mono"); hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1)
        cancel = QPushButton("Annuleer"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        ok = QPushButton("Klaar"); ok.setObjectName("cta"); ok.clicked.connect(self._accept)
        row.addWidget(ok)
        lay.addLayout(row)

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Tekstkleur")
        if c.isValid():
            self._color = c; self._refresh_color()

    def _pick_bg(self):
        c = QColorDialog.getColor(self._bg, self, "Achtergrondkleur")
        if c.isValid():
            self._bg = c; self.bg_chk.setChecked(True); self._refresh_bg()

    def _refresh_color(self):
        fg = "white" if self._color.lightness() < 128 else "black"
        self.color_btn.setStyleSheet(f"background-color:{self._color.name()};color:{fg};")
        self.color_btn.setText(self._color.name())

    def _refresh_bg(self):
        fg = "white" if self._bg.lightness() < 128 else "black"
        self.bg_btn.setStyleSheet(f"background-color:{self._bg.name()};color:{fg};")
        self.bg_btn.setText(self._bg.name())

    def _accept(self):
        self.clip.text = self.edit.toPlainText() or "Tekst"
        self.clip.size = self.size.value()
        self.clip.font = self.font_combo.currentFont().family()
        self.clip.text_width = self.width.value()
        self.clip.color = self._color.name()
        self.clip.bg = self._bg.name() if self.bg_chk.isChecked() else None
        self.clip.bg_opacity = self.bg_opacity.value()
        self.clip.name = (self.clip.text.splitlines() or ["Tekst"])[0][:24] or "Tekst"
        self.clip._cache = None
        self.accept()


# =========================================================================== #
#  AFTITELING-EDITOR (end credits)
# =========================================================================== #
class EndCreditsDialog(QDialog):
    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle("Aftiteling (end credits) - DraveMotion")
        self.resize(480, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(section("Aftiteling"))
        grid = QGridLayout()
        r = 0
        grid.addWidget(QLabel("Titel"), r, 0)
        self.f_title = QLineEdit(clip.title); grid.addWidget(self.f_title, r, 1); r += 1
        grid.addWidget(QLabel("Auteur"), r, 0)
        self.f_author = QLineEdit(clip.author); grid.addWidget(self.f_author, r, 1); r += 1
        grid.addWidget(QLabel("Copyright"), r, 0)
        self.f_copy = QLineEdit(clip.copyright)
        self.f_copy.setPlaceholderText("bv. 2026 Dravenlock")
        grid.addWidget(self.f_copy, r, 1); r += 1
        grid.addWidget(QLabel("Muziek / Song"), r, 0)
        self.f_song = QLineEdit(clip.song); grid.addWidget(self.f_song, r, 1); r += 1
        grid.addWidget(QLabel("Met dank aan"), r, 0)
        self.f_thanks = QLineEdit(clip.thanks); grid.addWidget(self.f_thanks, r, 1); r += 1
        lay.addLayout(grid)
        lay.addWidget(QLabel("Extra regels (vrij; één per regel)"))
        self.f_extra = QPlainTextEdit(clip.extra); self.f_extra.setMinimumHeight(90)
        lay.addWidget(self.f_extra)

        lay.addWidget(section("Stijl"))
        g2 = QGridLayout()
        g2.addWidget(QLabel("Lettertype"), 0, 0)
        self.font_combo = QFontComboBox(); self.font_combo.setCurrentFont(QFont(clip.font))
        g2.addWidget(self.font_combo, 0, 1)
        g2.addWidget(QLabel("Tekengrootte"), 1, 0)
        self.size = QSpinBox(); self.size.setRange(10, 200); self.size.setValue(clip.size)
        g2.addWidget(self.size, 1, 1)
        g2.addWidget(QLabel("Tekstkleur"), 2, 0)
        self.color_btn = QPushButton(); self.color_btn.clicked.connect(self._pick_color)
        self._color = QColor(clip.color); self._refresh_color()
        g2.addWidget(self.color_btn, 2, 1)
        g2.addWidget(QLabel("Duur (sec)"), 3, 0)
        self.dur = QDoubleSpinBox(); self.dur.setRange(1, 600); self.dur.setDecimals(1)
        self.dur.setValue(clip.duration()); g2.addWidget(self.dur, 3, 1)
        lay.addLayout(g2)
        self.scroll_chk = QCheckBox("Rollende aftiteling (van onder naar boven)")
        self.scroll_chk.setChecked(clip.scroll); lay.addWidget(self.scroll_chk)

        lay.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1)
        cancel = QPushButton("Annuleer"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        ok = QPushButton("Klaar"); ok.setObjectName("cta"); ok.clicked.connect(self._accept)
        row.addWidget(ok)
        lay.addLayout(row)

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Tekstkleur")
        if c.isValid():
            self._color = c; self._refresh_color()

    def _refresh_color(self):
        fg = "white" if self._color.lightness() < 128 else "black"
        self.color_btn.setStyleSheet(f"background-color:{self._color.name()};color:{fg};")
        self.color_btn.setText(self._color.name())

    def _accept(self):
        c = self.clip
        c.title = self.f_title.text()
        c.author = self.f_author.text()
        c.copyright = self.f_copy.text()
        c.song = self.f_song.text()
        c.thanks = self.f_thanks.text()
        c.extra = self.f_extra.toPlainText()
        c.font = self.font_combo.currentFont().family()
        c.size = self.size.value()
        c.color = self._color.name()
        c.scroll = self.scroll_chk.isChecked()
        c.set_duration(self.dur.value())
        c.name = (c.title.strip() or "Aftiteling")[:24]
        self.accept()


# =========================================================================== #
#  PROJECTINSTELLINGEN
# =========================================================================== #
class ProjectSettingsDialog(QDialog):
    PRESETS = [
        ("640 × 360  (16:9)", 640, 360),
        ("854 × 480  (16:9)", 854, 480),
        ("1280 × 720  (HD)", 1280, 720),
        ("1920 × 1080  (Full HD)", 1920, 1080),
        ("1080 × 1080  (vierkant)", 1080, 1080),
        ("1080 × 1920  (verticaal)", 1080, 1920),
        ("Aangepast…", None, None),
    ]

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Projectinstellingen") + " - DraveMotion")
        self.resize(380, 380)
        self._bg = QColor(project.background)
        lay = QVBoxLayout(self)
        lay.addWidget(section("Beeld"))
        self.preset = QComboBox()
        for label, _, _ in self.PRESETS:
            self.preset.addItem(label)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        lay.addWidget(self.preset)
        grid = QGridLayout()
        grid.addWidget(QLabel(t("Breedte")), 0, 0)
        self.w = QSpinBox(); self.w.setRange(16, 7680); self.w.setSingleStep(2)
        self.w.setValue(project.width); grid.addWidget(self.w, 0, 1)
        grid.addWidget(QLabel(t("Hoogte")), 1, 0)
        self.h = QSpinBox(); self.h.setRange(16, 4320); self.h.setSingleStep(2)
        self.h.setValue(project.height); grid.addWidget(self.h, 1, 1)
        grid.addWidget(QLabel(t("FPS")), 2, 0)
        self.fps = QSpinBox(); self.fps.setRange(1, 60); self.fps.setValue(project.fps)
        grid.addWidget(self.fps, 2, 1)
        grid.addWidget(QLabel(t("Achtergrond")), 3, 0)
        self.bg_btn = QPushButton(); self.bg_btn.clicked.connect(self._pick_bg)
        self._refresh_bg(); grid.addWidget(self.bg_btn, 3, 1)
        lay.addLayout(grid)
        # selecteer een passend preset
        self.preset.setCurrentIndex(self._match_preset(project.width, project.height))

        lay.addWidget(section("Taal"))
        self.lang = QComboBox()
        self._lang_codes = ["auto", "nl", "en"]
        self.lang.addItems([t("Automatisch (computertaal)"), t("Nederlands"), t("English")])
        cur = load_config().get("language", "auto")
        self.lang.setCurrentIndex(self._lang_codes.index(cur) if cur in self._lang_codes else 0)
        lay.addWidget(self.lang)
        ln = QLabel(t("De taal verandert nadat je DraveMotion opnieuw start."))
        ln.setObjectName("mono"); ln.setWordWrap(True); lay.addWidget(ln)

        lay.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1)
        cancel = QPushButton(t("Annuleer")); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        ok = QPushButton(t("Toepassen")); ok.setObjectName("cta"); ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)

    def get_language(self):
        return self._lang_codes[self.lang.currentIndex()]

    def _match_preset(self, w, h):
        for i, (_, pw, ph) in enumerate(self.PRESETS):
            if pw == w and ph == h:
                return i
        return len(self.PRESETS) - 1  # Aangepast

    def _preset_changed(self, i):
        _, pw, ph = self.PRESETS[i]
        custom = pw is None
        self.w.setEnabled(custom); self.h.setEnabled(custom)
        if not custom:
            self.w.setValue(pw); self.h.setValue(ph)

    def _pick_bg(self):
        c = QColorDialog.getColor(self._bg, self, "Achtergrondkleur")
        if c.isValid():
            self._bg = c; self._refresh_bg()

    def _refresh_bg(self):
        fg = "white" if self._bg.lightness() < 128 else "black"
        self.bg_btn.setStyleSheet(f"background-color:{self._bg.name()};color:{fg};")
        self.bg_btn.setText(self._bg.name())

    def values(self):
        # afmetingen even maken (h.264 houdt van even getallen)
        w = self.w.value() - (self.w.value() % 2)
        h = self.h.value() - (self.h.value() % 2)
        return max(16, w), max(16, h), self.fps.value(), self._bg.name()


# =========================================================================== #
#  MEDIABAK  (assets, sleepbaar naar de tijdlijn)
# =========================================================================== #
class AssetTree(QTreeWidget):
    """Medialijst als boom: (sub)mappen als uitklapbare groepen, bestanden eronder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setIconSize(QSize(40, 40))
        self.setIndentation(14)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        idx = item.data(0, Qt.UserRole)
        if idx is None:            # map-koptekst: niet sleepbaar
            return
        mime = QMimeData()
        mime.setData(ASSET_MIME, str(int(idx)).encode("ascii"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pm = item.icon(0).pixmap(40, 40)
        if not pm.isNull():
            drag.setPixmap(pm)
        drag.exec_(Qt.CopyAction)


# =========================================================================== #
#  TIJDLIJN-WIDGET  (sporen + clips + afspeelkop)
# =========================================================================== #
class TimelineView(QWidget):
    COLORS = {"scene": "#3b5266", "video": "#4a3f63", "image": "#3f5a45",
              "audio": "#5a4a2e", "text": "#444a55", "credits": "#52426b", "figure": "#3f5a5a", "studio": "#5a3f55", "rig": "#3f4a5a"}
    EDGE = 6  # px grijpzone aan de clipranden voor bijsnijden
    MIN_PPS, MAX_PPS = 20, 400

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.px_per_sec = 80
        self.track_h = 56
        self.header_h = 22
        self.snap = 0.05
        self.playhead = 0.0
        self.selected = None
        self.on_playhead = None
        self.on_select = None
        self.on_change = None
        self.on_drag_start = None     # voor undo: een keer aanroepen bij sleepstart
        self.on_drop_asset = None     # (asset_index, track_index, start) bij drop
        self._drag = None
        self._scrub = False
        self.cut_marker = None        # grijze knip-markering (absolute tijd)
        self.on_split = None          # callback (track_index, t_abs) bij rechtsklik-knip
        self.on_edit = None           # callback(clip) bij dubbelklik op een clip
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._update_size()

    def _layout_height(self):
        return self.header_h + self.track_h * len(self.project.tracks) + 10

    def _update_size(self):
        dur = max(self.project.duration(), 6)
        self.setMinimumWidth(int((dur + 3) * self.px_per_sec))
        self.setMinimumHeight(self._layout_height())
        self.updateGeometry()

    def sizeHint(self):
        return QSize(self.minimumWidth(), self._layout_height())

    def set_project(self, project):
        self.project = project
        self.selected = None
        self.playhead = 0.0
        self._drag = None
        self._update_size()
        self.update()

    def set_zoom(self, pps):
        self.px_per_sec = int(max(self.MIN_PPS, min(self.MAX_PPS, pps)))
        self._update_size()
        self.update()

    def _track_at_y(self, y):
        idx = int((y - self.header_h) // self.track_h)
        return max(0, min(idx, len(self.project.tracks) - 1))

    def _clip_at(self, ti, t):
        for c in self.project.tracks[ti].clips:
            if c.start <= t < c.start + c.duration():
                return c
        return None

    def _snap(self, v):
        return round(v / self.snap) * self.snap

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            factor = 1.25 if ev.angleDelta().y() > 0 else 0.8
            self.set_zoom(self.px_per_sec * factor)
            ev.accept()
        else:
            super().wheelEvent(ev)

    # ---- slepen vanuit de mediabak --------------------------------------- #
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(ASSET_MIME):
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasFormat(ASSET_MIME):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        if not ev.mimeData().hasFormat(ASSET_MIME):
            return
        try:
            idx = int(bytes(ev.mimeData().data(ASSET_MIME)).decode("ascii"))
        except ValueError:
            return
        pos = ev.pos()
        start = max(0.0, self._snap(pos.x() / self.px_per_sec))
        ti = self._track_at_y(pos.y())
        if self.on_drop_asset:
            self.on_drop_asset(idx, ti, start)
        ev.acceptProposedAction()

    def _edge_at(self, ev):
        """Geef (clip, rand, track_index) terug; rand is 'left'/'right'/None."""
        if ev.y() < self.header_h:
            return None, None, None
        ti = self._track_at_y(ev.y())
        for c in self.project.tracks[ti].clips:
            lpx = c.start * self.px_per_sec
            rpx = (c.start + c.duration()) * self.px_per_sec
            if not (lpx - self.EDGE <= ev.x() <= rpx + self.EDGE):
                continue
            if isinstance(c, (DrawnSceneClip, StickFigureClip, StudioClip, RigClip)) or (rpx - lpx) < 14:
                if lpx <= ev.x() <= rpx:
                    return c, None, ti  # scenes/smalle clips: alleen verplaatsen
                continue
            if abs(ev.x() - lpx) <= self.EDGE:
                return c, "left", ti
            if abs(ev.x() - rpx) <= self.EDGE:
                return c, "right", ti
            return c, None, ti
        return None, None, ti

    def _set_playhead(self, x):
        self.playhead = max(0.0, x / self.px_per_sec)
        if self.on_playhead:
            self.on_playhead(self.playhead)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        clip, _edge, _ti = self._edge_at(ev)
        if clip is not None:
            self.selected = clip
            if self.on_select:
                self.on_select(clip)
            self.update()
            if self.on_edit:
                self.on_edit(clip)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:        # rechtsklik = knippen + grijze markering
            t = max(0.0, self._snap(ev.x() / self.px_per_sec))
            self.cut_marker = t
            ti = self._track_at_y(ev.y()) if ev.y() >= self.header_h else None
            if ti is not None and self.on_split:
                self.on_split(ti, t)
            self.update()
            return
        self.cut_marker = None      # grijze knip-lijn verdwijnt zodra je links klikt
        ph_x = self.playhead * self.px_per_sec
        near_playhead = abs(ev.x() - ph_x) <= 6
        on_ruler = ev.y() < self.header_h
        if on_ruler or near_playhead:          # rode afspeelkop / liniaal: scrubben
            self.selected = None
            self._drag = None
            self._scrub = True
            if self.on_select:
                self.on_select(None)
            self._set_playhead(ev.x())
            self.update()
            return
        clip, edge, ti = self._edge_at(ev)
        if clip is not None:
            self.selected = clip
            if self.on_drag_start:
                self.on_drag_start()
            self._drag = {"clip": clip, "src": ti,
                          "mode": ("trim_" + edge) if edge else "move",
                          "grab": ev.x() / self.px_per_sec - clip.start,
                          "o_start": clip.start, "o_dur": clip.duration(),
                          "o_in": getattr(clip, "in_point", 0.0),
                          "o_out": getattr(clip, "out_point", 0.0),
                          "src_dur": getattr(clip, "src_dur", None), "moved": False}
            if self.on_select:
                self.on_select(clip)
        else:                                   # lege ruimte: ook scrubben
            self.selected = None
            self._drag = None
            self._scrub = True
            if self.on_select:
                self.on_select(None)
            self._set_playhead(ev.x())
        self.update()

    def mouseMoveEvent(self, ev):
        if self._scrub and ev.buttons() & Qt.LeftButton:
            self._set_playhead(ev.x())
            self.update()
            return
        if not (self._drag and ev.buttons() & Qt.LeftButton):
            ph_x = self.playhead * self.px_per_sec
            if abs(ev.x() - ph_x) <= 6 or ev.y() < self.header_h:
                self.setCursor(Qt.SizeHorCursor)
            else:
                _, edge, _ = self._edge_at(ev)
                self.setCursor(Qt.SizeHorCursor if edge else Qt.ArrowCursor)
            return
        d = self._drag
        clip = d["clip"]
        t = self._snap(ev.x() / self.px_per_sec)
        mode = d["mode"]

        if mode == "move":
            clip.start = max(0.0, self._snap(ev.x() / self.px_per_sec - d["grab"]))
            ti = self._track_at_y(ev.y())
            if ti != d["src"]:
                self.project.tracks[d["src"]].remove(clip)
                self.project.tracks[ti].add(clip)
                d["src"] = ti
        elif mode == "trim_right":
            new_dur = max(0.1, t - clip.start)
            if isinstance(clip, (ImageClip, TextClip, EndCreditsClip)):
                clip.set_duration(new_dur)
            else:  # video / audio: trim t.o.v. de bron (snelheid telt mee)
                spd = getattr(clip, "speed", 1.0)
                src_len = new_dur * spd
                cap = d["src_dur"] if d["src_dur"] else (clip.in_point + src_len)
                clip.out_point = min(cap, clip.in_point + src_len)
        elif mode == "trim_left":
            right = d["o_start"] + d["o_dur"]
            new_start = min(max(0.0, t), right - 0.1)
            if isinstance(clip, (ImageClip, TextClip, EndCreditsClip)):
                clip.start = new_start
                clip.set_duration(right - new_start)
            else:  # video / audio: schuif in_point mee, rechterrand blijft staan
                spd = getattr(clip, "speed", 1.0)
                new_in = d["o_in"] + (new_start - d["o_start"]) * spd
                if new_in < 0.0:
                    new_in = 0.0
                    new_start = d["o_start"] - d["o_in"] / spd
                new_in = min(new_in, d["o_out"] - 0.1)
                clip.in_point = new_in
                clip.start = new_start

        self.project.tracks[d["src"]].clips.sort(key=lambda c: c.start)
        d["moved"] = True
        self._update_size()
        self.update()
        if self.on_select:
            self.on_select(clip)
        if self.on_change:
            self.on_change()

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self._scrub = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#121216"))
        dur = max(self.project.duration(), self.width() / self.px_per_sec)
        # tijdraster: bij sterk uitzoomen alleen hele seconden tonen
        step = 1
        if self.px_per_sec < 45:
            step = 5
        if self.px_per_sec < 24:
            step = 10
        for s in range(0, int(dur) + 2, step):
            x = s * self.px_per_sec
            p.setPen(QColor("#3a3a44")); p.drawLine(x, self.header_h, x, self.height())
            p.setPen(QColor("#8e8e96")); p.drawText(x + 3, self.header_h - 6, f"{s}s")
        for i, track in enumerate(self.project.tracks):
            y = self.header_h + i * self.track_h
            bg = ("#16241c" if track.kind == "voice"
                  else "#1f1b16" if track.kind == "audio" else "#1b1b21")
            p.fillRect(0, y, self.width(), self.track_h - 2, QColor(bg))
            p.setPen(QColor("#a8a8b0")); p.drawText(6, y + 14, track.name)
            for c in track.clips:
                x = c.start * self.px_per_sec
                w = max(8, c.duration() * self.px_per_sec)
                rect = QRectF(x + 1, y + 18, w - 2, self.track_h - 24)
                p.setBrush(QColor(self.COLORS.get(c.KIND, "#444")))
                p.setPen(QPen(QColor("#6fa3d6"), 2) if c is self.selected
                         else QPen(QColor("#2a2a31"), 1))
                p.drawRoundedRect(rect, 5, 5)
                # fade-in/uit als doorzichtige driehoekjes tonen
                if getattr(c, "fade_in", 0.0) > 0 or getattr(c, "fade_out", 0.0) > 0:
                    p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 60))
                    top, bot = rect.top(), rect.bottom()
                    if c.fade_in > 0:
                        fw = min(rect.width(), c.fade_in * self.px_per_sec)
                        p.drawPolygon(QPolygonF([QPointF(rect.left(), bot),
                                                 QPointF(rect.left() + fw, top),
                                                 QPointF(rect.left(), top)]))
                    if c.fade_out > 0:
                        fw = min(rect.width(), c.fade_out * self.px_per_sec)
                        p.drawPolygon(QPolygonF([QPointF(rect.right(), bot),
                                                 QPointF(rect.right() - fw, top),
                                                 QPointF(rect.right(), top)]))
                p.setPen(QColor("#eaeaea"))
                p.drawText(rect.adjusted(5, 0, -3, 0), Qt.AlignVCenter, c.name)
                # keyframe-ruitjes voor de geselecteerde clip
                if c is self.selected:
                    ky = y + self.track_h - 8
                    for kt in c.transform.key_times():
                        kx = (c.start + kt) * self.px_per_sec
                        p.setBrush(QColor("#e0b24f")); p.setPen(QPen(QColor("#16161b"), 1))
                        p.drawPolygon(QPolygonF([
                            QPointF(kx, ky - 4), QPointF(kx + 4, ky),
                            QPointF(kx, ky + 4), QPointF(kx - 4, ky)]))
        if self.cut_marker is not None:          # grijze knip-markering
            cx0 = int(self.cut_marker * self.px_per_sec)
            p.setPen(QPen(QColor("#9aa0a8"), 2, Qt.DashLine))
            p.drawLine(cx0, 0, cx0, self.height())
        px = self.playhead * self.px_per_sec
        p.setPen(QPen(QColor("#e0584f"), 2)); p.drawLine(int(px), 0, int(px), self.height())
        p.end()


# =========================================================================== #
#  SNELGIDS
# =========================================================================== #
GUIDE_HTML = """
<h2 style="color:#f2f2f2;">Welkom bij DraveMotion</h2>
<p style="color:#9aa0a8;">een Dravenlock product · een portable animatie- &amp; videosuite</p>
<hr>
<h3 style="color:#6fa3d6;">1 · De tijdlijn</h3>
<p>Onderaan staat de <b>tijdlijn</b> met meerdere <b>sporen</b>. Je legt er
<i>clips</i> op. Waar clips elkaar overlappen, wint het <b>bovenste</b> spoor.
Klik op een leeg stuk om de rode <b>afspeelkop</b> te verzetten, of <b>sleep</b>
de afspeelkop (of de tijdbalk bovenaan) om soepel door je film te <b>scrubben</b>.
Met <b>Ctrl+scroll</b> (of de zoomknoppen) zoom je in en uit.</p>

<h3 style="color:#6fa3d6;">2 · Media bestanden &amp; clips toevoegen</h3>
<p>Importeer <b>video</b>, <b>foto</b> of <b>audio</b>: ze verschijnen in de
<b>Media bestanden</b>-boom links. Met <b>Map laden…</b> haal je in een keer een
hele map binnen (bv. een soundpool); elke <b>(sub)map</b> wordt een
<b>uitklapbare groep</b> — klik op een mapnaam om de bestanden erin te zien.
<b>Sleep</b> een bestand naar de tijdlijn of <b>dubbelklik</b> om het op de
afspeelkop te plaatsen. Maak daarnaast een <b>tekenscène</b>, <b>tekstclip</b>, <b>aftiteling</b> of een
<b>poppetje</b> of een <b>Studio</b> via de knoppen.</p>

<h3 style="color:#6fa3d6;">3 · Clips verplaatsen, knippen &amp; bijsnijden</h3>
<p>Pak een clip in het <b>midden</b> vast en <b>sleep</b> hem in de tijd, of
omhoog/omlaag naar een <b>ander spoor</b>. <b>Knippen?</b> <b>Rechtsklik</b> op een
clip waar je wilt knippen: er verschijnt een <b>grijze stippellijn</b> en de clip
wordt daar in tweeën geknipt. Wil je liever inkorten: pak een clip aan de
<b>linker- of rechterrand</b> vast (de cursor wordt een dubbele pijl). <b>Dubbelklik</b>
op een clip (in de tijdlijn of in het voorbeeld) om hem te <b>bewerken</b>.</p>

<h3 style="color:#6fa3d6;">4 · Transform, verslepen &amp; keyframes</h3>
<p>Rechts stel je per clip <b>positie</b>, <b>schaal</b>, <b>rotatie</b> en
<b>opaciteit</b> in. Je kunt de geselecteerde clip ook <b>direct in het voorbeeld
verslepen</b> om hem te verplaatsen. Klik op het <b>◆-knopje</b> naast een waarde
om er een <b>keyframe</b> van te maken op de huidige tijd. Verzet de afspeelkop,
wijzig de waarde (of versleep), en de clip <b>animeert</b> tussen de keyframes. Een selectie krijgt een <b>rand met hoekgrepen</b>: trek eraan om te schalen. Vergiste je je? Gebruik <b>↶ Ongedaan</b> / <b>↷ Opnieuw</b> (of Ctrl+Z / Ctrl+Y).</p>

<h3 style="color:#6fa3d6;">5 · Tekst &amp; titels</h3>
<p>Maak een <b>tekstclip</b> en open <b>Bewerk tekst</b>: kies <b>lettertype</b>,
<b>grootte</b>, <b>breedte</b> (waarbinnen de tekst afbreekt), <b>kleur</b> en een
optioneel <b>achtergrondkader</b>. <b>Dubbelklik</b> op de tekst in het voorbeeld
om hem te bewerken. <b>Verplaatsen</b> doe je door te slepen; <b>groter/kleiner</b>
maken door aan de <b>hoekgrepen</b> van de rand te trekken. De achtergrond kan met
<b>Achtergrond dekking</b> van vol tot volledig <b>doorzichtig</b>. Met <b>End credits</b>
maak je een <b>aftiteling</b> (titel, auteur, copyright, muziek, dank, extra), eventueel
<b>rollend</b> van onder naar boven.</p>
<p>Met <b>Stok-poppetje</b> teken je een eenvoudig lijn-figuurtje dat je
<b>frame voor frame</b> in een nieuwe houding zet: sleep de gewrichten, voeg een
<b>nieuw frame</b> toe en pose opnieuw. Het vorige frame schemert door (onion skin),
zodat je vloeiend kunt animeren. Dubbelklik de clip om hem te bewerken.</p>
<p>De <b>Teken-studio + poppetje</b> combineert beide in één venster met twee
<b>tabbladen</b> die op dezelfde frames werken. Gebruik het <b>Poppetje</b>-tabblad om
het skelet in een houding te zetten (sleep de bolletjes). Ga dan naar <b>Tekenen</b>: daar
zie je dat skelet als lichtblauwe <b>hulplijn</b> en kun je er je eigen figuur vrij overheen
tekenen. Het stick-poppetje is dus alleen een mal — je tekent zelf wat je wilt.</p>
<p>Met de knop <b>Skelet in eindbeeld: aan/uit</b> (in het Poppetje-tabblad) bepaal je per
frame of het skelet ook echt in de video komt. Zet je het <b>uit</b>, dan blijft alleen jouw
eigen tekening over (in de houding die je poseerde). Rechts beheer je de frames (toevoegen,
dupliceren, verwijderen) en de FPS; de canvas schaalt mee met het venster.</p>
<p><b>Poppetje met skelet (rigging)</b> is de krachtigste vorm: je tekent (of laadt) je figuur
<b>één keer</b> op het rust-skelet (tab “Tekenen (delen)”: kies links een deel, het bot licht
op, en teken het). Daarna ga je naar “Animeren” en zet je per frame de houding door de
gewrichten te slepen — je getekende delen draaien en verschuiven automatisch mee. Eén keer
tekenen, daarna animeer je met alleen het skelet. Voeg frames toe voor elke nieuwe houding.</p>
<p><b>Eigen skelet bouwen</b> (tab “Skelet”): kies een <b>mal</b> (Mens, Viervoeter, Vogel)
of begin leeg, en pas het skelet vrij aan. <b>Gewricht plaatsen</b>: klik op een leeg
plekje. <b>Bot maken</b>: klik twee gewrichten na elkaar. <b>Verplaatsen</b>: sleep een
gewricht. <b>Verwijderen</b>: klik op een gewricht of bot. Zo maak je elk wezen dat je wilt
en teken je daarna de delen erop.</p>
<p><b>Onion skin</b> (“vorig frame tonen”): zet je dit aan, dan zie je het vorige
frame lichtjes als schaduw onder je huidige frame. Zo kun je je nieuwe tekening of
houding er netjes op uitlijnen, voor een vloeiende animatie. Het verschijnt niet in de
uiteindelijke video — het is alleen een hulplijn tijdens het tekenen.</p>

<h3 style="color:#6fa3d6;">6 · Effecten</h3>
<p>Onder <b>Effecten</b> regel je per beeldclip <b>helderheid</b>, <b>contrast</b>,
<b>verzadiging</b> en <b>vervaging</b>, plus een <b>Filter</b> (grijswaarden, sepia
of negatief). Alles op 0 / "Geen" betekent: geen wijziging.</p>

<h3 style="color:#6fa3d6;">7 · Transities &amp; snelheid</h3>
<p>Geef een clip een <b>fade in</b> en/of <b>fade uit</b> (in seconden) en kies per
kant een <b>type</b>: vervagen, schuiven, vegen, zoom of dip naar zwart/wit. Laat
twee clips <b>overlappen</b> voor een <b>crossfade</b>. Bij een <b>videoclip</b>
stel je ook de <b>snelheid ×</b> in: onder 1 = slow motion, boven 1 = versneld /
timelapse. De schuine driehoekjes op een clip tonen de fades.</p>

<h3 style="color:#6fa3d6;">8 · Geluid</h3>
<p>Het geluid van een geïmporteerde <b>video</b> speelt automatisch mee; met de
<b>Volume</b>-regelaar (ook bij video) zet je het zachter of helemaal uit.</p>
<p>Audioclips staan op het <b>audiospoor</b> (geen beeld). Per audioclip stel je
<b>volume</b> en <b>fade in/uit</b> in. Tijdens het afspelen hoor je alles
<b>mee in de preview</b>; bij export wordt het op de juiste tijd gemengd.</p>

<h3 style="color:#6fa3d6;">9 · Exporteren &amp; portable</h3>
<p>Rechtsboven via <b>Exporteren…</b>: <b>MP4</b> (met geluid), <b>GIF</b> of een
<b>PNG-reeks</b>. Alles blijft in de app-map (<b>cache</b>, <b>projecten</b>) — neem
de map gewoon mee op een USB-stick.</p>

<h3 style="color:#6fa3d6;">Sneltoetsen</h3>
<p><b>Spatie</b> — afspelen/pauze &nbsp;·&nbsp; <b>Ctrl+Z</b> — ongedaan &nbsp;·&nbsp;
<b>Ctrl+Y</b> — opnieuw &nbsp;·&nbsp; <b>Ctrl+D</b> — clip dupliceren &nbsp;·&nbsp;
<b>Delete</b> — clip verwijderen</p>
"""


class QuickGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snelgids - DraveMotion")
        self.resize(620, 660)
        lay = QVBoxLayout(self)
        body = QLabel(GUIDE_HTML)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setAlignment(Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        row = QHBoxLayout()
        self.show_chk = QPushButton("Toon bij opstarten: aan")
        self.show_chk.setCheckable(True)
        self.show_chk.setChecked(load_config().get("show_guide_on_start", True))
        self._sync_chk()
        self.show_chk.clicked.connect(self._toggle_show)
        row.addWidget(self.show_chk)
        row.addStretch(1)
        close = QPushButton("Sluiten"); close.setObjectName("cta")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)

    def _sync_chk(self):
        on = self.show_chk.isChecked()
        self.show_chk.setText(f"Toon bij opstarten: {'aan' if on else 'uit'}")

    def _toggle_show(self):
        cfg = load_config()
        cfg["show_guide_on_start"] = self.show_chk.isChecked()
        save_config(cfg)
        self._sync_chk()


def open_quick_guide(parent=None):
    """Open de Snelgids, óók als er al een ander venster (editor) open staat."""
    QuickGuideDialog(parent).exec_()



# =========================================================================== #
#  HOOFDVENSTER
# =========================================================================== #
class PreviewCanvas(QLabel):
    """Voorbeeldvenster: geselecteerde clip verslepen, schalen (hoekgrepen) en
    dubbelklikken om te bewerken."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_drag = None          # callback(x, y, dx, dy, phase)
        self.on_double = None        # callback(x, y)
        self.on_hover = None         # callback(x, y) -> cursorvorm (Qt.CursorShape) of None
        self.on_resize = None        # callback() bij grootteverandering
        self._last = None
        self.setMouseTracking(True)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.on_resize:
            self.on_resize()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._last = ev.pos()
            if self.on_drag:
                self.on_drag(ev.x(), ev.y(), 0, 0, "start")

    def mouseMoveEvent(self, ev):
        if self._last is not None and (ev.buttons() & Qt.LeftButton):
            dx = ev.x() - self._last.x()
            dy = ev.y() - self._last.y()
            self._last = ev.pos()
            if self.on_drag:
                self.on_drag(ev.x(), ev.y(), dx, dy, "move")
        elif self.on_hover:
            shape = self.on_hover(ev.x(), ev.y())
            self.setCursor(shape if shape is not None else Qt.ArrowCursor)

    def mouseReleaseEvent(self, ev):
        if self._last is not None:
            self._last = None
            if self.on_drag:
                self.on_drag(ev.x(), ev.y(), 0, 0, "end")

    def mouseDoubleClickEvent(self, ev):
        if self.on_double:
            self.on_double(ev.x(), ev.y())


# =========================================================================== #
#  VERSIE-CONTROLE (leest version.txt van de site)
# =========================================================================== #
def parse_version(s):
    """'v0.33' -> (0, 33).  Onleesbaar -> (0,)."""
    if not s:
        return (0,)
    parts = re.findall(r"\d+", str(s))
    return tuple(int(p) for p in parts) if parts else (0,)


def is_newer(remote, local=APP_VERSION):
    return parse_version(remote) > parse_version(local)


def fetch_latest_version():
    """Haal version.txt op. 1e regel = versie, rest = notities. Geeft dict of None."""
    try:
        req = urllib.request.Request(UPDATE_CHECK_URL,
                                     headers={"User-Agent": f"DraveMotion/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=6) as r:
            text = r.read().decode("utf-8", "replace").strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return None
        return {"version": lines[0], "notes": "\n".join(lines[1:])}
    except Exception:
        return None


class _UpdateWorker(QThread):
    done = pyqtSignal(object)        # dict {version, notes} of None

    def run(self):
        self.done.emit(fetch_latest_version())


# =========================================================================== #
#  CONTACT (vraag / klacht / idee / bug -> service@dravenlock.nl)
# =========================================================================== #
class ContactDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Contact opnemen") + " - " + APP_NAME)
        self.resize(560, 600)
        lay = QVBoxLayout(self)
        intro = QLabel("Een vraag, klacht, idee of bug gevonden? Laat het de maker "
                       "(Dravenlock) weten. Vul hieronder in en klik op ‘Versturen’ — dan "
                       "open ik je e-mailprogramma met het bericht alvast klaargezet aan "
                       f"{SERVICE_EMAIL}.")
        intro.setWordWrap(True); lay.addWidget(intro)

        lay.addWidget(QLabel(t("Soort bericht:")))
        self.kind = QComboBox()
        self.kind.addItems([t("Vraag"), t("Klacht"), t("Idee"), t("Bug / fout"), t("Anders")])
        lay.addWidget(self.kind)

        lay.addWidget(QLabel(t("Je naam:")))
        self.name = QLineEdit(); lay.addWidget(self.name)

        lay.addWidget(QLabel(t("Je e-mailadres (zodat de maker je kan antwoorden):")))
        self.email = QLineEdit(); lay.addWidget(self.email)

        lay.addWidget(QLabel(t("Je bericht:")))
        self.body = QPlainTextEdit(); self.body.setMinimumHeight(180); lay.addWidget(self.body, 1)

        em = QLabel(f"Lukt het versturen niet? Mail dan rechtstreeks naar "
                    f"<b>{SERVICE_EMAIL}</b>.")
        em.setWordWrap(True); em.setTextFormat(Qt.RichText); lay.addWidget(em)

        row = QHBoxLayout()
        copy = QPushButton(t("📋 Kopieer e-mailadres")); copy.clicked.connect(self._copy)
        row.addWidget(copy); row.addStretch(1)
        cancel = QPushButton(t("Sluiten")); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        send = QPushButton(t("✉️ Versturen")); send.setObjectName("cta"); send.setMinimumHeight(36)
        send.clicked.connect(self._send); row.addWidget(send)
        lay.addLayout(row)

    def _copy(self):
        QApplication.clipboard().setText(SERVICE_EMAIL)
        QMessageBox.information(self, "Gekopieerd",
                                f"{SERVICE_EMAIL} is naar het klembord gekopieerd.")

    def _send(self):
        if not self.body.toPlainText().strip():
            QMessageBox.information(self, "Leeg bericht", "Typ eerst een bericht.")
            return
        kind = self.kind.currentText()
        name = self.name.text().strip() or "(geen naam)"
        mail = self.email.text().strip() or "(geen e-mail opgegeven)"
        subject = f"[{APP_NAME} v{APP_VERSION}] {kind} van {name}"
        body = (f"Soort bericht: {kind}\nNaam: {name}\nE-mail: {mail}\n"
                f"{APP_NAME} versie: {APP_VERSION}\n\n{self.body.toPlainText().strip()}\n")
        url = (f"mailto:{SERVICE_EMAIL}"
               f"?subject={urllib.parse.quote(subject)}"
               f"&body={urllib.parse.quote(body)}")
        opened = QDesktopServices.openUrl(QUrl(url))
        if opened:
            self.accept()
        else:
            QApplication.clipboard().setText(f"Aan: {SERVICE_EMAIL}\nOnderwerp: {subject}\n\n{body}")
            QMessageBox.information(self, "E-mailprogramma niet gevonden",
                f"Ik kon geen e-mailprogramma openen. Het hele bericht staat nu op je klembord — "
                f"plak het in je e-mail en stuur het naar {SERVICE_EMAIL}.")


class DraveMotion(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DraveMotion v{APP_VERSION}")
        self.project = Project()
        self.cur_track = 0
        self._sel = None
        self.assets = []                 # mediabak: lijst van {kind, path, name}
        self._undo_stack, self._redo_stack = [], []
        self._loading_ui = False
        self.play_timer = QTimer(self); self.play_timer.timeout.connect(self._play_tick)
        self.playing = False
        self.audio_player = QMediaPlayer(self) if HAVE_QTMM else None
        if self.audio_player:
            self.audio_player.setVolume(90)
            self.audio_player.mediaStatusChanged.connect(self._on_audio_status)
        self._audio_sig = None
        self._audio_file = None
        self._audio_counter = 0
        self._audio_play_pending = False
        self._build_ui()
        # app-brede sneltoetsen (werken ongeacht waar de focus ligt)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.redo)
        self._update_undo_buttons()
        self.refresh_timeline()
        self.update_preview()
        self.resize(1300, 800)

    # ---- opbouw ---------------------------------------------------------- #
    def _build_ui(self):
        central = QWidget(); outer = QVBoxLayout(central)
        outer.addWidget(self._header())
        body = QHBoxLayout()
        body.addWidget(self._left_panel())
        body.addWidget(self._center(), 1)
        body.addWidget(self._right_panel())
        outer.addLayout(body, 1)
        self.setCentralWidget(central)
        ver = QLabel(f"v{APP_VERSION}"); ver.setObjectName("mono")
        self.statusBar().addWidget(ver)
        donate = QPushButton("♥ Donatie"); donate.setObjectName("cta")
        donate.setToolTip("Steun Dravenlock")
        donate.clicked.connect(self._donate)
        self.statusBar().addPermanentWidget(donate)
        self.statusBar().showMessage("Klaar. Importeer media of maak een tekenscène/tekst.")

    def _donate(self):
        if not QDesktopServices.openUrl(QUrl(DONATE_URL)):
            QMessageBox.information(self, "Donatie",
                                    "Steun Dravenlock — bedankt!\n" + DONATE_URL)

    def _header(self):
        h = QWidget(); h.setObjectName("header"); lay = QHBoxLayout(h)
        logo = QLabel(); logo.setPixmap(make_logo(44)); lay.addWidget(logo)
        tbox = QVBoxLayout(); tbox.setSpacing(0)
        title = QLabel("DraveMotion"); title.setObjectName("title")
        sub = QLabel(f"v{APP_VERSION}  ·  {t('een Dravenlock product')}"); sub.setObjectName("subtitle")
        tbox.addWidget(title); tbox.addWidget(sub); lay.addLayout(tbox)
        lay.addStretch(1)
        guide = QPushButton(t("📖 Snelgids")); guide.clicked.connect(self.open_guide); lay.addWidget(guide)
        contact = QPushButton(t("✉️ Contact")); contact.clicked.connect(self.open_contact); lay.addWidget(contact)
        upd = QPushButton(t("🔄 Updates")); upd.clicked.connect(lambda: self.check_updates(False)); lay.addWidget(upd)
        info = QPushButton(t("ⓘ Info")); info.clicked.connect(self.show_info); lay.addWidget(info)
        exp = QPushButton(t("⤓ Exporteren…")); exp.setObjectName("cta"); exp.clicked.connect(self.export_dialog)
        lay.addWidget(exp)
        return h

    def _left_panel(self):
        lay = QVBoxLayout(); lay.setSpacing(6)
        lay.addWidget(section("Project"))
        for label, fn in [("Nieuw", self.new_project), ("Openen…", self.open_project),
                          ("Opslaan…", self.save_project), ("Instellingen…", self.open_settings)]:
            b = QPushButton(t(label)); b.clicked.connect(fn); lay.addWidget(b)

        lay.addWidget(section("Toevoegen"))
        b1 = QPushButton(t("✎ Nieuwe tekenscène")); b1.clicked.connect(self.add_scene); lay.addWidget(b1)
        bt = QPushButton(t("T  Tekst / titel")); bt.clicked.connect(self.add_text); lay.addWidget(bt)
        bc = QPushButton(t("▤  End credits / aftiteling"))
        bc.setToolTip("Aftiteling met titel, auteur, copyright, muziek, dank…")
        bc.clicked.connect(self.add_credits); lay.addWidget(bc)
        bf = QPushButton(t("🦴  Stok-poppetje"))
        bf.setToolTip("Vector-poppetje (skelet) dat je frame voor frame in een houding zet")
        bf.clicked.connect(self.add_figure); lay.addWidget(bf)
        bst = QPushButton(t("🎬  Teken-studio + poppetje"))
        bst.setToolTip("Eén editor met tabbladen: vrij tekenen én een skelet poseren per frame")
        bst.clicked.connect(self.add_studio); lay.addWidget(bst)
        brig = QPushButton(t("🧍  Poppetje met skelet"))
        brig.setToolTip("Rigging: teken elk lichaamsdeel één keer; daarna animeer je door "
                        "alleen het skelet te poseren — de tekening beweegt mee.")
        brig.clicked.connect(self.add_rig); lay.addWidget(brig)
        b2 = QPushButton(t("🎞 Importeer video…")); b2.clicked.connect(self.import_video); lay.addWidget(b2)
        b3 = QPushButton(t("🖼 Importeer foto…")); b3.clicked.connect(self.import_image); lay.addWidget(b3)
        b4 = QPushButton(t("🎵 Importeer audio…")); b4.clicked.connect(self.import_audio); lay.addWidget(b4)
        btts = QPushButton(t("🔊  Stem (tekst-naar-spraak)…"))
        btts.setToolTip("Maak met NeuVoice een gesproken stem van je tekst en zet die in de mediabak")
        btts.clicked.connect(self.open_tts); lay.addWidget(btts)
        if not HAVE_CV2:
            note = QLabel("Video uit: installeer opencv-python-headless"); note.setWordWrap(True)
            note.setObjectName("mono"); lay.addWidget(note)

        lay.addWidget(section("Media bestanden"))
        load_folder = QPushButton(t("📂 Map laden…"))
        load_folder.setToolTip("Kies een map; alle media erin (bv. een soundpool) wordt geladen")
        load_folder.clicked.connect(self.import_folder)
        lay.addWidget(load_folder)
        self.asset_tree = AssetTree()
        self.asset_tree.itemDoubleClicked.connect(self._asset_double_clicked)
        self.asset_tree.setToolTip("Klik een map open · sleep een bestand naar de tijdlijn of dubbelklik")
        lay.addWidget(self.asset_tree, 1)
        rm = QPushButton(t("Uit lijst verwijderen")); rm.clicked.connect(self._remove_asset); lay.addWidget(rm)

        lay.addWidget(section("Spoor"))
        self.track_combo = QComboBox(); self._refresh_track_combo()
        self.track_combo.currentIndexChanged.connect(self._set_track); lay.addWidget(self.track_combo)
        at = QPushButton(t("+ Spoor")); at.clicked.connect(self.add_track); lay.addWidget(at)

        panel = QWidget(); panel.setObjectName("panel"); panel.setLayout(lay)
        self.asset_tree.setMinimumHeight(140)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)  # links-scroll-0.40.3
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(296)
        return scroll

    def _center(self):
        w = QWidget(); lay = QVBoxLayout(w)
        self.preview = PreviewCanvas("Geen beeld"); self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(330)
        self.preview.setStyleSheet("background:#000; border:1px solid #2a2a31; border-radius:8px;")
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setCursor(Qt.OpenHandCursor)
        self.preview.on_drag = self._preview_drag
        self.preview.on_double = self._preview_double
        self.preview.on_hover = self._preview_hover
        self.preview.on_resize = self._place_intro
        self._build_intro_overlay()
        lay.addWidget(self.preview, 1)
        transport = QHBoxLayout()
        self.play_btn = QPushButton(t("▶ Afspelen")); self.play_btn.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_btn)
        self.stop_btn = QPushButton(t("⏹ Stop")); self.stop_btn.setToolTip("Stoppen en terug naar het begin")
        self.stop_btn.clicked.connect(self.stop_playback); transport.addWidget(self.stop_btn)
        self.undo_btn = QPushButton(t("↶ Ongedaan")); self.undo_btn.setToolTip("Ongedaan maken (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo); transport.addWidget(self.undo_btn)
        self.redo_btn = QPushButton(t("↷ Opnieuw")); self.redo_btn.setToolTip("Opnieuw doen (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.redo); transport.addWidget(self.redo_btn)
        self.dup_clip_btn = QPushButton(t("⧉ Dupliceer"))
        self.dup_clip_btn.setToolTip("Geselecteerde clip dupliceren (Ctrl+D)")
        self.dup_clip_btn.clicked.connect(self.duplicate_clip); transport.addWidget(self.dup_clip_btn)
        self.del_clip_btn = QPushButton(t("🗑 Verwijder"))
        self.del_clip_btn.setToolTip("Geselecteerde clip verwijderen (Delete)")
        self.del_clip_btn.clicked.connect(self.delete_clip); transport.addWidget(self.del_clip_btn)
        self.time_label = QLabel("0.00s / 0.00s"); self.time_label.setObjectName("mono")
        transport.addWidget(self.time_label); transport.addStretch(1)
        zo = QPushButton("➖"); zo.setToolTip("Uitzoomen"); zo.setFixedWidth(40)
        zo.clicked.connect(lambda: self.timeline.set_zoom(self.timeline.px_per_sec * 0.8))
        zi = QPushButton("➕"); zi.setToolTip("Inzoomen"); zi.setFixedWidth(40)
        zi.clicked.connect(lambda: self.timeline.set_zoom(self.timeline.px_per_sec * 1.25))
        transport.addWidget(zo); transport.addWidget(zi)
        transport.addWidget(QLabel(t("FPS")))
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 60); self.fps_spin.setValue(self.project.fps)
        self.fps_spin.valueChanged.connect(self._set_fps); transport.addWidget(self.fps_spin)
        lay.addLayout(transport)
        self.timeline = TimelineView(self.project)
        self.timeline.on_playhead = self._on_playhead
        self.timeline.on_select = self._on_select_clip
        self.timeline.on_change = self.update_preview
        self.timeline.on_drag_start = self._push_undo
        self.timeline.on_drop_asset = self._on_drop_asset
        self.timeline.on_split = self._split_at
        self.timeline.on_edit = self._edit_clip
        tl_scroll = QScrollArea(); tl_scroll.setWidgetResizable(True); tl_scroll.setWidget(self.timeline)
        tl_scroll.setFixedHeight(self.timeline._layout_height() + 16)
        lay.addWidget(tl_scroll)
        return w

    def _right_panel(self):
        lay = QVBoxLayout(); lay.setSpacing(6)
        lay.addWidget(section("Geselecteerde clip"))
        self.clip_name = QLabel(t("— geen clip —")); self.clip_name.setWordWrap(True); lay.addWidget(self.clip_name)
        lay.addWidget(QLabel(t("Start (s)")))
        self.start_spin = QDoubleSpinBox(); self.start_spin.setRange(0, 9999); self.start_spin.setSingleStep(0.1)
        self.start_spin.valueChanged.connect(self._edit_start); lay.addWidget(self.start_spin)
        lay.addWidget(QLabel(t("Duur / trim (s)")))
        self.dur_spin = QDoubleSpinBox(); self.dur_spin.setRange(0.1, 9999); self.dur_spin.setSingleStep(0.1)
        self.dur_spin.valueChanged.connect(self._edit_dur); lay.addWidget(self.dur_spin)

        lay.addWidget(section("Transform"))
        self.tf_spins, self.tf_kf = {}, {}
        specs = [("x", "X (px)", -4000, 4000), ("y", "Y (px)", -4000, 4000),
                 ("scale", "Schaal %", 1, 2000), ("rotation", "Rotatie °", -3600, 3600),
                 ("opacity", "Opaciteit %", 0, 100)]
        for name, label, lo, hi in specs:
            lay.addWidget(QLabel(t(label)))
            row = QHBoxLayout()
            spin = QDoubleSpinBox(); spin.setRange(lo, hi); spin.setDecimals(1); spin.setSingleStep(1)
            spin.valueChanged.connect(lambda v, n=name: self._set_prop(n, v))
            row.addWidget(spin, 1)
            kf = QToolButton(); kf.setText("○"); kf.setFixedWidth(34)
            kf.setToolTip("Keyframe op de huidige tijd aan/uit")
            kf.clicked.connect(lambda _, n=name: self._kf_toggle(n))
            row.addWidget(kf)
            lay.addLayout(row)
            self.tf_spins[name] = spin; self.tf_kf[name] = kf

        # --- Effecten (alleen visuele clips) ---
        self.fx_section = section("Effecten")
        lay.addWidget(self.fx_section)
        self.fx_spins, self.fx_labels = {}, {}
        fx_specs = [("brightness", "Helderheid", -100, 100),
                    ("contrast", "Contrast", -100, 100),
                    ("saturation", "Verzadiging", -100, 100),
                    ("blur", "Vervaging", 0, 50)]
        for name, label, lo, hi in fx_specs:
            lbl = QLabel(label); lay.addWidget(lbl)
            spin = QDoubleSpinBox(); spin.setRange(lo, hi)
            spin.setDecimals(0); spin.setSingleStep(1)
            spin.valueChanged.connect(lambda v, n=name: self._set_effect(n, v))
            lay.addWidget(spin)
            self.fx_spins[name] = spin; self.fx_labels[name] = lbl
        if not HAVE_NUMPY:
            for n in self.fx_spins:
                self.fx_spins[n].setEnabled(False)
        if not HAVE_CV2:
            self.fx_spins["blur"].setEnabled(False)
            self.fx_spins["blur"].setToolTip("Vervaging vereist opencv-python-headless")

        # --- Transitie / fade (+ snelheid voor video, volume voor audio) ---
        self.fade_section = section("Transitie / fade")
        lay.addWidget(self.fade_section)
        self.speed_lbl = QLabel("Snelheid × (video)"); lay.addWidget(self.speed_lbl)
        self.speed_spin = QDoubleSpinBox(); self.speed_spin.setRange(0.1, 8.0)
        self.speed_spin.setSingleStep(0.25); self.speed_spin.setDecimals(2)
        self.speed_spin.setValue(1.0)
        self.speed_spin.valueChanged.connect(self._set_speed)
        lay.addWidget(self.speed_spin)
        self.fade_in_lbl = QLabel("Fade in (s)"); lay.addWidget(self.fade_in_lbl)
        self.fade_in_spin = QDoubleSpinBox(); self.fade_in_spin.setRange(0, 30)
        self.fade_in_spin.setSingleStep(0.1)
        self.fade_in_spin.valueChanged.connect(lambda v: self._set_fade("fade_in", v))
        lay.addWidget(self.fade_in_spin)
        self.trans_in_lbl = QLabel("Type in"); lay.addWidget(self.trans_in_lbl)
        self.trans_in_combo = QComboBox(); self.trans_in_combo.addItems(TRANS_LABELS)
        self.trans_in_combo.currentIndexChanged.connect(
            lambda i: self._set_trans("in", TRANS_KEYS[i]))
        lay.addWidget(self.trans_in_combo)
        self.fade_out_lbl = QLabel("Fade uit (s)"); lay.addWidget(self.fade_out_lbl)
        self.fade_out_spin = QDoubleSpinBox(); self.fade_out_spin.setRange(0, 30)
        self.fade_out_spin.setSingleStep(0.1)
        self.fade_out_spin.valueChanged.connect(lambda v: self._set_fade("fade_out", v))
        lay.addWidget(self.fade_out_spin)
        self.trans_out_lbl = QLabel("Type uit"); lay.addWidget(self.trans_out_lbl)
        self.trans_out_combo = QComboBox(); self.trans_out_combo.addItems(TRANS_LABELS)
        self.trans_out_combo.currentIndexChanged.connect(
            lambda i: self._set_trans("out", TRANS_KEYS[i]))
        lay.addWidget(self.trans_out_combo)
        self.filter_lbl = QLabel("Filter"); lay.addWidget(self.filter_lbl)
        self.filter_combo = QComboBox(); self.filter_combo.addItems(FILTER_LABELS)
        self.filter_combo.currentIndexChanged.connect(
            lambda i: self._set_filter(FILTER_KEYS[i]))
        lay.addWidget(self.filter_combo)
        self.vol_lbl = QLabel("Volume %"); lay.addWidget(self.vol_lbl)
        self.vol_spin = QDoubleSpinBox(); self.vol_spin.setRange(0, 200)
        self.vol_spin.setDecimals(0); self.vol_spin.setSingleStep(5)
        self.vol_spin.valueChanged.connect(self._set_volume)
        lay.addWidget(self.vol_spin)

        self.edit_scene_btn = QPushButton("✎ Bewerk scène"); self.edit_scene_btn.setObjectName("cta")
        self.edit_scene_btn.clicked.connect(self.edit_scene); lay.addWidget(self.edit_scene_btn)
        self.edit_text_btn = QPushButton("T Bewerk tekst"); self.edit_text_btn.setObjectName("cta")
        self.edit_text_btn.clicked.connect(self.edit_text); lay.addWidget(self.edit_text_btn)
        self.edit_credits_btn = QPushButton("▤ Bewerk aftiteling"); self.edit_credits_btn.setObjectName("cta")
        self.edit_credits_btn.clicked.connect(self.edit_credits); lay.addWidget(self.edit_credits_btn)
        self.edit_figure_btn = QPushButton("🦴 Bewerk stok-poppetje"); self.edit_figure_btn.setObjectName("cta")
        self.edit_figure_btn.clicked.connect(self.edit_figure); lay.addWidget(self.edit_figure_btn)
        self.edit_studio_btn = QPushButton("🎬 Bewerk studio"); self.edit_studio_btn.setObjectName("cta")
        self.edit_studio_btn.clicked.connect(self.edit_studio); lay.addWidget(self.edit_studio_btn)
        self.edit_rig_btn = QPushButton("🧍 Bewerk poppetje (skelet)"); self.edit_rig_btn.setObjectName("cta")
        self.edit_rig_btn.clicked.connect(self.edit_rig); lay.addWidget(self.edit_rig_btn)
        self.talk_chk = QCheckBox("🗣  Praat mee met de stem")
        self.talk_chk.setToolTip("Aan: de mond van dit poppetje beweegt automatisch mee met de stem "
                                 "op het Stem-spoor. Heb je nog geen mond getekend, dan maak ik er "
                                 "automatisch één bij het hoofd.")
        self.talk_chk.toggled.connect(self._toggle_talk); lay.addWidget(self.talk_chk)
        self.place_mouth_btn = QPushButton("👄  Mond plaatsen…")
        self.place_mouth_btn.setToolTip("Klik op je figuur waar de mond zit en stel de grootte in.")
        self.place_mouth_btn.clicked.connect(self._place_mouth); lay.addWidget(self.place_mouth_btn)
        lay.addStretch(1)
        content = QWidget(); content.setObjectName("panel"); content.setLayout(lay)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(content)
        scroll.setFixedWidth(266)
        self._update_clip_panel(None)
        return scroll

    # ---- media bestanden ------------------------------------------------- #
    def _add_asset(self, kind, path=None, name=None, group="Losse bestanden"):
        self.assets.append({"kind": kind, "path": path, "group": group,
                            "name": name or (os.path.basename(path) if path else kind)})
        self._refresh_assets()
        self.statusBar().showMessage(f"Toegevoegd aan media bestanden: {self.assets[-1]['name']}")
        return len(self.assets) - 1

    def _refresh_assets(self):
        self.asset_tree.clear()
        groups = {}  # groepnaam -> QTreeWidgetItem
        folder_ic = self.style().standardIcon(QStyle.SP_DirIcon)
        for i, a in enumerate(self.assets):
            gname = a.get("group") or "Losse bestanden"
            parent = groups.get(gname)
            if parent is None:
                parent = QTreeWidgetItem(self.asset_tree, [gname])
                parent.setIcon(0, folder_ic)
                parent.setFlags(Qt.ItemIsEnabled)  # map zelf niet selecteerbaar/sleepbaar
                parent.setExpanded(False)
                groups[gname] = parent
            it = QTreeWidgetItem(parent, [a["name"]])
            it.setIcon(0, asset_icon(a["kind"], a.get("path")))
            it.setData(0, Qt.UserRole, i)
            it.setToolTip(0, a.get("path") or a["kind"])
        # tel files per groep in de koptekst
        for gname, parent in groups.items():
            parent.setText(0, f"{gname}  ({parent.childCount()})")

    def _remove_asset(self):
        it = self.asset_tree.currentItem()
        if it is None:
            return
        idx = it.data(0, Qt.UserRole)
        if idx is None:
            return
        if 0 <= idx < len(self.assets):
            del self.assets[idx]
            self._refresh_assets()

    def _asset_double_clicked(self, item, _col=0):
        idx = item.data(0, Qt.UserRole)
        if idx is None:            # dubbelklik op een map: open/sluit hem
            item.setExpanded(not item.isExpanded())
            return
        self._place_asset(idx)

    def _clip_from_asset(self, a):
        k = a["kind"]
        if k == "video":
            return VideoClip(a["path"]) if HAVE_CV2 else None
        if k == "image":
            return ImageClip(a["path"])
        if k == "audio":
            return AudioClip(a["path"]) if HAVE_FFMPEG else None
        return None

    def _place_asset(self, idx, ti=None, start=None):
        if not (0 <= idx < len(self.assets)):
            return
        clip = self._clip_from_asset(self.assets[idx])
        if clip is None:
            QMessageBox.warning(self, "Niet beschikbaar", "Dit cliptype is nu niet bruikbaar.")
            return
        if ti is None:
            ti = self.cur_track
        desired_start = max(0.0, self.timeline.playhead if start is None else start)
        if isinstance(clip, AudioClip) and self.project.tracks[ti].kind != "audio":
            ti = self._ensure_audio_track()
        clip.start = desired_start
        self._push_undo()
        self.project.tracks[ti].add(clip)
        self.timeline.selected = clip; self._on_select_clip(clip)
        self.refresh_timeline(); self.update_preview()

    def _on_drop_asset(self, idx, ti, start):
        self._place_asset(idx, ti, start)

    def import_video(self):
        if not HAVE_CV2:
            QMessageBox.warning(self, "Video uit", "Installeer opencv-python-headless voor video.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Video importeren", PROJECTS_DIR,
                                              "Video (*.mp4 *.mov *.avi *.mkv *.webm);;Alle (*)")
        if path:
            self._add_asset("video", path)

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Foto importeren", PROJECTS_DIR,
                                              "Afbeelding (*.png *.jpg *.jpeg *.bmp *.gif);;Alle (*)")
        if path:
            self._add_asset("image", path)

    def import_audio(self):
        if not HAVE_FFMPEG:
            QMessageBox.warning(self, "Audio", "ffmpeg ontbreekt; audio niet beschikbaar.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Audio importeren", PROJECTS_DIR,
            "Audio (*.mp3 *.wav *.m4a *.aac *.ogg *.flac *.wma *.aif *.aiff);;Alle (*)")
        if path:
            self._add_asset("audio", path)

    def import_folder(self):
        """Kies een map en laad alle herkende media erin (incl. submappen)."""
        folder = QFileDialog.getExistingDirectory(self, "Map met media laden", PROJECTS_DIR)
        if not folder:
            return
        # 1) verzamel alle media-bestanden (recursief) met hun (sub)mapnaam
        root_name = os.path.basename(os.path.normpath(folder)) or folder
        found = []
        for root, _dirs, files in os.walk(folder):
            rel = os.path.relpath(root, folder)
            group = root_name if rel == "." else os.path.join(root_name, rel)
            for fn in files:
                kind = kind_for_ext(fn)
                if kind is None:
                    continue
                if kind == "video" and not HAVE_CV2:
                    continue
                if kind == "audio" and not HAVE_FFMPEG:
                    continue
                found.append((kind, os.path.join(root, fn), group))
        if not found:
            QMessageBox.information(self, "Map laden",
                                    "Geen bruikbare mediabestanden in deze map gevonden.")
            return
        # 2) toevoegen met voortgangsbalk (annuleerbaar)
        dlg = QProgressDialog("Media inladen…", "Annuleer", 0, len(found), self)
        dlg.setWindowTitle("Map laden"); dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        added = 0
        for i, (kind, path, group) in enumerate(found):
            if dlg.wasCanceled():
                break
            self.assets.append({"kind": kind, "path": path, "group": group,
                                "name": os.path.basename(path)})
            added += 1
            dlg.setValue(i + 1)
            if added % 25 == 0:
                QApplication.processEvents()
        dlg.setValue(len(found))
        self._refresh_assets()
        self.statusBar().showMessage(f"{added} mediabestand(en) geladen uit {folder}")

    # ---- clips toevoegen ------------------------------------------------- #
    def _ensure_audio_track(self):
        ai = next((i for i, t in enumerate(self.project.tracks) if t.kind == "audio"), None)
        if ai is None:
            ph = self.timeline.playhead
            self.project.tracks.append(Track("Audio 1", kind="audio"))
            ai = len(self.project.tracks) - 1
            self._refresh_track_combo(); self.timeline.set_project(self.project)
            self.timeline.playhead = ph
        return ai

    def _ensure_voice_track(self):
        vi = next((i for i, t in enumerate(self.project.tracks) if t.kind == "voice"), None)
        if vi is None:
            ph = self.timeline.playhead
            self.project.tracks.append(Track("Stem", kind="voice"))
            vi = len(self.project.tracks) - 1
            self._refresh_track_combo(); self.timeline.set_project(self.project)
            self.timeline.playhead = ph
        return vi

    def add_voice_clip(self, path, start=None):
        """Zet een stembestand op het Stem-spoor (maakt het spoor aan als het nog niet bestaat)."""
        self._push_undo()
        vi = self._ensure_voice_track()
        c = AudioClip(path)
        c.start = self.timeline.playhead if start is None else float(start)
        self.project.tracks[vi].add(c)
        self.timeline.selected = c; self._on_select_clip(c)
        self.refresh_timeline(); self.update_preview()
        return c

    def _add_clip(self, clip):
        clip.start = self.timeline.playhead
        self._push_undo()
        self.project.tracks[self.cur_track].add(clip)
        self.timeline.selected = clip; self._on_select_clip(clip)
        self.refresh_timeline(); self.update_preview()

    def add_scene(self):
        sc = DrawnSceneClip(AnimationModel(self.project.width, self.project.height, 12))
        if DrawingStudio(sc.model, self).exec_() == QDialog.Accepted:
            self._add_clip(sc)

    def add_text(self):
        c = TextClip(box_w=self.project.width, box_h=self.project.height)
        if TextEditDialog(c, self).exec_() == QDialog.Accepted:
            self._add_clip(c)

    def add_credits(self):
        c = EndCreditsClip(box_w=self.project.width, box_h=self.project.height,
                           copyright="2026 Dravenlock", author="", song="")
        if EndCreditsDialog(c, self).exec_() == QDialog.Accepted:
            self._add_clip(c)

    def add_figure(self):
        c = StickFigureClip(fps=12)
        if PoseStudio(c, self).exec_() == QDialog.Accepted:
            self._add_clip(c)

    def add_studio(self):
        m = AnimationModel(self.project.width, self.project.height, 12)
        c = StudioClip(model=m)
        if StudioEditor(c, self).exec_() == QDialog.Accepted:
            self._add_clip(c)

    def add_rig(self):
        c = RigClip(width=self.project.width, height=self.project.height, fps=12)
        if RigStudio(c, self).exec_() == QDialog.Accepted:
            self._add_clip(c)

    def open_tts(self):
        if getattr(sys, "frozen", False):
            QMessageBox.information(
                self, "Stem (TTS)",
                "Tekst-naar-spraak werkt in de .exe-versie nog niet: de stem-engine NeuVoice "
                "draait via een losse Python en wordt niet meegebouwd. Gebruik hiervoor de "
                "gewone versie via run.bat — of laat het weten, dan maak ik er een "
                ".exe-vriendelijke stemoplossing voor.")
            return
        if not HAVE_TTS:
            QMessageBox.information(
                self, "Stem (TTS)",
                "Voor tekst-naar-spraak is NeuVoice nodig. Sluit de app en voer in de app-map uit:\n\n"
                "    py -m pip install neuvoice\n\n"
                "(of draai herstel.bat). Daarna kun je dit scherm gebruiken. Het stemmodel wordt "
                "de eerste keer automatisch gedownload.")
            return
        TtsStudio(self, self).exec_()

    def add_track(self):
        self._push_undo()
        self.project.tracks.append(Track(f"Spoor {len(self.project.tracks) + 1}"))
        self._refresh_track_combo(); self.timeline.set_project(self.project)

    # ---- selectie + clip-paneel ------------------------------------------ #
    def _refresh_track_combo(self):
        self.track_combo.blockSignals(True); self.track_combo.clear()
        self.track_combo.addItems([t.name for t in self.project.tracks])
        self.track_combo.setCurrentIndex(min(self.cur_track, len(self.project.tracks) - 1))
        self.track_combo.blockSignals(False)

    def _set_track(self, i): self.cur_track = i
    def _set_fps(self, v): self.project.fps = v; self._update_time_label()

    def _on_select_clip(self, clip):
        self._update_clip_panel(clip)

    def _clip_local(self):
        c = self._sel
        if not c:
            return 0.0
        return max(0.0, min(self.timeline.playhead - c.start, c.duration()))

    def _update_clip_panel(self, clip):
        self._sel = clip
        has = clip is not None
        is_audio = isinstance(clip, AudioClip)
        is_visual = has and not is_audio
        for w in (self.start_spin, self.dur_spin, self.dup_clip_btn, self.del_clip_btn):
            w.setEnabled(has)
        self.edit_scene_btn.setVisible(isinstance(clip, DrawnSceneClip))
        self.edit_text_btn.setVisible(isinstance(clip, TextClip))
        self.edit_credits_btn.setVisible(isinstance(clip, EndCreditsClip))
        self.edit_figure_btn.setVisible(isinstance(clip, StickFigureClip))
        self.edit_studio_btn.setVisible(isinstance(clip, StudioClip))
        self.edit_rig_btn.setVisible(isinstance(clip, RigClip))
        can_talk = isinstance(clip, (RigClip, ImageClip))
        self.talk_chk.setVisible(can_talk)
        self.place_mouth_btn.setVisible(isinstance(clip, ImageClip)
                                        and bool(getattr(clip, "talk", False)))
        if can_talk:
            self.talk_chk.blockSignals(True)
            self.talk_chk.setChecked(bool(getattr(clip, "talk", False)))
            self.talk_chk.blockSignals(False)
        # effecten + filter alleen bij beeld; fade bij alles; volume bij audio; snelheid bij video
        self.fx_section.setVisible(is_visual)
        for n in self.fx_spins:
            self.fx_spins[n].setVisible(is_visual); self.fx_labels[n].setVisible(is_visual)
        self.fade_section.setVisible(has)
        is_video = isinstance(clip, VideoClip)
        self.speed_lbl.setVisible(is_video); self.speed_spin.setVisible(is_video)
        for w in (self.fade_in_lbl, self.fade_in_spin, self.fade_out_lbl, self.fade_out_spin):
            w.setVisible(has)
        for w in (self.trans_in_lbl, self.trans_in_combo, self.trans_out_lbl,
                  self.trans_out_combo, self.filter_lbl, self.filter_combo):
            w.setVisible(is_visual)
        self.vol_lbl.setVisible(is_audio or is_video)
        self.vol_spin.setVisible(is_audio or is_video)
        if not has:
            self.clip_name.setText(t("— geen clip —"))
            self._refresh_transform_ui()
            return
        self.clip_name.setText(f"{clip.name}  ({clip.KIND})")
        for s in (self.start_spin, self.dur_spin):
            s.blockSignals(True)
        self.start_spin.setValue(clip.start)
        self.dur_spin.setValue(clip.duration())
        self.dur_spin.setEnabled(
            not isinstance(clip, (DrawnSceneClip, StickFigureClip, StudioClip, RigClip))
            or (isinstance(clip, RigClip) and bool(getattr(clip, "talk", False))))
        for s in (self.start_spin, self.dur_spin):
            s.blockSignals(False)
        self._refresh_transform_ui()
        self._refresh_fx_fade_ui()

    def _refresh_fx_fade_ui(self):
        c = self._sel
        if c is None:
            return
        self._loading_ui = True
        for n, spin in self.fx_spins.items():
            spin.blockSignals(True)
            spin.setValue(c.effects.get(n, 0.0))
            spin.blockSignals(False)
        for spin, val in ((self.fade_in_spin, c.fade_in), (self.fade_out_spin, c.fade_out)):
            spin.blockSignals(True); spin.setValue(val); spin.blockSignals(False)
        self.trans_in_combo.blockSignals(True)
        self.trans_in_combo.setCurrentIndex(_trans_index(c.trans_in))
        self.trans_in_combo.blockSignals(False)
        self.trans_out_combo.blockSignals(True)
        self.trans_out_combo.setCurrentIndex(_trans_index(c.trans_out))
        self.trans_out_combo.blockSignals(False)
        self.filter_combo.blockSignals(True)
        self.filter_combo.setCurrentIndex(_filter_index(getattr(c, "filter", "none")))
        self.filter_combo.blockSignals(False)
        if isinstance(c, VideoClip):
            self.speed_spin.blockSignals(True); self.speed_spin.setValue(c.speed)
            self.speed_spin.blockSignals(False)
        if isinstance(c, (AudioClip, VideoClip)):
            self.vol_spin.blockSignals(True); self.vol_spin.setValue(getattr(c, "volume", 100.0))
            self.vol_spin.blockSignals(False)
        self._loading_ui = False

    def _set_effect(self, name, value):
        c = self._sel
        if not c or self._loading_ui:
            return
        c.effects[name] = float(value)
        self.update_preview()

    def _set_fade(self, attr, value):
        c = self._sel
        if not c or self._loading_ui:
            return
        setattr(c, attr, float(value))
        self.refresh_timeline(); self.update_preview()

    def _set_trans(self, which, key):
        c = self._sel
        if not c or self._loading_ui:
            return
        if which == "in":
            c.trans_in = key
        else:
            c.trans_out = key
        self.update_preview()

    def _set_filter(self, key):
        c = self._sel
        if not c or self._loading_ui:
            return
        c.filter = key
        self.update_preview()

    def _set_speed(self, value):
        c = self._sel
        if not c or self._loading_ui or not isinstance(c, VideoClip):
            return
        c.speed = max(0.1, float(value))
        self.dur_spin.blockSignals(True); self.dur_spin.setValue(c.duration())
        self.dur_spin.blockSignals(False)
        self.refresh_timeline(); self.update_preview()

    def _set_volume(self, value):
        c = self._sel
        if not c or self._loading_ui:
            return
        if isinstance(c, (AudioClip, VideoClip)):
            c.volume = float(value)

    def _toggle_talk(self, on):
        c = self._sel
        if not isinstance(c, (RigClip, ImageClip)) or self._loading_ui:
            return
        c.talk = bool(on)
        if on and isinstance(c, RigClip):
            if not c.ensure_default_mouth():
                QMessageBox.information(
                    self, "Praat mee met de stem",
                    "Dit poppetje heeft geen ‘head’-gewricht, dus ik kon niet automatisch een mond "
                    "plaatsen. Teken zelf een mond via ‘Bewerk poppetje (skelet)’ → tabblad ‘Mond / lip-sync’.")
            if c.talk_dur is None:
                vlen = max((t.end() for t in self.project.tracks if t.kind == "voice"), default=0.0)
                c.talk_dur = vlen if vlen > 0.1 else 3.0
        if on:
            if not any(t.kind == "voice" for t in self.project.tracks):
                self._ensure_voice_track()
                self.statusBar().showMessage(
                    "Stem-spoor toegevoegd. Zet hier een stem op (knop in de Stem-studio) zodat de "
                    "mond meebeweegt.", 8000)
        self._update_clip_panel(c)
        if on and isinstance(c, ImageClip):
            self._place_mouth()   # meteen de mond laten plaatsen
        self.refresh_timeline(); self.update_preview()

    def _place_mouth(self):
        c = self._sel
        if not isinstance(c, ImageClip):
            return
        if c._img.isNull():
            QMessageBox.information(self, "Mond plaatsen",
                                    "Deze afbeelding kon niet worden gelezen, dus ik kan er geen "
                                    "mond op plaatsen.")
            return
        if MouthPlaceDialog(c, self).exec_() == QDialog.Accepted:
            self.refresh_timeline(); self.update_preview()

    def _refresh_transform_ui(self):
        c = self._sel
        self._loading_ui = True
        show = c is not None
        tl = self._clip_local()
        for name, spin in self.tf_spins.items():
            spin.setEnabled(show); self.tf_kf[name].setEnabled(show)
            if show:
                k = getattr(c.transform, name)
                spin.blockSignals(True)
                spin.setValue(k.value_at(tl))
                spin.blockSignals(False)
                here = k.key_at(tl) is not None
                self.tf_kf[name].setText("◆" if here else ("◇" if k.is_animated() else "○"))
            else:
                self.tf_kf[name].setText("○")
        self._loading_ui = False

    def _set_prop(self, name, value):
        c = self._sel
        if not c or self._loading_ui:
            return
        k = getattr(c.transform, name)
        if k.is_animated():
            k.set_key(self._clip_local(), value)
        else:
            k.default = float(value)
        self.refresh_timeline(); self.update_preview()

    def _kf_toggle(self, name):
        c = self._sel
        if not c:
            return
        k = getattr(c.transform, name)
        tl = self._clip_local()
        self._push_undo()
        if k.key_at(tl) is not None:
            k.remove_key(tl)
        else:
            k.set_key(tl, k.value_at(tl))
        self._refresh_transform_ui(); self.refresh_timeline(); self.update_preview()

    def _edit_start(self, v):
        if self._sel:
            self._sel.start = v
            for t in self.project.tracks:
                t.clips.sort(key=lambda c: c.start)
            self.refresh_timeline(); self.update_preview()

    def _edit_dur(self, v):
        c = self._sel
        if isinstance(c, (ImageClip, TextClip, EndCreditsClip)):
            c.set_duration(v)
        elif isinstance(c, VideoClip):
            c.out_point = c.in_point + max(0.1, v) * c.speed
        elif isinstance(c, AudioClip):
            c.out_point = c.in_point + max(0.1, v)
        elif isinstance(c, RigClip) and getattr(c, "talk", False):
            c.talk_dur = max(0.1, v)
        self.refresh_timeline(); self.update_preview()

    def edit_scene(self):
        if isinstance(self._sel, DrawnSceneClip):
            snap = json.dumps(self.project.to_dict())
            DrawingStudio(self._sel.model, self).exec_()
            self._commit_undo(snap)      # tekenen is undo-baar
            self.refresh_timeline(); self.update_preview()

    def edit_text(self):
        if isinstance(self._sel, TextClip):
            snap = json.dumps(self.project.to_dict())
            if TextEditDialog(self._sel, self).exec_() == QDialog.Accepted:
                self._commit_undo(snap)  # tekstwijziging is undo-baar
                self._update_clip_panel(self._sel)
                self.refresh_timeline(); self.update_preview()

    def edit_credits(self):
        if isinstance(self._sel, EndCreditsClip):
            snap = json.dumps(self.project.to_dict())
            if EndCreditsDialog(self._sel, self).exec_() == QDialog.Accepted:
                self._commit_undo(snap)
                self._update_clip_panel(self._sel)
                self.refresh_timeline(); self.update_preview()

    def edit_figure(self):
        if isinstance(self._sel, StickFigureClip):
            snap = json.dumps(self.project.to_dict())
            if PoseStudio(self._sel, self).exec_() == QDialog.Accepted:
                self._commit_undo(snap)
                self._update_clip_panel(self._sel)
                self.refresh_timeline(); self.update_preview()

    def edit_studio(self):
        if isinstance(self._sel, StudioClip):
            snap = json.dumps(self.project.to_dict())
            if StudioEditor(self._sel, self).exec_() == QDialog.Accepted:
                self._commit_undo(snap)
                self._update_clip_panel(self._sel)
                self.refresh_timeline(); self.update_preview()

    def edit_rig(self):
        if isinstance(self._sel, RigClip):
            snap = json.dumps(self.project.to_dict())
            if RigStudio(self._sel, self).exec_() == QDialog.Accepted:
                self._commit_undo(snap)
                self._update_clip_panel(self._sel)
                self.refresh_timeline(); self.update_preview()

    def _edit_clip(self, clip):
        """Open de juiste editor voor een clip (dubbelklik in de tijdlijn)."""
        self._sel = clip
        if isinstance(clip, TextClip):
            self.edit_text()
        elif isinstance(clip, EndCreditsClip):
            self.edit_credits()
        elif isinstance(clip, StudioClip):
            self.edit_studio()
        elif isinstance(clip, RigClip):
            self.edit_rig()
        elif isinstance(clip, StickFigureClip):
            self.edit_figure()
        elif isinstance(clip, DrawnSceneClip):
            self.edit_scene()

    def duplicate_clip(self):
        c = self._sel
        if not c:
            return
        ti = next((i for i, t in enumerate(self.project.tracks) if c in t.clips), self.cur_track)
        d = c.to_dict()
        nc = CLIP_TYPES[c.KIND].from_dict(d)
        nc.transform = Transform.from_dict(d.get("transform", {}))
        nc.fade_in = float(d.get("fade_in", 0.0))
        nc.fade_out = float(d.get("fade_out", 0.0))
        nc.trans_in = d.get("trans_in", "fade")
        nc.trans_out = d.get("trans_out", "fade")
        nc.effects = {**DEFAULT_EFFECTS, **d.get("effects", {})}
        nc.filter = d.get("filter", "none")
        nc.start = c.start + c.duration()
        self._push_undo()
        self.project.tracks[ti].add(nc)
        self.timeline.selected = nc; self._on_select_clip(nc)
        self.refresh_timeline(); self.update_preview()

    def delete_clip(self):
        if self._sel:
            self._push_undo()
            for t in self.project.tracks:
                t.remove(self._sel)
            self._update_clip_panel(None); self.refresh_timeline(); self.update_preview()

    def _split_at(self, ti, t):
        """Knip de clip op spoor ti die op tijd t ligt in tweeën (rechtsklik)."""
        if not (0 <= ti < len(self.project.tracks)):
            return
        track = self.project.tracks[ti]
        clip = next((c for c in track.clips
                     if c.start < t < c.start + c.duration()), None)
        if clip is None:
            self.statusBar().showMessage("Knippen: geen clip onder de grijze lijn.")
            return
        # niet te dicht op een rand knippen
        if t - clip.start < 0.05 or (clip.start + clip.duration()) - t < 0.05:
            return
        self._push_undo()
        left, right = split_clip(clip, t)
        track.remove(clip)
        track.add(left); track.add(right)
        self.timeline.selected = right
        self._on_select_clip(right)
        self.refresh_timeline(); self.update_preview()
        self.statusBar().showMessage("Clip geknipt.")

    # ---- undo / redo ----------------------------------------------------- #
    def _update_undo_buttons(self):
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(bool(self._undo_stack))
            self.redo_btn.setEnabled(bool(self._redo_stack))

    def _commit_undo(self, snap):
        """Leg een gegeven momentopname op de undo-stapel (en wis redo)."""
        self._redo_stack.clear()
        self._undo_stack.append(snap)
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)
        self._update_undo_buttons()

    def _push_undo(self):
        try:
            self._commit_undo(json.dumps(self.project.to_dict()))
        except Exception:  # noqa: BLE001
            pass

    def _restore(self, snap):
        self.project = Project.from_dict(json.loads(snap))
        self.cur_track = min(self.cur_track, len(self.project.tracks) - 1)
        self.timeline.set_project(self.project)
        self.timeline.on_drag_start = self._push_undo
        self.timeline.on_drop_asset = self._on_drop_asset
        self.timeline.on_split = self._split_at
        self.timeline.on_edit = self._edit_clip
        self._refresh_track_combo()
        self.fps_spin.blockSignals(True); self.fps_spin.setValue(self.project.fps); self.fps_spin.blockSignals(False)
        self._update_clip_panel(None); self.refresh_timeline(); self.update_preview()

    def undo(self):
        if not self._undo_stack:
            self.statusBar().showMessage("Niets om ongedaan te maken."); return
        self._redo_stack.append(json.dumps(self.project.to_dict()))
        self._restore(self._undo_stack.pop())
        self._update_undo_buttons()
        self.statusBar().showMessage("Ongedaan gemaakt.")

    def redo(self):
        if not self._redo_stack:
            self.statusBar().showMessage("Niets om opnieuw te doen."); return
        self._undo_stack.append(json.dumps(self.project.to_dict()))
        self._restore(self._redo_stack.pop())
        self._update_undo_buttons()
        self.statusBar().showMessage("Opnieuw gedaan.")

    # ---- preview / afspelen ---------------------------------------------- #
    def _on_playhead(self, t):
        self.update_preview()
        self._refresh_transform_ui()
        if self.playing:
            self._sync_audio_position()

    def _audio_signature(self):
        sig = []
        for tr in self.project.tracks:
            for c in tr.clips:
                if isinstance(c, AudioClip):
                    sig.append((c.path, round(c.start, 3),
                                round(c.in_point, 3), round(c.out_point, 3),
                                round(c.volume, 1), round(c.fade_in, 3),
                                round(c.fade_out, 3)))
                elif isinstance(c, VideoClip) and video_has_audio(c.path):
                    sig.append((c.path, round(c.start, 3),
                                round(c.in_point, 3), round(c.out_point, 3),
                                round(getattr(c, "volume", 100.0), 1),
                                round(c.fade_in, 3), round(c.fade_out, 3),
                                round(getattr(c, "speed", 1.0), 3)))
        return tuple(sig)

    def _ensure_preview_audio(self):
        if not (self.audio_player and HAVE_FFMPEG):
            return None
        clips = collect_audio_clips(self.project)
        if not clips:
            self.audio_player.stop()
            self.audio_player.setMedia(QMediaContent())
            self._audio_sig, self._audio_file = None, None
            return None
        sig = self._audio_signature()
        if sig != self._audio_sig or not (self._audio_file and os.path.exists(self._audio_file)):
            self.audio_player.stop()
            old = self._audio_file
            self._audio_counter += 1
            out = os.path.join(CACHE_DIR, f"_preview_audio_{self._audio_counter}.wav")
            mix = build_audio_mixdown(clips, out, self.project.duration(), acodec="pcm_s16le")
            if not mix:
                self._audio_sig, self._audio_file = None, None
                return None
            self._audio_sig, self._audio_file = sig, mix
            # nieuw uniek bestand laden; afspelen gebeurt pas als het GELADEN is
            self.audio_player.setMedia(QMediaContent(QUrl.fromLocalFile(mix)))
            if old and os.path.exists(old):
                try:
                    os.remove(old)
                except OSError:
                    pass
        return self._audio_file

    def _start_preview_audio(self):
        """Start de preview-audio zodra het medium geladen is (vermijdt race)."""
        if not self.audio_player:
            return
        self._audio_play_pending = True
        st = self.audio_player.mediaStatus()
        if st in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia,
                  QMediaPlayer.BufferingMedia):
            self._do_audio_play()

    def _do_audio_play(self):
        if not self.audio_player:
            return
        self._audio_play_pending = False
        self.audio_player.setPosition(int(self.timeline.playhead * 1000))
        self.audio_player.play()

    def _on_audio_status(self, status):
        if (self._audio_play_pending and self.playing and
                status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)):
            self._do_audio_play()

    def _sync_audio_position(self):
        if self.audio_player and self._audio_file:
            self.audio_player.setPosition(int(self.timeline.playhead * 1000))

    def _update_time_label(self):
        self.time_label.setText(f"{self.timeline.playhead:.2f}s / {self.project.duration():.2f}s")

    # ---- voorbeeld: selectie-geometrie, slepen, schalen, dubbelklik ------ #
    def _selected_visual(self):
        """De geselecteerde clip als hij zichtbaar is op de huidige tijd, anders None."""
        c = self._sel
        if c is None or isinstance(c, AudioClip):
            return None
        ph = self.timeline.playhead
        if not (c.start <= ph < c.start + c.duration()):
            return None
        return c

    def _sel_geometry(self):
        """Rechthoek (in voorbeeld-widgetcoördinaten) en midden van de selectie."""
        c = self._selected_visual()
        pm = self.preview.pixmap()
        if c is None or pm is None or pm.width() == 0:
            return None
        tl = self._clip_local()
        src = c.image_at(tl)
        if src is None or src.isNull():
            return None
        W, H = self.project.width, self.project.height
        sw, sh = src.width(), src.height()
        if sw == 0 or sh == 0:
            return None
        base = min(W / sw, H / sh)
        sc = max(0.0, c.transform.scale.value_at(tl) / 100.0)
        scl = base * sc                                  # project-px per beeld-px
        # strakke inhoud: bij tekst de tekst-rechthoek, anders het hele beeld
        if isinstance(c, TextClip):
            cr = c.content_rect()
        else:
            cr = QRectF(0, 0, sw, sh)
        # clip-midden in projectcoördinaten
        clip_cx = W / 2.0 + c.transform.x.value_at(tl)
        clip_cy = H / 2.0 + c.transform.y.value_at(tl)
        # inhoud-midden t.o.v. beeldmidden -> projectcoördinaten
        pcx = clip_cx + (cr.center().x() - sw / 2.0) * scl
        pcy = clip_cy + (cr.center().y() - sh / 2.0) * scl
        tw, th = cr.width() * scl, cr.height() * scl
        disp = pm.width() / float(W)                     # widget-px per project-px
        offx = (self.preview.width() - pm.width()) / 2.0
        offy = (self.preview.height() - pm.height()) / 2.0
        cxw = offx + pcx * disp
        cyw = offy + pcy * disp
        hw, hh = (tw / 2.0) * disp, (th / 2.0) * disp
        return {"cx": cxw, "cy": cyw, "hw": hw, "hh": hh, "disp": disp,
                "rect": QRectF(cxw - hw, cyw - hh, 2 * hw, 2 * hh)}

    def _handle_at(self, x, y, geo, r=12):
        """Welke hoekgreep ligt onder (x,y)? -> (sx,sy) richtingsteken of None."""
        corners = {(-1, -1): (geo["cx"] - geo["hw"], geo["cy"] - geo["hh"]),
                   (1, -1): (geo["cx"] + geo["hw"], geo["cy"] - geo["hh"]),
                   (-1, 1): (geo["cx"] - geo["hw"], geo["cy"] + geo["hh"]),
                   (1, 1): (geo["cx"] + geo["hw"], geo["cy"] + geo["hh"])}
        for sign, (hx, hy) in corners.items():
            if abs(x - hx) <= r and abs(y - hy) <= r:
                return sign
        return None

    def _preview_hover(self, x, y):
        geo = self._sel_geometry()
        if geo is None:
            return Qt.ArrowCursor
        if self._handle_at(x, y, geo) is not None:
            return Qt.SizeFDiagCursor
        if geo["rect"].contains(x, y):
            return Qt.OpenHandCursor
        return Qt.ArrowCursor

    def _preview_double(self, x, y):
        c = self._sel
        if isinstance(c, TextClip):
            self.edit_text()
        elif isinstance(c, EndCreditsClip):
            self.edit_credits()
        elif isinstance(c, StudioClip):
            self.edit_studio()
        elif isinstance(c, RigClip):
            self.edit_rig()
        elif isinstance(c, StickFigureClip):
            self.edit_figure()
        elif isinstance(c, DrawnSceneClip):
            self.edit_scene()

    def _preview_drag(self, x, y, dx, dy, phase):
        c = self._selected_visual()
        if c is None:
            return
        if phase == "start":
            geo = self._sel_geometry()
            self._drag_mode = None
            if geo is not None and self._handle_at(x, y, geo) is not None:
                # schalen: onthoud begin-afstand tot het midden + begin-schaal
                d0 = max(6.0, math.hypot(x - geo["cx"], y - geo["cy"]))
                self._scale_ref = (d0, c.transform.scale.value_at(self._clip_local()))
                self._drag_mode = "scale"
                self.preview.setCursor(Qt.SizeFDiagCursor)
            elif geo is not None and geo["rect"].contains(x, y):
                self._drag_mode = "move"
                self.preview.setCursor(Qt.ClosedHandCursor)
            else:
                self._drag_mode = "move"   # buiten de rand: toch verplaatsen
                self.preview.setCursor(Qt.ClosedHandCursor)
            self._push_undo()
            return
        if phase == "end":
            self._drag_mode = None
            self.preview.setCursor(Qt.OpenHandCursor)
            return
        pm = self.preview.pixmap()
        if pm is None or pm.width() == 0:
            return
        tl = self._clip_local()
        if getattr(self, "_drag_mode", None) == "scale":
            geo = self._sel_geometry()
            if geo is None:
                return
            d0, s0 = self._scale_ref
            d1 = math.hypot(x - geo["cx"], y - geo["cy"])
            new = max(1.0, min(2000.0, s0 * (d1 / d0)))
            k = c.transform.scale
            if k.is_animated():
                k.set_key(tl, new)
            else:
                k.default = new
        else:
            scale = self.project.width / pm.width()
            for k, delta in ((c.transform.x, dx * scale), (c.transform.y, dy * scale)):
                if k.is_animated():
                    k.set_key(tl, k.value_at(tl) + delta)
                else:
                    k.default = k.default + delta
        self._refresh_transform_ui()
        self.update_preview()

    def _logo_pixmap(self, h):
        for name in ("logo.png", "logo.ico"):
            p = os.path.join(APP_DIR, name)
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    return pm.scaledToHeight(h, Qt.SmoothTransformation)
        ic = app_icon()
        return ic.pixmap(h, h) if ic is not None else None

    def _build_intro_overlay(self):
        self.intro = QWidget(self.preview)
        self.intro.setObjectName("introOverlay")
        self.intro.setStyleSheet(
            "#introOverlay { background-color:transparent; }"
            "#introOverlay QLabel { background-color:transparent; border:none; }")
        v = QVBoxLayout(self.intro); v.setAlignment(Qt.AlignCenter); v.setSpacing(14)
        logo = QLabel(); logo.setAlignment(Qt.AlignCenter)
        pm = self._logo_pixmap(170)
        if pm is not None:
            logo.setPixmap(pm)
        else:
            logo.setText("🎬"); logo.setStyleSheet("font-size:96px; background-color:transparent;")
        v.addWidget(logo)
        title_lbl = QLabel(APP_NAME); title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("color:#f2f2f2; font-size:46px; font-weight:bold;")
        v.addWidget(title_lbl)
        sub = QLabel(f"v{APP_VERSION}  ·  een {AUTHOR_NAME} product"); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#9aa0a8; font-size:18px;")
        v.addWidget(sub)
        tag = QLabel(t("2D-animatieprogramma én videobewerker in één")); tag.setAlignment(Qt.AlignCenter)
        tag.setStyleSheet("color:#7fb4ff; font-size:22px; font-weight:bold;")
        v.addSpacing(4); v.addWidget(tag)
        hint = QLabel(t("Nieuw hier? Lees even de Snelgids voor een vliegende start —\n"
                        "of begin meteen met een tekenscène of het importeren van media."))
        hint.setAlignment(Qt.AlignCenter); hint.setWordWrap(True)
        hint.setStyleSheet("color:#c8ccd4; font-size:20px;")
        v.addSpacing(8); v.addWidget(hint); v.addSpacing(10)
        row = QHBoxLayout(); row.setAlignment(Qt.AlignCenter); row.setSpacing(12)
        g = QPushButton(t("📖 Open de Snelgids")); g.setObjectName("cta"); g.setMinimumHeight(48)
        g.setMinimumWidth(210); g.clicked.connect(self.open_guide); row.addWidget(g)
        sc = QPushButton(t("✎ Nieuwe tekenscène")); sc.setMinimumHeight(48); sc.setMinimumWidth(210)
        sc.clicked.connect(self.add_scene); row.addWidget(sc)
        v.addLayout(row)
        self.intro.hide()

    def _place_intro(self):
        if hasattr(self, "intro"):
            self.intro.setGeometry(0, 0, self.preview.width(), self.preview.height())

    def _project_is_empty(self):
        return not any(getattr(t, "clips", None) for t in self.project.tracks)

    def _update_intro(self):
        if not hasattr(self, "intro"):
            return
        show = self._project_is_empty() and not self.playing
        if show:
            self._place_intro()
        self.intro.setVisible(show)
        self.intro.raise_()

    def update_preview(self):
        img = self.project.render_frame(self.timeline.playhead)
        pm = QPixmap.fromImage(img).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pm)
        self._draw_selection_overlay()
        self._update_time_label()
        self._update_intro()

    def _draw_selection_overlay(self):
        geo = self._sel_geometry()
        if geo is None:
            return
        pm = self.preview.pixmap()
        if pm is None:
            return
        # teken op een kopie van de pixmap; reken widget->pixmap (haal offset eraf)
        offx = (self.preview.width() - pm.width()) / 2.0
        offy = (self.preview.height() - pm.height()) / 2.0
        rx = geo["cx"] - geo["hw"] - offx
        ry = geo["cy"] - geo["hh"] - offy
        rw, rh = 2 * geo["hw"], 2 * geo["hh"]
        canvas = QPixmap(pm)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#cfd2d6"), 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(rx, ry, rw, rh))
        # hoekgrepen (gevulde vierkantjes, hoog contrast)
        p.setPen(QPen(QColor("#0b0b0d"), 1))
        p.setBrush(QColor("#7fd4ff"))
        for hx, hy in ((rx, ry), (rx + rw, ry), (rx, ry + rh), (rx + rw, ry + rh)):
            p.drawRect(QRectF(hx - 6, hy - 6, 12, 12))
        p.end()
        self.preview.setPixmap(canvas)

    def refresh_timeline(self):
        self.timeline._update_size()
        self.timeline.update()
        self._update_intro()

    def stop_playback(self):
        """Stop het afspelen en zet de rode afspeelkop terug naar het begin."""
        self.play_timer.stop()
        self.playing = False
        self.play_btn.setText(t("▶ Afspelen"))
        self._audio_play_pending = False
        if self.audio_player:
            self.audio_player.stop()
            if self._audio_file:
                self.audio_player.setPosition(0)
        self.timeline.playhead = 0.0
        self.timeline.cut_marker = None
        self.timeline.update()
        self.update_preview()
        self._refresh_transform_ui()
        self._update_time_label()

    def toggle_play(self):
        if self.playing:
            self.play_timer.stop(); self.playing = False; self.play_btn.setText(t("▶ Afspelen"))
            self._audio_play_pending = False
            if self.audio_player:
                self.audio_player.pause()
        else:
            if self.project.duration() <= 0:
                self.statusBar().showMessage("Niets om af te spelen — voeg eerst clips toe."); return
            self.playing = True; self.play_btn.setText(t("⏸ Pauze"))
            self.timeline.cut_marker = None
            if self._ensure_preview_audio():
                self._start_preview_audio()
            self.play_timer.start(int(1000 / self.project.fps))

    def _play_tick(self):
        t = self.timeline.playhead + 1.0 / self.project.fps
        if t >= self.project.duration():
            t = 0.0
            self.timeline.playhead = t
            if self.audio_player and self._audio_file:
                self._do_audio_play()      # audio opnieuw vanaf het begin
        else:
            self.timeline.playhead = t
        self.timeline.update(); self.update_preview()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "preview"):
            self.update_preview()

    # ---- project --------------------------------------------------------- #
    def new_project(self):
        self.project = Project(); self.cur_track = 0
        self._undo_stack.clear(); self._redo_stack.clear()
        self._update_undo_buttons()
        self.timeline.set_project(self.project)
        self.timeline.on_drag_start = self._push_undo
        self.timeline.on_drop_asset = self._on_drop_asset
        self.timeline.on_split = self._split_at
        self.timeline.on_edit = self._edit_clip
        self._refresh_track_combo()
        self.fps_spin.setValue(self.project.fps)
        self._update_clip_panel(None); self.refresh_timeline(); self.update_preview()

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Project opslaan",
                                              os.path.join(PROJECTS_DIR, "project.draveanim"),
                                              "DraveMotion (*.draveanim)")
        if not path:
            return
        total = sum(len(t.clips) for t in self.project.tracks)
        dlg = QProgressDialog("Project opslaan…", None, 0, max(1, total) + 1, self)
        dlg.setWindowTitle("Opslaan"); dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0); dlg.setValue(0); QApplication.processEvents()
        data = {"app": "DraveMotion", "version": APP_VERSION,
                "width": self.project.width, "height": self.project.height,
                "fps": self.project.fps, "background": self.project.background.name(),
                "tracks": []}
        done = 0
        for tr in self.project.tracks:
            td = {"name": tr.name, "kind": tr.kind, "clips": []}
            for c in tr.clips:
                td["clips"].append(c.to_dict())  # scenes coderen hier hun frames
                done += 1; dlg.setValue(done); QApplication.processEvents()
            data["tracks"].append(td)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            dlg.setValue(total + 1)
            self.statusBar().showMessage(f"Opgeslagen: {path}")
        except OSError as e:
            dlg.close()
            QMessageBox.critical(self, "Opslaan mislukt", str(e))

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Project openen", PROJECTS_DIR,
                                              "DraveMotion (*.draveanim);;Alle (*)")
        if not path:
            return
        with open(path, encoding="utf-8") as fh:
            self.project = Project.from_dict(json.load(fh))
        self.cur_track = 0
        self._undo_stack.clear(); self._redo_stack.clear()
        self._update_undo_buttons()
        self.timeline.set_project(self.project)
        self.timeline.on_drag_start = self._push_undo
        self.timeline.on_drop_asset = self._on_drop_asset
        self.timeline.on_split = self._split_at
        self.timeline.on_edit = self._edit_clip
        self._refresh_track_combo()
        self.fps_spin.setValue(self.project.fps)
        self._update_clip_panel(None); self.refresh_timeline(); self.update_preview()
        self.statusBar().showMessage(f"Geopend: {path}")

    def open_settings(self):
        dlg = ProjectSettingsDialog(self.project, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        w, h, fps, bg = dlg.values()
        self._push_undo()
        self.project.width, self.project.height = w, h
        self.project.fps = fps
        self.project.background = QColor(bg)
        for tr in self.project.tracks:
            for c in tr.clips:
                if isinstance(c, TextClip):
                    c.box_w, c.box_h, c._cache = w, h, None
                    if c.text_width > w or c.text_width <= 0:
                        c.text_width = w
        self.fps_spin.blockSignals(True); self.fps_spin.setValue(fps); self.fps_spin.blockSignals(False)
        self.refresh_timeline(); self.update_preview()
        self.statusBar().showMessage(f"Project: {w}×{h} @ {fps} fps")
        new_lang = dlg.get_language()
        cfg = load_config()
        if new_lang != cfg.get("language", "auto"):
            cfg["language"] = new_lang
            save_config(cfg)
            QMessageBox.information(self, t("Taal"),
                                   t("De taal verandert nadat je DraveMotion opnieuw start."))

    def export_dialog(self):
        if self.project.duration() <= 0:
            QMessageBox.information(self, "Export", "Voeg eerst clips toe."); return
        box = QMessageBox(self); box.setWindowTitle(t("Exporteren")); box.setText(t("Kies een exportformaat:"))
        mp4 = box.addButton("MP4", QMessageBox.AcceptRole)
        gif = box.addButton("GIF", QMessageBox.AcceptRole)
        png = box.addButton(t("PNG-reeks"), QMessageBox.AcceptRole)
        box.addButton(t("Annuleer"), QMessageBox.RejectRole)
        if not HAVE_FFMPEG:
            mp4.setEnabled(False)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is None or clicked not in (mp4, gif, png):
            return

        # naam opvragen (voor het bestand of de PNG-reeks)
        name, ok = QInputDialog.getText(self, "Exporteren", "Naam van het bestand:",
                                        text="film")
        if not ok:
            return
        name = "".join(ch for ch in name if ch.isalnum() or ch in " -_").strip() or "film"

        prog = QProgressDialog("Exporteren…", None, 0, 100, self)
        prog.setWindowTitle("Exporteren"); prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)

        def step(label):
            def cb(i, n):
                prog.setLabelText(label)
                prog.setMaximum(n); prog.setValue(i)
                QApplication.processEvents()
            return cb

        try:
            if clicked is mp4:
                p, _ = QFileDialog.getSaveFileName(self, "MP4 opslaan",
                                                   os.path.join(PROJECTS_DIR, name + ".mp4"), "MP4 (*.mp4)")
                if p:
                    prog.setValue(0); QApplication.processEvents()
                    export_video(self.project, p, progress=step("MP4 renderen…"))
                    prog.close()
                    self.statusBar().showMessage(f"MP4 klaar: {p}")
            elif clicked is gif:
                p, _ = QFileDialog.getSaveFileName(self, "GIF opslaan",
                                                   os.path.join(PROJECTS_DIR, name + ".gif"), "GIF (*.gif)")
                if p:
                    prog.setValue(0); QApplication.processEvents()
                    export_gif(self.project, p, progress=step("GIF renderen…"))
                    prog.close()
                    self.statusBar().showMessage(f"GIF klaar: {p}")
            elif clicked is png:
                folder = QFileDialog.getExistingDirectory(self, "Map voor PNG-reeks", PROJECTS_DIR)
                if folder:
                    prog.setValue(0); QApplication.processEvents()
                    n = export_png_sequence(self.project, folder,
                                            progress=step("PNG-reeks renderen…"), prefix=name)
                    prog.close()
                    self.statusBar().showMessage(f"{n} PNG's ({name}_0001.png …) opgeslagen in {folder}")
        except Exception as e:  # noqa: BLE001
            prog.close()
            QMessageBox.critical(self, "Exportfout", str(e))

    def open_guide(self):
        QuickGuideDialog(self).exec_()

    def open_contact(self):
        ContactDialog(self).exec_()

    def check_updates(self, silent=True):
        """Controleer op een nieuwere versie. silent=True: alleen melden bij een update."""
        if getattr(self, "_upd_worker", None) is not None and self._upd_worker.isRunning():
            return
        self._upd_silent = silent
        if not silent:
            self.statusBar().showMessage(t("Controleren op updates…"))
        self._upd_worker = _UpdateWorker(self)
        self._upd_worker.done.connect(self._on_update_checked)
        self._upd_worker.start()

    def _on_update_checked(self, latest):
        silent = getattr(self, "_upd_silent", True)
        if latest is None:
            if not silent:
                self.statusBar().showMessage("Updatecontrole mislukt.")
                QMessageBox.information(self, "Updates",
                    "Ik kon de versie-informatie nu niet ophalen. Controleer je "
                    f"internetverbinding, of kijk op {WEBSITE_URL}.")
            return
        remote = latest.get("version", "")
        notes = latest.get("notes", "").strip()
        if is_newer(remote):
            self.statusBar().showMessage(f"Nieuwe versie beschikbaar: {remote}")
            extra = f"<br><br>Wijzigingen:<br>{notes.replace(chr(10), '<br>')}" if notes else ""
            QMessageBox.information(self, "✨ Update beschikbaar",
                f"Er is een nieuwere versie van {APP_NAME}.<br><br>"
                f"Jij gebruikt: <b>v{APP_VERSION}</b><br>"
                f"Nieuwste: <b>v{remote}</b>{extra}<br><br>"
                f"Download de nieuwste versie op:<br>{DOWNLOAD_PAGE_URL}")
        else:
            self.statusBar().showMessage(f"Je hebt de nieuwste versie (v{APP_VERSION}).")
            if not silent:
                QMessageBox.information(self, "Updates",
                    f"Je gebruikt de nieuwste versie van {APP_NAME} (v{APP_VERSION}).")

    def show_info(self):
        QMessageBox.information(
            self, APP_NAME,
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br>een {AUTHOR_NAME} product<br>"
            f"<a href='{WEBSITE_URL}'>{WEBSITE_URL}</a><br><br>"
            "Een portable animatie- &amp; videosuite.<br><br>"
            "Sneltoetsen:<br>Spatie — afspelen/pauze<br>"
            "Ctrl+Z / Ctrl+Y — ongedaan / opnieuw<br>"
            "Ctrl+D — clip dupliceren · Delete — clip verwijderen<br>"
            "Rechtsklik op de tijdlijn — clip knippen (grijze lijn)<br>"
            "Sleep de rode afspeelkop — scrubben<br>Stop-knop — terug naar het begin<br>"
            "Ctrl+scroll op de tijdlijn — zoomen<br><br>"
            f"Video: {'aan' if HAVE_CV2 else 'uit'} · MP4-export: {'aan' if HAVE_FFMPEG else 'uit'}")

    def keyPressEvent(self, ev):
        mod = ev.modifiers()
        key = ev.key()
        if key == Qt.Key_Space:
            self.toggle_play()
        elif mod & Qt.ControlModifier and key == Qt.Key_Z:
            self.undo()
        elif mod & Qt.ControlModifier and (key == Qt.Key_Y or
                                           (key == Qt.Key_Z and mod & Qt.ShiftModifier)):
            self.redo()
        elif mod & Qt.ControlModifier and key == Qt.Key_D:
            self.duplicate_clip()
        elif key in (Qt.Key_Delete, Qt.Key_Backspace) and self._sel is not None:
            self.delete_clip()
        else:
            super().keyPressEvent(ev)


# =========================================================================== #
def app_icon():
    """Zoek logo.ico / logo.png naast het script en geef er een QIcon van."""
    for name in ("logo.ico", "logo.png"):
        p = os.path.join(APP_DIR, name)
        if os.path.exists(p):
            ic = QIcon(p)
            if not ic.isNull():
                return ic
    return None


def main():
    # zorg dat Windows de taskbar-icoon van de app gebruikt i.p.v. die van python
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dravenlock.DraveMotion")
        except Exception:
            pass
    app = QApplication(sys.argv)
    font = app.font(); font.setPointSize(13); app.setFont(font)
    app.setStyleSheet(DRAVENLOCK_QSS)
    ic = app_icon()
    if ic is not None:
        app.setWindowIcon(ic)
    win = DraveMotion()
    if ic is not None:
        win.setWindowIcon(ic)
    win.show()
    try:
        win.check_updates(silent=True)
    except Exception:
        pass
    if load_config().get("show_guide_on_start", True):
        QuickGuideDialog(win).exec_()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
