"""
Modul Gambar Detail Arsitektur & Struktur (Skala 1 : 20).
Menata 4 gambar detail DED dalam grid 2x2 di dalam viewport kertas A3,
secara adaptif menyesuaikan struktur Rumah 1 Lantai maupun 2 Lantai.
"""
from typing import Dict, Optional, Sequence, Tuple

import ezdxf
from ezdxf.enums import TextEntityAlignment as TA


def _siapkan_layer_detail(doc: ezdxf.document.Drawing) -> None:
    for nama, warna in [
        ("A-WALL", 6),
        ("A-WALL-PATT", 8),
        ("S-COLS", 1),
        ("S-FNDN", 4),
        ("A-DOOR", 1),
        ("A-GLAZ", 4),
        ("A-ANNO-TEXT", 2),
        ("A-ANNO-DIMS", 3),
        ("A-ANNO-SYMB", 7),
    ]:
        if nama not in doc.layers:
            doc.layers.add(nama, color=warna)


def _poly(msp, pts: Sequence[Tuple[float, float]], layer: str, tutup: bool = True, color: Optional[int] = None):
    attr: Dict[str, object] = {"layer": layer}
    if color is not None:
        attr["color"] = color
    return msp.add_lwpolyline(list(pts), close=tutup, dxfattribs=attr)


def _garis(msp, p1: Tuple[float, float], p2: Tuple[float, float], layer: str = "A-WALL", color: Optional[int] = None):
    attr: Dict[str, object] = {"layer": layer}
    if color is not None:
        attr["color"] = color
    return msp.add_line(p1, p2, dxfattribs=attr)


def _arsir(msp, pts: Sequence[Tuple[float, float]], pola: str, skala: float, layer: str, color: int = 256):
    if len(pts) < 3:
        return
    h = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    if pola.upper() == "SOLID":
        h.set_solid_fill()
    else:
        try:
            h.set_pattern_fill(pola, scale=skala)
        except Exception:
            h.set_pattern_fill("ANSI31", scale=skala)
    h.paths.add_polyline_path(list(pts), is_closed=True)


def _teks(msp, isi: str, pos: Tuple[float, float], tinggi: float = 80.0, rata=TA.MIDDLE_CENTER, layer: str = "A-ANNO-TEXT", color: Optional[int] = None):
    style_name = "KOP_FONT" if "KOP_FONT" in msp.doc.styles else "Standard"
    attr: Dict[str, object] = {"layer": layer, "style": style_name}
    if color is not None:
        attr["color"] = color
    msp.add_text(isi, height=tinggi, dxfattribs=attr).set_placement(pos, align=rata)


def _callout(msp, p_target: Tuple[float, float], x_txt: float, y_txt: float, label: str, s: float, rata=TA.MIDDLE_LEFT):
    arah = -1.0 if rata == TA.MIDDLE_LEFT else 1.0
    x_belok = x_txt + arah * 95.0 * s
    _garis(msp, p_target, (x_belok, y_txt), "A-ANNO-SYMB", color=2)
    _garis(msp, (x_belok, y_txt), (x_txt, y_txt), "A-ANNO-SYMB", color=2)
    msp.add_circle(p_target, radius=16.0 * s, dxfattribs={"layer": "A-ANNO-SYMB", "color": 2})
    _teks(msp, label, (x_txt - arah * 30.0 * s, y_txt), tinggi=48.0 * s, rata=rata, color=2)


def _kuadran_batu_kali(msp, rumah, qx0: float, qy0: float, qx1: float, qy1: float) -> None:
    """Kuadran 1 (Kiri Atas): Detail Pondasi Batu Kali & Sloof."""
    qw, qh = qx1 - qx0, qy1 - qy0
    s = min(qw / 2300.0, qh / 2250.0)
    cx = qx0 + qw * 0.32
    y_nol = qy0 + qh * 0.68

    st = rumah.struktur or {}
    pnd = st.get("pondasi", {"lebar_bawah": 600, "lebar_atas": 300, "tinggi": 650})
    lb_bwh = float(pnd.get("lebar_bawah", 600.0)) * s
    lb_ats = float(pnd.get("lebar_atas", 300.0)) * s
    t_pnd = min(float(pnd.get("tinggi", 650.0)), 650.0) * s
    sloof_def = [150, 200] if getattr(rumah, "jumlah_lantai", 1) == 1 else [200, 300]
    sloof = st.get("sloof", sloof_def)
    sw, sh = float(sloof[0]) * s, float(sloof[1]) * s

    y_top_pnd = y_nol - sh
    y_bot_pnd = y_top_pnd - t_pnd

    _poly(msp, [(cx - lb_bwh / 2 - 100 * s, y_bot_pnd - 180 * s), (cx + lb_bwh / 2 + 100 * s, y_bot_pnd - 180 * s),
                (cx + lb_bwh / 2 + 100 * s, y_bot_pnd - 130 * s), (cx - lb_bwh / 2 - 100 * s, y_bot_pnd - 130 * s)], "S-FNDN")
    _poly(msp, [(cx - lb_bwh / 2 - 100 * s, y_bot_pnd - 130 * s), (cx + lb_bwh / 2 + 100 * s, y_bot_pnd - 130 * s),
                (cx + lb_bwh / 2 + 100 * s, y_bot_pnd), (cx - lb_bwh / 2 - 100 * s, y_bot_pnd)], "S-FNDN")

    pnd_pts = [(cx - lb_bwh / 2, y_bot_pnd), (cx + lb_bwh / 2, y_bot_pnd), (cx + lb_ats / 2, y_top_pnd), (cx - lb_ats / 2, y_top_pnd)]
    _poly(msp, pnd_pts, "S-FNDN")
    _arsir(msp, pnd_pts, "GRAVEL", 18.0 * s, "S-FNDN")

    sl_pts = [(cx - sw / 2, y_top_pnd), (cx + sw / 2, y_top_pnd), (cx + sw / 2, y_nol), (cx - sw / 2, y_nol)]
    _poly(msp, sl_pts, "S-COLS", color=1)
    _arsir(msp, sl_pts, "AR-CONC", 12.0 * s, "S-COLS", color=1)
    for dx_b in (-sw * 0.28, sw * 0.28):
        for dy_b in (y_top_pnd + 30 * s, y_nol - 30 * s):
            msp.add_circle((cx + dx_b, dy_b), radius=12 * s, dxfattribs={"layer": "S-COLS", "color": 1})

    dw = 150.0 * s
    d_pts = [(cx - dw / 2, y_nol), (cx + dw / 2, y_nol), (cx + dw / 2, y_nol + 460 * s), (cx - dw / 2, y_nol + 460 * s)]
    _poly(msp, d_pts, "A-WALL")
    _arsir(msp, d_pts, "ANSI31", 18.0 * s, "A-WALL-PATT")
    _garis(msp, (cx + dw / 2, y_nol), (cx + lb_bwh / 2 + 140 * s, y_nol), "A-WALL")
    _garis(msp, (cx - lb_bwh / 2 - 140 * s, y_nol - 150 * s), (cx - dw / 2, y_nol - 150 * s), "A-WALL")

    x_lbl = cx + lb_bwh / 2 + 210 * s
    _callout(msp, (cx + dw / 2, y_nol + 300 * s), x_lbl, y_nol + 340 * s, "DINDING BATA 1:4", s)
    _callout(msp, (cx + dw / 2 + 70 * s, y_nol), x_lbl, y_nol + 100 * s, "LANTAI KERAMIK ±0.00", s)
    _callout(msp, (cx + sw / 2, y_nol - sh / 2), x_lbl, y_nol - 130 * s, f"SLOOF {int(sloof[0])}/{int(sloof[1])} (4Ø12)", s)
    _callout(msp, (cx + (lb_bwh + lb_ats) / 4, (y_top_pnd + y_bot_pnd) / 2), x_lbl, (y_top_pnd + y_bot_pnd) / 2 + 20 * s, "PONDASI BATU KALI 1:4", s)
    _callout(msp, (cx + lb_bwh / 2 + 50 * s, y_bot_pnd - 65 * s), x_lbl, y_bot_pnd - 65 * s, "AANSTAMPING 15 cm", s)

    cx_j = (qx0 + qx1) / 2.0
    _teks(msp, "DETAIL PONDASI BATU KALI", (cx_j, qy0 + 130 * s), tinggi=78.0 * s, color=2)
    _teks(msp, "Skala 1 : 20", (cx_j, qy0 + 42 * s), tinggi=58.0 * s, color=2)


def _kuadran_kolom_praktis(msp, rumah, qx0: float, qy0: float, qx1: float, qy1: float) -> None:
    """Kuadran 2 (Kanan Atas - Mode 1 Lantai): Detail Kolom Praktis KP 15/15 & Penulangan."""
    qw, qh = qx1 - qx0, qy1 - qy0
    s = min(qw / 2450.0, qh / 2300.0)
    st = rumah.struktur or {}
    kol = st.get("kolom", [150, 150])
    kw, kh = int(kol[0]), int(kol[1])

    # Kiri: Potongan Vertikal Kolom Praktis & Pertemuan Sloof + Angkur Bata
    cx1 = qx0 + qw * 0.26
    y_bot = qy0 + qh * 0.25
    y_sl_top = y_bot + 260 * s
    y_top = qy0 + qh * 0.84
    hw = 110 * s

    # Sloof bawah
    _poly(msp, [(cx1 - 420 * s, y_bot), (cx1 + 420 * s, y_bot), (cx1 + 420 * s, y_sl_top), (cx1 - 420 * s, y_sl_top)], "S-COLS", color=1)
    # Dinding bata kiri-kanan + kolom praktis tengah
    _poly(msp, [(cx1 - 420 * s, y_sl_top), (cx1 - hw, y_sl_top), (cx1 - hw, y_top), (cx1 - 420 * s, y_top)], "A-WALL")
    _arsir(msp, [(cx1 - 420 * s, y_sl_top), (cx1 - hw, y_sl_top), (cx1 - hw, y_top), (cx1 - 420 * s, y_top)], "ANSI31", 18.0 * s, "A-WALL-PATT")
    _poly(msp, [(cx1 + hw, y_sl_top), (cx1 + 420 * s, y_sl_top), (cx1 + 420 * s, y_top), (cx1 + hw, y_top)], "A-WALL")
    _arsir(msp, [(cx1 + hw, y_sl_top), (cx1 + 420 * s, y_sl_top), (cx1 + 420 * s, y_top), (cx1 + hw, y_top)], "ANSI31", 18.0 * s, "A-WALL-PATT")

    _poly(msp, [(cx1 - hw, y_sl_top), (cx1 + hw, y_sl_top), (cx1 + hw, y_top), (cx1 - hw, y_top)], "S-COLS", color=1)
    # Tulangan vertikal kolom praktis (berkait di sloof) + begel Ø6-150
    _poly(msp, [(cx1 - 190 * s, y_bot + 60 * s), (cx1 - 75 * s, y_bot + 60 * s), (cx1 - 75 * s, y_top)], "A-ANNO-TEXT", tutup=False, color=2)
    _poly(msp, [(cx1 + 190 * s, y_bot + 60 * s), (cx1 + 75 * s, y_bot + 60 * s), (cx1 + 75 * s, y_top)], "A-ANNO-TEXT", tutup=False, color=2)
    for ib in range(7):
        yb = y_sl_top + 90 * s + ib * 150 * s
        if yb < y_top - 40 * s:
            _garis(msp, (cx1 - 75 * s, yb), (cx1 + 75 * s, yb), "A-ANNO-TEXT", color=2)
    # Stek / angkur Ø8 tiap 6 lapis bata
    for ya in (y_sl_top + 320 * s, y_sl_top + 770 * s):
        _garis(msp, (cx1 - 280 * s, ya), (cx1 + 280 * s, ya), "A-ANNO-TEXT", color=3)

    # Kanan: Penampang Melintang Kolom Praktis 15x15 cm
    cx2 = qx0 + qw * 0.68
    cy2 = qy0 + qh * 0.56
    bx = 240 * s
    _poly(msp, [(cx2 - bx, cy2 - bx), (cx2 + bx, cy2 - bx), (cx2 + bx, cy2 + bx), (cx2 - bx, cy2 + bx)], "S-COLS", color=1)
    _arsir(msp, [(cx2 - bx, cy2 - bx), (cx2 + bx, cy2 - bx), (cx2 + bx, cy2 + bx), (cx2 - bx, cy2 + bx)], "AR-CONC", 14.0 * s, "S-COLS", color=1)
    bi = bx - 45 * s
    _poly(msp, [(cx2 - bi, cy2 - bi), (cx2 + bi, cy2 - bi), (cx2 + bi, cy2 + bi), (cx2 - bi, cy2 + bi)], "A-ANNO-TEXT", color=2)
    for sx in (-bi + 22 * s, bi - 22 * s):
        for sy in (-bi + 22 * s, bi - 22 * s):
            msp.add_circle((cx2 + sx, cy2 + sy), radius=20 * s, dxfattribs={"layer": "A-ANNO-TEXT", "color": 2})

    _callout(msp, (cx2 + bi - 22 * s, cy2 + bi - 22 * s), cx2 + bx + 110 * s, cy2 + 190 * s, "TUL. POKOK 4Ø10", s)
    _callout(msp, (cx2 + bi, cy2), cx2 + bx + 110 * s, cy2, "BEGEL Ø6 - 150", s)
    _callout(msp, (cx2 + bx, cy2 - 140 * s), cx2 + bx + 110 * s, cy2 - 190 * s, f"BETON K-175 ({kw}×{kh})", s)
    _teks(msp, f"PENAMPANG KP {kw}×{kh} cm", (cx2, cy2 - bx - 130 * s), tinggi=52.0 * s, color=3)

    cx_j = (qx0 + qx1) / 2.0
    _teks(msp, f"DETAIL KOLOM PRAKTIS ({kw}/{kh})", (cx_j, qy0 + 130 * s), tinggi=78.0 * s, color=2)
    _teks(msp, "Skala 1 : 20", (cx_j, qy0 + 42 * s), tinggi=58.0 * s, color=2)


def _kuadran_ring_balk(msp, rumah, qx0: float, qy0: float, qx1: float, qy1: float) -> None:
    """Kuadran 3 (Kiri Bawah - Mode 1 Lantai): Detail Ring Balk & Tumpuan Kuda-Kuda Baja Ringan."""
    qw, qh = qx1 - qx0, qy1 - qy0
    s = min(qw / 2300.0, qh / 2150.0)
    cx = qx0 + qw * 0.34
    y_rb = qy0 + qh * 0.48

    st = rumah.struktur or {}
    rb = st.get("ring_balok", [150, 150])
    rw, rh = float(rb[0]) * s * 1.35, float(rb[1]) * s * 1.35
    dw = rw

    # Dinding bata di bawah ring balk
    d_pts = [(cx - dw / 2, y_rb - 460 * s), (cx + dw / 2, y_rb - 460 * s), (cx + dw / 2, y_rb), (cx - dw / 2, y_rb)]
    _poly(msp, d_pts, "A-WALL")
    _arsir(msp, d_pts, "ANSI31", 18.0 * s, "A-WALL-PATT")

    # Ring Balk beton bertulang
    rb_pts = [(cx - rw / 2, y_rb), (cx + rw / 2, y_rb), (cx + rw / 2, y_rb + rh), (cx - rw / 2, y_rb + rh)]
    _poly(msp, rb_pts, "S-COLS", color=1)
    _arsir(msp, rb_pts, "AR-CONC", 12.0 * s, "S-COLS", color=1)
    for dx_b in (-rw * 0.28, rw * 0.28):
        for dy_b in (y_rb + 32 * s, y_rb + rh - 32 * s):
            msp.add_circle((cx + dx_b, dy_b), radius=13 * s, dxfattribs={"layer": "A-ANNO-TEXT", "color": 2})

    # Kuda-kuda baja ringan (batang bawah & kaki kuda-kuda miring) + atap
    y_kk = y_rb + rh
    _poly(msp, [(cx - 320 * s, y_kk), (cx + 460 * s, y_kk), (cx + 460 * s, y_kk + 75 * s), (cx - 320 * s, y_kk + 75 * s)], "A-GLAZ", color=4)
    _poly(msp, [(cx - 320 * s, y_kk), (cx + 460 * s, y_kk + 430 * s), (cx + 460 * s, y_kk + 505 * s), (cx - 320 * s, y_kk + 75 * s)], "A-GLAZ", color=4)
    # Garis penutup atap genteng metal di atas kaki kuda-kuda
    _garis(msp, (cx - 420 * s, y_kk + 45 * s), (cx + 480 * s, y_kk + 545 * s), "A-DOOR", color=1)

    x_lbl = cx + 520 * s
    _callout(msp, (cx + 220 * s, y_kk + 400 * s), x_lbl, y_kk + 430 * s, "PENUTUP GENTENG METAL", s)
    _callout(msp, (cx + 180 * s, y_kk + 280 * s), x_lbl, y_kk + 230 * s, "KUDA-KUDA BAJA RINGAN C75", s)
    _callout(msp, (cx + rw / 2, y_rb + rh / 2), x_lbl, y_rb + 30 * s, f"RING BALK {int(rb[0])}/{int(rb[1])} (4Ø10)", s)
    _callout(msp, (cx + dw / 2, y_rb - 240 * s), x_lbl, y_rb - 220 * s, "DINDING BATA 1:4", s)

    cx_j = (qx0 + qx1) / 2.0
    _teks(msp, "DETAIL RING BALK & TUMPUAN ATAP", (cx_j, qy0 + 130 * s), tinggi=78.0 * s, color=2)
    _teks(msp, "Skala 1 : 20", (cx_j, qy0 + 42 * s), tinggi=58.0 * s, color=2)


def _kuadran_footplat(msp, qx0: float, qy0: float, qx1: float, qy1: float) -> None:
    """Kuadran 2 (Kanan Atas - Mode 2 Lantai): Detail Penulangan Footplat K-250."""
    qw, qh = qx1 - qx0, qy1 - qy0
    s = min(qw / 2700.0, qh / 2650.0)

    cx1 = qx0 + qw * 0.27
    y_fp = qy0 + qh * 0.24

    _poly(msp, [(cx1 - 540 * s, y_fp - 120 * s), (cx1 + 540 * s, y_fp - 120 * s), (cx1 + 540 * s, y_fp - 50 * s), (cx1 - 540 * s, y_fp - 50 * s)], "S-FNDN", color=8)
    _arsir(msp, [(cx1 - 540 * s, y_fp - 120 * s), (cx1 + 540 * s, y_fp - 120 * s), (cx1 + 540 * s, y_fp - 50 * s), (cx1 - 540 * s, y_fp - 50 * s)], "GRAVEL", 12.0 * s, "S-FNDN", color=8)
    _poly(msp, [(cx1 - 540 * s, y_fp - 50 * s), (cx1 + 540 * s, y_fp - 50 * s), (cx1 + 540 * s, y_fp), (cx1 - 540 * s, y_fp)], "S-FNDN", color=4)

    fp_pts = [
        (cx1 - 500 * s, y_fp),
        (cx1 + 500 * s, y_fp),
        (cx1 + 500 * s, y_fp + 240 * s),
        (cx1 + 150 * s, y_fp + 340 * s),
        (cx1 - 150 * s, y_fp + 340 * s),
        (cx1 - 500 * s, y_fp + 240 * s),
    ]
    _poly(msp, fp_pts, "S-COLS", color=1)

    y_sl_bot = y_fp + 1350 * s
    y_sl_top = y_sl_bot + 300 * s
    _garis(msp, (cx1 - 125 * s, y_fp + 340 * s), (cx1 - 125 * s, y_sl_bot), "S-COLS", color=1)
    _garis(msp, (cx1 + 125 * s, y_fp + 340 * s), (cx1 + 125 * s, y_sl_bot), "S-COLS", color=1)
    _garis(msp, (cx1 - 460 * s, y_sl_bot), (cx1 - 125 * s, y_sl_bot), "S-COLS", color=1)
    _garis(msp, (cx1 + 125 * s, y_sl_bot), (cx1 + 460 * s, y_sl_bot), "S-COLS", color=1)
    _garis(msp, (cx1 - 460 * s, y_sl_top), (cx1 - 125 * s, y_sl_top), "S-COLS", color=1)
    _garis(msp, (cx1 + 125 * s, y_sl_top), (cx1 + 460 * s, y_sl_top), "S-COLS", color=1)
    _garis(msp, (cx1 - 125 * s, y_sl_top), (cx1 - 125 * s, y_sl_top + 240 * s), "S-COLS", color=1)
    _garis(msp, (cx1 + 125 * s, y_sl_top), (cx1 + 125 * s, y_sl_top + 240 * s), "S-COLS", color=1)

    for side in (-1.0, 1.0):
        for ig in range(1, 5):
            xg = cx1 + side * (125 * s + ig * 72 * s)
            y_b = y_fp + 340 * s - (ig * 72 * s / 350.0) * 100 * s
            _garis(msp, (xg, y_b), (xg, y_sl_bot), "A-WALL-PATT", color=8)

    _poly(msp, [(cx1 - 460 * s, y_fp + 130 * s), (cx1 - 460 * s, y_fp + 40 * s), (cx1 + 460 * s, y_fp + 40 * s), (cx1 + 460 * s, y_fp + 130 * s)], "A-ANNO-TEXT", tutup=False, color=2)
    _poly(msp, [(cx1 - 460 * s, y_fp + 140 * s), (cx1 - 460 * s, y_fp + 210 * s), (cx1 - 150 * s, y_fp + 300 * s),
                (cx1 + 150 * s, y_fp + 300 * s), (cx1 + 460 * s, y_fp + 210 * s), (cx1 + 460 * s, y_fp + 140 * s)], "A-ANNO-TEXT", tutup=False, color=2)
    for ix in range(-3, 4):
        msp.add_circle((cx1 + ix * 125 * s, y_fp + 62 * s), radius=12 * s, dxfattribs={"layer": "A-ANNO-TEXT", "color": 2})

    _poly(msp, [(cx1 - 210 * s, y_fp + 75 * s), (cx1 - 90 * s, y_fp + 75 * s), (cx1 - 90 * s, y_sl_top + 240 * s)], "A-ANNO-TEXT", tutup=False, color=2)
    _poly(msp, [(cx1 + 210 * s, y_fp + 75 * s), (cx1 + 90 * s, y_fp + 75 * s), (cx1 + 90 * s, y_sl_top + 240 * s)], "A-ANNO-TEXT", tutup=False, color=2)
    for ks in range(11):
        ys = y_fp + 360 * s + ks * 135 * s
        _garis(msp, (cx1 - 90 * s, ys), (cx1 + 90 * s, ys), "A-ANNO-TEXT", color=2)

    _garis(msp, (cx1 - 460 * s, y_sl_bot + 35 * s), (cx1 + 460 * s, y_sl_bot + 35 * s), "A-ANNO-TEXT", color=2)
    _garis(msp, (cx1 - 460 * s, y_sl_top - 35 * s), (cx1 + 460 * s, y_sl_top - 35 * s), "A-ANNO-TEXT", color=2)
    _teks(msp, "100 cm", (cx1, y_fp - 195 * s), tinggi=50.0 * s, color=3)

    cx2 = qx0 + qw * 0.72
    cy2 = qy0 + qh * 0.56
    hf = 460 * s
    hc = 115 * s
    _poly(msp, [(cx2 - hf, cy2 - hf), (cx2 + hf, cy2 - hf), (cx2 + hf, cy2 + hf), (cx2 - hf, cy2 + hf)], "S-COLS", color=1)
    _poly(msp, [(cx2 - hc, cy2 - hc), (cx2 + hc, cy2 - hc), (cx2 + hc, cy2 + hc), (cx2 - hc, cy2 + hc)], "S-COLS", color=1)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        _garis(msp, (cx2 + sx * hc, cy2 + sy * hc), (cx2 + sx * hf, cy2 + sy * hf), "S-COLS", color=1)

    for idx_t in (-2, -1, 1, 2):
        off = idx_t * 145 * s
        _garis(msp, (cx2 - hf + 40 * s, cy2 + off), (cx2 + hf - 40 * s, cy2 + off), "A-ANNO-TEXT", color=2)
        _garis(msp, (cx2 + off, cy2 - hf + 40 * s), (cx2 + off, cy2 + hf - 40 * s), "A-ANNO-TEXT", color=2)

    _callout(msp, (cx2 + 145 * s, cy2 + 290 * s), cx2 + 300 * s, cy2 + hf + 120 * s, "TUL. ATAS Ø10-150", s)
    _callout(msp, (cx2 + 290 * s, cy2 - 145 * s), cx2 + 300 * s, cy2 - hf - 90 * s, "TUL. BAWAH Ø13-150", s)
    _callout(msp, (cx2 + hc, cy2), cx2 + 300 * s, cy2 + 40 * s, "KOLOM 25/25 (8Ø13)", s)
    _teks(msp, "DENAH FOOTPLAT 100×100", (cx2, cy2 - hf - 210 * s), tinggi=52.0 * s, color=3)

    cx_j = (qx0 + qx1) / 2.0
    _teks(msp, "DETAIL TULANGAN FOOTPLAT K-250", (cx_j, qy0 + 130 * s), tinggi=78.0 * s, color=2)
    _teks(msp, "Skala 1 : 20", (cx_j, qy0 + 42 * s), tinggi=58.0 * s, color=2)


def _kuadran_pelat_balok(msp, qx0: float, qy0: float, qx1: float, qy1: float) -> None:
    """Kuadran 3 (Kiri Bawah - Mode 2 Lantai): Detail Pertemuan Pelat Lantai 2 & Balok Induk."""
    qw, qh = qx1 - qx0, qy1 - qy0
    s = min(qw / 2200.0, qh / 2050.0)
    cx = qx0 + qw * 0.36
    y_pl = qy0 + qh * 0.62

    pl_pts = [(cx - 560 * s, y_pl - 120 * s), (cx + 560 * s, y_pl - 120 * s), (cx + 560 * s, y_pl), (cx - 560 * s, y_pl)]
    _poly(msp, pl_pts, "S-COLS", color=1)
    _arsir(msp, pl_pts, "AR-CONC", 14.0 * s, "S-COLS", color=1)
    _poly(msp, [(cx - 560 * s, y_pl), (cx + 560 * s, y_pl), (cx + 560 * s, y_pl + 35 * s), (cx - 560 * s, y_pl + 35 * s)], "A-WALL", color=4)

    bi_pts = [(cx - 100 * s, y_pl - 350 * s), (cx + 100 * s, y_pl - 350 * s), (cx + 100 * s, y_pl - 120 * s), (cx - 100 * s, y_pl - 120 * s)]
    _poly(msp, bi_pts, "S-COLS", color=1)
    _arsir(msp, bi_pts, "AR-CONC", 14.0 * s, "S-COLS", color=1)
    for dx_b in (-65 * s, 0.0, 65 * s):
        for dy_b in (y_pl - 315 * s, y_pl - 155 * s):
            msp.add_circle((cx + dx_b, dy_b), radius=11 * s, dxfattribs={"layer": "S-COLS", "color": 2})

    x_lbl = cx + 620 * s
    _callout(msp, (cx + 350 * s, y_pl + 20 * s), x_lbl, y_pl + 220 * s, "KERAMIK 60×60 + SPESI", s)
    _callout(msp, (cx + 420 * s, y_pl - 60 * s), x_lbl, y_pl - 40 * s, "PELAT LT.2 t=12 cm (Ø10-150)", s)
    _callout(msp, (cx + 100 * s, y_pl - 240 * s), x_lbl, y_pl - 310 * s, "BALOK INDUK 20/35 (6Ø13)", s)

    cx_j = (qx0 + qx1) / 2.0
    _teks(msp, "DETAIL PELAT LT.2 & BALOK INDUK", (cx_j, qy0 + 130 * s), tinggi=78.0 * s, color=2)
    _teks(msp, "Skala 1 : 20", (cx_j, qy0 + 42 * s), tinggi=58.0 * s, color=2)


def _kuadran_kusen(msp, qx0: float, qy0: float, qx1: float, qy1: float) -> None:
    """Kuadran 4 (Kanan Bawah): Detail Kusen Pintu Utama (P1) & Jendela (J1)."""
    qw, qh = qx1 - qx0, qy1 - qy0
    s = min(qw / 2550.0, qh / 2550.0)
    y_base = qy0 + qh * 0.18

    pw, ph, kw = 900.0 * s, 2100.0 * s, 60.0 * s
    xp = qx0 + qw * 0.12
    _poly(msp, [(xp, y_base), (xp + pw, y_base), (xp + pw, y_base + ph), (xp, y_base + ph)], "A-DOOR", color=1)
    _poly(msp, [(xp + kw, y_base), (xp + pw - kw, y_base), (xp + pw - kw, y_base + ph - kw), (xp + kw, y_base + ph - kw)], "A-DOOR", color=1)
    _garis(msp, (xp - 90 * s, y_base + ph), (xp + pw + 90 * s, y_base + ph), "A-DOOR", color=1)
    _poly(msp, [(xp + kw + 90 * s, y_base + 1050 * s), (xp + pw - kw - 90 * s, y_base + 1050 * s),
                (xp + pw - kw - 90 * s, y_base + ph - kw - 120 * s), (xp + kw + 90 * s, y_base + ph - kw - 120 * s)], "A-DOOR", color=1)
    _poly(msp, [(xp + kw + 90 * s, y_base + 160 * s), (xp + pw - kw - 90 * s, y_base + 160 * s),
                (xp + pw - kw - 90 * s, y_base + 920 * s), (xp + kw + 90 * s, y_base + 920 * s)], "A-DOOR", color=1)
    _teks(msp, "KUSEN PINTU P1", (xp + pw / 2.0, y_base - 95 * s), tinggi=62.0 * s, color=2)
    _teks(msp, "90 × 210 cm", (xp + pw / 2.0, y_base - 170 * s), tinggi=52.0 * s, color=3)

    jw, jh = 1150.0 * s, 1300.0 * s
    xj = xp + pw + 260.0 * s
    yj = y_base + 650.0 * s
    _poly(msp, [(xj, yj), (xj + jw, yj), (xj + jw, yj + jh), (xj, yj + jh)], "A-GLAZ", color=4)
    _poly(msp, [(xj + kw, yj + kw), (xj + jw - kw, yj + kw), (xj + jw - kw, yj + jh - kw), (xj + kw, yj + jh - kw)], "A-GLAZ", color=4)
    xm = xj + jw / 2.0
    _poly(msp, [(xm - 25 * s, yj + kw), (xm + 25 * s, yj + kw), (xm + 25 * s, yj + jh - kw), (xm - 25 * s, yj + jh - kw)], "A-GLAZ", color=4)
    _garis(msp, (xj - 90 * s, yj + jh), (xj + jw + 90 * s, yj + jh), "A-GLAZ", color=4)
    _garis(msp, (xj - 90 * s, yj), (xj + jw + 90 * s, yj), "A-GLAZ", color=4)
    _teks(msp, "KUSEN JENDELA J1", (xj + jw / 2.0, y_base - 95 * s), tinggi=62.0 * s, color=2)
    _teks(msp, "120 × 130 cm", (xj + jw / 2.0, y_base - 170 * s), tinggi=52.0 * s, color=3)

    cx_j = (qx0 + qx1) / 2.0
    _teks(msp, "DETAIL KUSEN PINTU & JENDELA (Skala 1 : 20)", (cx_j, qy0 + 42 * s), tinggi=68.0 * s, color=2)


def gambar_detail(
    rumah,
    msp,
    ox: float = 0.0,
    oy: float = 0.0,
    skala_label: str = "1 : 20",
    viewport: Optional[Tuple[float, float, float, float]] = None,
    **kwargs,
) -> Tuple[float, float, float, float]:
    _siapkan_layer_detail(msp.doc)
    if viewport is not None:
        vx0, vy0, vx1, vy1 = viewport
    else:
        vx0, vy0, vx1, vy1 = (ox, oy, ox + 15000.0, oy + 12000.0)

    mid_x = (vx0 + vx1) / 2.0
    mid_y = (vy0 + vy1) / 2.0
    pad = (vx1 - vx0) * 0.02

    _garis(msp, (mid_x, vy0 + pad), (mid_x, vy1 - pad), "A-ANNO-SYMB", color=8)
    _garis(msp, (vx0 + pad, mid_y), (vx1 - pad, mid_y), "A-ANNO-SYMB", color=8)

    _kuadran_batu_kali(msp, rumah, vx0 + pad, mid_y + pad, mid_x - pad, vy1 - pad)
    if getattr(rumah, "jumlah_lantai", 1) >= 2:
        _kuadran_footplat(msp, mid_x + pad, mid_y + pad, vx1 - pad, vy1 - pad)
        _kuadran_pelat_balok(msp, vx0 + pad, vy0 + pad, mid_x - pad, mid_y - pad)
    else:
        _kuadran_kolom_praktis(msp, rumah, mid_x + pad, mid_y + pad, vx1 - pad, vy1 - pad)
        _kuadran_ring_balk(msp, rumah, vx0 + pad, vy0 + pad, mid_x - pad, mid_y - pad)
    _kuadran_kusen(msp, mid_x + pad, vy0 + pad, vx1 - pad, mid_y - pad)

    return (vx0, vy0, vx1, vy1)