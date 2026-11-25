"""
Modul Kop Gambar A3 & Penyusun Paket Multi-Lembar Kerja (.DXF) + Pratinjau Gambar.
"""
import datetime
import io
from typing import Any, Dict, List, Optional, Tuple

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.enums import TextEntityAlignment as TA
import matplotlib.pyplot as plt

from drawing.denah import gambar_denah_lantai
from drawing.detail import gambar_detail
from drawing.potongan import gambar_potongan, gambar_tampak


def _siapkan_layer_kop(doc: ezdxf.document.Drawing) -> None:
    for nama, warna in [
        ("A-ANNO-TITL", 7),
        ("A-ANNO-TEXT", 2),
        ("A-ANNO-DIMS", 3),
    ]:
        if nama not in doc.layers:
            doc.layers.add(nama, color=warna)

    if "KOP_FONT" not in doc.styles:
        try:
            doc.styles.add("KOP_FONT", font="arial.ttf")
        except Exception:
            doc.styles.new("KOP_FONT")


def _gambar_bingkai_kop_a3(
    msp,
    x0: float,
    y0: float,
    skala: float,
    meta: Dict[str, str],
) -> Tuple[float, float, float, float]:
    """Menggambar bingkai kertas A3 (420 x 297 mm) diskalakan dengan `skala` + blok kop kanan."""
    W = 420.0 * skala
    H = 297.0 * skala
    m_kiri = 15.0 * skala
    m_lain = 8.0 * skala
    w_kop = 74.0 * skala

    bx0, by0 = x0 + m_kiri, y0 + m_lain
    bx1, by1 = x0 + W - m_lain, y0 + H - m_lain
    kx0 = bx1 - w_kop

    msp.add_lwpolyline([(x0, y0), (x0 + W, y0), (x0 + W, y0 + H), (x0, y0 + H)], close=True, dxfattribs={"layer": "A-ANNO-TITL", "color": 8})
    msp.add_lwpolyline([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], close=True, dxfattribs={"layer": "A-ANNO-TITL", "lineweight": 35})
    msp.add_line((kx0, by0), (kx0, by1), dxfattribs={"layer": "A-ANNO-TITL", "lineweight": 35})

    style_name = "KOP_FONT" if "KOP_FONT" in msp.doc.styles else "Standard"

    def teks_kop(isi: str, px: float, py: float, h_mm: float, rata=TA.MIDDLE_CENTER, warna: int = 7):
        msp.add_text(
            isi,
            height=h_mm * skala,
            dxfattribs={"layer": "A-ANNO-TEXT", "style": style_name, "color": warna},
        ).set_placement((px, py), align=rata)

    cx_k = (kx0 + bx1) / 2.0
    tinggi_tot = by1 - by0
    rasio_sekat = [0.16, 0.34, 0.56, 0.72, 0.86]
    ys_sekat = [by1 - r * tinggi_tot for r in rasio_sekat]
    for ys in ys_sekat:
        msp.add_line((kx0, ys), (bx1, ys), dxfattribs={"layer": "A-ANNO-TITL"})

    teks_kop("GAMBAR KERJA", cx_k, (by1 + ys_sekat[0]) / 2.0 + 3.2 * skala, 2.9, warna=3)
    teks_kop("ARSITEKTUR & STRUKTUR", cx_k, (by1 + ys_sekat[0]) / 2.0 - 3.2 * skala, 2.1, warna=7)

    teks_kop("NAMA PROYEK :", kx0 + 3.0 * skala, ys_sekat[0] - 4.5 * skala, 1.9, rata=TA.MIDDLE_LEFT, warna=8)
    teks_kop(meta.get("nama_proyek", "RUMAH TINGGAL").upper(), cx_k, (ys_sekat[0] + ys_sekat[1]) / 2.0 - 2.0 * skala, 2.5, warna=2)

    teks_kop("JUDUL GAMBAR :", kx0 + 3.0 * skala, ys_sekat[1] - 4.5 * skala, 1.9, rata=TA.MIDDLE_LEFT, warna=8)
    teks_kop(meta.get("judul_gambar", "DENAH").upper(), cx_k, (ys_sekat[1] + ys_sekat[2]) / 2.0 - 2.0 * skala, 2.5, warna=3)

    teks_kop("PEMILIK / KLIEN :", kx0 + 3.0 * skala, ys_sekat[2] - 4.2 * skala, 1.8, rata=TA.MIDDLE_LEFT, warna=8)
    teks_kop(meta.get("pemilik", "Pemilik Bangunan"), cx_k, ys_sekat[2] - 11.5 * skala, 2.2, warna=7)
    teks_kop("DIGAMBAR / PERENCANA :", kx0 + 3.0 * skala, ys_sekat[2] - 20.5 * skala, 1.8, rata=TA.MIDDLE_LEFT, warna=8)
    teks_kop(meta.get("perencana", "Rancang.io Studio"), cx_k, ys_sekat[2] - 27.5 * skala, 2.0, warna=7)

    teks_kop(f"SKALA : {meta.get('skala_label', '1 : 50')}", kx0 + 3.0 * skala, (ys_sekat[3] + ys_sekat[4]) / 2.0 + 3.0 * skala, 2.2, rata=TA.MIDDLE_LEFT, warna=7)
    teks_kop(f"TANGGAL : {meta.get('tanggal', datetime.date.today().strftime('%d-%m-%Y'))}", kx0 + 3.0 * skala, (ys_sekat[3] + ys_sekat[4]) / 2.0 - 3.5 * skala, 2.0, rata=TA.MIDDLE_LEFT, warna=7)

    teks_kop(meta.get("kode_lembar", "ARS-01"), cx_k, (ys_sekat[4] + by0) / 2.0 + 3.8 * skala, 4.0, warna=2)
    teks_kop(f"LEMBAR {meta.get('no_halaman', '01 / 08')}", cx_k, (ys_sekat[4] + by0) / 2.0 - 4.2 * skala, 2.2, warna=7)

    return (bx0 + 4.0 * skala, by0 + 4.0 * skala, kx0 - 4.0 * skala, by1 - 4.0 * skala)


def _tentukan_skala_adaptif(rumah, skala_pilihan: str = "Otomatis (Menyesuaikan)") -> float:
    if "50" in skala_pilihan:
        return 50.0
    if "75" in skala_pilihan:
        return 75.0
    if "100" in skala_pilihan:
        return 100.0

    x0, y0, x1, y1 = rumah.batas
    bentang_max = max(abs(x1 - x0), abs(y1 - y0))
    if getattr(rumah, "jumlah_lantai", 1) >= 2:
        bentang_max = max(bentang_max, 8200.0)
    if bentang_max <= 7500.0:
        return 50.0
    if bentang_max <= 11500.0:
        return 75.0
    return 100.0


def daftar_lembar_kerja(rumah) -> List[Dict[str, str]]:
    is_2lt = getattr(rumah, "jumlah_lantai", 1) >= 2
    if is_2lt:
        return [
            {"id": "denah_1", "label": "Denah Lantai 1", "kode": "ARS-01", "judul": "DENAH LANTAI 1"},
            {"id": "denah_2", "label": "Denah Lantai 2", "kode": "ARS-02", "judul": "DENAH LANTAI 2"},
            {"id": "potongan_a", "label": "Potongan A-A", "kode": "ARS-03", "judul": "POTONGAN A-A"},
            {"id": "potongan_b", "label": "Potongan B-B", "kode": "ARS-04", "judul": "POTONGAN B-B"},
            {"id": "tampak_depan", "label": "Tampak depan", "kode": "ARS-05", "judul": "TAMPAK DEPAN"},
            {"id": "tampak_belakang", "label": "Tampak belakang", "kode": "ARS-06", "judul": "TAMPAK BELAKANG"},
            {"id": "tampak_kanan", "label": "Tampak kanan", "kode": "ARS-07", "judul": "TAMPAK KANAN"},
            {"id": "tampak_kiri", "label": "Tampak kiri", "kode": "ARS-08", "judul": "TAMPAK KIRI"},
            {"id": "detail", "label": "Detail Pondasi & Kusen", "kode": "STR-01", "judul": "DETAIL STRUKTUR & KUSEN"},
        ]
    return [
        {"id": "denah_1", "label": "Denah", "kode": "ARS-01", "judul": "DENAH RENCANA"},
        {"id": "potongan_a", "label": "Potongan A-A", "kode": "ARS-02", "judul": "POTONGAN A-A"},
        {"id": "potongan_b", "label": "Potongan B-B", "kode": "ARS-03", "judul": "POTONGAN B-B"},
        {"id": "tampak_depan", "label": "Tampak depan", "kode": "ARS-04", "judul": "TAMPAK DEPAN"},
        {"id": "tampak_belakang", "label": "Tampak belakang", "kode": "ARS-05", "judul": "TAMPAK BELAKANG"},
        {"id": "tampak_kanan", "label": "Tampak kanan", "kode": "ARS-06", "judul": "TAMPAK KANAN"},
        {"id": "tampak_kiri", "label": "Tampak kiri", "kode": "ARS-07", "judul": "TAMPAK KIRI"},
        {"id": "detail", "label": "Detail Pondasi & Kusen", "kode": "STR-01", "judul": "DETAIL PONDASI & KUSEN"},
    ]


def _gambar_isi_lembar(
    rumah,
    msp,
    sheet_id: str,
    ox: float,
    oy: float,
    skala_label: str,
    viewport: Optional[Tuple[float, float, float, float]] = None,
) -> Tuple[float, float, float, float]:
    if sheet_id == "denah_1":
        return gambar_denah_lantai(rumah, msp, lantai=1, ox=ox, oy=oy, skala_label=skala_label)
    if sheet_id == "denah_2":
        return gambar_denah_lantai(rumah, msp, lantai=2, ox=ox, oy=oy, skala_label=skala_label)
    if sheet_id == "potongan_a":
        cfg_a = next((p for p in rumah.potongan if "A" in str(p.get("nama", "")).upper()), {"nama": "A-A", "arah": "x"})
        return gambar_potongan(rumah, msp, potongan_cfg=cfg_a, ox=ox, oy=oy, skala_label=skala_label)
    if sheet_id == "potongan_b":
        cfg_b = next((p for p in rumah.potongan if "B" in str(p.get("nama", "")).upper()), {"nama": "B-B", "arah": "y"})
        return gambar_potongan(rumah, msp, potongan_cfg=cfg_b, ox=ox, oy=oy, skala_label=skala_label)
    if sheet_id.startswith("tampak_"):
        sisi = sheet_id.replace("tampak_", "")
        return gambar_tampak(rumah, msp, sisi=sisi, ox=ox, oy=oy, skala_label=skala_label)
    return gambar_detail(rumah, msp, ox=ox, oy=oy, skala_label="1 : 20", viewport=viewport)


def buat_paket_dxf(
    rumah,
    nama_proyek: str = "Rumah Tinggal",
    pemilik: str = "Pemilik Bangunan",
    perencana: str = "Rancang.io Studio",
    skala_pilihan: str = "Otomatis (Menyesuaikan)",
) -> Tuple[bytes, Dict[str, Any]]:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    _siapkan_layer_kop(doc)
    msp = doc.modelspace()

    skala = _tentukan_skala_adaptif(rumah, skala_pilihan)
    skala_str = f"1 : {int(skala)}"
    sheets = daftar_lembar_kerja(rumah)
    total_hal = len(sheets)

    W_a3 = 420.0 * skala
    H_a3 = 297.0 * skala
    jarak_x = W_a3 + 60.0 * skala
    jarak_y = H_a3 + 60.0 * skala
    kolom_grid = 3

    peta_bbox: Dict[str, Tuple[float, float, float, float]] = {}

    for idx, sh in enumerate(sheets):
        col = idx % kolom_grid
        row = idx // kolom_grid
        sx0 = col * jarak_x
        sy0 = -row * jarak_y

        meta = {
            "nama_proyek": nama_proyek,
            "judul_gambar": sh["judul"],
            "pemilik": pemilik,
            "perencana": perencana,
            "skala_label": "1 : 20" if sh["id"] == "detail" else skala_str,
            "kode_lembar": sh["kode"],
            "no_halaman": f"{idx + 1:02d} / {total_hal:02d}",
        }
        vx0, vy0, vx1, vy1 = _gambar_bingkai_kop_a3(msp, sx0, sy0, skala, meta)

        x0_b, y0_b, x1_b, y1_b = rumah.batas
        cx_b = (x0_b + x1_b) / 2.0
        cy_b = (y0_b + y1_b) / 2.0
        vcx = (vx0 + vx1) / 2.0
        vcy = (vy0 + vy1) / 2.0

        if sh["id"] in ("denah_1", "denah_2"):
            ox = vcx - cx_b
            oy = vcy - cy_b + 350.0
        elif sh["id"] in ("potongan_a", "potongan_b", "tampak_depan", "tampak_belakang", "tampak_kanan", "tampak_kiri"):
            tinggi_tot = float(rumah.lantai.get("tinggi_dinding", 3000.0)) + (
                float(rumah.lantai_2.get("tinggi_dinding", 3200.0)) if getattr(rumah, "jumlah_lantai", 1) >= 2 else 0.0
            )
            ox = vcx - cx_b + 550.0
            oy = vcy - (tinggi_tot * 0.44)
        else:
            ox = vx0
            oy = vy0

        _gambar_isi_lembar(rumah, msp, sh["id"], ox, oy, meta["skala_label"], viewport=(vx0, vy0, vx1, vy1))
        peta_bbox[sh["id"]] = (sx0, sy0, sx0 + W_a3, sy0 + H_a3)

    stream = io.StringIO()
    doc.write(stream)
    dxf_bytes = stream.getvalue().encode("utf-8")

    return dxf_bytes, {
        "skala": int(skala),
        "skala_label": skala_str,
        "sheets": sheets,
        "peta_bbox": peta_bbox,
    }


def render_pratinjau_lembar_png(
    rumah,
    sheet_id: str,
    nama_proyek: str = "Rumah Tinggal",
    pemilik: str = "Pemilik Bangunan",
    perencana: str = "Rancang.io Studio",
    skala_pilihan: str = "Otomatis (Menyesuaikan)",
) -> bytes:
    doc = ezdxf.new("R2010", setup=True)
    _siapkan_layer_kop(doc)
    msp = doc.modelspace()

    skala = _tentukan_skala_adaptif(rumah, skala_pilihan)
    skala_str = f"1 : {int(skala)}"
    sheets = daftar_lembar_kerja(rumah)
    idx = next((i for i, s in enumerate(sheets) if s["id"] == sheet_id), 0)
    sh = sheets[idx]

    W_a3 = 420.0 * skala
    H_a3 = 297.0 * skala
    meta = {
        "nama_proyek": nama_proyek,
        "judul_gambar": sh["judul"],
        "pemilik": pemilik,
        "perencana": perencana,
        "skala_label": "1 : 20" if sh["id"] == "detail" else skala_str,
        "kode_lembar": sh["kode"],
        "no_halaman": f"{idx + 1:02d} / {len(sheets):02d}",
    }
    vx0, vy0, vx1, vy1 = _gambar_bingkai_kop_a3(msp, 0.0, 0.0, skala, meta)

    x0_b, y0_b, x1_b, y1_b = rumah.batas
    cx_b, cy_b = (x0_b + x1_b) / 2.0, (y0_b + y1_b) / 2.0
    vcx, vcy = (vx0 + vx1) / 2.0, (vy0 + vy1) / 2.0

    if sh["id"] in ("denah_1", "denah_2"):
        ox, oy = vcx - cx_b, vcy - cy_b + 350.0
    elif sh["id"] in ("potongan_a", "potongan_b", "tampak_depan", "tampak_belakang", "tampak_kanan", "tampak_kiri"):
        tinggi_tot = float(rumah.lantai.get("tinggi_dinding", 3000.0)) + (
            float(rumah.lantai_2.get("tinggi_dinding", 3200.0)) if getattr(rumah, "jumlah_lantai", 1) >= 2 else 0.0
        )
        ox, oy = vcx - cx_b + 550.0, vcy - (tinggi_tot * 0.44)
    else:
        ox, oy = vx0, vy0

    _gambar_isi_lembar(rumah, msp, sh["id"], ox, oy, meta["skala_label"], viewport=(vx0, vy0, vx1, vy1))

    fig = plt.figure(figsize=(11.69, 8.27), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#0B1120")
    fig.patch.set_facecolor("#0B1120")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)

    pad = 12.0 * skala
    ax.set_xlim(-pad, W_a3 + pad)
    ax.set_ylim(-pad, H_a3 + pad)
    ax.set_aspect("equal")
    ax.axis("off")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor="#0B1120")
    plt.close(fig)
    return buf.getvalue()