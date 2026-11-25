"""
Modul Gambar Potongan Arsitektural & Struktur (Potongan A-A & B-B)
serta Gambar 4 Sisi Tampak (Depan, Belakang, Kanan, Kiri) yang proporsional dan estetis.
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

import ezdxf
from ezdxf.enums import TextEntityAlignment as TA


def _siapkan_layer_potongan(doc: ezdxf.document.Drawing) -> None:
    layers = [
        ("A-WALL", 6),
        ("A-WALL-PATT", 8),
        ("S-COLS", 1),
        ("S-FNDN", 4),
        ("A-ROOF", 30),
        ("A-ROOF-PATT", 8),
        ("A-DOOR", 1),
        ("A-GLAZ", 4),
        ("A-FLOR-STRS", 3),
        ("A-FURN", 30),
        ("A-ANNO-DIMS", 3),
        ("A-ANNO-TEXT", 2),
        ("A-ANNO-SYMB", 7),
    ]
    for nama, warna in layers:
        if nama not in doc.layers:
            doc.layers.add(nama, color=warna)


def _poly(msp, pts: Sequence[Tuple[float, float]], layer: str, tutup: bool = True, color: Optional[int] = None):
    attr: Dict[str, object] = {"layer": layer}
    if color is not None:
        attr["color"] = color
    return msp.add_lwpolyline(list(pts), close=tutup, dxfattribs=attr)


def _garis(msp, p1: Tuple[float, float], p2: Tuple[float, float], layer: str, color: Optional[int] = None):
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


def _teks(msp, isi: str, pos: Tuple[float, float], tinggi: float = 100.0, rata=TA.MIDDLE_CENTER, layer: str = "A-ANNO-TEXT", rotasi: float = 0.0, color: Optional[int] = None):
    style_name = "KOP_FONT" if "KOP_FONT" in msp.doc.styles else "Standard"
    attr: Dict[str, object] = {"layer": layer, "style": style_name, "rotation": rotasi}
    if color is not None:
        attr["color"] = color
    msp.add_text(isi, height=tinggi, dxfattribs=attr).set_placement(pos, align=rata)


def _callout_kiri(msp, p_target: Tuple[float, float], x_label: float, y_label: float, teks_lbl: str) -> None:
    x_belok = x_label + 260.0
    _garis(msp, p_target, (x_belok, y_label), "A-ANNO-SYMB", color=2)
    _garis(msp, (x_belok, y_label), (x_label, y_label), "A-ANNO-SYMB", color=2)
    msp.add_circle(p_target, radius=32.0, dxfattribs={"layer": "A-ANNO-SYMB", "color": 2})
    _teks(msp, teks_lbl, (x_label - 60.0, y_label), tinggi=88.0, rata=TA.MIDDLE_RIGHT, color=2)


def _simbol_elevasi_kanan(msp, x_mulai: float, x_datum: float, y_elev: float, nilai_m: float) -> None:
    _garis(msp, (x_mulai, y_elev), (x_datum + 450.0, y_elev), "A-ANNO-SYMB", color=8)
    _poly(msp, [(x_datum - 65.0, y_elev + 100.0), (x_datum + 65.0, y_elev + 100.0), (x_datum, y_elev)], "A-ANNO-SYMB", tutup=True, color=2)
    lbl = "±0.00" if abs(nilai_m) < 1e-4 else f"{nilai_m:+.2f}"
    _teks(msp, lbl, (x_datum + 110.0, y_elev + 95.0), tinggi=92.0, rata=TA.MIDDLE_LEFT, color=2)


def _dim_horizontal(msp, x1: float, x2: float, y_dim: float) -> None:
    dim = msp.add_linear_dim(
        base=((x1 + x2) / 2.0, y_dim),
        p1=(x1, y_dim),
        p2=(x2, y_dim),
        angle=0.0,
        override={"dimtxt": 105.0, "dimasz": 80.0, "dimdec": 0, "dimclrd": 1, "dimclre": 1, "dimclrt": 2},
        dxfattribs={"layer": "A-ANNO-DIMS"},
    )
    dim.render()


def _dinding_terpotong_pada_garis(dinding_list, arah: str, pos: float) -> List[Tuple[float, float]]:
    hasil: List[Tuple[float, float]] = []
    for d in dinding_list:
        if arah == "x":
            ya, yb = float(d.a[1]), float(d.b[1])
            if min(ya, yb) - 1.0 <= pos <= max(ya, yb) + 1.0 and abs(yb - ya) > 10.0:
                t = (pos - ya) / (yb - ya)
                xc = float(d.a[0]) + t * (float(d.b[0]) - float(d.a[0]))
                hasil.append((xc, float(d.tebal)))
        else:
            xa, xb = float(d.a[0]), float(d.b[0])
            if min(xa, xb) - 1.0 <= pos <= max(xa, xb) + 1.0 and abs(xb - xa) > 10.0:
                t = (pos - xa) / (xb - xa)
                yc = float(d.a[1]) + t * (float(d.b[1]) - float(d.a[1]))
                hasil.append((yc, float(d.tebal)))
    hasil.sort(key=lambda item: item[0])
    unik: List[Tuple[float, float]] = []
    for c, tb in hasil:
        if not unik or abs(c - unik[-1][0]) > 50.0:
            unik.append((c, tb))
    return unik


def _gambar_pondasi_potongan(msp, cx: float, y_nol: float, rumah, is_2lt: bool) -> None:
    st = rumah.struktur or {}
    pnd = st.get("pondasi", {"lebar_bawah": 600, "lebar_atas": 300, "tinggi": 700})
    lb_bwh = float(pnd.get("lebar_bawah", 600.0))
    lb_ats = float(pnd.get("lebar_atas", 300.0))
    t_pnd = float(pnd.get("tinggi", 700.0))
    sloof = st.get("sloof", [200, 300] if is_2lt else [150, 200])
    sw, sh = float(sloof[0]), float(sloof[1])

    y_top_pnd = y_nol - sh
    y_bot_pnd = y_top_pnd - t_pnd

    if is_2lt:
        y_fp = y_nol - 1200.0
        # Pasir urug & lantai kerja
        _poly(msp, [(cx - 560.0, y_fp - 100.0), (cx + 560.0, y_fp - 100.0), (cx + 560.0, y_fp - 50.0), (cx - 560.0, y_fp - 50.0)], "S-FNDN")
        _poly(msp, [(cx - 560.0, y_fp - 50.0), (cx + 560.0, y_fp - 50.0), (cx + 560.0, y_fp), (cx - 560.0, y_fp)], "S-FNDN")
        # Footplat trapesium 100x100x25/35
        fp_pts = [(cx - 500.0, y_fp), (cx + 500.0, y_fp), (cx + 500.0, y_fp + 220.0), (cx + 150.0, y_fp + 300.0), (cx - 150.0, y_fp + 300.0), (cx - 500.0, y_fp + 220.0)]
        _poly(msp, fp_pts, "S-COLS", color=1)
        _arsir(msp, fp_pts, "AR-CONC", 22.0, "S-COLS", color=1)
        # Pedestal
        ped_pts = [(cx - 125.0, y_fp + 300.0), (cx + 125.0, y_fp + 300.0), (cx + 125.0, y_nol), (cx - 125.0, y_nol)]
        _poly(msp, ped_pts, "S-COLS", color=1)
        _arsir(msp, ped_pts, "AR-CONC", 22.0, "S-COLS", color=1)
    else:
        _poly(msp, [(cx - lb_bwh / 2 - 100, y_bot_pnd - 200), (cx + lb_bwh / 2 + 100, y_bot_pnd - 200),
                    (cx + lb_bwh / 2 + 100, y_bot_pnd - 150), (cx - lb_bwh / 2 - 100, y_bot_pnd - 150)], "S-FNDN")
        _poly(msp, [(cx - lb_bwh / 2 - 100, y_bot_pnd - 150), (cx + lb_bwh / 2 + 100, y_bot_pnd - 150),
                    (cx + lb_bwh / 2 + 100, y_bot_pnd), (cx - lb_bwh / 2 - 100, y_bot_pnd)], "S-FNDN")
        pts_pnd = [(cx - lb_bwh / 2, y_bot_pnd), (cx + lb_bwh / 2, y_bot_pnd), (cx + lb_ats / 2, y_top_pnd), (cx - lb_ats / 2, y_top_pnd)]
        _poly(msp, pts_pnd, "S-FNDN")
        _arsir(msp, pts_pnd, "GRAVEL", 32.0, "S-FNDN")

    pts_sl = [(cx - sw / 2, y_top_pnd), (cx + sw / 2, y_top_pnd), (cx + sw / 2, y_nol), (cx - sw / 2, y_nol)]
    _poly(msp, pts_sl, "S-COLS", color=1)
    _arsir(msp, pts_sl, "AR-CONC", 22.0, "S-COLS", color=1)


def _gambar_tangga_potongan_sinkron(
    msp,
    arah: str,
    xl: float,
    xr: float,
    x_mid_wall: float,
    y_nol: float,
    y_lt2: float,
    t_pelat: float,
    n_trap_tot: int,
) -> Tuple[float, float]:
    """Menggambar tangga L-shape sinkron dengan denah (selasar 900 mm di atas tangga)."""
    y_bordes = y_nol + (y_lt2 - y_nol) * 0.50

    if arah == "x":
        # POTONGAN A-A:
        # Bordes di kanan (x = 5100..5925), Lengan 2 miring naik ke KIRI dari x=5100 sampai x=3900,
        # menyisakan selasar bersih 900 mm (x=3000..3900) dari dinding tengah!
        w_bordes = 825.0
        x_b1 = xr - 75.0
        x_b0 = x_b1 - w_bordes
        x_top = max(x_mid_wall + 900.0, x_b0 - 1200.0)

        pts_bordes = [(x_b0, y_bordes - 150.0), (x_b1, y_bordes - 150.0), (x_b1, y_bordes), (x_b0, y_bordes)]
        _poly(msp, pts_bordes, "S-COLS", tutup=True, color=1)
        _arsir(msp, pts_bordes, "AR-CONC", 20.0, "S-COLS", color=1)

        n1 = 8
        _poly(msp, [(x_b0, y_nol), (x_b1, y_nol), (x_b1, y_bordes - 150.0), (x_b0, y_bordes - 150.0)], "A-FLOR-STRS", tutup=True, color=3)
        for i in range(1, n1):
            ys = y_nol + i * ((y_bordes - 150.0 - y_nol) / n1)
            _garis(msp, (x_b0, ys), (x_b1, ys), "A-FLOR-STRS", color=3)

        n2 = 6
        dx = (x_b0 - x_top) / n2
        dy = (y_lt2 - y_bordes) / n2
        pts_lengan2 = [(x_b0, y_bordes)]
        for s in range(n2):
            xa = x_b0 - s * dx
            xb = x_b0 - (s + 1) * dx
            yb = y_bordes + (s + 1) * dy
            pts_lengan2.append((xa, yb))
            pts_lengan2.append((xb, yb))
        pts_lengan2.append((x_top, y_lt2 - t_pelat))
        pts_lengan2.append((x_b0, y_bordes - 150.0))
        _poly(msp, pts_lengan2, "S-COLS", tutup=True, color=1)
        _arsir(msp, pts_lengan2, "AR-CONC", 20.0, "S-COLS", color=1)

        _garis(msp, (x_b1 - 40.0, y_bordes + 900.0), (x_b0, y_bordes + 900.0), "A-FLOR-STRS", color=3)
        _garis(msp, (x_b0, y_bordes + 900.0), (x_top, y_lt2 + 900.0), "A-FLOR-STRS", color=3)
        for k in range(n2 + 1):
            xr_p = x_b0 - k * dx
            yr_p = y_bordes + k * dy
            _garis(msp, (xr_p, yr_p), (xr_p, yr_p + 900.0), "A-FLOR-STRS", color=3)

        return (x_top, x_b1)
    else:
        # POTONGAN B-B:
        # Lengan 1 mulai y=2700 sampai bordes y=4500..5400
        y_start = xl + 2700.0
        y_b0 = xl + 4500.0
        y_b1 = xl + 5400.0

        n1 = 8
        dx = (y_b0 - y_start) / n1
        dy = (y_bordes - y_nol) / n1
        pts_lengan1 = [(y_start, y_nol)]
        for s in range(n1):
            ya = y_start + s * dx
            yb = y_start + (s + 1) * dx
            zb = y_nol + (s + 1) * dy
            pts_lengan1.append((ya, zb))
            pts_lengan1.append((yb, zb))
        pts_lengan1.append((y_b1, y_bordes))
        pts_lengan1.append((y_b1, y_bordes - 150.0))
        pts_lengan1.append((y_b0, y_bordes - 150.0))
        pts_lengan1.append((y_start + 220.0, y_nol))
        _poly(msp, pts_lengan1, "S-COLS", tutup=True, color=1)
        _arsir(msp, pts_lengan1, "AR-CONC", 20.0, "S-COLS", color=1)

        n2 = 6
        _poly(msp, [(y_b0, y_bordes), (y_b1, y_bordes), (y_b1, y_lt2), (y_b0, y_lt2)], "A-FLOR-STRS", tutup=True, color=3)
        for j in range(1, n2):
            zs = y_bordes + j * ((y_lt2 - y_bordes) / n2)
            _garis(msp, (y_b0, zs), (y_b1, zs), "A-FLOR-STRS", color=3)

        _garis(msp, (y_start, y_nol + 900.0), (y_b0, y_bordes + 900.0), "A-FLOR-STRS", color=3)
        for k in range(n1 + 1):
            yr_p = y_start + k * dx
            zr_p = y_nol + k * dy
            _garis(msp, (yr_p, zr_p), (yr_p, zr_p + 900.0), "A-FLOR-STRS", color=3)
        _poly(msp, [(y_start, y_lt2), (y_b0, y_lt2), (y_b0, y_lt2 + 900.0), (y_start, y_lt2 + 900.0)], "A-FLOR-STRS", tutup=True, color=3)
        for kv in range(1, 7):
            xv = y_start + kv * ((y_b0 - y_start) / 7.0)
            _garis(msp, (xv, y_lt2), (xv, y_lt2 + 900.0), "A-FLOR-STRS", color=3)

        return (y_start, y_b0)


def _gambar_interior_potongan(msp, arah: str, xl: float, xr: float, x_mid: float, y_nol: float, y_lt2: float, is_2lt: bool) -> None:
    """Menambahkan detail interior tampak dalam (pintu panel, jendela kusen, roster tangga, sanitair)."""
    px = xl + (x_mid - xl) * 0.32
    _poly(msp, [(px, y_nol), (px + 850.0, y_nol), (px + 850.0, y_nol + 2100.0), (px, y_nol + 2100.0)], "A-DOOR", color=8)
    _poly(msp, [(px + 60.0, y_nol), (px + 790.0, y_nol), (px + 790.0, y_nol + 2040.0), (px + 60.0, y_nol + 2040.0)], "A-DOOR", color=8)
    _poly(msp, [(px + 150.0, y_nol + 1050.0), (px + 700.0, y_nol + 1050.0), (px + 700.0, y_nol + 1900.0), (px + 150.0, y_nol + 1900.0)], "A-DOOR", color=8)
    _poly(msp, [(px + 150.0, y_nol + 180.0), (px + 700.0, y_nol + 180.0), (px + 700.0, y_nol + 920.0), (px + 150.0, y_nol + 920.0)], "A-DOOR", color=8)

    if is_2lt:
        jx2 = xl + (x_mid - xl) * 0.25
        _poly(msp, [(jx2, y_lt2 + 800.0), (jx2 + 1150.0, y_lt2 + 800.0), (jx2 + 1150.0, y_lt2 + 2100.0), (jx2, y_lt2 + 2100.0)], "A-GLAZ", color=8)
        _garis(msp, (jx2 + 575.0, y_lt2 + 800.0), (jx2 + 575.0, y_lt2 + 2100.0), "A-GLAZ", color=8)
        _garis(msp, (jx2, y_lt2 + 1650.0), (jx2 + 1150.0, y_lt2 + 1650.0), "A-GLAZ", color=8)
        if arah == "y":
            # Panel roster dekoratif di samping tangga & sanitair KM/WC di ruang kanan
            rx_r = xl + 5600.0
            _poly(msp, [(rx_r, y_lt2 + 400.0), (rx_r + 1200.0, y_lt2 + 400.0), (rx_r + 1200.0, y_lt2 + 2200.0), (rx_r, y_lt2 + 2200.0)], "A-FURN", color=8)
            for ir in range(1, 6):
                _garis(msp, (rx_r + ir * 200.0, y_lt2 + 400.0), (rx_r + ir * 200.0, y_lt2 + 2200.0), "A-FURN", color=8)
            kx = xr - 720.0
            _poly(msp, [(kx, y_nol), (kx + 380.0, y_nol), (kx + 380.0, y_nol + 420.0), (kx, y_nol + 420.0)], "A-FURN", color=8)
            _poly(msp, [(kx + 240.0, y_nol + 420.0), (kx + 390.0, y_nol + 420.0), (kx + 390.0, y_nol + 800.0), (kx + 240.0, y_nol + 800.0)], "A-FURN", color=8)
            _garis(msp, (xr - 150.0, y_nol + 1100.0), (xr - 150.0, y_nol + 2050.0), "A-FURN", color=8)
            _garis(msp, (xr - 150.0, y_nol + 2050.0), (xr - 360.0, y_nol + 2050.0), "A-FURN", color=8)


def _gambar_rangka_atap_pelana(msp, x_kiri: float, x_kanan: float, y_ring: float, rumah) -> float:
    atap = rumah.atap or {}
    ov = float(atap.get("overstek", 600.0))
    sudut = float(atap.get("kemiringan_derajat", 30.0))
    rad = math.radians(sudut)

    x_mid = (x_kiri + x_kanan) / 2.0
    bentang_setengah = (x_kanan - x_kiri) / 2.0
    tinggi_kuda = bentang_setengah * math.tan(rad)
    y_puncak = y_ring + tinggi_kuda

    _poly(msp, [(x_kiri, y_ring), (x_kanan, y_ring), (x_kanan, y_ring + 80.0), (x_kiri, y_ring + 80.0)], "A-ROOF", color=30)
    _poly(msp, [(x_kiri, y_ring + 80.0), (x_kanan, y_ring + 80.0), (x_mid, y_puncak)], "A-ROOF", tutup=True, color=30)
    _garis(msp, (x_mid, y_ring + 80.0), (x_mid, y_puncak), "A-ROOF", color=30)
    for frac in (0.33, 0.66):
        xm_l = x_kiri + (x_mid - x_kiri) * frac
        ym_l = y_ring + 80.0 + (y_puncak - y_ring - 80.0) * frac
        _garis(msp, (xm_l, y_ring + 80.0), (xm_l, ym_l), "A-ROOF", color=30)
        xm_r = x_kanan - (x_kanan - x_mid) * frac
        _garis(msp, (xm_r, y_ring + 80.0), (xm_r, ym_l), "A-ROOF", color=30)
        # Diagonal web baja ringan
        _garis(msp, (xm_l, y_ring + 80.0), (x_mid if frac > 0.5 else x_kiri + (x_mid - x_kiri) * 0.66, ym_l if frac > 0.5 else y_ring + 80.0 + (y_puncak - y_ring - 80.0) * 0.66), "A-ROOF", color=30)

    x_ov_kiri = x_kiri - ov
    x_ov_kanan = x_kanan + ov
    y_ov = y_ring - ov * math.tan(rad)
    tebal_atap = 115.0

    _poly(msp, [(x_ov_kiri, y_ov), (x_mid, y_puncak), (x_mid, y_puncak + tebal_atap), (x_ov_kiri, y_ov + tebal_atap)], "A-ROOF", color=30)
    _poly(msp, [(x_mid, y_puncak), (x_ov_kanan, y_ov), (x_ov_kanan, y_ov + tebal_atap), (x_mid, y_puncak + tebal_atap)], "A-ROOF", color=30)
    _poly(msp, [(x_ov_kiri - 30.0, y_ov - 60.0), (x_ov_kiri, y_ov - 60.0), (x_ov_kiri, y_ov + tebal_atap + 20.0), (x_ov_kiri - 30.0, y_ov + tebal_atap + 20.0)], "A-ROOF", color=2)
    _poly(msp, [(x_ov_kanan, y_ov - 60.0), (x_ov_kanan + 30.0, y_ov - 60.0), (x_ov_kanan + 30.0, y_ov + tebal_atap + 20.0), (x_ov_kanan, y_ov + tebal_atap + 20.0)], "A-ROOF", color=2)
    return y_puncak + tebal_atap


def gambar_potongan(
    rumah,
    msp,
    potongan_cfg: Optional[Dict[str, object]] = None,
    ox: float = 0.0,
    oy: float = 0.0,
    skala_label: str = "1 : 50",
) -> Tuple[float, float, float, float]:
    _siapkan_layer_potongan(msp.doc)
    cfg = potongan_cfg or {"nama": "A-A", "arah": "x"}
    nama_pot = str(cfg.get("nama", "A-A")).upper()
    arah = str(cfg.get("arah", "x")).lower()
    is_2lt = getattr(rumah, "jumlah_lantai", 1) >= 2

    x0, y0, x1, y1 = rumah.batas
    pos_def = (y0 + y1) / 2.0 if arah == "x" else (x0 + x1) / 2.0
    pos = float(cfg.get("posisi", pos_def))

    s0 = x0 if arah == "x" else y0
    s1 = x1 if arah == "x" else y1
    xl = ox + s0
    xr = ox + s1
    y_nol = oy

    t_lt1 = float(rumah.lantai.get("tinggi_dinding", 3000.0))
    p_lt1 = float(rumah.lantai.get("tinggi_plafon", 2800.0))
    t_lt2 = float(rumah.lantai_2.get("tinggi_dinding", 3200.0)) if is_2lt else 0.0
    p_lt2 = float(rumah.lantai_2.get("tinggi_plafon", 2900.0)) if is_2lt else 0.0

    _garis(msp, (xl - 750.0, y_nol - 150.0), (xr + 750.0, y_nol - 150.0), "A-WALL", color=6)
    tanah_pts = [(xl + 150.0, y_nol - 420.0), (xr - 150.0, y_nol - 420.0), (xr - 150.0, y_nol - 100.0), (xl + 150.0, y_nol - 100.0)]
    _poly(msp, tanah_pts, "S-FNDN", color=8)
    _arsir(msp, tanah_pts, "ANSI31", 55.0, "A-WALL-PATT", color=8)
    _poly(msp, [(xl, y_nol - 100.0), (xr, y_nol - 100.0), (xr, y_nol), (xl, y_nol)], "S-FNDN", color=4)

    pot_lt1 = _dinding_terpotong_pada_garis(rumah.dinding, arah, pos)
    if not pot_lt1:
        pot_lt1 = [(s0, 150.0), (s1, 150.0)]

    x_mid_wall = ox + (pot_lt1[1][0] if len(pot_lt1) > 2 else (s0 + s1) / 2.0)

    for cs, tb in pot_lt1:
        cx_d = ox + cs
        hw = tb / 2.0
        _gambar_pondasi_potongan(msp, cx_d, y_nol, rumah, is_2lt)
        d_pts = [(cx_d - hw, y_nol), (cx_d + hw, y_nol), (cx_d + hw, y_nol + t_lt1), (cx_d - hw, y_nol + t_lt1)]
        _poly(msp, d_pts, "A-WALL", color=6)
        _arsir(msp, d_pts, "ANSI31", 40.0, "A-WALL-PATT")
        if is_2lt:
            _poly(msp, [(cx_d - 125.0, y_nol), (cx_d + 125.0, y_nol), (cx_d + 125.0, y_nol + t_lt1 + t_lt2), (cx_d - 125.0, y_nol + t_lt1 + t_lt2)], "S-COLS", color=1)

    y_atas_bgn = y_nol + t_lt1
    _gambar_interior_potongan(msp, arah, xl, xr, x_mid_wall, y_nol, y_atas_bgn, is_2lt)

    if is_2lt:
        y_lt2 = y_nol + t_lt1
        t_pelat = float(((rumah.struktur or {}).get("pelat_lantai") or {}).get("tebal", 120.0))

        n_tg = int(rumah.tangga.jumlah_anak_tangga) if rumah.tangga else 15
        xv0, xv1 = _gambar_tangga_potongan_sinkron(msp, arah, xl, xr, x_mid_wall, y_nol, y_lt2, t_pelat, n_tg)

        segmen_pelat: List[Tuple[float, float]] = []
        if xv0 > xl - 50.0:
            segmen_pelat.append((xl - 125.0, xv0))
        if xv1 < xr + 50.0:
            segmen_pelat.append((xv1, xr + 125.0))
        for sp0, sp1 in segmen_pelat:
            if sp1 - sp0 > 80.0:
                p_pts = [(sp0, y_lt2 - t_pelat), (sp1, y_lt2 - t_pelat), (sp1, y_lt2), (sp0, y_lt2)]
                _poly(msp, p_pts, "S-COLS", color=1)
                _arsir(msp, p_pts, "AR-CONC", 22.0, "S-COLS", color=1)

        if xv0 > xl + 200.0:
            _garis(msp, (xl + 100.0, y_nol + p_lt1), (xv0 - 50.0, y_nol + p_lt1), "A-WALL", color=6)

        pot_lt2 = _dinding_terpotong_pada_garis(rumah.dinding_lt2, arah, pos)
        if not pot_lt2:
            pot_lt2 = [(s0, 150.0), (s1, 150.0)]
        for cs2, tb2 in pot_lt2:
            cx_d2 = ox + cs2
            hw2 = tb2 / 2.0
            b_pts = [(cx_d2 - 100.0, y_lt2 - 350.0), (cx_d2 + 100.0, y_lt2 - 350.0), (cx_d2 + 100.0, y_lt2 - t_pelat), (cx_d2 - 100.0, y_lt2 - t_pelat)]
            _poly(msp, b_pts, "S-COLS", color=1)
            _arsir(msp, b_pts, "AR-CONC", 22.0, "S-COLS", color=1)
            d2_pts = [(cx_d2 - hw2, y_lt2), (cx_d2 + hw2, y_lt2), (cx_d2 + hw2, y_lt2 + t_lt2), (cx_d2 - hw2, y_lt2 + t_lt2)]
            _poly(msp, d2_pts, "A-WALL", color=6)
            _arsir(msp, d2_pts, "ANSI31", 40.0, "A-WALL-PATT")

        _garis(msp, (xl, y_lt2 + p_lt2), (xr, y_lt2 + p_lt2), "A-WALL", color=6)
        y_atas_bgn = y_lt2 + t_lt2
        rb_pts = [(xl - 100.0, y_atas_bgn - 200.0), (xr + 100.0, y_atas_bgn - 200.0), (xr + 100.0, y_atas_bgn), (xl - 100.0, y_atas_bgn)]
        _poly(msp, rb_pts, "S-COLS", color=1)
        _arsir(msp, rb_pts, "AR-CONC", 22.0, "S-COLS", color=1)
    else:
        _garis(msp, (xl, y_nol + p_lt1), (xr, y_nol + p_lt1), "A-WALL", color=6)
        rb_pts = [(xl - 75.0, y_atas_bgn - 150.0), (xr + 75.0, y_atas_bgn - 150.0), (xr + 75.0, y_atas_bgn), (xl - 75.0, y_atas_bgn)]
        _poly(msp, rb_pts, "S-COLS", color=1)
        _arsir(msp, rb_pts, "AR-CONC", 22.0, "S-COLS", color=1)

    y_puncak = _gambar_rangka_atap_pelana(msp, xl, xr, y_atas_bgn, rumah)

    x_lbl = xl - 1150.0
    _callout_kiri(msp, ((xl + (xl + xr) / 2.0) / 2.0, (y_atas_bgn + y_puncak) / 2.0 + 180.0), x_lbl, y_puncak - 120.0, "PENUTUP ATAP GENTENG")
    _callout_kiri(msp, (xl + (xr - xl) * 0.25, y_atas_bgn + 240.0), x_lbl, y_atas_bgn + 480.0, "KUDA-KUDA BAJA RINGAN")
    _callout_kiri(msp, (xl, y_atas_bgn - 100.0), x_lbl, y_atas_bgn - 80.0, "RING BALK 15/20")
    if is_2lt:
        _callout_kiri(msp, (xl + 400.0, y_nol + t_lt1 + p_lt2), x_lbl, y_nol + t_lt1 + p_lt2 - 260.0, f"PLAFOND +{(t_lt1 + p_lt2)/1000:.2f}")
        _callout_kiri(msp, (xl + 450.0, y_nol + t_lt1 - 60.0), x_lbl, y_nol + t_lt1 + 160.0, "PELAT LANTAI t=12 cm")
        _callout_kiri(msp, (xl, y_nol + t_lt1 - 240.0), x_lbl, y_nol + t_lt1 - 380.0, "BALOK INDUK 20/35")
        _callout_kiri(msp, (xl, y_nol + t_lt1 * 0.45), x_lbl, y_nol + t_lt1 * 0.45, "DINDING 1/2 BATA")
        _callout_kiri(msp, (xl, y_nol - 150.0), x_lbl, y_nol - 280.0, "SLOOF 20/30")
        _callout_kiri(msp, (xl - 250.0, y_nol - 1050.0), x_lbl, y_nol - 980.0, "FOOTPLAT 100x100x25")
    else:
        _callout_kiri(msp, (xl + 400.0, y_nol + p_lt1), x_lbl, y_nol + p_lt1 - 260.0, f"PLAFOND +{p_lt1/1000:.2f}")
        _callout_kiri(msp, (xl, y_nol + t_lt1 * 0.45), x_lbl, y_nol + t_lt1 * 0.45, "DINDING 1/2 BATA")
        _callout_kiri(msp, (xl, y_nol - 100.0), x_lbl, y_nol - 260.0, "SLOOF 15/20")
        _callout_kiri(msp, (xl - 150.0, y_nol - 550.0), x_lbl, y_nol - 680.0, "PONDASI BATU KALI")

    x_datum = xr + 1050.0
    _garis(msp, (x_datum, y_nol - 1300.0), (x_datum, y_puncak + 300.0), "A-ANNO-SYMB", color=8)
    _simbol_elevasi_kanan(msp, xr, x_datum, y_nol, 0.0)
    if is_2lt:
        _simbol_elevasi_kanan(msp, xr, x_datum, y_nol - 1200.0, -1.20)
        _simbol_elevasi_kanan(msp, xr, x_datum, y_nol + t_lt1, t_lt1 / 1000.0)
        _simbol_elevasi_kanan(msp, xr, x_datum, y_atas_bgn, (t_lt1 + t_lt2) / 1000.0)
    else:
        _simbol_elevasi_kanan(msp, xr, x_datum, y_nol - 900.0, -0.90)
        _simbol_elevasi_kanan(msp, xr, x_datum, y_atas_bgn, t_lt1 / 1000.0)
    _simbol_elevasi_kanan(msp, (xl + xr) / 2.0, x_datum, y_puncak, (y_puncak - y_nol) / 1000.0)

    for idx_c in range(len(pot_lt1) - 1):
        _dim_horizontal(msp, ox + pot_lt1[idx_c][0], ox + pot_lt1[idx_c + 1][0], y_nol - 1450.0)
    _dim_horizontal(msp, xl, xr, y_nol - 1820.0)

    cx_j = (xl + xr) / 2.0
    y_j = y_nol - 2450.0
    _teks(msp, f"POTONGAN {nama_pot}", (cx_j, y_j), tinggi=185.0, color=2)
    _garis(msp, (cx_j - 950.0, y_j - 125.0), (cx_j + 950.0, y_j - 125.0), "A-ANNO-TEXT", color=2)
    _teks(msp, f"Skala {skala_label}", (cx_j, y_j - 260.0), tinggi=115.0, color=2)

    return (xl - 2600.0, y_j - 450.0, x_datum + 750.0, y_puncak + 450.0)


def _gambar_pintu_tampak(msp, x: float, y: float, w: float = 900.0, h: float = 2100.0, dengan_kanopi: bool = True) -> None:
    """Menggambar pintu tampak berpanel kayu dengan kusen, handle, dan topi-topi kanopi."""
    kw = 60.0
    _poly(msp, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], "A-DOOR", color=1)
    _poly(msp, [(x + kw, y), (x + w - kw, y), (x + w - kw, y + h - kw), (x + kw, y + h - kw)], "A-DOOR", color=1)
    # Panel atas & bawah daun pintu
    _poly(msp, [(x + 150.0, y + 1050.0), (x + w - 150.0, y + 1050.0), (x + w - 150.0, y + h - 160.0), (x + 150.0, y + h - 160.0)], "A-DOOR", color=1)
    _poly(msp, [(x + 150.0, y + 180.0), (x + w - 150.0, y + 180.0), (x + w - 150.0, y + 920.0), (x + 150.0, y + 920.0)], "A-DOOR", color=1)
    # Handle pintu
    _garis(msp, (x + w - 140.0, y + 950.0), (x + w - 140.0, y + 1080.0), "A-DOOR", color=2)
    if dengan_kanopi:
        _poly(msp, [(x - 140.0, y + h), (x + w + 140.0, y + h), (x + w + 140.0, y + h + 110.0), (x - 140.0, y + h + 110.0)], "S-COLS", color=2)


def _gambar_jendela_tampak(msp, x: float, y: float, w: float = 1200.0, h: float = 1350.0, dua_daun: bool = True, dengan_kanopi: bool = True) -> None:
    """Menggambar jendela tampak lengkap dengan kusen, daun kaca, bovenlicht, dan ambang bawah."""
    kw = 55.0
    _poly(msp, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], "A-GLAZ", color=4)
    _poly(msp, [(x + kw, y + kw), (x + w - kw, y + kw), (x + w - kw, y + h - kw), (x + kw, y + h - kw)], "A-GLAZ", color=4)
    if dua_daun:
        xm = x + w / 2.0
        _poly(msp, [(xm - 25.0, y + kw), (xm + 25.0, y + kw), (xm + 25.0, y + h - kw), (xm - 25.0, y + h - kw)], "A-GLAZ", color=4)
    # Garis bovenlicht atas
    yb = y + h - 360.0
    _garis(msp, (x + kw, yb), (x + w - kw, yb), "A-GLAZ", color=4)
    # Ambang bawah jendela
    _poly(msp, [(x - 70.0, y - 60.0), (x + w + 70.0, y - 60.0), (x + w + 70.0, y), (x - 70.0, y)], "A-WALL", color=2)
    if dengan_kanopi:
        _poly(msp, [(x - 120.0, y + h), (x + w + 120.0, y + h), (x + w + 120.0, y + h + 100.0), (x - 120.0, y + h + 100.0)], "S-COLS", color=2)


def gambar_tampak(
    rumah,
    msp,
    sisi: str = "depan",
    ox: float = 0.0,
    oy: float = 0.0,
    skala_label: str = "1 : 50",
) -> Tuple[float, float, float, float]:
    """Merender Tampak Depan, Belakang, Kanan, dan Kiri secara natural, berproporsi, dan estetis."""
    _siapkan_layer_potongan(msp.doc)
    sisi_l = sisi.lower().strip()
    is_2lt = getattr(rumah, "jumlah_lantai", 1) >= 2
    x0, y0, x1, y1 = rumah.batas

    is_lebar_x = sisi_l in ("depan", "belakang")
    bentang = (x1 - x0) if is_lebar_x else (y1 - y0)
    xl = ox + (x0 if is_lebar_x else y0)
    xr = xl + bentang
    y_nol = oy

    t_lt1 = float(rumah.lantai.get("tinggi_dinding", 3000.0))
    t_lt2 = float(rumah.lantai_2.get("tinggi_dinding", 3200.0)) if is_2lt else 0.0
    t_tot = t_lt1 + t_lt2

    # Muka tanah & plinth dasar bangunan
    _garis(msp, (xl - 900.0, y_nol - 150.0), (xr + 900.0, y_nol - 150.0), "A-WALL", color=6)
    _poly(msp, [(xl - 80.0, y_nol - 150.0), (xr + 80.0, y_nol - 150.0), (xr + 80.0, y_nol), (xl - 80.0, y_nol)], "S-FNDN", color=4)

    # Massa dinding Lantai 1 & Lantai 2
    _poly(msp, [(xl, y_nol), (xr, y_nol), (xr, y_nol + t_lt1), (xl, y_nol + t_lt1)], "A-WALL", color=6)
    if is_2lt:
        _poly(msp, [(xl, y_nol + t_lt1), (xr, y_nol + t_lt1), (xr, y_nol + t_tot), (xl, y_nol + t_tot)], "A-WALL", color=6)
        # Ban-banan garis pelat lantai 2
        _poly(msp, [(xl - 60.0, y_nol + t_lt1 - 140.0), (xr + 60.0, y_nol + t_lt1 - 140.0), (xr + 60.0, y_nol + t_lt1 + 30.0), (xl - 60.0, y_nol + t_lt1 + 30.0)], "A-WALL", color=2)

    if is_lebar_x:
        if sisi_l == "depan":
            # --- TAMPAK DEPAN ---
            # Pilar teras kiri & undakan tangga teras
            _poly(msp, [(xl, y_nol), (xl + 240.0, y_nol), (xl + 240.0, y_nol + t_lt1), (xl, y_nol + t_lt1)], "S-COLS", color=2)
            _poly(msp, [(xl + 800.0, y_nol - 150.0), (xl + 2400.0, y_nol - 150.0), (xl + 2400.0, y_nol - 75.0), (xl + 800.0, y_nol - 75.0)], "A-WALL", color=8)

            # Pintu Utama berpanel + Sidelight kaca samping
            px = xl + 1100.0
            _gambar_pintu_tampak(msp, px, y_nol, w=900.0, h=2100.0, dengan_kanopi=False)
            _poly(msp, [(px + 900.0, y_nol + 450.0), (px + 1280.0, y_nol + 450.0), (px + 1280.0, y_nol + 2100.0), (px + 900.0, y_nol + 2100.0)], "A-GLAZ", color=4)
            _poly(msp, [(px - 150.0, y_nol + 2100.0), (px + 1430.0, y_nol + 2100.0), (px + 1430.0, y_nol + 2210.0), (px - 150.0, y_nol + 2210.0)], "S-COLS", color=2)

            # Jendela Kamar Tidur 1 kanan bawah
            _gambar_jendela_tampak(msp, xl + 3650.0, y_nol + 700.0, w=1400.0, h=1400.0, dua_daun=True, dengan_kanopi=True)

            if is_2lt:
                y2 = y_nol + t_lt1
                # Pintu akses Balkon + Jendela Kamar Tidur Anak kanan atas
                _gambar_pintu_tampak(msp, xl + 1100.0, y2, w=800.0, h=2100.0, dengan_kanopi=True)
                _gambar_jendela_tampak(msp, xl + 3750.0, y2 + 700.0, w=1400.0, h=1400.0, dua_daun=True, dengan_kanopi=True)

                # Balkon kantilever depan kiri (x = 0..3000)
                bx_e = xl + 3000.0
                _poly(msp, [(xl - 80.0, y2 - 140.0), (bx_e, y2 - 140.0), (bx_e, y2 + 30.0), (xl - 80.0, y2 + 30.0)], "S-COLS", color=2)
                _poly(msp, [(xl - 60.0, y2 + 30.0), (bx_e, y2 + 30.0), (bx_e, y2 + 980.0), (xl - 60.0, y2 + 980.0)], "A-FLOR-STRS", color=3)
                _garis(msp, (xl - 60.0, y2 + 920.0), (bx_e, y2 + 920.0), "A-FLOR-STRS", color=3)
                for ib in range(1, 16):
                    xb = xl - 60.0 + ib * ((bx_e - xl + 60.0) / 16.0)
                    _garis(msp, (xb, y2 + 30.0), (xb, y2 + 920.0), "A-FLOR-STRS", color=3)
        else:
            # --- TAMPAK BELAKANG ---
            _gambar_jendela_tampak(msp, xl + 1000.0, y_nol + 800.0, w=1200.0, h=1300.0, dua_daun=True, dengan_kanopi=True)
            _gambar_jendela_tampak(msp, xl + 3300.0, y_nol + 800.0, w=1100.0, h=1300.0, dua_daun=True, dengan_kanopi=True)
            # Bovenlicht KM/WC Lt.1
            _poly(msp, [(xr - 1100.0, y_nol + 1850.0), (xr - 500.0, y_nol + 1850.0), (xr - 500.0, y_nol + 2250.0), (xr - 1100.0, y_nol + 2250.0)], "A-GLAZ", color=4)
            if is_2lt:
                y2 = y_nol + t_lt1
                _gambar_jendela_tampak(msp, xl + 1000.0, y2 + 800.0, w=1200.0, h=1300.0, dua_daun=True, dengan_kanopi=True)
                _gambar_jendela_tampak(msp, xl + 3300.0, y2 + 800.0, w=1100.0, h=1300.0, dua_daun=True, dengan_kanopi=True)
                _poly(msp, [(xr - 1100.0, y2 + 1850.0), (xr - 500.0, y2 + 1850.0), (xr - 500.0, y2 + 2250.0), (xr - 1100.0, y2 + 2250.0)], "A-GLAZ", color=4)
    else:
        # --- TAMPAK SAMPING KANAN & KIRI ---
        _gambar_jendela_tampak(msp, xl + bentang * 0.22, y_nol + 800.0, w=1200.0, h=1300.0, dua_daun=True, dengan_kanopi=True)
        _gambar_jendela_tampak(msp, xl + bentang * 0.64, y_nol + 800.0, w=1200.0, h=1300.0, dua_daun=True, dengan_kanopi=True)

        if is_2lt:
            y2 = y_nol + t_lt1
            _gambar_jendela_tampak(msp, xl + bentang * 0.22, y2 + 800.0, w=1200.0, h=1300.0, dua_daun=True, dengan_kanopi=True)
            _gambar_jendela_tampak(msp, xl + bentang * 0.64, y2 + 800.0, w=1200.0, h=1300.0, dua_daun=True, dengan_kanopi=True)

            # Profil samping Balkon Depan (di sisi kiri untuk Tampak Kanan, sisi kanan untuk Tampak Kiri)
            if sisi_l == "kanan":
                _poly(msp, [(xl - 1500.0, y2 - 140.0), (xl, y2 - 140.0), (xl, y2 + 30.0), (xl - 1500.0, y2 + 30.0)], "S-COLS", color=2)
                _poly(msp, [(xl - 1500.0, y2 + 30.0), (xl, y2 + 30.0), (xl, y2 + 980.0), (xl - 1500.0, y2 + 980.0)], "A-FLOR-STRS", color=3)
                for ib in range(1, 9):
                    xb = xl - ib * (1500.0 / 9.0)
                    _garis(msp, (xb, y2 + 30.0), (xb, y2 + 980.0), "A-FLOR-STRS", color=3)
            else:
                _poly(msp, [(xr, y2 - 140.0), (xr + 1500.0, y2 - 140.0), (xr + 1500.0, y2 + 30.0), (xr, y2 + 30.0)], "S-COLS", color=2)
                _poly(msp, [(xr, y2 + 30.0), (xr + 1500.0, y2 + 30.0), (xr + 1500.0, y2 + 980.0), (xr, y2 + 980.0)], "A-FLOR-STRS", color=3)
                for ib in range(1, 9):
                    xb = xr + ib * (1500.0 / 9.0)
                    _garis(msp, (xb, y2 + 30.0), (xb, y2 + 980.0), "A-FLOR-STRS", color=3)

    # Atap Pelana Proporsional
    atap = rumah.atap or {}
    ov = float(atap.get("overstek", 600.0))
    sudut = float(atap.get("kemiringan_derajat", 30.0))
    rad = math.radians(sudut)
    y_ring = y_nol + t_tot

    if is_lebar_x:
        bentang_samping = (y1 - y0) / 2.0
        tinggi_atap = bentang_samping * math.tan(rad)
        y_bub = y_ring + tinggi_atap
        y_ov = y_ring - ov * math.tan(rad)
        # Bidang genteng + lisplank bawah & bubungan atas
        _poly(msp, [(xl - ov, y_ov), (xr + ov, y_ov), (xr + ov, y_bub), (xl - ov, y_bub)], "A-ROOF", color=30)
        _poly(msp, [(xl - ov, y_ov - 160.0), (xr + ov, y_ov - 160.0), (xr + ov, y_ov), (xl - ov, y_ov)], "A-ROOF", color=2)
        _poly(msp, [(xl - ov, y_bub - 110.0), (xr + ov, y_bub - 110.0), (xr + ov, y_bub), (xl - ov, y_bub)], "A-ROOF", color=2)
        # Garis susunan genteng horizontal halus (layer A-ROOF-PATT warna abu-abu)
        n_baris = max(7, int((y_bub - 110.0 - y_ov) / 280.0))
        for k in range(1, n_baris):
            yk = y_ov + k * ((y_bub - 110.0 - y_ov) / n_baris)
            _garis(msp, (xl - ov, yk), (xr + ov, yk), "A-ROOF-PATT", color=8)
        y_puncak = y_bub
    else:
        bentang_setengah = bentang / 2.0
        tinggi_atap = bentang_setengah * math.tan(rad)
        y_bub = y_ring + tinggi_atap
        y_ov = y_ring - ov * math.tan(rad)
        x_mid = (xl + xr) / 2.0
        # Kemiringan atap pelana + lisplank miring
        _poly(msp, [(xl - ov, y_ov), (x_mid, y_bub), (xr + ov, y_ov), (xr + ov, y_ov + 140.0), (x_mid, y_bub + 140.0), (xl - ov, y_ov + 140.0)], "A-ROOF", color=30)
        # Dinding segitiga sopi-sopi + lubang angin ventilasi segitiga
        _poly(msp, [(xl, y_ring), (xr, y_ring), (x_mid, y_bub)], "A-WALL", color=6)
        _poly(msp, [(x_mid - 360.0, y_ring + 350.0), (x_mid + 360.0, y_ring + 350.0), (x_mid, y_ring + 820.0)], "A-GLAZ", color=4)
        y_puncak = y_bub + 140.0

    # Elevasi datum di sisi kanan + dimensi lebar bawah
    x_datum = xr + (1850.0 if (is_2lt and sisi_l == "kiri") else 1000.0)
    _garis(msp, (x_datum, y_nol - 250.0), (x_datum, y_puncak + 300.0), "A-ANNO-SYMB", color=8)
    _simbol_elevasi_kanan(msp, xr, x_datum, y_nol, 0.0)
    if is_2lt:
        _simbol_elevasi_kanan(msp, xr, x_datum, y_nol + t_lt1, t_lt1 / 1000.0)
    _simbol_elevasi_kanan(msp, xr, x_datum, y_ring, t_tot / 1000.0)
    _simbol_elevasi_kanan(msp, (xl + xr) / 2.0, x_datum, y_puncak, (y_puncak - y_nol) / 1000.0)

    _dim_horizontal(msp, xl, xr, y_nol - 550.0)
    cx_j = (xl + xr) / 2.0
    y_j = y_nol - 1150.0
    _teks(msp, f"TAMPAK {sisi_l.upper()}", (cx_j, y_j), tinggi=185.0, color=2)
    _garis(msp, (cx_j - 950.0, y_j - 125.0), (cx_j + 950.0, y_j - 125.0), "A-ANNO-TEXT", color=2)
    _teks(msp, f"Skala {skala_label}", (cx_j, y_j - 260.0), tinggi=115.0, color=2)

    return (xl - 1800.0, y_j - 450.0, x_datum + 750.0, y_puncak + 450.0)