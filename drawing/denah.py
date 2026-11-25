"""
Modul Gambar Denah Arsitektural (Lantai 1 & Lantai 2) pada AutoCAD DXF.
"""
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ezdxf
from ezdxf.enums import TextEntityAlignment as TA


def _siapkan_layer_denah(doc: ezdxf.document.Drawing) -> None:
    layers = [
        ("A-WALL", 6),
        ("A-WALL-PATT", 8),
        ("S-COLS", 1),
        ("A-DOOR", 1),
        ("A-GLAZ", 4),
        ("A-FLOR-STRS", 3),
        ("A-FLOR-OVHD", 8),
        ("A-FURN", 30),
        ("A-ROOF-OUTL", 30),
        ("A-ANNO-DIMS", 3),
        ("A-ANNO-TEXT", 2),
        ("A-ANNO-SYMB", 7),
    ]
    for nama, warna in layers:
        if nama not in doc.layers:
            doc.layers.add(nama, color=warna)


def _poly(msp, pts: Sequence[Tuple[float, float]], layer: str, tutup: bool = True, color: Optional[int] = None, linetype: Optional[str] = None):
    attr: Dict[str, object] = {"layer": layer}
    if color is not None:
        attr["color"] = color
    if linetype is not None:
        attr["linetype"] = linetype
    return msp.add_lwpolyline(list(pts), close=tutup, dxfattribs=attr)


def _garis(msp, p1: Tuple[float, float], p2: Tuple[float, float], layer: str, color: Optional[int] = None, linetype: Optional[str] = None):
    attr: Dict[str, object] = {"layer": layer}
    if color is not None:
        attr["color"] = color
    if linetype is not None:
        attr["linetype"] = linetype
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


def _teks(msp, isi: str, pos: Tuple[float, float], tinggi: float = 110.0, rata=TA.MIDDLE_CENTER, layer: str = "A-ANNO-TEXT", rotasi: float = 0.0, color: Optional[int] = None):
    style_name = "KOP_FONT" if "KOP_FONT" in msp.doc.styles else "Standard"
    attr: Dict[str, object] = {"layer": layer, "style": style_name, "rotation": rotasi}
    if color is not None:
        attr["color"] = color
    msp.add_text(isi, height=tinggi, dxfattribs=attr).set_placement(pos, align=rata)


def _dim_linear(msp, p1: Tuple[float, float], p2: Tuple[float, float], jarak: float, sudut: float = 0.0, ox: float = 0.0, oy: float = 0.0):
    q1 = (p1[0] + ox, p1[1] + oy)
    q2 = (p2[0] + ox, p2[1] + oy)
    rad = math.radians(sudut)
    nx, ny = -math.sin(rad), math.cos(rad)
    base = ((q1[0] + q2[0]) / 2.0 + nx * jarak, (q1[1] + q2[1]) / 2.0 + ny * jarak)
    dim = msp.add_linear_dim(
        base=base,
        p1=q1,
        p2=q2,
        angle=sudut,
        override={
            "dimtxt": 110.0,
            "dimasz": 85.0,
            "dimexe": 65.0,
            "dimexo": 45.0,
            "dimgap": 38.0,
            "dimdec": 0,
            "dimclrd": 3,
            "dimclre": 3,
            "dimclrt": 3,
        },
        dxfattribs={"layer": "A-ANNO-DIMS"},
    )
    dim.render()


def _gambar_dinding_terpotong(msp, dinding_list, bukaan_list, ox: float, oy: float) -> None:
    """Menggambar segmen dinding yang otomatis terpotong bersih di lokasi pintu & jendela."""
    bukaan_per_dinding: Dict[str, List[Any]] = {}
    for b in bukaan_list:
        bukaan_per_dinding.setdefault(b.dinding, []).append(b)

    for d in dinding_list:
        pjg = d.panjang
        if pjg < 1.0:
            continue
        ux, uy = (d.b[0] - d.a[0]) / pjg, (d.b[1] - d.a[1]) / pjg
        nx, ny = -uy, ux
        hw = d.tebal / 2.0

        bks = sorted(bukaan_per_dinding.get(d.id, []), key=lambda item: item.offset)
        interval: List[Tuple[float, float]] = []
        cursor = 0.0
        for b in bks:
            s0 = max(cursor, float(b.offset))
            s1 = min(pjg, float(b.offset + b.lebar))
            if s0 > cursor + 1.0:
                interval.append((cursor, s0))
            cursor = max(cursor, s1)
        if pjg > cursor + 1.0:
            interval.append((cursor, pjg))

        for s0, s1 in interval:
            p0 = (ox + d.a[0] + ux * s0, oy + d.a[1] + uy * s0)
            p1 = (ox + d.a[0] + ux * s1, oy + d.a[1] + uy * s1)
            pts = [
                (p0[0] + nx * hw, p0[1] + ny * hw),
                (p1[0] + nx * hw, p1[1] + ny * hw),
                (p1[0] - nx * hw, p1[1] - ny * hw),
                (p0[0] - nx * hw, p0[1] - ny * hw),
            ]
            _poly(msp, pts, "A-WALL")
            _arsir(msp, pts, "ANSI31", 45.0, "A-WALL-PATT")


def _gambar_kolom_struktur(msp, dinding_list, ox: float, oy: float, ukuran: float = 200.0) -> None:
    """Menempatkan kolom struktur pada seluruh sudut & pertemuan dinding."""
    titik_unik: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for d in dinding_list:
        for pt in (d.a, d.b):
            kunci = (int(round(pt[0] / 50.0)), int(round(pt[1] / 50.0)))
            titik_unik[kunci] = pt

    hw = ukuran / 2.0
    for px, py in titik_unik.values():
        cx, cy = ox + px, oy + py
        pts = [(cx - hw, cy - hw), (cx + hw, cy - hw), (cx + hw, cy + hw), (cx - hw, cy + hw)]
        _poly(msp, pts, "S-COLS", color=1)
        _arsir(msp, pts, "SOLID", 1.0, "S-COLS", color=1)


def _gambar_bukaan(msp, dinding_list, bukaan_list, ox: float, oy: float) -> None:
    """Menggambar simbol daun pintu + ayunan busur dan kusen kaca jendela."""
    peta_d = {d.id: d for d in dinding_list}
    for b in bukaan_list:
        d = peta_d.get(b.dinding)
        if not d or d.panjang < 1.0:
            continue
        pjg = d.panjang
        ux, uy = (d.b[0] - d.a[0]) / pjg, (d.b[1] - d.a[1]) / pjg
        nx, ny = -uy, ux
        hw = d.tebal / 2.0

        s0 = float(b.offset)
        s1 = s0 + float(b.lebar)
        p0 = (ox + d.a[0] + ux * s0, oy + d.a[1] + uy * s0)
        p1 = (ox + d.a[0] + ux * s1, oy + d.a[1] + uy * s1)

        kw = 50.0
        for pk, dir_u in ((p0, 1.0), (p1, -1.0)):
            q_in = (pk[0] + ux * kw * dir_u, pk[1] + uy * kw * dir_u)
            k_pts = [
                (pk[0] + nx * hw, pk[1] + ny * hw),
                (q_in[0] + nx * hw, q_in[1] + ny * hw),
                (q_in[0] - nx * hw, q_in[1] - ny * hw),
                (pk[0] - nx * hw, pk[1] - ny * hw),
            ]
            _poly(msp, k_pts, "A-DOOR" if b.jenis == "pintu" else "A-GLAZ")

        if b.jenis == "pintu":
            lebar_daun = max(300.0, float(b.lebar) - 2 * kw)
            engsel = (p0[0] + ux * kw + nx * hw, p0[1] + uy * kw + ny * hw)
            ujung_buka = (engsel[0] + nx * lebar_daun, engsel[1] + ny * lebar_daun)
            ujung_tutup = (engsel[0] + ux * lebar_daun, engsel[1] + uy * lebar_daun)
            _garis(msp, engsel, ujung_buka, "A-DOOR", color=1)
            ang1 = math.degrees(math.atan2(ujung_tutup[1] - engsel[1], ujung_tutup[0] - engsel[0]))
            ang2 = math.degrees(math.atan2(ujung_buka[1] - engsel[1], ujung_buka[0] - engsel[0]))
            diff = (ang2 - ang1) % 360.0
            if diff <= 180.0:
                msp.add_arc(engsel, radius=lebar_daun, start_angle=ang1, end_angle=ang2, dxfattribs={"layer": "A-DOOR", "color": 1})
            else:
                msp.add_arc(engsel, radius=lebar_daun, start_angle=ang2, end_angle=ang1, dxfattribs={"layer": "A-DOOR", "color": 1})
        else:
            _garis(msp, (p0[0] + nx * hw, p0[1] + ny * hw), (p1[0] + nx * hw, p1[1] + ny * hw), "A-GLAZ")
            _garis(msp, (p0[0] - nx * hw, p0[1] - ny * hw), (p1[0] - nx * hw, p1[1] - ny * hw), "A-GLAZ")
            _garis(msp, (p0[0] + nx * 22.0, p0[1] + ny * 22.0), (p1[0] + nx * 22.0, p1[1] + ny * 22.0), "A-GLAZ")
            _garis(msp, (p0[0] - nx * 22.0, p0[1] - ny * 22.0), (p1[0] - nx * 22.0, p1[1] - ny * 22.0), "A-GLAZ")


def _gambar_tangga_denah(msp, tangga, lantai: int, ox: float, oy: float) -> None:
    """
    Menggambar denah tangga L secara sinkron dengan potongan:
    - Lengan 1 naik ke Utara (+Y) di sisi kanan menuju bordes (+1.70 m).
    - Lengan 2 berbelok ke Barat/Kiri (-X) dari bordes menuju Lantai 2 (+3.40 m),
      berhenti pada jarak 900 mm dari dinding pembatas agar sirkulasi atas lapang.
    """
    if tangga is None:
        return

    w = float(tangga.lebar)
    ax = ox + float(tangga.asal[0])
    ay = oy + float(tangga.asal[1])

    n_leg1 = 8
    ant1 = 225.0
    p1 = n_leg1 * ant1  # 1800 mm

    n_leg2 = 6
    ant2 = 200.0
    p2 = n_leg2 * ant2  # 1200 mm -> ujung atas tangga di x = 5100 - 1200 = 3900 (jarak 900 mm ke dinding x=3000)

    pts_outline = [
        (ax, ay),
        (ax + w, ay),
        (ax + w, ay + p1 + w),
        (ax - p2, ay + p1 + w),
        (ax - p2, ay + p1),
        (ax, ay + p1),
    ]
    _poly(msp, pts_outline, "A-FLOR-STRS", tutup=True, color=3)

    for i in range(1, n_leg1 + 1):
        yy = ay + i * ant1
        _garis(msp, (ax, yy), (ax + w, yy), "A-FLOR-STRS", color=3)

    for j in range(1, n_leg2):
        xx = ax - j * ant2
        _garis(msp, (xx, ay + p1), (xx, ay + p1 + w), "A-FLOR-STRS", color=3)

    cx1 = ax + w / 2.0
    cy_bordes = ay + p1 + w / 2.0
    x_atas = ax - p2 + 100.0
    y_bawah = ay + 130.0

    if lantai == 1:
        y_cut = ay + p1 * 0.55
        _garis(msp, (ax - 60.0, y_cut - 85.0), (ax + w + 60.0, y_cut + 85.0), "A-ANNO-SYMB", color=7)

        msp.add_circle((cx1, y_bawah), radius=42.0, dxfattribs={"layer": "A-FLOR-STRS", "color": 3})
        _garis(msp, (cx1, y_bawah), (cx1, cy_bordes), "A-FLOR-STRS", color=3)
        _garis(msp, (cx1, cy_bordes), (x_atas, cy_bordes), "A-FLOR-STRS", color=3)
        _garis(msp, (x_atas, cy_bordes), (x_atas + 130.0, cy_bordes + 85.0), "A-FLOR-STRS", color=3)
        _garis(msp, (x_atas, cy_bordes), (x_atas + 130.0, cy_bordes - 85.0), "A-FLOR-STRS", color=3)
        _teks(msp, "NAIK", (cx1, ay - 140.0), tinggi=85.0, color=3)
    else:
        msp.add_circle((x_atas, cy_bordes), radius=42.0, dxfattribs={"layer": "A-FLOR-STRS", "color": 3})
        _garis(msp, (x_atas, cy_bordes), (cx1, cy_bordes), "A-FLOR-STRS", color=3)
        _garis(msp, (cx1, cy_bordes), (cx1, y_bawah), "A-FLOR-STRS", color=3)
        _garis(msp, (cx1, y_bawah), (cx1 - 85.0, y_bawah + 130.0), "A-FLOR-STRS", color=3)
        _garis(msp, (cx1, y_bawah), (cx1 + 85.0, y_bawah + 130.0), "A-FLOR-STRS", color=3)
        _teks(msp, "TURUN", (ax - p2 - 240.0, cy_bordes), tinggi=85.0, color=3)


def _gambar_perabot(msp, ruang_list, ox: float, oy: float) -> None:
    """Menggambar furnitur skematik detail di dalam tiap ruangan berdasarkan fungsi ruang."""
    for r in ruang_list:
        if not r.kotak or len(r.kotak) != 4:
            continue
        x0, y0, x1, y1 = [float(v) for v in r.kotak]
        rx0, ry0 = ox + min(x0, x1), oy + min(y0, y1)
        rx1, ry1 = ox + max(x0, x1), oy + max(y0, y1)
        rw, rh = rx1 - rx0, ry1 - ry0
        nama = r.nama.lower()

        if "tidur" in nama or "kamar" in nama:
            bw = min(1600.0, rw * 0.56)
            bh = min(1950.0, rh * 0.60)
            bx = rx0 + (rw - bw) / 2.0
            by = ry1 - bh - 160.0
            _poly(msp, [(bx, by), (bx + bw, by), (bx + bw, by + bh), (bx, by + bh)], "A-FURN")
            pw = bw * 0.36
            _poly(msp, [(bx + bw * 0.08, by + bh - 340.0), (bx + bw * 0.08 + pw, by + bh - 340.0),
                        (bx + bw * 0.08 + pw, by + bh - 90.0), (bx + bw * 0.08, by + bh - 90.0)], "A-FURN")
            _poly(msp, [(bx + bw * 0.56, by + bh - 340.0), (bx + bw * 0.56 + pw, by + bh - 340.0),
                        (bx + bw * 0.56 + pw, by + bh - 90.0), (bx + bw * 0.56, by + bh - 90.0)], "A-FURN")
        elif "tamu" in nama or "keluarga" in nama:
            sw = min(1700.0, rw * 0.58)
            sh = 600.0
            sx = rx0 + (rw - sw) / 2.0
            sy = ry0 + 250.0
            _poly(msp, [(sx, sy), (sx + sw, sy), (sx + sw, sy + sh), (sx, sy + sh)], "A-FURN")
            mw = sw * 0.52
            _poly(msp, [(rx0 + (rw - mw) / 2.0, sy + sh + 170.0), (rx0 + (rw + mw) / 2.0, sy + sh + 170.0),
                        (rx0 + (rw + mw) / 2.0, sy + sh + 500.0), (rx0 + (rw - mw) / 2.0, sy + sh + 500.0)], "A-FURN")
        elif "dapur" in nama:
            dw = min(1350.0, rw * 0.78)
            dh = 500.0
            dx = rx0 + (rw - dw) / 2.0
            dy = ry1 - dh - 140.0
            _poly(msp, [(dx, dy), (dx + dw, dy), (dx + dw, dy + dh), (dx, dy + dh)], "A-FURN")
            msp.add_circle((dx + dw * 0.32, dy + dh * 0.5), radius=100.0, dxfattribs={"layer": "A-FURN"})
            msp.add_circle((dx + dw * 0.68, dy + dh * 0.5), radius=100.0, dxfattribs={"layer": "A-FURN"})
        elif "km" in nama or "wc" in nama or "mandi" in nama:
            _poly(msp, [(rx0 + 130.0, ry1 - 560.0), (rx0 + 560.0, ry1 - 560.0),
                        (rx0 + 560.0, ry1 - 130.0), (rx0 + 130.0, ry1 - 130.0)], "A-FURN")
            msp.add_circle((rx1 - 340.0, ry0 + 440.0), radius=175.0, dxfattribs={"layer": "A-FURN"})


def _gambar_garis_potongan(msp, rumah, ox: float, oy: float) -> None:
    """Menggambar garis sumbu potongan A-A dan B-B beserta simbol lingkaran arah pandang."""
    x0, y0, x1, y1 = rumah.batas
    for sec in rumah.potongan:
        nama = str(sec.get("nama", "A-A"))
        huruf = nama.split("-")[0].strip()
        arah = str(sec.get("arah", "x")).lower()
        pos = float(sec.get("posisi", (y0 + y1) / 2.0 if arah == "x" else (x0 + x1) / 2.0))

        if arah == "x":
            ya = oy + pos
            xa1, xa2 = ox + x0 - 950.0, ox + x1 + 950.0
            _garis(msp, (xa1, ya), (xa2, ya), "A-ANNO-SYMB", color=7)
            for cx_s in (xa1 - 220.0, xa2 + 220.0):
                msp.add_circle((cx_s, ya), radius=220.0, dxfattribs={"layer": "A-ANNO-SYMB", "color": 7})
                _poly(msp, [(cx_s - 155.0, ya + 155.0), (cx_s, ya + 340.0), (cx_s + 155.0, ya + 155.0)], "A-ANNO-SYMB", tutup=False, color=7)
                _teks(msp, huruf, (cx_s, ya), tinggi=140.0, color=7)
        else:
            xa = ox + pos
            ya1, ya2 = oy + y0 - 950.0, oy + y1 + 950.0
            _garis(msp, (xa, ya1), (xa, ya2), "A-ANNO-SYMB", color=7)
            for cy_s in (ya1 - 220.0, ya2 + 220.0):
                msp.add_circle((xa, cy_s), radius=220.0, dxfattribs={"layer": "A-ANNO-SYMB", "color": 7})
                _poly(msp, [(xa + 155.0, cy_s - 155.0), (xa + 340.0, cy_s), (xa + 155.0, cy_s + 155.0)], "A-ANNO-SYMB", tutup=False, color=7)
                _teks(msp, huruf, (xa, cy_s), tinggi=140.0, color=7)


def _gambar_utara(msp, cx: float, cy: float) -> None:
    """Simbol orientasi arah Utara di sebelah kanan denah."""
    msp.add_circle((cx, cy), radius=240.0, dxfattribs={"layer": "A-ANNO-SYMB", "color": 7})
    _poly(msp, [(cx, cy + 240.0), (cx - 110.0, cy - 150.0), (cx, cy - 60.0), (cx + 110.0, cy - 150.0)], "A-ANNO-SYMB", tutup=True, color=7)
    _teks(msp, "U", (cx, cy + 380.0), tinggi=145.0, color=2)


def gambar_denah_lantai(
    rumah,
    msp,
    lantai: int = 1,
    ox: float = 0.0,
    oy: float = 0.0,
    skala_label: str = "1 : 50",
) -> Tuple[float, float, float, float]:
    """Merender Denah Lantai 1 atau Denah Lantai 2 lengkap ke Modelspace DXF."""
    _siapkan_layer_denah(msp.doc)
    is_lt2 = lantai == 2 and getattr(rumah, "jumlah_lantai", 1) >= 2

    dinding_list = rumah.dinding_lt2 if is_lt2 else rumah.dinding
    bukaan_list = rumah.bukaan_lt2 if is_lt2 else rumah.bukaan
    ruang_list = rumah.ruang_lt2 if is_lt2 else rumah.ruang

    _gambar_dinding_terpotong(msp, dinding_list, bukaan_list, ox, oy)
    _gambar_kolom_struktur(msp, dinding_list, ox, oy)
    _gambar_bukaan(msp, dinding_list, bukaan_list, ox, oy)
    _gambar_perabot(msp, ruang_list, ox, oy)

    # Area Void & Balkon pada Lantai 2 (digambar sebelum tangga agar tangga tetap jernih di atasnya)
    if is_lt2:
        for v in rumah.void or []:
            k = v.get("kotak")
            if isinstance(k, list) and len(k) == 4:
                vx0, vy0, vx1, vy1 = ox + float(k[0]), oy + float(k[1]), ox + float(k[2]), oy + float(k[3])
                _poly(msp, [(vx0, vy0), (vx1, vy0), (vx1, vy1), (vx0, vy1)], "A-FLOR-OVHD", color=8)
                _garis(msp, (vx0, vy0), (vx1, vy1), "A-FLOR-OVHD", color=8)
                _garis(msp, (vx0, vy1), (vx1, vy0), "A-FLOR-OVHD", color=8)
                _teks(msp, "VOID", ((vx0 + vx1) / 2.0, (vy0 + vy1) / 2.0), tinggi=105.0, color=8)

        for blk in rumah.balkon or []:
            k = blk.get("kotak")
            if isinstance(k, list) and len(k) == 4:
                bx0, by0, bx1, by1 = ox + float(k[0]), oy + float(k[1]), ox + float(k[2]), oy + float(k[3])
                _poly(msp, [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], "A-WALL")
                _teks(msp, "BALKON", ((bx0 + bx1) / 2.0, (by0 + by1) / 2.0), tinggi=105.0, color=3)

    if getattr(rumah, "jumlah_lantai", 1) >= 2:
        _gambar_tangga_denah(msp, rumah.tangga, lantai=lantai, ox=ox, oy=oy)

    elev_m = float(rumah.lantai_2.get("elevasi", 3400.0)) / 1000.0 if is_lt2 else float(rumah.lantai.get("elevasi", 0.0)) / 1000.0
    for r in ruang_list:
        cx_r, cy_r = ox + float(r.pusat[0]), oy + float(r.pusat[1])
        peil_str = "±0.00" if abs(elev_m) < 1e-4 else f"+{elev_m:.2f}"
        if any(k in r.nama.lower() for k in ("km", "wc", "mandi")):
            peil_str = "-0.05" if not is_lt2 else f"+{elev_m - 0.05:.2f}"
        _teks(msp, r.nama.upper(), (cx_r, cy_r + 75.0), tinggi=98.0, color=2)
        _teks(msp, peil_str, (cx_r, cy_r - 75.0), tinggi=85.0, color=3)

    x0, y0, x1, y1 = rumah.batas
    ov = float((rumah.atap or {}).get("overstek", 600.0))
    _poly(
        msp,
        [(ox + x0 - ov, oy + y0 - ov), (ox + x1 + ov, oy + y0 - ov), (ox + x1 + ov, oy + y1 + ov), (ox + x0 - ov, oy + y1 + ov)],
        "A-ROOF-OUTL",
        color=30,
    )

    _gambar_garis_potongan(msp, rumah, ox, oy)

    xs_grid = sorted({round(pt[0], 1) for d in dinding_list for pt in (d.a, d.b)})
    ys_grid = sorted({round(pt[1], 1) for d in dinding_list for pt in (d.a, d.b)})

    for i in range(len(xs_grid) - 1):
        _dim_linear(msp, (xs_grid[i], y1), (xs_grid[i + 1], y1), jarak=420.0, sudut=0.0, ox=ox, oy=oy)
        _dim_linear(msp, (xs_grid[i], y0), (xs_grid[i + 1], y0), jarak=-420.0, sudut=0.0, ox=ox, oy=oy)
    _dim_linear(msp, (x0, y1), (x1, y1), jarak=780.0, sudut=0.0, ox=ox, oy=oy)
    _dim_linear(msp, (x0, y0), (x1, y0), jarak=-780.0, sudut=0.0, ox=ox, oy=oy)

    for j in range(len(ys_grid) - 1):
        _dim_linear(msp, (x0, ys_grid[j]), (x0, ys_grid[j + 1]), jarak=420.0, sudut=90.0, ox=ox, oy=oy)
        _dim_linear(msp, (x1, ys_grid[j]), (x1, ys_grid[j + 1]), jarak=-420.0, sudut=90.0, ox=ox, oy=oy)
    _dim_linear(msp, (x0, y0), (x0, y1), jarak=780.0, sudut=90.0, ox=ox, oy=oy)
    _dim_linear(msp, (x1, y0), (x1, y1), jarak=-780.0, sudut=90.0, ox=ox, oy=oy)

    _gambar_utara(msp, ox + x1 + 1450.0, oy + (y0 + y1) / 2.0)
    judul_denah = f"DENAH LANTAI {lantai}" if getattr(rumah, "jumlah_lantai", 1) >= 2 else "DENAH RENCANA"
    cx_j = ox + (x0 + x1) / 2.0
    y_j = oy + y0 - 1350.0
    _teks(msp, judul_denah, (cx_j, y_j), tinggi=185.0, color=2)
    _garis(msp, (cx_j - 950.0, y_j - 125.0), (cx_j + 950.0, y_j - 125.0), "A-ANNO-TEXT", color=2)
    _teks(msp, f"Skala {skala_label}", (cx_j, y_j - 260.0), tinggi=115.0, color=2)

    return (ox + x0 - 1100.0, oy + y0 - 1700.0, ox + x1 + 1800.0, oy + y1 + 1100.0)