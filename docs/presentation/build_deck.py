#!/usr/bin/env python3
"""Build the team's 5-minute pitch: docs/presentation/CrimsonSnow-pitch.pptx

    pip install python-pptx
    python docs/presentation/build_deck.py                        # rebuild from img/ and NUMBERS
    python docs/presentation/build_deck.py --refresh-images       # copy the pictures again from outputs/
    python docs/presentation/build_deck.py --panel-shot shot.png  # put a control-panel screenshot on slide 7

Every number on the slides is in NUMBERS below: change one (e.g. after the final exam) and
rebuild. The spoken script and the time for each slide are in its speaker notes
(PowerPoint: View > Notes). Total talk: 4:10.
"""

from __future__ import annotations

import argparse
import io
import sys
import uuid
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.oxml.shapes.autoshape import CT_Shape
from pptx.shapes.autoshape import Shape
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMG = HERE / "img"
OUT = HERE / "CrimsonSnow-pitch.pptx"

# ---------------------------------------------------------------- numbers (all on one place)
NUMBERS = {
    # data: SenseCraft dataset metadata (meta/info.json)
    "s1_episodes": "108", "s2_episodes": "149",
    "episodes": "257", "frames": "169,675", "minutes": "94",
    # first model (ACT, 40k steps, session 1): hand trials with `so try` -> journal/eval.csv
    "trials": "3/7",
    # first automatic-retry tests with that model -> journal/demo.csv (16:10-16:21); notes only
    "retry_ok": "4/7", "retry_saved": "3",
    # final model, 22 Nov: every order of the 4 objects over the 4 taped places (battery straight), team's test page
    "final": "24/24",
    # the team's shared test pages: 23/23 on the all-24-arrangements page + 11/11 on the tapes-2-and-3 page
    # (the 24th arrangement and the 12th tapes run were run but not ticked)
    "test_runs": "34", "test_fails": "0",
    # clutter test, 22 Nov (outputs/demo/test video trash/test.mp4): objects on the mat besides the battery
    "clutter_others": "14",
    # the demo model
    "params": "51.6M", "steps": "100,000", "steps_short": "100k", "gpu": "RTX 5090",
    # our own vision check -> journal/vision-report.md
    "vis_frames": "4,000", "vis_minutes": "8", "vis_unseen_eps": "50",
    "vis_acc": "99.8%", "vis_real": "10/10", "vis_real_hands": "7/8", "vis_ms": "11 ms",
    # its answers on the three example frames of slide 6 (first row of outputs/vision/samples.jpg)
    "ex_box": "96%", "ex_mat": "96%", "ex_gripper": "99%",
}
REPO = "github.com/SO-101-Hackathon/CrimsonSnow"

# name in img/ : where it comes from in the repository (outputs/ is git-ignored; see --refresh-images)
IMAGES = {
    "scene_start.jpg": "outputs/vision/frames/ds_af51284a6c/ep0000_f0000_on_mat.jpg",
    "scene_carry.jpg": "outputs/vision/frames/ds_af51284a6c/ep0000_f0452_in_gripper.jpg",
    "scene_end.jpg": "outputs/vision/frames/ds_af51284a6c/ep0000_f0695_in_box.jpg",
    "wrist_cam.jpg": "outputs/demo/20261121_155735/attempt01_run1_wrist.jpg",
    "grip_only_wrong.jpg": "outputs/demo/20261121_155735/attempt01_run1_top.jpg",
    # episodes 89, 49 and 209 are held out (every fifth episode): the model never trained on them
    "check_box.jpg": "outputs/vision/frames/ds_af51284a6c/ep0089_f0630_in_box.jpg",
    "check_mat.jpg": "outputs/vision/frames/ds_af51284a6c/ep0049_f0051_on_mat.jpg",
    "check_gripper.jpg": "outputs/vision/frames/ds_af51284a6c/ep0209_f0288_in_gripper.jpg",
}
PANEL = "panel.jpg"  # written by --panel-shot
# Stills of the clutter test (22 Nov 2026), from outputs/demo/test video trash/test.mp4 (overhead camera on
# the left half, wrist camera on the right): kept as they are in img/, --refresh-images does not touch them.
# trash_end_rest.jpg is the overhead half at 32.5 s: battery in the box, arm back at rest.
FIXED = ["trash_start.jpg", "trash_grip_wrist.jpg", "trash_end_rest.jpg", "clutter_poster.jpg", "bonus_es_poster.jpg"]

# Videos. The clutter clip (17 s, the real test at 2x speed, first frame = clutter_poster.jpg) lives with the
# deck; the 1-minute Spanish video stays in outputs/ (60 s, no sound; bonus_es_poster.jpg is its frame at 20 s).
# A missing video is skipped with a note: slide 3 falls back to the stills, the bonus slide is left out.
CLUTTER_VIDEO = HERE / "video" / "clutter_test_2x.mp4"
BONUS_VIDEO = ROOT / "outputs" / "video" / "CrimsonSnow-1min-ES.mp4"
BONUS_VIDEO_EN = "outputs/video/CrimsonSnow-1min.mp4"

# where the battery is in the photos (pixel centre, ring half-size) for the crimson rings
BATTERY = {
    "scene_start.jpg": ((451, 360), (46, 62)),
    "scene_end.jpg": ((71, 285), (34, 46)),
    "grip_only_wrong.jpg": ((473, 326), (34, 34)),
    "trash_start.jpg": ((237, 334), (36, 50)),
    "trash_end_rest.jpg": ((78, 345), (42, 36)),
}

# ---------------------------------------------------------------- look
BG, CARD, CARD_HI, LINE = "16181D", "22262D", "2A2F37", "3A404A"
SNOW, MUTED, CRIMSON, GREEN, AMBER, INK = "F4F6F8", "A9B1BC", "E8384F", "3BB273", "F2A541", "16181D"
FONT = "Calibri"
SLIDE_W, SLIDE_H = Emu(12192000), Emu(6858000)  # 13.333 x 7.5 in (16:9)
M = 0.6  # side margin, inches


def rgb(hex6: str) -> RGBColor:
    return RGBColor.from_string(hex6)


# ---------------------------------------------------------------- theme, master and layouts
def apply_theme(prs: Presentation) -> None:
    """Dark CrimsonSnow theme: colours and fonts in the theme, dark background and title style on
    the master, so the deck restyles from one place in PowerPoint."""
    part = prs.slide_master.part.part_related_by(RT.THEME)
    root = etree.fromstring(part.blob)
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    root.set("name", "CrimsonSnow")
    scheme = root.find(f".//{{{a}}}clrScheme")
    scheme.set("name", "CrimsonSnow")
    colors = {"dk1": BG, "lt1": SNOW, "dk2": CARD, "lt2": MUTED, "accent1": CRIMSON, "accent2": GREEN,
              "accent3": AMBER, "accent4": "5DA9E9", "accent5": "8C939E", "accent6": "9E1B32",
              "hlink": "7DB8F0", "folHlink": MUTED}
    for name, value in colors.items():
        el = scheme.find(f"{{{a}}}{name}")
        for child in list(el):
            el.remove(child)
        etree.SubElement(el, f"{{{a}}}srgbClr", val=value)
    fonts = root.find(f".//{{{a}}}fontScheme")
    fonts.set("name", "CrimsonSnow")
    for tag in ("majorFont", "minorFont"):
        fonts.find(f"{{{a}}}{tag}/{{{a}}}latin").set("typeface", FONT)
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    master = prs.slide_master._element
    clr_map = master.find(qn("p:clrMap"))  # dark slides: background = dk1, text = lt1
    clr_map.set("bg1", "dk1"), clr_map.set("tx1", "lt1"), clr_map.set("bg2", "dk2"), clr_map.set("tx2", "lt2")
    c_sld = master.find(qn("p:cSld"))
    old = c_sld.find(qn("p:bg"))
    if old is not None:
        c_sld.remove(old)
    bg = etree.SubElement(c_sld, qn("p:bg"))
    c_sld.insert(0, bg)
    bg_pr = etree.SubElement(bg, qn("p:bgPr"))
    fill = etree.SubElement(bg_pr, qn("a:solidFill"))
    etree.SubElement(fill, qn("a:schemeClr"), val="bg1")
    etree.SubElement(bg_pr, qn("a:effectLst"))
    title = master.find(qn("p:txStyles")).find(qn("p:titleStyle")).find(qn("a:lvl1pPr"))
    title.set("algn", "l")
    title.find(qn("a:defRPr")).set("sz", "3600")
    title.find(qn("a:defRPr")).set("b", "1")


def place(shape, x, y, w, h) -> None:
    shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)


def layout_text(layout, name, x, y, w, h, text=None, slide_number=False) -> None:
    """Footer text or slide number drawn on a layout, so every slide of that layout shows it."""
    tree = layout.shapes._spTree
    next_id = max(int(e.get("id")) for e in tree.iter(qn("p:cNvPr"))) + 1
    sp = CT_Shape.new_textbox_sp(next_id, name, Inches(x), Inches(y), Inches(w), Inches(h))
    tree.append(sp)
    tf = Shape(sp, layout.shapes).text_frame
    tf.word_wrap, tf.auto_size = True, MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT if slide_number else PP_ALIGN.LEFT
    if slide_number:
        fld = etree.SubElement(p._p, qn("a:fld"), id="{" + str(uuid.uuid4()).upper() + "}", type="slidenum")
        rpr = etree.SubElement(fld, qn("a:rPr"), lang="en-US", sz="1200", dirty="0")
        fill = etree.SubElement(rpr, qn("a:solidFill"))
        etree.SubElement(fill, qn("a:srgbClr"), val=MUTED)
        etree.SubElement(fld, qn("a:t")).text = "‹#›"
    else:
        r = p.add_run()
        r.text = text
        r.font.size, r.font.color.rgb = Pt(12), rgb(MUTED)


def no_insets(shape) -> None:
    """Text flush with the shape's edge, so titles line up with pictures and cards below them."""
    tf = shape.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0


def setup_layouts(prs: Presentation):
    """The two layouts this deck uses: Title Slide and Title Only, re-placed for 16:9."""
    master = prs.slide_master
    for ph in list(master.placeholders):
        if ph.placeholder_format.type == PP_PLACEHOLDER.TITLE:
            place(ph, M, 0.42, 13.333 - 2 * M, 0.95)
            no_insets(ph)
        elif ph.placeholder_format.type == PP_PLACEHOLDER.BODY:
            place(ph, M, 1.6, 13.333 - 2 * M, 4.9)
    title_layout, content_layout = prs.slide_layouts[0], prs.slide_layouts[5]
    for ph in list(title_layout.placeholders):
        idx = ph.placeholder_format.idx
        if idx == 0:
            place(ph, M, 1.95, 5.9, 1.15)
            no_insets(ph)
        elif idx == 1:
            place(ph, M, 3.2, 5.8, 1.7)
            no_insets(ph)
        else:
            ph._element.getparent().remove(ph._element)  # no date/footer/number on the title slide
    for ph in list(content_layout.placeholders):
        if ph.placeholder_format.idx == 0:
            place(ph, M, 0.42, 13.333 - 2 * M, 0.95)
            no_insets(ph)
        else:
            ph._element.getparent().remove(ph._element)
    layout_text(content_layout, "Footer", M, 6.92, 8.0, 0.3, text="CrimsonSnow · Hackathon LeRobot Bilbao 2026")
    layout_text(content_layout, "Slide number", 13.333 - M - 1.0, 6.92, 1.0, 0.3, slide_number=True)
    return title_layout, content_layout


# ---------------------------------------------------------------- building blocks
def text(slide, x, y, w, h, paras, *, size=18, color=SNOW, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None, after=0, font=None):
    """paras: a string, or a list of paragraphs; a paragraph is a string or a list of
    (text, {size, color, bold, font}) runs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.name = name or (paras if isinstance(paras, str) else "Text")[:40]
    tf = box.text_frame
    tf.word_wrap, tf.auto_size, tf.vertical_anchor = True, MSO_AUTO_SIZE.NONE, anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate([paras] if isinstance(paras, str) else paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if after:
            p.space_after = Pt(after)
        for run in ([(para, {})] if isinstance(para, str) else para):
            t, o = run
            r = p.add_run()
            r.text = t
            r.font.size, r.font.bold = Pt(o.get("size", size)), o.get("bold", bold)
            r.font.color.rgb = rgb(o.get("color", color))
            if o.get("font", font):
                r.font.name = o.get("font", font)
    return box


def card(slide, x, y, w, h, fill=CARD, radius=0.14, line=None, name="Card"):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb, s.line.width = rgb(line[0]), Pt(line[1])
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.name = name
    return s


def badge(slide, x, y, d, label, fill=CRIMSON, size=18, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    s.shadow.inherit = False
    s.name = name or f"Badge {label}"
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.color.rgb = Pt(size), True, rgb(SNOW)
    return s


def photo(slide, name, x, y, w=None, h=None, alt="", radius=0.12):
    """A picture with rounded corners (cropped to a rounded rectangle, the deck's motif)."""
    path = IMG / name
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    pic.name = alt[:60] or name
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    geom = pic._element.spPr.find(qn("a:prstGeom"))
    geom.set("prst", "roundRect")
    av = geom.find(qn("a:avLst"))
    if av is None:
        av = etree.SubElement(geom, qn("a:avLst"))
    short = min(pic.width, pic.height) / 914400
    etree.SubElement(av, qn("a:gd"), name="adj", fmla=f"val {int(min(50000, radius / short * 100000))}")
    pic.line.color.rgb, pic.line.width = rgb(LINE), Pt(1)
    return pic


def ring(slide, pic, name, color=CRIMSON, width=3.0):
    """A crimson ring around the battery in the photo `name`, placed on the slide as `pic`."""
    from PIL import Image

    (cx, cy), (rw, rh) = BATTERY[name]
    with Image.open(IMG / name) as img:
        px_w, px_h = img.size
    sx, sy = pic.width / px_w, pic.height / px_h
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(int(pic.left + (cx - rw) * sx)), Emu(int(pic.top + (cy - rh) * sy)),
                               Emu(int(2 * rw * sx)), Emu(int(2 * rh * sy)))
    s.fill.background()
    s.line.color.rgb, s.line.width = rgb(color), Pt(width)
    s.shadow.inherit = False
    s.name = "Battery ring"
    return s


def movie(slide, path: Path, x, y, w, h, poster: str, alt: str):
    """An embedded MP4 that plays when clicked (in the slide show, or with the play button when editing)."""
    m = slide.shapes.add_movie(str(path), Inches(x), Inches(y), Inches(w), Inches(h),
                               poster_frame_image=str(IMG / poster), mime_type="video/mp4")
    m.name = alt[:60]
    m._element.nvPicPr.cNvPr.set("descr", alt)
    m.line.color.rgb, m.line.width = rgb(LINE), Pt(1)
    return m


def _arrow_head(line_format) -> None:
    ln = line_format._get_or_add_ln()
    etree.SubElement(ln, qn("a:tailEnd"), type="triangle", w="med", len="med")


def arrow(slide, x1, y1, x2, y2, color=CRIMSON, width=2.5, name="Arrow"):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb, c.line.width = rgb(color), Pt(width)
    _arrow_head(c.line)
    c.name = name
    return c


def polyline(slide, points, color, width=2.5, head=True, name="Line"):
    pts = [(Inches(x), Inches(y)) for x, y in points]
    fb = slide.shapes.build_freeform(pts[0][0], pts[0][1], scale=1.0)
    fb.add_line_segments(pts[1:], close=False)
    s = fb.convert_to_shape()
    s.fill.background()
    s.line.color.rgb, s.line.width = rgb(color), Pt(width)
    if head:
        _arrow_head(s.line)
    s.shadow.inherit = False
    s.name = name
    return s


def stat(slide, x, y, w, value, label, *, value_size=54, color=SNOW, label_size=16, label_h=0.7, name=None):
    value_h = value_size / 72 * 1.15
    text(slide, x, y, w, value_h, [[(value, {"size": value_size, "bold": True, "color": color})]], name=name or value)
    text(slide, x, y + value_h + 0.02, w, label_h, label, size=label_size, color=MUTED, name=f"{value} label")


def notes(slide, script: str) -> None:
    slide.notes_slide.notes_text_frame.text = script


def said(fraction: str) -> str:
    """'3/7' as it is spoken: '3 out of 7'."""
    return fraction.replace("/", " out of ")


def title(slide, words: str) -> None:
    slide.shapes.title.text = words


def clutter_stills(s, N) -> None:
    """Slide 3 without the video: start still (battery circled), grip close-up and end still."""
    big_h, small_w = 4.45, 2.75
    pic = photo(s, "trash_start.jpg", M, 1.6, h=big_h,
                alt=f"Clutter test start: the battery among {N['clutter_others']} other objects: five rubber ducks, "
                    "a phone, scissors, a nail clipper, keys, a tape roll, a pen and three cubes")
    ring(s, pic, "trash_start.jpg")
    rx = M + pic.width / 914400 + 0.35
    small_h = small_w * 0.75
    shots = [("trash_grip_wrist.jpg", 1.6, "Gripped", "wrist camera, first run",
              "Wrist camera: the battery held between the gripper jaws"),
             ("trash_end_rest.jpg", 1.6 + big_h - small_h, "In the box", f"the other {N['clutter_others']} untouched",
              "Clutter test end: the battery in the box, every other object where it was, the arm back at rest")]
    for img, y, head, sub_text, alt in shots:
        shot = photo(s, img, rx, y, w=small_w, alt=alt)
        if img in BATTERY:
            ring(s, shot, img, width=2.5)
        lx = rx + small_w + 0.3
        text(s, lx, y + small_h / 2 - 0.5, 13.333 - M - lx, 0.45, head, size=22, bold=True)
        text(s, lx, y + small_h / 2 - 0.02, 13.333 - M - lx, 0.7, sub_text, size=15, color=MUTED)
    text(s, M, 6.2, 13.333 - 2 * M, 0.45,
         [[(N["clutter_others"], {"bold": True, "color": CRIMSON}), (" other objects on the mat  ·  battery picked ", {}),
           ("first try", {"bold": True, "color": CRIMSON})]], size=20, name="Clutter caption")


# ---------------------------------------------------------------- the slides
def build(panel_available: bool) -> Presentation:
    N = NUMBERS
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    prs.core_properties.title = "CrimsonSnow: teaching an arm to pick out the battery"
    prs.core_properties.author = prs.core_properties.last_modified_by = "Team CrimsonSnow"
    prs.core_properties.subject = "Hackathon LeRobot Bilbao 2026: 5-minute pitch"
    apply_theme(prs)
    title_layout, content = setup_layouts(prs)

    # 1 -- title ----------------------------------------------------------------------------
    s = prs.slides.add_slide(title_layout)
    s.shapes.title.text = "CrimsonSnow"
    r = s.shapes.title.text_frame.paragraphs[0].runs[0]
    r.font.size, r.font.bold, r.font.color.rgb = Pt(60), True, rgb(SNOW)
    s.shapes.title.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    sub = s.placeholders[1]
    sub.text = "Teaching an arm\vto pick out the battery —\vand to notice when it failed"  # \v: line break
    sub.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    sub.text_frame.vertical_anchor = MSO_ANCHOR.TOP
    for r in sub.text_frame.paragraphs[0].runs:
        r.font.size, r.font.color.rgb = Pt(26), rgb(SNOW)
    text(s, M, 5.05, 5.8, 0.4, "Hackathon LeRobot Bilbao · 20–22 Nov 2026", size=18, color=CRIMSON, bold=True)
    text(s, M, 5.5, 5.8, 0.4, "SO-101 arm · LeRobot 0.7.0 · ACT", size=18, color=MUTED)
    pic = photo(s, "scene_start.jpg", 6.73, 1.5, w=6.0,
                alt="Overhead camera: the battery (wooden block) on the mat among a duck, a toy car and a TNT cube")
    ring(s, pic, "scene_start.jpg")
    notes(s, "[0:15 | total 0:15]\n"
             "Hi, we are CrimsonSnow. We taught an SO-101 arm to find a battery among other objects and put "
             "it in a box, and to notice by itself when it failed, and try again.")

    # 2 -- the task ---------------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, "Find the battery, drop it in the box")
    findings = [(["Spain: a waste plant catches fire", "every 3.5 days"],
                 "109 fires in 2023; lithium batteries are a growing cause"),
                (["EU law: collect 73% of portable", "batteries by 2030"], "every one has to be sorted out of the rest"),
                ("Picking them out by hand is dangerous", "a damaged battery can catch fire without warning")]
    for i, (head, sub_text) in enumerate(findings):
        y = 1.65 + i * 1.32
        badge(s, M, y, 0.48, str(i + 1), size=18)
        text(s, M + 0.7, y - 0.04, 5.3, 0.8, head, size=20, bold=True)
        text(s, M + 0.7, y + 0.72 if isinstance(head, list) else y + 0.42, 5.3, 0.45, sub_text, size=15, color=MUTED)
    text(s, M, 5.75, 5.9, 0.6, "Sources: TECNIFUEGO via IFEMA SICUR (fires); Regulation (EU) 2023/1542 "
                               "on batteries and waste batteries (collection target)", size=12, color=MUTED, name="Sources")
    pw = 13.333 - M - 6.95
    pic = photo(s, "scene_start.jpg", 6.95, 1.6, w=pw,
                alt="Our task: the battery (wooden block) on the mat among a duck, a toy car and a TNT cube")
    ring(s, pic, "scene_start.jpg")
    below = 1.6 + pic.height / 914400
    text(s, 6.95, below + 0.15, pw, 0.45, [[("Our task: ", {"bold": True, "color": CRIMSON}),
                                           ("pick the battery out, drop it in the box", {"bold": True})]], size=18)
    text(s, 6.95, below + 0.6, pw, 0.4, "on the mat with it: a rubber duck, a toy car, a TNT cube", size=15,
         color=MUTED)
    notes(s, "[0:30 | total 0:45]\n"
             "Why batteries? In Spain a waste plant catches fire every three and a half days: 109 fires in 2023, and "
             "lithium batteries are a growing cause. And EU law says 73 percent of portable batteries must be collected "
             "by 2030, so every one of them has to be sorted out of the rest. Picking them out by hand is dangerous; a damaged battery can catch fire without warning. So our task: among "
             "other objects, the arm picks the battery and drops it into its own box, learned only from our "
             "demonstrations.\n"
             "[If asked: the UK counted 2,839 battery fires in its waste system in 2025, one every 3 hours (Recycle "
             "Your Electricals research, reported by Insurance Times). They arrive in household rubbish: phones, vapes, "
             "toys (FER). Spain's 109 fires: TECNIFUEGO via IFEMA SICUR, all waste-plant "
             "fires, so 'a growing cause', not 'the cause'. 73% by 2030: Regulation (EU) 2023/1542. Later recordings also had a "
             "yellow cube, a tape roll and a pen on the mat.]")

    # 3 -- clutter test -------------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, "Only the battery, even in a pile of junk")
    if CLUTTER_VIDEO.is_file():
        vw = 11.4
        vh = vw * 524 / 1280
        vx = (13.333 - vw) / 2
        movie(s, CLUTTER_VIDEO, vx, 1.55, vw, vh, "clutter_poster.jpg",
              f"Clutter test video at 2x speed: overhead camera left, wrist camera right; the battery among "
              f"{N['clutter_others']} other objects is picked and dropped in the box on the first run")
        text(s, vx, 1.55 + vh + 0.15, vw * 0.68, 0.45,
             [[(N["clutter_others"], {"bold": True, "color": CRIMSON}), (" other objects on the mat  ·  battery picked ", {}),
               ("first try", {"bold": True, "color": CRIMSON})]], size=20, name="Clutter caption")
        text(s, vx + vw * 0.68, 1.55 + vh + 0.2, vw * 0.32, 0.4, "click to play · real run, 2× speed", size=14,
             color=MUTED, align=PP_ALIGN.RIGHT, name="Play hint")
    else:
        print(f"note: {CLUTTER_VIDEO.relative_to(ROOT).as_posix()} not found: slide 3 shows the stills instead")
        clutter_stills(s, N)
    notes(s, "[0:20 | total 1:05]\n"
             f"Then we made it hard: the battery plus {N['clutter_others']} other things on the mat, five rubber "
             "ducks, a phone, scissors, keys, a pen, cubes. [Click the video: 17 s, real run at 2x speed.] First run: "
             "the arm goes straight for the battery, grips it, that is the wrist camera on the right, and drops it in "
             "the box. Nothing else moves.\n"
             "[Source: outputs/demo/test video trash/test.mp4, 22 Nov 2026, recorded by so demo --record-video.]")


    # 4 -- data ---------------------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, f"{N['episodes']} demonstrations, aimed at our failures")
    cards = [("1", "Session 1", N["s1_episodes"], SNOW, "demonstrations", "objects shuffled in a balanced order"),
             ("2", "Test of model 1", N["trials"], CRIMSON, "hand trials succeeded",
              "battery turned · grasp too low or too high · anything moved"),
             ("3", "Session 2", N["s2_episodes"], SNOW, "targeted demonstrations",
              "turned ±20° · moved ±2 cm · about 80% still straight")]
    for i, (num, head, big, color, label, detail) in enumerate(cards):
        x = M + i * (3.7 + 0.515)
        card(s, x, 1.6, 3.7, 3.4, name=f"{head} card")
        badge(s, x + 0.3, 1.88, 0.5, num, size=18)
        text(s, x + 0.95, 1.88, 2.6, 0.5, head, size=18, bold=True, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 0.3, 2.5, 3.1, 1.0, [[(big, {"size": 60, "bold": True, "color": color})]], name=f"{head} number")
        text(s, x + 0.3, 3.5, 3.1, 0.45, label, size=18)
        text(s, x + 0.3, 4.0, 3.15, 0.9, detail, size=15, color=MUTED)
        if i < 2:
            arrow(s, x + 3.75, 3.3, x + 4.165, 3.3, color=CRIMSON, width=3)
    banner = card(s, M, 5.3, 13.333 - 2 * M, 1.25, fill=CARD_HI, name="Total card")
    text(s, M + 0.4, 5.3, 13.333 - 2 * M - 0.8, 1.25,
         [[(N["episodes"], {"size": 34, "bold": True, "color": CRIMSON}), ("  episodes   ·   ", {}),
           (N["frames"], {"size": 34, "bold": True, "color": CRIMSON}), ("  frames   ·   ≈ ", {}),
           (N["minutes"], {"size": 34, "bold": True, "color": CRIMSON}), ("  minutes of demonstrations", {})]],
         size=22, anchor=MSO_ANCHOR.MIDDLE, name="Total")
    notes(s, "[0:45 | total 1:50]\n"
             f"How did it get there? Data. Session one: {N['s1_episodes']} demonstrations, objects shuffled in a "
             "balanced order so the arm cannot memorise one layout. A first model got "
             f"{said(N['trials'])} by hand, and every failure got a note: battery turned, no attempt; grasp too low "
             "or at the very top, stuck; anything moved, lost. So session two aimed exactly there: "
             f"{N['s2_episodes']} demonstrations with the battery turned 20 degrees and moved 2 centimetres, keeping "
             "about 80 percent normal placements so it does not forget what it knew. In total "
             f"{N['episodes']} demonstrations, about {N['minutes']} minutes of us driving the arm.")

    # 5 -- closed loop ----------------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, "If it fails, it tries again — hands off")
    steps = [("1", "Run the policy", "ACT, up to 40 s"), ("2", "Back to the start", "the same pose every run"),
             ("3", "Check", "is the battery in the box?")]
    bw, gap, top, bh = 2.85, 0.42, 1.7, 1.4
    for i, (num, head, sub_text) in enumerate(steps):
        x = M + i * (bw + gap)
        card(s, x, top, bw, bh, name=f"Step {num}")
        badge(s, x + 0.22, top + 0.24, 0.44, num, size=16)
        text(s, x + 0.78, top + 0.24, bw - 0.95, 0.44, head, size=20, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 0.25, top + 0.8, bw - 0.45, 0.55, sub_text, size=15, color=MUTED)
        arrow(s, x + bw + 0.03, top + bh / 2, x + bw + gap - 0.03, top + bh / 2,
              color=GREEN if i == 2 else CRIMSON, width=3)
    sx = M + 3 * (bw + gap)
    card(s, sx, top, 13.333 - M - sx, bh, fill=CARD, line=(GREEN, 2.25), name="Success")
    text(s, sx + 0.25, top + 0.24, 13.333 - M - sx - 0.4, 0.44, "Success", size=22, bold=True, color=GREEN,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, sx + 0.25, top + 0.8, 13.333 - M - sx - 0.4, 0.55, "battery in the box", size=15, color=SNOW)
    x1, x3 = M + bw / 2, M + 2 * (bw + gap) + bw / 2
    polyline(s, [(x3, top + bh + 0.03), (x3, top + bh + 0.62), (x1, top + bh + 0.62), (x1, top + bh + 0.05)],
             AMBER, width=3, name="Retry loop")
    text(s, x1, top + bh + 0.72, x3 - x1, 0.4, "still on the mat → run again, up to 3 runs", size=17,
         color=AMBER, bold=True, align=PP_ALIGN.CENTER, name="Retry label")
    pic = photo(s, "grip_only_wrong.jpg", M, 4.55, w=2.85,
                alt="Check photo: the battery is still in the gripper although the gripper-only check said success")
    ring(s, pic, "grip_only_wrong.jpg", width=2.5)
    text(s, M + 3.27, 4.55, 13.333 - M - (M + 3.27), pic.height / 914400,
         [[("First test: ", {"color": CRIMSON, "bold": True}), ("the gripper alone said “success”.", {"bold": True})],
          [("The camera shows the battery still in the gripper. That is why we check with vision.",
            {"size": 18, "color": MUTED})]], size=22, after=8, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "[0:45 | total 2:35]\n"
             "The demo is five attempts with nobody touching the robot. So we closed the loop. The policy runs; the "
             "arm goes back exactly to its start pose; then we check the result. Battery in the box: success. Still "
             "on the mat: the robot simply tries again, up to three runs per attempt. Why a camera? In our first "
             "test the gripper-only check said success. This photo was taken at that moment: the battery is still "
             "in the gripper. The gripper alone cannot see the box.")

    # 6 -- our own vision check ---------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, "Our own vision model checks the box")
    text(s, M, 1.6, 5.6, 0.4, "Its answers on recordings it never saw", size=16, color=MUTED)
    examples = [("check_box.jpg", f"in the box  {N['ex_box']}", "truth: in the box"),
                ("check_mat.jpg", f"on the mat  {N['ex_mat']}", "truth: on the mat"),
                ("check_gripper.jpg", f"in the gripper  {N['ex_gripper']}", "truth: in the gripper")]
    for i, (img, answer, truth) in enumerate(examples):
        y = 2.08 + i * 1.55
        photo(s, img, M, y, h=1.38, alt=f"Unseen recording, model answer {answer}, {truth}", radius=0.1)
        text(s, M + 2.05, y + 0.3, 3.5, 0.45, answer, size=20, bold=True)
        text(s, M + 2.05, y + 0.78, 3.5, 0.4, truth, size=15, color=GREEN)
    rx, rw = 6.75, 13.333 - M - 6.75
    text(s, rx, 1.6, rw, 0.45, "Labelled for free by the gripper", size=20, bold=True)
    # schematic gripper opening over one demonstration: closed, open, holding, open (release), closed
    tx0, ty_open, ty_hold, ty_closed = rx + 0.05, 2.25, 2.72, 3.08
    seg = lambda f: tx0 + f * (rw - 0.1)  # noqa: E731
    polyline(s, [(seg(0.0), ty_closed), (seg(0.07), ty_closed), (seg(0.12), ty_open), (seg(0.35), ty_open),
                 (seg(0.40), ty_hold), (seg(0.73), ty_hold), (seg(0.77), ty_open), (seg(0.86), ty_open),
                 (seg(0.91), ty_closed), (seg(1.0), ty_closed)], SNOW, width=2.25, head=False, name="Gripper trace")
    for a, b, label, fill in ((0.0, 0.34, "on the mat", MUTED), (0.41, 0.72, "in the gripper", AMBER),
                              (0.80, 1.0, "in the box", GREEN)):
        bar = card(s, seg(a), 3.25, seg(b) - seg(a), 0.45, fill=fill, radius=0.08, name=f"Label {label}")
        text(s, seg(a), 3.25, seg(b) - seg(a), 0.45, label, size=14, bold=True, color=INK,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"{label} text")
    text(s, rx, 3.78, rw, 0.35, "gripper opening during one demonstration", size=14, color=MUTED)
    sw = (rw - 0.3) / 3
    stat(s, rx, 4.35, sw, N["vis_acc"], f"right on {N['vis_unseen_eps']} unseen recordings", value_size=40,
         color=CRIMSON, label_size=15, label_h=0.6)
    stat(s, rx + sw + 0.15, 4.35, sw, N["vis_real"], ["real demo photos", "no hands in view"], value_size=40,
         label_size=15, label_h=0.6)
    stat(s, rx + 2 * (sw + 0.15), 4.35, sw, N["vis_ms"], "per photo, offline", value_size=40, label_size=15,
         label_h=0.6)
    text(s, rx, 5.95, rw, 0.7, f"{N['vis_frames']} labelled frames, trained in {N['vis_minutes']} min on the laptop. "
                               "One .env line switches to ChatGPT or Claude.", size=16)
    notes(s, "[0:45 | total 3:20]\n"
             "We first let ChatGPT check the photo, but the demo should not depend on the venue Wi-Fi. So we "
             "trained our own vision model on this laptop, with no hand labelling: the gripper signal says when the "
             "battery was grabbed and let go. Before, it is on the mat; while held, in the gripper; after, in the "
             f"box. {N['vis_frames']} frames for free, {N['vis_minutes']} minutes of training. On "
             f"{N['vis_unseen_eps']} recordings it never saw: {N['vis_acc'].replace('%', ' percent')} right, never a "
             f"wrong 'in the box'. Real demo photos without hands: {said(N['vis_real'])}. "
             f"{N['vis_ms'].replace('ms', 'milliseconds')}, offline. One .env line switches to ChatGPT or Claude.\n"
             f"[If asked: with a person's hand in the picture it answered {said(N['vis_real_hands'])} right; when "
             "unsure it falls back to the gripper reading. Details: journal/vision-report.md]")

    # 7 -- built to be repeated -----------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, "Built to be repeated — and to demo")
    if panel_available:
        shot = photo(s, PANEL, M, 1.7, w=7.4, alt="The local control panel: run the demo from a browser, every check on screen")
        text(s, M, 1.7 + shot.height / 914400 + 0.15, 7.4, 0.7,
             "so panel: the demo from a browser, every check on screen (simulated run shown)", size=14, color=MUTED)
    else:
        card(s, M, 1.6, 7.2, 4.05, fill="0E1013", line=(LINE, 1), radius=0.12, name="Terminal")
        lines = [("> so demo --sensecraft", SNOW), ("[demo] Attempt 3: press Enter", MUTED),
                 ("[demo]   run 1 | grip: held | camera: on mat", MUTED),
                 ("[demo]   -> not done: still on the mat", AMBER),
                 ("[demo]   running the policy again...", MUTED),
                 ("[demo]   run 3 | grip: held | camera: in box", MUTED),
                 ("[demo]   -> SUCCESS: battery is in the box", GREEN)]
        text(s, M + 0.35, 1.9, 6.6, 3.5, [[(t, {"color": c})] for t, c in lines], size=15, font="Consolas", after=6)
        text(s, M, 5.75, 7.2, 0.4, "so demo: run, check, run again (output shortened)", size=14, color=MUTED)
    rows = [("so helper", "wraps the official LeRobot commands and logs every one in journal/"),
            ("Tested everywhere", "unit tests and CI on Ubuntu, macOS and Windows"),
            ("Open on GitHub", REPO.split("/", 1)[1])]
    for i, (head, body) in enumerate(rows):
        y = 1.75 + i * 1.4
        badge(s, 8.45, y, 0.5, str(i + 1), size=18)
        text(s, 9.15, y - 0.02, 13.333 - M - 9.15, 0.45, head, size=20, bold=True)
        text(s, 9.15, y + 0.45, 13.333 - M - 9.15, 0.8, body, size=16, color=MUTED)
    notes(s, "[0:25 | total 3:45]\n"
             "Everything is reproducible. Our 'so' helper wraps the official LeRobot commands and writes every "
             "command we ran into the repository's journal; the tests run on Ubuntu, macOS and Windows in CI. And for "
             "today we built a small control panel: the demo runs from a browser, and you can see every check as it "
             "happens.\n"
             "(Team: before the jury round, publish the dataset on Hugging Face. CrimsonSnowLLC/battery-sample is "
             "still private; public gives the +3 bonus. Only then say: 'and our dataset is public on Hugging Face'.)")

    # 8 -- results and live demo ------------------------------------------------------------------------
    s = prs.slides.add_slide(content)
    title(s, "Live now: five attempts, hands off")
    card(s, M, 1.6, 5.8, 2.6, name="Before and after card")
    text(s, M + 0.3, 1.85, 1.6, 0.85, [[(N["trials"], {"size": 44, "bold": True, "color": MUTED})]], name="Before number")
    text(s, M + 0.3, 2.75, 1.6, 1.0, ["first model,", "by hand"], size=15, color=MUTED, name="Before label")
    arrow(s, M + 1.85, 2.3, M + 2.5, 2.3, color=CRIMSON, width=3.5, name="Before to after")
    text(s, M + 2.7, 1.7, 3.0, 1.15, [[(N["final"], {"size": 66, "bold": True, "color": CRIMSON})]], name="After number")
    text(s, M + 2.7, 2.85, 2.95, 0.7, ["final model: all 24 orders", "of 4 objects on 4 places"], size=16,
         name="After label")
    text(s, M + 0.3, 3.65, 5.3, 0.4, f"{N['test_runs']} logged test runs, {N['test_fails']} failures", size=16,
         bold=True, color=GREEN, name="Evidence")
    card(s, M, 4.4, 5.8, 1.05, name="Clutter card")
    text(s, M + 0.3, 4.4, 1.9, 1.05, [[("1st try", {"size": 30, "bold": True, "color": SNOW})]],
         anchor=MSO_ANCHOR.MIDDLE, name="Clutter number")
    text(s, M + 2.3, 4.4, 3.35, 1.05, f"clutter test: the battery among {N['clutter_others']} other objects",
         size=16, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
    card(s, M, 5.65, 5.8, 0.95, fill=CARD_HI, line=(CRIMSON, 2), name="Today card")
    text(s, M + 0.3, 5.65, 5.3, 0.95, [[("Today  ", {"bold": True, "color": CRIMSON}),
                                       (f"ACT {N['steps_short']} steps · {N['episodes']} demonstrations · "
                                        "our own vision check", {"bold": True})]],
         size=16, anchor=MSO_ANCHOR.MIDDLE)
    pw = 5.5
    pic = photo(s, "scene_end.jpg", 13.333 - M - pw, 1.6, w=pw, alt="The goal: the battery in the box, the arm back at rest")
    ring(s, pic, "scene_end.jpg")
    below = 1.6 + pic.height / 914400
    text(s, 13.333 - M - pw, below + 0.12, pw, 0.45, "Thank you!", size=24, bold=True, color=CRIMSON)
    text(s, 13.333 - M - pw, below + 0.58, pw, 0.35, REPO, size=16, color=SNOW)
    notes(s, "[0:25 | total 4:10]\n"
             f"Where we stand: our first model got {said(N['trials'])} by hand. The final model: "
             f"{said(N['final'])}, every order of the four objects over the four places, and "
             f"{N['test_runs']} logged test runs without a failure. In the clutter test, first try. Now live: five "
             "attempts, hands off. Thank you!\n"
             f"[If asked: the {N['final'].split('/')[1]} arrangements had the battery straight. The {N['test_runs']} "
             "runs are the team's test pages: 23 of 23 on the all-arrangements page and 11 of 11 on the tapes 2 and 3 "
             "page. Two candidates are still running: a fine-tune with 24 extra demonstrations for tapes 2 and 3, and "
             "a from-scratch retrain on all 281 episodes (ACT, 100k steps, A100); the demo runs the one that tests "
             f"best. Our first automatic-retry tests with the old model reached {said(N['retry_ok'])} attempts, "
             f"{N['retry_saved']} of them saved by a retry.]")

    # bonus -- not part of the 5:00 talk --------------------------------------------------------------
    if BONUS_VIDEO.is_file():
        s = prs.slides.add_slide(content)
        title(s, "Backup / bonus: CrimsonSnow in 1 minute")
        vh = 4.6
        vw = vh * 16 / 9
        vx = (13.333 - vw) / 2
        movie(s, BONUS_VIDEO, vx, 1.5, vw, vh, "bonus_es_poster.jpg",
              "CrimsonSnow in 1 minute, Spanish version, 60 seconds, no sound")
        text(s, vx, 1.5 + vh + 0.15, vw, 0.4, "Spanish version · 60 s · no sound: voice-over live · click to play",
             size=14, color=MUTED, align=PP_ALIGN.CENTER, name="Bonus caption")
        notes(s, "[Backup / bonus: not part of the 5:00 talk. Show only if there is time or the jury asks.]\n"
                 "The Spanish 1-minute video has no sound: one of us reads the voice-over live while it plays. "
                 f"English version: {BONUS_VIDEO_EN}.")
    else:
        print(f"note: {BONUS_VIDEO.relative_to(ROOT).as_posix()} not found on this computer: bonus slide left out")
    return prs


# ---------------------------------------------------------------- images
def _save_jpeg(src, dest: Path, max_kb: int = 300) -> None:
    from PIL import Image

    with Image.open(src) as img:
        img = img.convert("RGB")
        if img.width > 1600:
            img = img.resize((1600, round(img.height * 1600 / img.width)), Image.LANCZOS)
        for quality in (90, 85, 80, 75, 70):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_kb * 1024:
                break
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(buf.getvalue())


def refresh_images() -> None:
    for name, source in IMAGES.items():
        src = ROOT / source
        if src.is_file():
            _save_jpeg(src, IMG / name)
            print(f"  img/{name}  <-  {source}")
        else:
            print(f"  img/{name}: {source} not found, keeping the copy in img/")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--refresh-images", action="store_true", help="copy the pictures again from outputs/ (git-ignored)")
    p.add_argument("--panel-shot", type=Path, help="screenshot of `so panel` for slide 7")
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    if args.refresh_images:
        refresh_images()
    if args.panel_shot:
        _save_jpeg(args.panel_shot, IMG / PANEL)
    missing = [n for n in [*IMAGES, *FIXED] if not (IMG / n).is_file()]
    if missing:
        raise SystemExit(f"missing pictures in {IMG}: {missing} (run with --refresh-images on the team laptop)")
    prs = build(panel_available=(IMG / PANEL).is_file())
    prs.save(args.out)
    print(f"saved {args.out}  ({len(prs.slides)} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
