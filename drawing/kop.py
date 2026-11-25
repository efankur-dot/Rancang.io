"""
Modul Kop Gambar Kerja Standar Proyek Konsultan (Kertas A3 Skala Adaptif).
- Ukuran fisik kertas A3: 420 x 297 mm.
- Pada skala 1 : S, ukuran modelspace bingkai luar adalah (420 * S) x (297 * S) mm,
  sehingga koordinat bangunan tetap 1:1 mm (akurat saat diukur di AutoCAD) sementara
  proporsi teks dan garis kop selalu konsisten saat dicetak ke kertas A3.
"""

from datetime import datetime
from typing import Dict, Optional, Sequence, Tuple

import ezdxf

LEBAR_A3 = 42000.0
TINGGI_A3 = 29700.0
MARGIN_KIRI = 1500.0
MARGIN_LUAR = 1000.0
LEBAR_KOP = 7500.0

SKALA_STANDAR: Tuple[int, ...] = (10, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200)


def pilih_skala_otomatis(
    bbox: Tuple[float, float, float, float],
    skala_kandidat: Sequence[int] = SKALA_STANDAR,
    margin_rasio: float = 1.08,
) -> int:
    """
    Memilih skala standar terbaik (penyebut S terkecil) agar bbox gambar muat nyaman
    di dalam viewport bersih kertas A3 (320 mm x 277 mm pada kertas).
    """
    x0, y0, x1, y1 = bbox
    w_req = max(1.0, (x1 - x0) * margin_rasio)
    h_req = max(1.0, (y1 - y0) * margin_rasio)

    # Viewport bersih pada kertas A3 = 320 mm x 277 mm
    for s in sorted(skala_kandidat):
        if (320.0 * s) >= w_req and (277.0 * s) >= h_req:
            return int(s)
    return int(max(skala_kandidat))


def siapkan_layer_kop(doc: ezdxf.document.Drawing) -> None:
    """Menyiapkan layer dan text style bersih untuk garis tepi dan kop konsultan."""
    layers = [
        {"name": "A-ANNO-KOP", "color": 7},        # Putih/Hitam (Garis bingkai & sekat utama)
        {"name": "A-ANNO-KOP-THIN", "color": 8},   # Abu-abu (Garis tepi luar & sub-sekat tipis)
        {"name": "A-ANNO-KOP-LABEL", "color": 8},  # Abu-abu terang (Label header kecil)
        {"name": "A-ANNO-KOP-TEXT", "color": 7},   # Putih/Hitam (Isi data utama)
        {"name": "A-ANNO-KOP-ACCENT", "color": 4}, # Cyan (Judul proyek, judul lembar & kode)
    ]
    for l in layers:
        if l["name"] not in doc.layers:
            doc.layers.add(name=l["name"], color=l["color"])
        else:
            doc.layers.get(l["name"]).dxf.color = l["color"]

    if "KOP_FONT" not in doc.styles:
        try:
            doc.styles.add("KOP_FONT", font="arial.ttf")
        except Exception:
            doc.styles.new("KOP_FONT")


def hitung_viewport_kop(
    ox: float, oy: float, skala_num: int = 100
) -> Tuple[float, float, float, float]:
    """Mengembalikan batas area gambar bersih (vx0, vy0, vx1, vy1) di sebelah kiri kop."""
    f = skala_num / 100.0
    vx0 = ox + MARGIN_KIRI * f
    vy0 = oy + MARGIN_LUAR * f
    vx1 = ox + (LEBAR_A3 - MARGIN_LUAR - LEBAR_KOP) * f
    vy1 = oy + (TINGGI_A3 - MARGIN_LUAR) * f
    return (vx0, vy0, vx1, vy1)


def _tambah_teks(
    msp,
    teks: str,
    pos: Tuple[float, float],
    tinggi: float,
    layer: str = "A-ANNO-KOP-TEXT",
    lebar_maks: float = 6900.0,
    anchor: int = 5,
    spasi_baris: float = 1.3,
) -> None:
    """Helper penempatan MTEXT berformat rapi di dalam sel kop."""
    style_name = "KOP_FONT" if "KOP_FONT" in msp.doc.styles else "Standard"
    mt = msp.add_mtext(
        teks,
        dxfattribs={
            "layer": layer,
            "style": style_name,
            "char_height": tinggi,
            "width": lebar_maks,
            "attachment_point": anchor,
            "line_spacing_factor": spasi_baris,
        },
    )
    mt.set_location(pos)


def _gambar_simbol_utara(msp, cx: float, cy: float, radius: float = 460.0, f: float = 1.0) -> None:
    """Menggambar simbol kompas arah utara yang proporsional pada kolom kop."""
    msp.add_circle((cx, cy), radius=radius, dxfattribs={"layer": "A-ANNO-KOP"})
    msp.add_circle((cx, cy), radius=radius * 0.85, dxfattribs={"layer": "A-ANNO-KOP-THIN"})

    p_atas = (cx, cy + radius * 1.18)
    p_bawah = (cx, cy - radius * 0.95)
    p_kiri = (cx - radius * 0.28, cy)
    p_kanan = (cx + radius * 0.28, cy)

    jarum_utara = [p_atas, p_kiri, (cx, cy + radius * 0.12), p_kanan]
    msp.add_lwpolyline(jarum_utara, close=True, dxfattribs={"layer": "A-ANNO-KOP-ACCENT", "color": 4})
    h = msp.add_hatch(color=4, dxfattribs={"layer": "A-ANNO-KOP-ACCENT"})
    h.set_solid_fill()
    h.paths.add_polyline_path(jarum_utara, is_closed=True)

    msp.add_lwpolyline(
        [p_bawah, p_kiri, (cx, cy - radius * 0.12), p_kanan],
        close=True,
        dxfattribs={"layer": "A-ANNO-KOP"},
    )
    _tambah_teks(
        msp,
        "U",
        (cx, cy + radius * 1.48),
        tinggi=220 * f,
        layer="A-ANNO-KOP-ACCENT",
        lebar_maks=600 * f,
        anchor=5,
    )


def gambar_kop_a3(
    msp,
    ox: float,
    oy: float,
    judul_lembar: str = "DENAH RENCANA",
    kode_gambar: str = "ARS-01",
    nomor_lembar: str = "01 / 08",
    skala: Optional[str] = None,
    skala_num: int = 100,
    info_proyek: Optional[Dict[str, str]] = None,
    tampilkan_utara: bool = True,
) -> Tuple[float, float, float, float]:
    """
    Menggambar bingkai kertas A3 dan kop vertikal sisi kanan standar konsultan
    yang diskalakan sesuai skala_num (misal 1:50 -> f=0.5, 1:20 -> f=0.2).
    Mengembalikan bounding box penuh lembar (x0, y0, x1, y1).
    """
    siapkan_layer_kop(msp.doc)
    info = info_proyek or {}
    f = skala_num / 100.0
    label_skala = skala or f"1 : {skala_num}"

    nama_proyek = info.get("nama_proyek") or "RUMAH TINGGAL SEDERHANA"
    lokasi_proyek = info.get("lokasi") or "Kab. Magelang, Jawa Tengah"
    klien = info.get("klien") or "Pemilik Bangunan"
    perencana = info.get("perencana") or "Rancang.io Engineering Studio"
    tanggal = info.get("tanggal") or datetime.now().strftime("%d %B %Y")

    x_luar_0, y_luar_0 = ox, oy
    x_luar_1, y_luar_1 = ox + LEBAR_A3 * f, oy + TINGGI_A3 * f

    ix0 = ox + MARGIN_KIRI * f
    iy0 = oy + MARGIN_LUAR * f
    ix1 = ox + (LEBAR_A3 - MARGIN_LUAR) * f
    iy1 = oy + (TINGGI_A3 - MARGIN_LUAR) * f

    kx0 = ix1 - LEBAR_KOP * f
    kx1 = ix1
    cx_kop = kx0 + (LEBAR_KOP * f) / 2.0
    pad_x = 280.0 * f
    w_teks = (LEBAR_KOP * f) - 2 * pad_x

    # 1. Garis Tepi Luar Kertas A3 & Garis Tepi Dalam
    msp.add_lwpolyline(
        [(x_luar_0, y_luar_0), (x_luar_1, y_luar_0), (x_luar_1, y_luar_1), (x_luar_0, y_luar_1)],
        close=True,
        dxfattribs={"layer": "A-ANNO-KOP-THIN"},
    )
    msp.add_lwpolyline(
        [(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)],
        close=True,
        dxfattribs={"layer": "A-ANNO-KOP"},
    )

    # 2. Garis Batas Vertikal Kolom Kop Kanan
    msp.add_line((kx0, iy0), (kx0, iy1), dxfattribs={"layer": "A-ANNO-KOP"})

    # 3. Sekat Horizontal Utama Kop
    sekat_utama = [26300, 22100, 20100, 11900, 9000, 6400, 3400]
    for y_rel in sekat_utama:
        msp.add_line((kx0, oy + y_rel * f), (kx1, oy + y_rel * f), dxfattribs={"layer": "A-ANNO-KOP"})

    # 4. Sub-sekat Tipis untuk Pemisahan Field yang Rapi
    sekat_tipis = [24100, 17200, 7450]
    for y_rel in sekat_tipis:
        msp.add_line((kx0, oy + y_rel * f), (kx1, oy + y_rel * f), dxfattribs={"layer": "A-ANNO-KOP-THIN"})

    # --- BLOK 1: IDENTITAS STUDIO / KONSULTAN ---
    _tambah_teks(
        msp, "RANCANG.IO", (cx_kop, oy + 27880 * f),
        tinggi=380 * f, layer="A-ANNO-KOP-ACCENT", lebar_maks=w_teks, anchor=5,
    )
    _tambah_teks(
        msp, "ARCHITECTURAL & CIVIL ENGINEERING STUDIO", (cx_kop, oy + 26980 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=5,
    )

    # --- BLOK 2A: NAMA PROYEK ---
    _tambah_teks(
        msp, "NAMA PROYEK", (kx0 + pad_x, oy + 26040 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    _tambah_teks(
        msp, nama_proyek.upper(), (cx_kop, oy + 24980 * f),
        tinggi=265 * f, layer="A-ANNO-KOP-ACCENT", lebar_maks=w_teks, anchor=5,
    )

    # --- BLOK 2B: LOKASI PROYEK ---
    _tambah_teks(
        msp, "LOKASI PROYEK", (kx0 + pad_x, oy + 23840 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    _tambah_teks(
        msp, lokasi_proyek, (cx_kop, oy + 22920 * f),
        tinggi=215 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=w_teks, anchor=5,
    )

    # --- BLOK 3: PEMILIK / KLIEN ---
    _tambah_teks(
        msp, "PEMILIK / KLIEN", (kx0 + pad_x, oy + 21840 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    _tambah_teks(
        msp, klien, (cx_kop, oy + 20920 * f),
        tinggi=225 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=w_teks, anchor=5,
    )

    # --- BLOK 4A: CATATAN TEKNIS ---
    _tambah_teks(
        msp, "CATATAN TEKNIS", (kx0 + pad_x, oy + 19840 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    catatan = (
        "1. Seluruh ukuran dalam satuan milimeter (mm).\n"
        "2. Mutu beton struktur K-300; kolom 150×150 mm.\n"
        "3. Dinding pasangan bata merah 1:4 tebal 150 mm."
    )
    _tambah_teks(
        msp, catatan, (kx0 + pad_x, oy + 19360 * f),
        tinggi=160 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=w_teks, anchor=1, spasi_baris=1.38,
    )

    # --- BLOK 4B: LEGENDA GAMBAR ---
    _tambah_teks(
        msp, "LEGENDA GAMBAR", (kx0 + pad_x, oy + 16940 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )

    legenda = [
        ("S-COLS", 1, "Kolom Praktis Beton 150×150"),
        ("A-WALL", 6, "Dinding Pasangan Bata Merah"),
        ("A-DOOR", 1, "Kusen & Daun Pintu"),
        ("A-GLAZ", 4, "Kusen & Kaca Jendela"),
        ("A-FURN", 30, "Furnitur & Sanitair"),
        ("A-ANNO-DIMS", 3, "Garis Dimensi Ukur"),
    ]
    y_leg = oy + 16250 * f
    for lyr, warna, ket in legenda:
        p_bl = (kx0 + pad_x, y_leg - 300 * f)
        p_br = (kx0 + pad_x + 560 * f, y_leg - 300 * f)
        p_tr = (kx0 + pad_x + 560 * f, y_leg)
        p_tl = (kx0 + pad_x, y_leg)
        kotak = [p_bl, p_br, p_tr, p_tl]

        if lyr == "S-COLS":
            h_leg = msp.add_hatch(color=warna, dxfattribs={"layer": lyr})
            h_leg.set_solid_fill()
            h_leg.paths.add_polyline_path(kotak, is_closed=True)
            msp.add_lwpolyline(kotak, close=True, dxfattribs={"layer": lyr, "color": warna})
            msp.add_line(p_bl, p_tr, dxfattribs={"layer": lyr, "color": warna})
            msp.add_line(p_tl, p_br, dxfattribs={"layer": lyr, "color": warna})
        else:
            msp.add_lwpolyline(kotak, close=True, dxfattribs={"layer": lyr, "color": warna})

        _tambah_teks(
            msp, ket, (kx0 + pad_x + 760 * f, y_leg - 150 * f),
            tinggi=165 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=w_teks - 760 * f, anchor=4,
        )
        y_leg -= 720 * f

    # --- BLOK 5: ARAH UTARA & SKALA / FORMAT ---
    kx_mid = kx0 + 3400.0 * f
    msp.add_line((kx_mid, oy + 9000 * f), (kx_mid, oy + 11900 * f), dxfattribs={"layer": "A-ANNO-KOP"})
    msp.add_line((kx_mid, oy + 10200 * f), (kx1, oy + 10200 * f), dxfattribs={"layer": "A-ANNO-KOP-THIN"})

    cx_kiri = (kx0 + kx_mid) / 2.0
    if tampilkan_utara:
        _gambar_simbol_utara(msp, cx_kiri, oy + 10240 * f, radius=450.0 * f, f=f)
    else:
        _tambah_teks(
            msp, "PROYEKSI\nORTOGONAL", (cx_kiri, oy + 10450 * f),
            tinggi=175 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=(kx_mid - kx0) - 240 * f, anchor=5, spasi_baris=1.35,
        )

    cx_kanan = (kx_mid + kx1) / 2.0
    _tambah_teks(
        msp, "SKALA", (kx_mid + 240 * f, oy + 11680 * f),
        tinggi=150 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=3600 * f, anchor=1,
    )
    _tambah_teks(
        msp, label_skala, (cx_kanan, oy + 10840 * f),
        tinggi=310 * f, layer="A-ANNO-KOP-ACCENT", lebar_maks=3600 * f, anchor=5,
    )

    _tambah_teks(
        msp, "UKURAN KERTAS", (kx_mid + 240 * f, oy + 10020 * f),
        tinggi=140 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=3600 * f, anchor=1,
    )
    _tambah_teks(
        msp, "A3 (420 × 297 mm)", (cx_kanan, oy + 9440 * f),
        tinggi=165 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=3600 * f, anchor=5,
    )

    # --- BLOK 6: PERENCANA & TANGGAL TERBIT ---
    _tambah_teks(
        msp, "PERENCANA / DIGAMBAR OLEH", (kx0 + pad_x, oy + 8780 * f),
        tinggi=150 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    _tambah_teks(
        msp, perencana, (cx_kop, oy + 8020 * f),
        tinggi=210 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=w_teks, anchor=5,
    )

    _tambah_teks(
        msp, "TANGGAL TERBIT", (kx0 + pad_x, oy + 7260 * f),
        tinggi=145 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    _tambah_teks(
        msp, tanggal, (cx_kop, oy + 6760 * f),
        tinggi=185 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=w_teks, anchor=5,
    )

    # --- BLOK 7: JUDUL LEMBAR GAMBAR ---
    _tambah_teks(
        msp, "JUDUL GAMBAR", (kx0 + pad_x, oy + 6150 * f),
        tinggi=155 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=w_teks, anchor=1,
    )
    _tambah_teks(
        msp, judul_lembar.upper(), (cx_kop, oy + 4720 * f),
        tinggi=315 * f, layer="A-ANNO-KOP-ACCENT", lebar_maks=w_teks, anchor=5,
    )

    # --- BLOK 8: NO. GAMBAR & NOMOR LEMBAR ---
    kx_kode = kx0 + 4100.0 * f
    msp.add_line((kx_kode, iy0), (kx_kode, oy + 3400 * f), dxfattribs={"layer": "A-ANNO-KOP"})

    _tambah_teks(
        msp, "NO. GAMBAR", (kx0 + pad_x, oy + 3160 * f),
        tinggi=150 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=3600 * f, anchor=1,
    )
    _tambah_teks(
        msp, kode_gambar.upper(), ((kx0 + kx_kode) / 2.0, oy + 2020 * f),
        tinggi=315 * f, layer="A-ANNO-KOP-ACCENT", lebar_maks=3600 * f, anchor=5,
    )

    _tambah_teks(
        msp, "LEMBAR", (kx_kode + 240 * f, oy + 3160 * f),
        tinggi=150 * f, layer="A-ANNO-KOP-LABEL", lebar_maks=3000 * f, anchor=1,
    )
    _tambah_teks(
        msp, nomor_lembar, ((kx_kode + kx1) / 2.0, oy + 2020 * f),
        tinggi=285 * f, layer="A-ANNO-KOP-TEXT", lebar_maks=3000 * f, anchor=5,
    )

    return (x_luar_0, y_luar_0, x_luar_1, y_luar_1)