# -*- coding: utf-8 -*-
"""
certificate.py — генератор персонального PDF-сертификата BALA LAB.
Использование:
    from certificate import generate_certificate
    path = generate_certificate("Айгерим", "07.07.2026")
    # path -> временный .pdf файл, готов к отправке через reply_document
"""
import math
import tempfile
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

# Пути к ассетам — положи папки fonts/ и stickers/ рядом с ботом
FDIR = "assets/fonts/"
STICKERS = "assets/stickers/"

_FONTS_REGISTERED = False

def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont('Unbounded-Black', FDIR + 'Unbounded-Black.ttf'))
    pdfmetrics.registerFont(TTFont('Unbounded-Bold', FDIR + 'Unbounded-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Nunito', FDIR + 'Nunito-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Nunito-Bold', FDIR + 'Nunito-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Nunito-ExtraBold', FDIR + 'Nunito-ExtraBold.ttf'))
    pdfmetrics.registerFont(TTFont('Neucha', FDIR + 'Neucha.ttf'))
    _FONTS_REGISTERED = True

NAVY = colors.HexColor('#152244')
NAVY_SOFT = colors.HexColor('#22335C')
GREEN = colors.HexColor('#7CB342')
GREEN_DARK = colors.HexColor('#4C7A22')
GOLD = colors.HexColor('#D9A62E')
BLUE = colors.HexColor('#2F80ED')
PURPLE = colors.HexColor('#7C5CC7')
INK = colors.HexColor('#1B2432')
PAPER = colors.HexColor('#FAF8F1')


def _star(c, cx, cy, r, color, rot=0):
    c.saveState()
    c.translate(cx, cy); c.rotate(rot)
    c.setFillColor(color)
    p = c.beginPath()
    pts = []
    for i in range(4):
        a1 = i*math.pi/2
        pts.append((r*math.cos(a1), r*math.sin(a1)))
        a2 = a1 + math.pi/4
        pts.append((r*0.32*math.cos(a2), r*0.32*math.sin(a2)))
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

def _icon_leaf(c, cx, cy, s, color):
    c.saveState(); c.translate(cx, cy); c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(0, -s*0.8)
    p.curveTo(s*0.7, -s*0.5, s*0.7, s*0.4, 0, s*0.85)
    p.curveTo(-s*0.7, s*0.4, -s*0.7, -s*0.5, 0, -s*0.8)
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

def _icon_magnifier(c, cx, cy, s, color):
    c.saveState(); c.translate(cx, cy)
    c.setStrokeColor(color); c.setLineWidth(s*0.18)
    c.circle(-s*0.05, s*0.15, s*0.45, fill=0, stroke=1)
    c.line(s*0.28, -s*0.18, s*0.62, -s*0.55)
    c.restoreState()

def _icon_book(c, cx, cy, s, color):
    c.saveState(); c.translate(cx, cy); c.setFillColor(color)
    c.roundRect(-s*0.55, -s*0.5, s*1.1, s*1.0, 3, fill=1, stroke=0)
    c.restoreState()

def _icon_rocket(c, cx, cy, s, color):
    c.saveState(); c.translate(cx, cy); c.setFillColor(color)
    body = c.beginPath()
    body.moveTo(0, s*0.9)
    body.curveTo(s*0.35, s*0.3, s*0.3, -s*0.5, 0, -s*0.9)
    body.curveTo(-s*0.3, -s*0.5, -s*0.35, s*0.3, 0, s*0.9)
    c.drawPath(body, fill=1, stroke=0)
    c.restoreState()

def _badge(c, cx, cy, r, icon_fn, color):
    c.setFillColor(color)
    c.circle(cx, cy, r, fill=1, stroke=0)
    icon_fn(c, cx, cy, r*0.6, colors.white)

def _dotted(c, x1, y, x2, color=GREEN, lw=1.1):
    c.saveState()
    c.setStrokeColor(color); c.setLineWidth(lw); c.setDash(2, 2.6)
    c.line(x1, y, x2, y)
    c.restoreState()

def _fit(c, path, x, y, w, h):
    img = ImageReader(path)
    iw, ih = img.getSize()
    scale = min(w/iw, h/ih)
    nw, nh = iw*scale, ih*scale
    c.drawImage(img, x+(w-nw)/2, y+(h-nh)/2, nw, nh, mask='auto')


def generate_certificate(child_name: str, date_str: str, plant_name: str = "микрозелень") -> str:
    """Генерирует PDF-сертификат и возвращает путь к временному файлу."""
    _register_fonts()
    W, H = A5
    fd, path = tempfile.mkstemp(suffix=".pdf")
    c = canvas.Canvas(path, pagesize=A5)

    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.saveState(); c.setStrokeColor(NAVY); c.setLineWidth(5)
    c.roundRect(10, 10, W-20, H-20, 16, fill=0, stroke=1)
    c.setStrokeColor(GREEN); c.setLineWidth(1.2)
    c.roundRect(19, 19, W-38, H-38, 11, fill=0, stroke=1)
    c.restoreState()

    _star(c, 32, H-32, 7, GOLD)
    _star(c, W-32, H-32, 7, GREEN)
    _star(c, 32, 32, 6, GREEN)
    _star(c, W-32, 32, 6, GOLD)

    c.setFillColor(NAVY)
    c.setFont('Unbounded-Black', 10.5)
    c.drawCentredString(W/2, H-58, "BALA LAB")
    c.setFont('Unbounded-Black', 19)
    c.drawCentredString(W/2, H-98, "СЕРТИФИКАТ")
    c.setFont('Neucha', 15)
    c.setFillColor(GREEN_DARK)
    c.drawCentredString(W/2, H-116, "юного исследователя")

    try:
        _fit(c, STICKERS + '08_aplodiruet.png', W/2-78, H-316, 156, 190)
    except Exception:
        pass

    c.setFont('Nunito', 9.2)
    c.setFillColor(INK)
    c.drawCentredString(W/2, H-320, "Этот сертификат подтверждает, что")
    c.setFont('Unbounded-Bold', 13)
    c.setFillColor(NAVY)
    c.drawCentredString(W/2, H-345, child_name)
    _dotted(c, W/2-135, H-352, W/2+135, color=GREEN)
    c.setFont('Nunito', 8.8)
    c.setFillColor(INK)
    c.drawCentredString(W/2, H-368, f"успешно вырастил(а) свою первую {plant_name} —")
    c.drawCentredString(W/2, H-380, "от семечка до урожая, проводя настоящие научные наблюдения!")

    badges = [(_icon_leaf, GREEN), (_icon_magnifier, BLUE), (_icon_book, GOLD), (_icon_rocket, PURPLE)]
    gap = (W - 2*40) / 3
    by = H - 420
    for i, (icon_fn, col) in enumerate(badges):
        _badge(c, 40 + i*gap, by, 15, icon_fn, col)

    c.setFont('Nunito', 9)
    c.setFillColor(INK)
    c.drawString(30, 50, f"Дата: {date_str}")
    c.drawString(W-140, 50, "Алем, BALA LAB")

    c.showPage()
    c.save()
    return path
