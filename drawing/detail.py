"""
Lembar Detail Arsitektur & Struktur (Skala 1 : 20) — ARS-08.
Berisi:
1. Detail Pondasi Batu Kali & Sloof Beton (Skala 1 : 20)
2. Detail Penampang Kolom Praktis & Ring Balok (Skala 1 : 20)
3. Detail & Jadwal Tipe Kusen Pintu / Jendela (Skala 1 : 20)
"""
from collections import OrderedDict
from typing import Dict, List, Tuple

from ezdxf.enums import TextEntityAlignment as TA

from drawing.kop import hitung_viewport_kop


def _poly(msp, pts, layer, tutup=True, color=None):
    attr = {"layer": layer}
    if color is not None:
        attr["color"] = color
    return msp.add_lwpolyline(pts, close=tutup, dxfattribs=attr)


def _garis(msp, p1, p2, layer="A-ANNO-TEXT", color=None):
    attr = {"layer": layer}
    if color is not None:
        attr["color"] = color
    return msp.add_line(p1, p2, dxfattribs=attr)


def _arsir(msp, pts, pola, skala, layer, color=256):
    h = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    if str(pola).upper() == "SOLID":
        h.set_solid_fill()
    else:
        h.set_pattern_fill(pola, scale=skala)
    h.paths.add_polyline_path(pts, is_closed=True)


def _teks(msp, isi, pos, tinggi=55.0, rata=TA.LEFT, layer="A-ANNO-TEXT", color=None):
    style_name = "KOP_FONT" if "KOP_FONT" in msp.doc.styles else "Standard"
    attr = {"layer": layer, "style": style_name}
    if color is not None:
        attr["color"] = color
    msp.add_text(isi, height=tinggi, dxfattribs=attr).set_placement(pos, align=rata)


def _penunjuk(msp, target, awal, label, tinggi=48.0):
    _garis(msp, awal, target, "A-ANNO-TEXT")
    msp.add_circle(target, radius=12.0, dxfattribs={"layer": "A-ANNO-TEXT"})
    _teks(msp, label, (awal[0] + 35.0, awal[1] - tinggi * 0.35), tinggi=tinggi, rata=TA.LEFT)


def _dim_garis_h(msp, x1, x2, y_ref, y_dim, label, tinggi=46.0):
    _garis(msp, (x1, y_ref), (x1, y_dim - 25), "A-ANNO-DIMS")
    _garis(msp, (x2, y_ref), (x2, y_dim - 25), "A-ANNO-DIMS")
    _garis(msp, (x1 - 25, y_dim), (x2 + 25, y_dim), "A-ANNO-DIMS")
    for xp in (x1, x2):
        _garis(msp, (xp - 18, y_dim - 18), (xp + 18, y_dim + 18), "A-ANNO-DIMS")
    _teks(msp, label, ((x1 + x2) / 2.0, y_dim + 22), tinggi=tinggi, rata=TA.BOTTOM_CENTER, layer="A-ANNO-DIMS")


def _dim_garis_v(msp, x_ref, y1, y2, x_dim, label, tinggi=46.0):
    _garis(msp, (x_ref, y1), (x_dim - 25, y1), "A-ANNO-DIMS")
    _garis(msp, (x_ref, y2), (x_dim - 25, y2), "A-ANNO-DIMS")
    _garis(msp, (x_dim, y1 - 25), (x_dim, y2 + 25), "A-ANNO-DIMS")
    for yp in (y1, y2):
        _garis(msp, (x_dim - 18, yp - 18), (x_dim + 18, yp + 18), "A-ANNO-DIMS")
    _teks(msp, label, (x_dim - 28, (y1 + y2) / 2.0), tinggi=tinggi, rata=TA.MIDDLE_RIGHT, layer="A-ANNO-DIMS")


def _judul_detail(msp, judul, subjudul, cx, y):
    _teks(msp, judul, (cx, y), tinggi=85.0, rata=TA.MIDDLE_CENTER, layer="A-ANNO-KOP-ACCENT")
    _garis(msp, (cx - 750, y - 55), (cx + 750, y - 55), "A-ANNO-TEXT")
    _teks(msp, subjudul, (cx, y - 115), tinggi=52.0, rata=TA.MIDDLE_CENTER, layer="A-ANNO-TEXT")


def _gambar_detail_pondasi(msp, rumah, cx: float, y_lantai: float):
    """Detail Pondasi Batu Kali & Sloof (1:1 mm, disajikan pada lembar skala 1:20)."""
    st = rumah.struktur
    pf = st.get("pondasi", {})
    sl = st.get("sloof", [150, 200])

    t = float(rumah.dinding_default.get("tebal", 150))
    lb = float(pf.get("lebar_bawah", 600))
    la = float(pf.get("lebar_atas", 300))
    tp = float(pf.get("tinggi", 700))
    bs = float(sl[0])
    hs = float(sl[1])
    z_tanah = -400.0

    y_sloof_bwh = y_lantai - hs
    y_pond_bwh = y_sloof_bwh - tp
    y_aanst_bwh = y_pond_bwh - 150.0
    y_pasir_bwh = y_aanst_bwh - 50.0

    # 1. Pasir Urug t=50 mm
    pts_pasir = [(cx - lb / 2, y_pasir_bwh), (cx + lb / 2, y_pasir_bwh),
                 (cx + lb / 2, y_aanst_bwh), (cx - lb / 2, y_aanst_bwh)]
    _poly(msp, pts_pasir, "S-PONDASI")
    _arsir(msp, pts_pasir, "AR-SAND", 3.0, "S-PONDASI")

    # 2. Aanstamping Batu Kosong t=150 mm
    pts_aanst = [(cx - lb / 2, y_aanst_bwh), (cx + lb / 2, y_aanst_bwh),
                 (cx + lb / 2, y_pond_bwh), (cx - lb / 2, y_pond_bwh)]
    _poly(msp, pts_aanst, "S-PONDASI")
    _arsir(msp, pts_aanst, "GRAVEL", 8.0, "S-PONDASI")

    # 3. Badan Pondasi Batu Kali 1:4
    pts_pond = [(cx - lb / 2, y_pond_bwh), (cx + lb / 2, y_pond_bwh),
                (cx + la / 2, y_sloof_bwh), (cx - la / 2, y_sloof_bwh)]
    _poly(msp, pts_pond, "S-PONDASI")
    _arsir(msp, pts_pond, "ANSI37", 18.0, "S-PONDASI")

    # 4. Sloof Beton Bertulang + Tulangan Utama & Sengkang
    pts_sloof = [(cx - bs / 2, y_sloof_bwh), (cx + bs / 2, y_sloof_bwh),
                 (cx + bs / 2, y_lantai), (cx - bs / 2, y_lantai)]
    _poly(msp, pts_sloof, "S-BETON")
    _arsir(msp, pts_sloof, "AR-CONC", 1.0, "S-BETON")

    selimut = 22.0
    _poly(msp, [
        (cx - bs / 2 + selimut, y_sloof_bwh + selimut),
        (cx + bs / 2 - selimut, y_sloof_bwh + selimut),
        (cx + bs / 2 - selimut, y_lantai - selimut),
        (cx - bs / 2 + selimut, y_lantai - selimut),
    ], "S-COLS", color=1)
    for bx in (cx - bs / 2 + selimut + 8, cx + bs / 2 - selimut - 8):
        for by in (y_sloof_bwh + selimut + 8, y_lantai - selimut - 8):
            msp.add_circle((bx, by), radius=7.0, dxfattribs={"layer": "S-COLS", "color": 1})

    # 5. Dinding Bata & Lantai Keramik
    pts_dinding = [(cx - t / 2, y_lantai), (cx + t / 2, y_lantai),
                   (cx + t / 2, y_lantai + 550), (cx - t / 2, y_lantai + 550)]
    _poly(msp, pts_dinding, "A-SECT-WALL")
    _arsir(msp, pts_dinding, "ANSI31", 15.0, "A-WALL-PATT")

    for arah in (-1, 1):
        x0 = cx + arah * (t / 2)
        x1 = cx + arah * 620.0
        xa, xb = sorted([x0, x1])
        pts_lt = [(xa, y_lantai - 100), (xb, y_lantai - 100), (xb, y_lantai), (xa, y_lantai)]
        _poly(msp, pts_lt, "A-SECT-WALL")
        _arsir(msp, pts_lt, "AR-SAND", 3.0, "A-SECT-WALL")

    # 6. Garis Muka Tanah Asli
    yt = y_lantai + z_tanah
    _garis(msp, (cx - 720, yt), (cx - lb / 2 - 40, yt), "A-GROUND")
    _garis(msp, (cx + lb / 2 + 40, yt), (cx + 720, yt), "A-GROUND")

    # 7. Dimensi Ukur
    _dim_garis_h(msp, cx - lb / 2, cx + lb / 2, y_pasir_bwh, y_pasir_bwh - 130, f"{int(lb)}")
    _dim_garis_h(msp, cx - la / 2, cx + la / 2, y_sloof_bwh, y_pasir_bwh - 250, f"{int(la)}")
    xd = cx - 640
    _dim_garis_v(msp, cx - lb / 2, y_pasir_bwh, y_aanst_bwh, xd, "50")
    _dim_garis_v(msp, cx - lb / 2, y_aanst_bwh, y_pond_bwh, xd, "150")
    _dim_garis_v(msp, cx - lb / 2, y_pond_bwh, y_sloof_bwh, xd, f"{int(tp)}")
    _dim_garis_v(msp, cx - bs / 2, y_sloof_bwh, y_lantai, xd, f"{int(hs)}")

    # 8. Keterangan Penunjuk Kanan
    xk = cx + 680
    _penunjuk(msp, (cx + t / 2, y_lantai + 320), (xk, y_lantai + 360), f"Dinding bata 1:4 t={int(t)} mm")
    _penunjuk(msp, (cx + 350, y_lantai - 40), (xk, y_lantai + 120), "Keramik 40×40 + spesi")
    _penunjuk(msp, (cx + bs / 2, y_lantai - hs / 2), (xk, y_lantai - 130), f"Sloof {int(bs)}/{int(hs)} K-300 (4Ø10)")
    _penunjuk(msp, (cx + la / 2 + 40, y_sloof_bwh - tp * 0.45), (xk, y_sloof_bwh - tp * 0.45), "Pondasi batu kali 1:4")
    _penunjuk(msp, (cx + lb / 2, y_pond_bwh - 75), (xk, y_pond_bwh - 80), "Aanstamping batu t=150")
    _penunjuk(msp, (cx + lb / 2, y_aanst_bwh - 25), (xk, y_aanst_bwh - 240), "Pasir urug padat t=50")

    _judul_detail(msp, "DETAIL PONDASI & SLOOF", "Skala 1 : 20", cx + 180, y_pasir_bwh - 460)


def _gambar_detail_kolom(msp, rumah, cx: float, cy: float):
    """Detail Penampang Kolom Praktis & Ring Balok (disajikan skala visual 1:10 pada lembar)."""
    t = float(rumah.dinding_default.get("tebal", 150))
    # Digambar skala 2x terhadap 1:20 (= 1:10) agar tulangan & selimut beton terbaca jelas
    s = 2.0
    w = t * s
    sel = 20.0 * s

    pts_k = [(cx - w / 2, cy - w / 2), (cx + w / 2, cy - w / 2),
             (cx + w / 2, cy + w / 2), (cx - w / 2, cy + w / 2)]
    _poly(msp, pts_k, "S-BETON")
    _arsir(msp, pts_k, "AR-CONC", 1.2, "S-BETON")

    # Sengkang Ø8-150 + kait 135 derajat
    _poly(msp, [
        (cx - w / 2 + sel, cy - w / 2 + sel),
        (cx + w / 2 - sel, cy - w / 2 + sel),
        (cx + w / 2 - sel, cy + w / 2 - sel),
        (cx - w / 2 + sel, cy + w / 2 - sel),
    ], "S-COLS", color=1)
    _garis(msp, (cx - w / 2 + sel, cy + w / 2 - sel), (cx - w / 2 + sel + 32, cy + w / 2 - sel - 32), "S-COLS", color=1)

    # 4 Tulangan Pokok Ø10
    for bx in (cx - w / 2 + sel + 12, cx + w / 2 - sel - 12):
        for by in (cy - w / 2 + sel + 12, cy + w / 2 - sel - 12):
            msp.add_circle((bx, by), radius=11.0, dxfattribs={"layer": "S-COLS", "color": 1})

    _dim_garis_h(msp, cx - w / 2, cx + w / 2, cy - w / 2, cy - w / 2 - 120, f"{int(t)} mm")
    _dim_garis_v(msp, cx - w / 2, cy - w / 2, cy + w / 2, cx - w / 2 - 120, f"{int(t)} mm")

    xk = cx + w / 2 + 180
    _penunjuk(msp, (cx + w / 2 - sel - 12, cy + w / 2 - sel - 12), (xk, cy + 120), "Tulangan pokok 4 Ø 10 mm")
    _penunjuk(msp, (cx + w / 2 - sel, cy), (xk, cy - 10), "Sengkang Ø 8 - 150 mm")
    _penunjuk(msp, (cx + w / 2, cy - w / 2 + 25), (xk, cy - 140), "Beton K-300 (selimut 20 mm)")

    _judul_detail(msp, "DETAIL PENAMPANG KOLOM PRAKTIS", "Skala 1 : 10", cx + 220, cy - w / 2 - 310)


def _gambar_jadwal_kusen(msp, rumah, x0: float, y_top: float, lebar_area: float):
    """Menggambar rekap dan detail elevasi tiap tipe pintu & jendela dari model rumah."""
    grup = OrderedDict()
    for q in rumah.bukaan:
        if q.jenis == "bukaan":
            continue
        kunci = (q.jenis, int(round(q.lebar)), int(round(q.tinggi)), int(round(q.ambang)), q.bahan or "")
        grup.setdefault(kunci, []).append(q)

    # Urutkan pintu dulu lalu jendela
    items = sorted(grup.items(), key=lambda kv: (0 if kv[0][0] == "pintu" else 1, -kv[0][1]))
    no_p, no_j = 1, 1
    kolom = 2
    lebar_sel = lebar_area / kolom
    tinggi_sel = 2350.0

    for idx, ((jenis, lbr, tgi, amb, bahan), daftar_q) in enumerate(items[:4]):
        if jenis == "pintu":
            kode = f"P{no_p}"
            no_p += 1
            lyr = "A-DOOR"
            bhn_teks = bahan or "Kusen kayu solid + panel"
        else:
            kode = f"J{no_j}"
            no_j += 1
            lyr = "A-GLAZ"
            bhn_teks = bahan or "Kusen aluminium + kaca 5 mm"

        col = idx % kolom
        row = idx // kolom
        cx = x0 + col * lebar_sel + lebar_sel * 0.45
        y_base = y_top - row * tinggi_sel - 1650.0

        # Gambar kusen 1:1 mm (skala 1:20 pada lembar)
        scale_fit = min(1.0, 1450.0 / max(1.0, float(tgi)))
        w = lbr * scale_fit
        h = tgi * scale_fit
        kw = 50.0 * scale_fit

        _poly(msp, [(cx - w / 2, y_base), (cx + w / 2, y_base),
                    (cx + w / 2, y_base + h), (cx - w / 2, y_base + h)], lyr)
        _poly(msp, [(cx - w / 2 + kw, y_base + (0 if jenis == "pintu" else kw)),
                    (cx + w / 2 - kw, y_base + (0 if jenis == "pintu" else kw)),
                    (cx + w / 2 - kw, y_base + h - kw),
                    (cx - w / 2 + kw, y_base + h - kw)], lyr)

        if jenis == "pintu":
            # Panel pintu & garis ayun bukaan
            _poly(msp, [(cx - w / 2 + kw * 2.5, y_base + h * 0.52),
                        (cx + w / 2 - kw * 2.5, y_base + h * 0.52),
                        (cx + w / 2 - kw * 2.5, y_base + h - kw * 2.5),
                        (cx - w / 2 + kw * 2.5, y_base + h - kw * 2.5)], lyr)
            _garis(msp, (cx - w / 2 + kw, y_base + h - kw), (cx + w / 2 - kw, y_base + h * 0.5), lyr)
            _garis(msp, (cx - w / 2 + kw, y_base), (cx + w / 2 - kw, y_base + h * 0.5), lyr)
        else:
            if lbr > 1000:
                _garis(msp, (cx, y_base + kw), (cx, y_base + h - kw), lyr)
            # Garis pantulan kaca
            _garis(msp, (cx - w * 0.18, y_base + h * 0.35), (cx + w * 0.08, y_base + h * 0.65), lyr)
            _garis(msp, (cx - w * 0.05, y_base + h * 0.32), (cx + w * 0.20, y_base + h * 0.62), lyr)

        _dim_garis_h(msp, cx - w / 2, cx + w / 2, y_base, y_base - 110, f"{lbr}")
        _dim_garis_v(msp, cx - w / 2, y_base, y_base + h, cx - w / 2 - 110, f"{tgi}")

        _teks(msp, f"TIPE {kode} ({len(daftar_q)} UNIT)", (cx, y_base - 290), tinggi=62.0, rata=TA.MIDDLE_CENTER, layer="A-ANNO-KOP-ACCENT")
        _teks(msp, f"Ukuran: {lbr} × {tgi} mm", (cx, y_base - 385), tinggi=46.0, rata=TA.MIDDLE_CENTER)
        _teks(msp, bhn_teks[:30], (cx, y_base - 470), tinggi=42.0, rata=TA.MIDDLE_CENTER)

    _judul_detail(msp, "DETAIL & JADWAL KUSEN PINTU / JENDELA", "Skala 1 : 20", x0 + lebar_area * 0.46, y_top - 4780.0)


def gambar_lembar_detail(rumah, msp, ox: float, oy: float, skala_num: int = 20) -> Tuple[float, float, float, float]:
    """Menggambar seluruh konten lembar detail pondasi, kolom, dan kusen di dalam viewport A3."""
    vx0, vy0, vx1, vy1 = hitung_viewport_kop(ox, oy, skala_num=skala_num)

    # Pembatas kolom kiri (Struktur) dan kolom kanan (Arsitektur Kusen)
    x_bagi = vx0 + (vx1 - vx0) * 0.48
    _garis(msp, (x_bagi, vy0 + 220), (x_bagi, vy1 - 220), "A-ANNO-KOP-THIN")

    # Panel 1 (Kiri Atas): Pondasi Batu Kali & Sloof
    _gambar_detail_pondasi(msp, rumah, cx=vx0 + 1150.0, y_lantai=vy1 - 950.0)

    # Panel 2 (Kiri Bawah): Penampang Kolom Praktis
    _gambar_detail_kolom(msp, rumah, cx=vx0 + 1150.0, cy=vy0 + 1080.0)

    # Panel 3 (Kanan): Jadwal & Detail Kusen Pintu/Jendela
    _gambar_jadwal_kusen(msp, rumah, x0=x_bagi + 180.0, y_top=vy1 - 260.0, lebar_area=(vx1 - x_bagi - 240.0))

    return (vx0, vy0, vx1, vy1)