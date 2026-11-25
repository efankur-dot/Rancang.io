"""Volume dan RAB rumah dari model Rumah -> file Excel dengan rumus hidup (openpyxl).

Harga satuan basis: HSPK dan HSD Edisi ke-2 Tahun 2024, kolom Kab. Magelang.
Mendukung penyesuaian Indeks Kemahalan Konstruksi (IKK) lintas kota dan override harga daerah.
"""
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from shapely.geometry import LineString, MultiPoint, Point

# kode: (uraian, satuan, harga Rp, sumber)
HARGA = {
    # --- upah (HSD Kab. Magelang) ---
    "PEKERJA": ("Pekerja", "OH", 75000, "Upah no. 5"),
    "TUKANG_BATU": ("Tukang batu", "OH", 105000, "Upah no. 11"),
    "TUKANG_BESI": ("Tukang besi", "OH", 105000, "Upah no. 13"),
    "TUKANG_KAYU": ("Tukang kayu", "OH", 105000, "Upah no. 15"),
    "TUKANG_CAT": ("Tukang cat", "OH", 105000, "Upah no. 14"),
    "TUKANG_ALU": ("Tukang aluminium", "OH", 105000, "Upah no. 10"),
    "TUKANG_PIPA": ("Tukang pipa", "OH", 105000, "Upah no. 16"),
    "KEPALA_TUKANG": ("Kepala tukang", "OH", 120000, "Upah no. 1"),
    "MANDOR": ("Mandor", "OH", 110000, "Upah no. 2"),
    # --- bahan (HSPK Kab. Magelang) ---
    "BATU_BELAH": ("Batu belah", "m3", 279125, "Bahan no. 106"),
    "PASIR_PASANG": ("Pasir pasang", "m3", 268214, "Bahan no. 119"),
    "PASIR_URUG": ("Pasir urug", "m3", 193687, "Bahan no. 120"),
    "SEMEN_KG": ("Semen portland", "kg", 1348, "Bahan no. 127"),
    "BATA_MERAH": ("Bata merah", "buah", 893, "Bahan no. 97"),
    "BETON_K300": ("Beton K-300", "m3", 1125000, "Bahan no. 516"),
    "BETON_15": ("Beton 15 MPa", "m3", 1100000, "Bahan no. 515"),
    "BESI_TUL": ("Baja tulangan sirip BjTS 280", "kg", 16250, "Bahan no. 38"),
    "KAWAT_BETON": ("Kawat beton", "kg", 19166, "Bahan no. 57"),
    "PLYWOOD_9": ("Plywood 9 mm", "lembar", 184000, "Bahan no. 258"),
    "KASO_46": ("Kayu kaso 4/6 (kelas 3)", "m3", 2200000, "Bahan no. 236"),
    "PAKU": ("Paku 5-10 cm", "kg", 19000, "Bahan no. 268"),
    "MINYAK_BEKISTING": ("Minyak beton dan bekisting", "liter", 37050, "Bahan no. 539"),
    "KERAMIK_40": ("Ubin keramik (dianggap 40x40)", "buah", 10958, "Bahan no. 348"),
    "KERAMIK_20": ("Keramik 20x20 cm", "buah", 1830, "Bahan no. 315"),
    "CAT_TEMBOK": ("Cat", "kg", 29625, "Bahan no. 139"),
    "PLAMUUR": ("Plamuur", "kg", 36333, "Bahan no. 151"),
    "GYPSUM_9": ("Gypsum tebal 9 mm", "lembar", 66100, "Bahan no. 259"),
    "RANGKA_PLAFON": ("Rangka plafon metal furing", "m2", 29000, "Bahan no. 248"),
    "LIST_GYPSUM": ("List gypsum", "m'", 22000, "Bahan no. 250"),
    "RANGKA_ATAP": ("Rangka atap baja ringan", "m2", 125000, "Bahan no. 249"),
    "GENTENG_METAL": ("Genteng metal", "buah", 33300, "Bahan no. 290"),
    "NOK_METAL": ("Nok genteng metal", "buah", 18500, "Bahan no. 301"),
    "PROFIL_ALU": ("Profil aluminium", "m'", 74400, "Bahan no. 555"),
    "KACA_5": ("Kaca polos 5 mm", "m2", 124333, "Bahan no. 206"),
    "KLOSET": ("Closet duduk", "unit", 1876000, "Bahan no. 490"),
    "BAK_FIBER": ("Bak fiberglass", "unit", 283500, "Bahan no. 474"),
    "KRAN": ("Kran air", "buah", 55000, "Bahan no. 478"),
    "FLOOR_DRAIN": ("Floor drain", "unit", 26666, "Bahan no. 492"),
    # --- tidak ada di HSPK: ASUMSI, isi dari survei harga ---
    "PINTU_PANEL": ("Pintu panel kayu + kusen (jadi)", "unit", 1800000, "ASUMSI, tidak ada di HSPK"),
    "PINTU_PVC": ("Pintu PVC kamar mandi + kusen", "unit", 450000, "ASUMSI, tidak ada di HSPK"),
}

# Paket komponen yang dipakai berulang
_BETON = [("BETON_K300", 1.0), ("PEKERJA", 1.65), ("TUKANG_BATU", 0.275), ("KEPALA_TUKANG", 0.028), ("MANDOR", 0.083)]
_KERAMIK_KERJA = [("SEMEN_KG", 10), ("PASIR_PASANG", 0.045), ("PEKERJA", 0.7), ("TUKANG_BATU", 0.35),
                  ("KEPALA_TUKANG", 0.035), ("MANDOR", 0.035)]

# (kode, divisi, uraian, satuan, kunci_volume, [(kode_harga, koefisien), ...])
PEKERJAAN = [
    ("A.1", "A. Persiapan", "Pembersihan lahan dan perataan", "m2", "lahan", [("PEKERJA", 0.05), ("MANDOR", 0.0025)]),
    ("B.1", "B. Tanah dan pondasi", "Galian tanah pondasi", "m3", "galian", [("PEKERJA", 0.75), ("MANDOR", 0.025)]),
    ("B.2", "B. Tanah dan pondasi", "Urugan pasir bawah pondasi (t=5 cm)", "m3", "pasir_pondasi",
     [("PASIR_URUG", 1.2), ("PEKERJA", 0.3), ("MANDOR", 0.01)]),
    ("B.3", "B. Tanah dan pondasi", "Aanstamping batu belah (t=15 cm)", "m3", "aanstamping",
     [("BATU_BELAH", 1.2), ("PASIR_URUG", 0.432), ("PEKERJA", 0.78), ("TUKANG_BATU", 0.26), ("KEPALA_TUKANG", 0.026), ("MANDOR", 0.039)]),
    ("B.4", "B. Tanah dan pondasi", "Pondasi batu kali 1:4", "m3", "pondasi",
     [("BATU_BELAH", 1.2), ("SEMEN_KG", 163), ("PASIR_PASANG", 0.52), ("PEKERJA", 1.5), ("TUKANG_BATU", 0.75),
      ("KEPALA_TUKANG", 0.075), ("MANDOR", 0.075)]),
    ("B.5", "B. Tanah dan pondasi", "Urugan tanah kembali", "m3", "urug_kembali", [("PEKERJA", 0.25), ("MANDOR", 0.0125)]),
    ("B.6", "B. Tanah dan pondasi", "Urugan pasir bawah lantai (t=10 cm)", "m3", "pasir_lantai",
     [("PASIR_URUG", 1.2), ("PEKERJA", 0.3), ("MANDOR", 0.01)]),
    ("B.7", "B. Tanah dan pondasi", "Lantai kerja beton 15 MPa (t=5 cm)", "m3", "lantai_kerja",
     [("BETON_15", 1.0), ("PEKERJA", 1.65), ("TUKANG_BATU", 0.275), ("KEPALA_TUKANG", 0.028), ("MANDOR", 0.083)]),
    ("C.1", "C. Struktur beton", "Beton sloof 15/20 (K-300)", "m3", "beton_sloof", _BETON),
    ("C.2", "C. Struktur beton", "Beton kolom praktis 15/15 (K-300)", "m3", "beton_kolom", _BETON),
    ("C.3", "C. Struktur beton", "Beton ring balok 15/15 (K-300)", "m3", "beton_ring", _BETON),
    ("C.4", "C. Struktur beton", "Pembesian sloof, kolom, ring balok", "kg", "besi",
     [("BESI_TUL", 1.05), ("KAWAT_BETON", 0.015), ("TUKANG_BESI", 0.007), ("PEKERJA", 0.007), ("KEPALA_TUKANG", 0.0007), ("MANDOR", 0.0004)]),
    ("C.5", "C. Struktur beton", "Bekisting sloof, kolom, ring balok", "m2", "bekisting",
     [("PLYWOOD_9", 0.35), ("KASO_46", 0.055), ("PAKU", 0.4), ("MINYAK_BEKISTING", 0.2), ("TUKANG_KAYU", 0.33),
      ("PEKERJA", 0.66), ("KEPALA_TUKANG", 0.033), ("MANDOR", 0.033)]),
    ("D.1", "D. Dinding", "Pasangan bata merah 1/2 bata (1:4)", "m2", "dinding_bersih",
     [("BATA_MERAH", 70), ("SEMEN_KG", 11.5), ("PASIR_PASANG", 0.043), ("PEKERJA", 0.3), ("TUKANG_BATU", 0.1),
      ("KEPALA_TUKANG", 0.01), ("MANDOR", 0.015)]),
    ("D.2", "D. Dinding", "Plesteran 1:4 tebal 15 mm (dua sisi)", "m2", "plester",
     [("SEMEN_KG", 6.24), ("PASIR_PASANG", 0.024), ("PEKERJA", 0.3), ("TUKANG_BATU", 0.15), ("KEPALA_TUKANG", 0.015), ("MANDOR", 0.015)]),
    ("D.3", "D. Dinding", "Acian", "m2", "plester",
     [("SEMEN_KG", 3.25), ("PEKERJA", 0.2), ("TUKANG_BATU", 0.1), ("KEPALA_TUKANG", 0.01), ("MANDOR", 0.01)]),
    ("D.4", "D. Dinding", "Pengecatan dinding (plamuur + 2 lapis)", "m2", "cat",
     [("CAT_TEMBOK", 0.26), ("PLAMUUR", 0.1), ("PEKERJA", 0.02), ("TUKANG_CAT", 0.063), ("KEPALA_TUKANG", 0.0063), ("MANDOR", 0.0033)]),
    ("D.5", "D. Dinding", "Keramik dinding 20x20 (area basah)", "m2", "keramik_dinding", [("KERAMIK_20", 26.25)] + _KERAMIK_KERJA),
    ("E.1", "E. Lantai", "Keramik lantai 40x40", "m2", "lantai_40", [("KERAMIK_40", 6.56)] + _KERAMIK_KERJA),
    ("E.2", "E. Lantai", "Keramik lantai 20x20 (area basah)", "m2", "lantai_20", [("KERAMIK_20", 26.25)] + _KERAMIK_KERJA),
    ("F.1", "F. Plafon", "Plafon gypsum 9 mm dengan rangka metal furing", "m2", "plafon",
     [("GYPSUM_9", 0.382), ("RANGKA_PLAFON", 1.0), ("TUKANG_KAYU", 0.15), ("PEKERJA", 0.1), ("KEPALA_TUKANG", 0.015), ("MANDOR", 0.005)]),
    ("F.2", "F. Plafon", "List plafon gypsum", "m'", "list_plafon", [("LIST_GYPSUM", 1.05), ("TUKANG_KAYU", 0.05), ("PEKERJA", 0.025)]),
    ("G.1", "G. Atap", "Rangka atap baja ringan", "m2", "atap", [("RANGKA_ATAP", 1.0), ("TUKANG_BESI", 0.1), ("PEKERJA", 0.1)]),
    ("G.2", "G. Atap", "Penutup atap genteng metal", "m2", "atap",
     [("GENTENG_METAL", 3.1), ("TUKANG_KAYU", 0.07), ("PEKERJA", 0.07), ("KEPALA_TUKANG", 0.007), ("MANDOR", 0.0035)]),
    ("G.3", "G. Atap", "Nok genteng metal", "m'", "nok", [("NOK_METAL", 2.5), ("TUKANG_KAYU", 0.05), ("PEKERJA", 0.05)]),
    ("H.1", "H. Pintu dan jendela", "Jendela aluminium + kaca 5 mm", "m2", "jendela",
     [("PROFIL_ALU", 4.5), ("KACA_5", 1.05), ("TUKANG_ALU", 0.4), ("PEKERJA", 0.2), ("KEPALA_TUKANG", 0.04), ("MANDOR", 0.02)]),
    ("H.2", "H. Pintu dan jendela", "Pintu panel kayu + kusen", "unit", "pintu_panel", [("PINTU_PANEL", 1), ("TUKANG_KAYU", 0.5), ("PEKERJA", 0.25)]),
    ("H.3", "H. Pintu dan jendela", "Pintu PVC kamar mandi + kusen", "unit", "pintu_pvc", [("PINTU_PVC", 1), ("TUKANG_KAYU", 0.3), ("PEKERJA", 0.15)]),
    ("I.1", "I. Sanitair", "Pasang kloset duduk", "unit", "kloset", [("KLOSET", 1), ("TUKANG_PIPA", 0.5), ("PEKERJA", 0.25)]),
    ("I.2", "I. Sanitair", "Pasang bak air fiberglass", "unit", "bak", [("BAK_FIBER", 1), ("PEKERJA", 0.25)]),
    ("I.3", "I. Sanitair", "Pasang kran air", "buah", "kran", [("KRAN", 1), ("TUKANG_PIPA", 0.1)]),
    ("I.4", "I. Sanitair", "Pasang floor drain", "unit", "drain", [("FLOOR_DRAIN", 1), ("TUKANG_PIPA", 0.1)]),
]

RASIO_BESI = 150.0   # kg besi per m3 beton (ASUMSI)


def _hitung_jumlah_kolom(r) -> int:
    """Menghitung jumlah titik kolom yang sinkron 100% dengan modul drawing/denah.py."""
    titik_kolom: List[Tuple[float, float]] = []

    def tambah_unik(x: float, y: float, tol: float = 15.0) -> None:
        rx, ry = float(round(x)), float(round(y))
        for ex, ey in titik_kolom:
            if math.hypot(rx - ex, ry - ey) <= tol:
                return
        titik_kolom.append((rx, ry))

    garis_dinding = []
    for d in r.dinding:
        tambah_unik(d.a[0], d.a[1])
        tambah_unik(d.b[0], d.b[1])
        garis_dinding.append((d, LineString([d.a, d.b])))

    n_garis = len(garis_dinding)
    for i in range(n_garis):
        for j in range(i + 1, n_garis):
            inter = garis_dinding[i][1].intersection(garis_dinding[j][1])
            if inter.is_empty:
                continue
            if isinstance(inter, Point):
                tambah_unik(inter.x, inter.y)
            elif isinstance(inter, MultiPoint):
                for pt in inter.geoms:
                    tambah_unik(pt.x, pt.y)

    bentang_maks = 3500.0
    for d, garis in garis_dinding:
        pjg = garis.length
        if pjg > bentang_maks:
            jumlah_bagi = math.ceil(pjg / bentang_maks)
            dx = d.b[0] - d.a[0]
            dy = d.b[1] - d.a[1]
            for k in range(1, jumlah_bagi):
                rasio = k / jumlah_bagi
                jarak = pjg * rasio
                menabrak = any(
                    b.dinding == d.id and (b.offset - 180.0) <= jarak <= (b.akhir + 180.0)
                    for b in r.bukaan
                )
                if not menabrak:
                    tambah_unik(d.a[0] + dx * rasio, d.a[1] + dy * rasio, tol=250.0)

    return max(4, len(titik_kolom))


def _gabung_harga(harga_override: Optional[Dict[str, float]] = None) -> Dict[str, Tuple[str, str, float, str]]:
    """Menggabungkan database HARGA bawaan dengan perubahan harga kustom dari pengguna."""
    hasil = dict(HARGA)
    if harga_override:
        for kode, nilai_baru in harga_override.items():
            if kode in hasil and nilai_baru is not None:
                u, s, _, src = hasil[kode]
                hasil[kode] = (u, s, float(nilai_baru), f"{src} (Kustom)")
    return hasil


def hitung_volume(r):
    """Hitung semua volume dari model Rumah. Kembalian: {kunci: (nilai, keterangan)}."""
    t = r.dinding_default.get("tebal", 150) / 1000
    H = r.lantai.get("tinggi_dinding", 3000) / 1000
    xs = [p[0] for d in r.dinding for p in (d.a, d.b)]
    ys = [p[1] for d in r.dinding for p in (d.a, d.b)]
    W, D = (max(xs) - min(xs)) / 1000, (max(ys) - min(ys)) / 1000
    Lw = sum(d.panjang for d in r.dinding) / 1000

    pf = r.struktur.get("pondasi", {})
    lb, la, tp = pf.get("lebar_bawah", 600) / 1000, pf.get("lebar_atas", 300) / 1000, pf.get("tinggi", 700) / 1000
    bs, hs = [v / 1000 for v in r.struktur.get("sloof", [150, 200])]
    kw, kh = [v / 1000 for v in r.struktur.get("kolom", [150, 150])]
    rw, rh = [v / 1000 for v in r.struktur.get("ring_balok", [150, 150])]
    n_kolom = _hitung_jumlah_kolom(r)

    luas_bukaan = sum(b.lebar * b.tinggi for b in r.bukaan) / 1e6
    dinding_kotor = Lw * H
    dinding_bersih = dinding_kotor - luas_bukaan
    plester = 2 * dinding_bersih

    k_dinding = 0.0
    for rg in r.ruang:
        if rg.keramik_dinding_tinggi:
            hk = rg.keramik_dinding_tinggi / 1000
            kel = 2 * ((rg.panjang / 1000 - t) + (rg.lebar / 1000 - t))
            pintu = sum(b.lebar / 1000 for b in r.bukaan if b.jenis == "pintu"
                        and b.ayun_ke and b.ayun_ke.strip().lower() == rg.nama.strip().lower())
            k_dinding += (kel - pintu) * hk

    def bersih(rg):
        return (rg.panjang / 1000 - t) * (rg.lebar / 1000 - t)

    lantai_40 = sum(bersih(g) for g in r.ruang if g.lantai and "40x40" in g.lantai)
    lantai_20 = sum(bersih(g) for g in r.ruang if g.lantai and "20x20" in g.lantai)
    plafon = sum(bersih(g) for g in r.ruang if g.plafon and "gypsum" in g.plafon.lower())
    list_plafon = sum(2 * ((g.panjang / 1000 - t) + (g.lebar / 1000 - t)) for g in r.ruang
                      if g.plafon and "gypsum" in g.plafon.lower())
    luas_lantai = sum(bersih(g) for g in r.ruang)

    galian = Lw * (lb + 0.2) * (tp + 0.05 + 0.15)
    pasir_p, aanst, pond = Lw * lb * 0.05, Lw * lb * 0.15, Lw * (lb + la) / 2 * tp
    b_sloof, b_kolom, b_ring = Lw * bs * hs, n_kolom * kw * kh * H, Lw * rw * rh
    beton = b_sloof + b_kolom + b_ring
    bekisting = Lw * 2 * hs + n_kolom * 4 * kw * H + Lw * (2 * rh + rw)

    th = math.radians(r.atap.get("kemiringan_derajat", 30))
    ov = r.atap.get("overstek", 600) / 1000
    Wt, Dt = W + t, D + t
    if r.atap.get("arah_nok", "x") == "x":
        p_nok, bentang = Wt + 2 * ov, Dt + 2 * ov
    else:
        p_nok, bentang = Dt + 2 * ov, Wt + 2 * ov
    atap = 2 * (bentang / 2) / math.cos(th) * p_nok

    jendela = sum(b.lebar * b.tinggi for b in r.bukaan if b.jenis == "jendela") / 1e6
    pintu = [b for b in r.bukaan if b.jenis == "pintu"]
    pvc = sum(1 for b in pintu if b.bahan and "pvc" in b.bahan.lower())
    nama = [g.nama.lower() for g in r.ruang]
    n_km = sum(("km" in n or "wc" in n) for n in nama)
    n_cuci = sum("cuci" in n for n in nama)
    n_dapur = sum("dapur" in n for n in nama)

    return {
        "lahan": ((W + t + 2) * (D + t + 2), f"({W+t:.2f}+2) x ({D+t:.2f}+2) m, sisa 1 m tiap sisi"),
        "galian": (galian, f"panjang dinding {Lw:.2f} m x lebar {lb+0.2:.2f} m x dalam {tp+0.2:.2f} m"),
        "pasir_pondasi": (pasir_p, f"{Lw:.2f} x {lb:.2f} x 0,05"),
        "aanstamping": (aanst, f"{Lw:.2f} x {lb:.2f} x 0,15"),
        "pondasi": (pond, f"{Lw:.2f} x (({lb:.2f}+{la:.2f})/2) x {tp:.2f}"),
        "urug_kembali": (max(galian - pasir_p - aanst - pond, 0), "galian - (pasir + aanstamping + pondasi)"),
        "pasir_lantai": (luas_lantai * 0.10, f"luas lantai bersih {luas_lantai:.2f} m2 x 0,10"),
        "lantai_kerja": (luas_lantai * 0.05, f"luas lantai bersih {luas_lantai:.2f} m2 x 0,05"),
        "beton_sloof": (b_sloof, f"{Lw:.2f} x {bs:.2f} x {hs:.2f}"),
        "beton_kolom": (b_kolom, f"{n_kolom} titik kolom (sudut, simpang, bentang) x {kw:.2f} x {kh:.2f} x {H:.2f}"),
        "beton_ring": (b_ring, f"{Lw:.2f} x {rw:.2f} x {rh:.2f}"),
        "besi": (beton * RASIO_BESI, f"beton {beton:.3f} m3 x {RASIO_BESI:.0f} kg/m3 (asumsi)"),
        "bekisting": (bekisting, "sisi sloof + 4 sisi kolom + sisi dan alas ring balok"),
        "dinding_bersih": (dinding_bersih, f"{Lw:.2f} x {H:.2f} - bukaan {luas_bukaan:.2f} m2"),
        "plester": (plester, "2 sisi x luas dinding bersih"),
        "cat": (max(plester - k_dinding, 0), f"luas plester - keramik dinding {k_dinding:.2f} m2"),
        "keramik_dinding": (k_dinding, "keliling bersih ruang basah x tinggi keramik - pintu"),
        "lantai_40": (lantai_40, "luas bersih ruang berlantai 40x40"),
        "lantai_20": (lantai_20, "luas bersih ruang berlantai 20x20"),
        "plafon": (plafon, "luas bersih ruang berplafon gypsum"),
        "list_plafon": (list_plafon, "keliling bersih ruang berplafon gypsum"),
        "atap": (atap, f"bidang atap pelana, {math.degrees(th):.0f} derajat, overstek {ov:.2f} m"),
        "nok": (p_nok, "panjang nok = panjang atap searah nok"),
        "jendela": (jendela, "jumlah lebar x tinggi semua jendela"),
        "pintu_panel": (len(pintu) - pvc, "jumlah pintu non-PVC"),
        "pintu_pvc": (pvc, "jumlah pintu PVC"),
        "kloset": (n_km, "1 per kamar mandi"),
        "bak": (n_km, "1 per kamar mandi"),
        "kran": (n_km + n_cuci + n_dapur, "kamar mandi + dapur + ruang cuci"),
        "drain": (n_km + n_cuci, "kamar mandi + ruang cuci"),
    }


def hitung_rab(
    r,
    overhead: float = 0.12,
    ppn: float = 0.11,
    ikk: float = 1.0,
    harga_override: Optional[Dict[str, float]] = None,
    **kwargs,
):
    """Hitung RAB dengan koefisien wilayah (IKK) dan harga satuan kustom opsional."""
    vol = hitung_volume(r)
    harga_aktif = _gabung_harga(harga_override)
    baris, per_divisi = [], {}
    for kode, divisi, uraian, sat, kv, komp in PEKERJAAN:
        hs = sum(k * round(harga_aktif[h][2] * ikk) for h, k in komp)
        v = vol[kv][0]
        baris.append((kode, divisi, uraian, sat, v, hs, v * hs))
        per_divisi[divisi] = per_divisi.get(divisi, 0) + v * hs
    jl = sum(per_divisi.values())
    oh = jl * overhead
    pp = (jl + oh) * ppn
    return baris, per_divisi, {"jumlah": jl, "overhead": oh, "ppn": pp, "total": jl + oh + pp}


def buat_rab_excel(
    r,
    path="hasil/RAB_rumah.xlsx",
    overhead: float = 0.12,
    ppn: float = 0.11,
    ikk: float = 1.0,
    wilayah: str = "Kab. Magelang (Basis HSPK 2024)",
    harga_override: Optional[Dict[str, float]] = None,
):
    """Tulis Excel: sheet Harga Satuan, Volume, AHSP, RAB, Rekap (semua dengan rumus hidup & IKK wilayah)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vol = hitung_volume(r)
    harga_aktif = _gabung_harga(harga_override)

    judul = Font(bold=True, color="FFFFFF")
    isi_judul = PatternFill("solid", fgColor="1F3A5F")
    isi_sub = PatternFill("solid", fgColor="DCE6F1")
    isi_input = PatternFill("solid", fgColor="FFF2CC")
    RP, V2 = "#,##0", "#,##0.00"

    def header(ws, cols, widths):
        ws.append(cols)
        for c in ws[ws.max_row]:
            c.font, c.fill = judul, isi_judul
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for i, w in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = w
        ws.freeze_panes = "A2"

    wb = Workbook()
    # 1. Harga Satuan (mengalikan Harga Basis dengan Indeks Wilayah di Rekap!B2)
    wh = wb.active
    wh.title = "Harga Satuan"
    header(
        wh,
        ["Kode", "Uraian", "Satuan", "Harga Basis (Rp)", "Indeks Wilayah", "Harga Berlaku (Rp)", "Sumber"],
        [20, 38, 10, 18, 15, 20, 30]
    )
    for kode, (u, s, h, src) in harga_aktif.items():
        rr = wh.max_row + 1
        wh.append([kode, u, s, h, "=Rekap!$B$2", f"=ROUND(D{rr}*E{rr},0)", src])
        wh.cell(rr, 4).number_format = RP
        wh.cell(rr, 4).fill = isi_input
        wh.cell(rr, 5).number_format = "0.00"
        wh.cell(rr, 6).number_format = RP
    n_h = wh.max_row
    cari = lambda kol, kode_cell: f"INDEX('Harga Satuan'!${kol}$2:${kol}${n_h},MATCH({kode_cell},'Harga Satuan'!$A$2:$A${n_h},0))"

    # 2. Volume
    wv = wb.create_sheet("Volume")
    header(wv, ["Kode", "Uraian pekerjaan", "Satuan", "Volume", "Cara hitung"], [8, 46, 10, 14, 70])
    vol_row = {}
    for kode, divisi, uraian, sat, kv, komp in PEKERJAAN:
        nilai, ket = vol[kv]
        wv.append([kode, uraian, sat, round(nilai, 3), ket])
        wv.cell(wv.max_row, 4).number_format = V2
        vol_row[kode] = wv.max_row

    # 3. AHSP
    wa = wb.create_sheet("AHSP")
    header(wa, ["Kode harga", "Komponen", "Satuan", "Koefisien", "Harga (Rp)", "Jumlah (Rp)"], [20, 38, 10, 12, 16, 16])
    ahsp_row = {}
    for kode, divisi, uraian, sat, kv, komp in PEKERJAAN:
        wa.append([f"{kode}  {uraian} (per {sat})"])
        for c in wa[wa.max_row]:
            c.font, c.fill = Font(bold=True), isi_sub
        mulai = wa.max_row + 1
        for h, k in komp:
            rr = wa.max_row + 1
            wa.append([h, f"={cari('B', f'A{rr}')}", f"={cari('C', f'A{rr}')}", k, f"={cari('F', f'A{rr}')}", f"=D{rr}*E{rr}"])
            wa.cell(rr, 4).fill = isi_input
            wa.cell(rr, 4).number_format = "0.0000"
            wa.cell(rr, 5).number_format = RP
            wa.cell(rr, 6).number_format = RP
        rr = wa.max_row + 1
        wa.append(["", "Harga satuan pekerjaan", "", "", "", f"=SUM(F{mulai}:F{rr-1})"])
        for c in wa[rr]:
            c.font = Font(bold=True)
        wa.cell(rr, 6).number_format = RP
        ahsp_row[kode] = rr

    # 4. RAB
    wr = wb.create_sheet("RAB")
    header(wr, ["No", "Divisi", "Uraian pekerjaan", "Satuan", "Volume", "Harga satuan (Rp)", "Jumlah (Rp)"], [8, 24, 46, 10, 12, 18, 18])
    for kode, divisi, uraian, sat, kv, komp in PEKERJAAN:
        rr = wr.max_row + 1
        wr.append([kode, divisi, uraian, sat, f"=Volume!D{vol_row[kode]}", f"=AHSP!F{ahsp_row[kode]}", f"=E{rr}*F{rr}"])
        wr.cell(rr, 5).number_format = V2
        wr.cell(rr, 6).number_format = RP
        wr.cell(rr, 7).number_format = RP
    akhir_rab = wr.max_row

    # 5. Rekap (Baris 2 = Indeks Wilayah editable, Baris 3 = Nama Wilayah)
    wk = wb.create_sheet("Rekap")
    header(wk, ["Parameter / Divisi Pekerjaan", "Nilai / Jumlah (Rp)"], [44, 24])
    wk.append(["Indeks Kemahalan Konstruksi (IKK)", float(ikk)])
    wk.cell(2, 2).number_format = "0.00"
    wk.cell(2, 2).fill = isi_input
    wk.cell(2, 2).font = Font(bold=True)

    wk.append(["Wilayah Acuan Harga", wilayah])
    wk.cell(3, 2).font = Font(bold=True)
    wk.append([])

    a = wk.max_row + 1  # Baris 5
    divisi_unik = list(dict.fromkeys(p[1] for p in PEKERJAAN))
    for dv in divisi_unik:
        rr = wk.max_row + 1
        wk.append([dv, f"=SUMIF(RAB!$B$2:$B${akhir_rab},A{rr},RAB!$G$2:$G${akhir_rab})"])
        wk.cell(rr, 2).number_format = RP
    b = wk.max_row

    wk.append(["Jumlah pekerjaan", f"=SUM(B{a}:B{b})"])
    r_jml = wk.max_row
    wk.append(["Persen overhead dan keuntungan", overhead])
    r_ohp = wk.max_row
    wk.append(["Overhead dan keuntungan", f"=B{r_jml}*B{r_ohp}"])
    r_oh = wk.max_row
    wk.append(["Persen PPN", ppn])
    r_ppp = wk.max_row
    wk.append(["PPN", f"=(B{r_jml}+B{r_oh})*B{r_ppp}"])
    r_pp = wk.max_row
    wk.append(["TOTAL RAB", f"=B{r_jml}+B{r_oh}+B{r_pp}"])
    r_tot = wk.max_row
    wk.append(["Dibulatkan (ratusan ribu)", f"=ROUND(B{r_tot},-5)"])
    for rr in (r_ohp, r_ppp):
        wk.cell(rr, 2).number_format = "0%"
        wk.cell(rr, 2).fill = isi_input
    for rr in (r_jml, r_oh, r_pp, r_tot, r_tot + 1):
        wk.cell(rr, 2).number_format = RP
    for rr in (r_jml, r_tot, r_tot + 1):
        for c in wk[rr]:
            c.font = Font(bold=True)
    wk.append([])
    wk.append(["Catatan: Basis harga dari HSPK/HSD Kab. Magelang 2024 dikalikan IKK Wilayah (sel kuning Rekap!B2). Seluruh sel kuning dapat diubah."])

    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    return path