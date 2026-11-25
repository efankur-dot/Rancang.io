"""
Modul Perhitungan Volume Pekerjaan & Rencana Anggaran Biaya (RAB) Konstruksi.
Mendukung 1 Lantai maupun 2 Lantai berdasarkan analisa AHSP SNI & Indeks Kemahalan Konstruksi (IKK).
"""
import io
import math
from typing import Any, Dict, List, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

IKK_WILAYAH: Dict[str, float] = {
    "Kota Semarang": 1.06,
    "Kota Magelang": 1.02,
    "Kab. Magelang": 1.00,
    "Kota Yogyakarta": 1.04,
    "Kota Surakarta (Solo)": 1.03,
    "Kota Salatiga": 1.02,
    "Kab. Temanggung": 1.00,
    "Kab. Boyolali": 1.01,
    "Kab. Sleman": 1.03,
    "Kab. Bantul": 1.02,
    "DKI Jakarta": 1.18,
    "Kota Bandung": 1.08,
    "Kota Surabaya": 1.10,
    "Kota Malang": 1.06,
    "Kota Denpasar": 1.12,
    "Kota Medan": 1.05,
    "Kota Makassar": 1.07,
    "Kota Balikpapan": 1.15,
}


def hitung_rab(rumah, wilayah: str = "Kota Semarang", ikk_custom: float = 0.0) -> Dict[str, Any]:
    """Menghitung rincian volume, harga satuan terkoreksi IKK, dan total biaya RAB (1 & 2 Lantai)."""
    ikk = float(ikk_custom) if ikk_custom > 0 else float(IKK_WILAYAH.get(wilayah, 1.00))
    is_2lt = getattr(rumah, "jumlah_lantai", 1) >= 2

    x0, y0, x1, y1 = rumah.batas
    panjang_bgn_m = abs(x1 - x0) / 1000.0
    lebar_bgn_m = abs(y1 - y0) / 1000.0
    luas_tapak_m2 = panjang_bgn_m * lebar_bgn_m

    luas_lt1_m2 = sum(r.luas_m2 for r in rumah.ruang) or luas_tapak_m2
    luas_lt2_m2 = sum(r.luas_m2 for r in rumah.ruang_lt2) if is_2lt else 0.0
    luas_balkon_m2 = sum(
        (abs(float(b["kotak"][2]) - float(b["kotak"][0])) * abs(float(b["kotak"][3]) - float(b["kotak"][1]))) / 1_000_000.0
        for b in (rumah.balkon or [])
        if isinstance(b.get("kotak"), list) and len(b["kotak"]) == 4
    ) if is_2lt else 0.0
    luas_total_m2 = luas_lt1_m2 + luas_lt2_m2 + luas_balkon_m2

    # Panjang dinding total Lantai 1 & Lantai 2
    pjg_d1_m = sum(d.panjang / 1000.0 for d in rumah.dinding)
    pjg_d2_m = sum(d.panjang / 1000.0 for d in rumah.dinding_lt2) if is_2lt else 0.0
    tinggi_lt1_m = float(rumah.lantai.get("tinggi_dinding", 3000.0)) / 1000.0
    tinggi_lt2_m = float(rumah.lantai_2.get("tinggi_dinding", 3200.0)) / 1000.0 if is_2lt else 0.0

    luas_bukaan_1_m2 = sum((b.lebar * b.tinggi) / 1_000_000.0 for b in rumah.bukaan)
    luas_bukaan_2_m2 = sum((b.lebar * b.tinggi) / 1_000_000.0 for b in rumah.bukaan_lt2) if is_2lt else 0.0

    luas_dinding_net_m2 = max(
        10.0,
        (pjg_d1_m * tinggi_lt1_m - luas_bukaan_1_m2) + (pjg_d2_m * tinggi_lt2_m - luas_bukaan_2_m2),
    )

    # Estimasi jumlah titik kolom struktur utama (sudut & simpang)
    titik_kolom = max(4, len({(round(p[0], -1), round(p[1], -1)) for d in rumah.dinding for p in (d.a, d.b)}))

    # Parameter pondasi & struktur
    st = rumah.struktur or {}
    pnd = st.get("pondasi", {"lebar_bawah": 600, "lebar_atas": 300, "tinggi": 700})
    luas_penampang_pnd = ((float(pnd["lebar_bawah"]) + float(pnd["lebar_atas"])) / 2000.0) * (float(pnd["tinggi"]) / 1000.0)

    sloof = st.get("sloof", [150, 200] if not is_2lt else [200, 300])
    vol_sloof_m3 = pjg_d1_m * (float(sloof[0]) / 1000.0) * (float(sloof[1]) / 1000.0)

    rb = st.get("ring_balok", [150, 150] if not is_2lt else [150, 200])
    pjg_ring_m = pjg_d2_m if is_2lt and pjg_d2_m > 0 else pjg_d1_m
    vol_ring_m3 = pjg_ring_m * (float(rb[0]) / 1000.0) * (float(rb[1]) / 1000.0)

    # Atap
    atap = rumah.atap or {}
    ov_m = float(atap.get("overstek", 600.0)) / 1000.0
    sudut_rad = math.radians(float(atap.get("kemiringan_derajat", 30.0)))
    luas_atap_m2 = ((panjang_bgn_m + 2 * ov_m) * (lebar_bgn_m + 2 * ov_m)) / max(0.65, math.cos(sudut_rad))

    # Bukaan pintu & jendela gabungan
    semua_bk = rumah.semua_bukaan
    jml_pintu = sum(1 for b in semua_bk if b.jenis == "pintu")
    luas_jendela_m2 = sum((b.lebar * b.tinggi) / 1_000_000.0 for b in semua_bk if b.jenis == "jendela")

    # Keramik KM/WC
    ruang_km = [r for r in rumah.semua_ruang if any(k in r.nama.lower() for k in ("km", "wc", "mandi"))]
    luas_lantai_km = sum(r.luas_m2 for r in ruang_km)
    luas_dinding_km = sum((r.keliling / 1000.0) * (float(r.keramik_dinding_tinggi or 1500.0) / 1000.0) for r in ruang_km)
    luas_lantai_kering = max(5.0, luas_total_m2 - luas_lantai_km)

    items: List[Dict[str, Any]] = []

    def tambah(divisi: str, kode: str, uraian: str, sat: str, vol: float, hsp_dasar: float):
        if vol <= 1e-4:
            return
        hsp_wil = round(hsp_dasar * ikk, -2)
        jumlah = round(vol * hsp_wil, 0)
        items.append({
            "divisi": divisi,
            "kode": kode,
            "uraian": uraian,
            "satuan": sat,
            "volume": round(vol, 2),
            "harga_satuan": hsp_wil,
            "jumlah_harga": jumlah,
        })

    # ---------------- DIVISI I: PEKERJAAN PERSIAPAN & TANAH ----------------
    div1 = "I. PEKERJAAN PERSIAPAN & TANAH"
    tambah(div1, "A.2.2.1.4", "Pembersihan Lapangan dan Perataan Lahan", "m²", luas_tapak_m2 * 1.25, 16500)
    tambah(div1, "A.2.2.1.9", "Pengukuran dan Pemasangan Bowplank", "m'", 2 * (panjang_bgn_m + lebar_bgn_m + 2.0), 68000)
    vol_galian_menerus = pjg_d1_m * 0.80 * 0.85
    vol_galian_fp = (titik_kolom * 1.20 * 1.20 * 1.35) if is_2lt else 0.0
    tambah(div1, "A.2.3.1.1", "Galian Tanah Biasa Sedalam 1 m - 1,5 m", "m³", vol_galian_menerus + vol_galian_fp, 86000)
    tambah(div1, "A.2.3.1.9", "Urugan Tanah Kembali Dipadatkan", "m³", (vol_galian_menerus + vol_galian_fp) * 0.35, 54000)
    tambah(div1, "A.2.3.1.11", "Urugan Pasir Bawah Pondasi & Lantai t = 5 cm", "m³", (pjg_d1_m * 0.80 * 0.05) + (luas_tapak_m2 * 0.05), 245000)

    # ---------------- DIVISI II: PONDASI & STRUKTUR BETON BERTULANG ----------------
    div2 = "II. PEKERJAAN PONDASI & STRUKTUR BETON"
    tambah(div2, "A.3.2.1.9", "Pasangan Batu Kosong (Aanstamping) t = 15 cm", "m³", pjg_d1_m * 0.80 * 0.15, 495000)
    tambah(div2, "A.3.2.1.2", "Pasangan Pondasi Batu Kali Campuran 1SP : 4PP", "m³", pjg_d1_m * luas_penampang_pnd, 895000)

    if is_2lt:
        fp = st.get("footplat", {"lebar": 1000, "panjang": 1000, "tebal": 250, "kedalaman": 1200})
        vol_fp = titik_kolom * (float(fp["lebar"]) / 1000.0) * (float(fp["panjang"]) / 1000.0) * (float(fp["tebal"]) / 1000.0)
        vol_ped = titik_kolom * 0.25 * 0.25 * 0.95
        tambah(div2, "A.4.1.1.7", "Pondasi Footplat Beton Bertulang K-250 (100×100×25 cm)", "m³", vol_fp + vol_ped, 3850000)
        tambah(div2, "A.4.1.1.8", "Sloof Beton Bertulang K-250 (20 × 30 cm)", "m³", vol_sloof_m3, 3920000)

        vol_kolom_utama = titik_kolom * 0.25 * 0.25 * (tinggi_lt1_m + tinggi_lt2_m)
        tambah(div2, "A.4.1.1.9", "Kolom Struktur Utama Beton Bertulang K-250 (25 × 25 cm)", "m³", vol_kolom_utama, 4350000)

        bi = st.get("balok_induk", [200, 350])
        vol_bi = (pjg_d2_m * 0.75) * (float(bi[0]) / 1000.0) * (float(bi[1]) / 1000.0)
        tambah(div2, "A.4.1.1.10", "Balok Induk Lantai 2 Beton Bertulang K-250 (20 × 35 cm)", "m³", vol_bi, 4280000)

        t_pelat_m = float((st.get("pelat_lantai") or {}).get("tebal", 120.0)) / 1000.0
        vol_pelat = max(1.0, luas_lt2_m2 + luas_balkon_m2) * t_pelat_m
        tambah(div2, "A.4.1.1.11", "Pelat Lantai 2 & Balkon Beton Bertulang K-300 (t = 12 cm)", "m³", vol_pelat, 4150000)

        # Tangga Beton Bertulang + Railing
        vol_tangga = 1.65
        tambah(div2, "A.4.1.1.12", "Struktur Tangga Beton Bertulang K-250 & Anak Tangga", "m³", vol_tangga, 4450000)
        tambah(div2, "A.4.2.1.15", "Railing Tangga & Balkon Besi Hollow Galvanis Finishing Cat", "m'", 4.8 + (luas_balkon_m2 * 1.4), 685000)
    else:
        tambah(div2, "A.4.1.1.8", "Sloof Beton Bertulang Praktis (15 × 20 cm)", "m³", vol_sloof_m3, 3450000)
        vol_kp = titik_kolom * 0.15 * 0.15 * tinggi_lt1_m
        tambah(div2, "A.4.1.1.9", "Kolom Praktis Beton Bertulang (15 × 15 cm)", "m³", vol_kp, 3680000)

    tambah(div2, "A.4.1.1.13", "Ring Balok Beton Bertulang (15 × 20 cm)", "m³", vol_ring_m3, 3580000)
    tambah(div2, "A.4.1.1.4", "Lantai Kerja / Rabat Beton Tumbuk K-125 t = 5 cm", "m³", luas_tapak_m2 * 0.05, 985000)

    # ---------------- DIVISI III: DINDING BATA & PLESTERAN ----------------
    div3 = "III. PEKERJAAN PASANGAN DINDING & PLESTERAN"
    tambah(div3, "A.4.4.1.9", "Pasangan Dinding Bata Merah Tebal 1/2 Bata Campuran 1SP : 4PP", "m²", luas_dinding_net_m2, 138000)
    tambah(div3, "A.4.4.2.4", "Plesteran Dinding Campuran 1SP : 4PP Tebal 15 mm (2 Sisi)", "m²", luas_dinding_net_m2 * 2.0, 69000)
    tambah(div3, "A.4.4.2.27", "Acian Dinding Semen Portland Halus (2 Sisi)", "m²", luas_dinding_net_m2 * 2.0, 42500)

    # ---------------- DIVISI IV: KUSEN, PINTU & JENDELA ----------------
    div4 = "IV. PEKERJAAN KUSEN, PINTU & JENDELA"
    tambah(div4, "A.4.6.1.2", "Pengadaan & Pemasangan Unit Pintu Lengkap Kusen + Daun + Kunci", "unit", float(max(2, jml_pintu)), 2450000)
    tambah(div4, "A.4.6.2.16", "Pengadaan & Pemasangan Jendela Kusen + Kaca Bening 5 mm", "m²", max(1.5, luas_jendela_m2), 1180000)

    # ---------------- DIVISI V: ATAP & PLAFON ----------------
    div5 = "V. PEKERJAAN RANGKA ATAP, PENUTUP ATAP & PLAFON"
    tambah(div5, "A.4.2.1.21", "Pemasangan Rangka Atap Baja Ringan Profil C75.75 SNI", "m²", luas_atap_m2, 215000)
    tambah(div5, "A.4.5.2.32", "Pemasangan Penutup Atap Genteng Metal / Beton Berwarna", "m²", luas_atap_m2, 128000)
    tambah(div5, "A.4.5.2.36", "Pemasangan Nok / Bubungan Genteng", "m'", panjang_bgn_m + 2 * ov_m, 96000)
    tambah(div5, "A.4.6.1.21", "Pemasangan Lisplang Papan GRC Lebar 20 cm", "m'", 2 * (panjang_bgn_m + lebar_bgn_m + 4 * ov_m), 78000)
    tambah(div5, "A.4.5.1.7", "Pemasangan Plafon Gypsum Board 9 mm + Rangka Hollow Galvanis", "m²", luas_total_m2, 142000)

    # ---------------- DIVISI VI: PENUTUP LANTAI & DINDING KERAMIK ----------------
    div6 = "VI. PEKERJAAN PENUTUP LANTAI & KERAMIK"
    tambah(div6, "A.4.4.3.35", "Pemasangan Lantai Keramik Utama 40×40 / 60×60 cm Polished", "m²", luas_lantai_kering, 218000)
    if luas_lantai_km > 0:
        tambah(div6, "A.4.4.3.36", "Pemasangan Lantai Keramik KM/WC 20×20 cm Anti-Slip", "m²", luas_lantai_km, 205000)
    if luas_dinding_km > 0:
        tambah(div6, "A.4.4.3.54", "Pemasangan Keramik Dinding KM/WC 20×25 cm (t = 1,50 m)", "m²", luas_dinding_km, 232000)

    # ---------------- DIVISI VII: PENGECATAN, SANITAIR & MEP ----------------
    div7 = "VII. PEKERJAAN PENGECATAN, SANITAIR & INSTALASI"
    tambah(div7, "A.4.7.1.10", "Pengecatan Dinding Tembok Baru 3 Lapis (Plamir + Cat Dasar + Penutup)", "m²", luas_dinding_net_m2 * 2.0, 36500)
    tambah(div7, "A.4.7.1.11", "Pengecatan Plafon Gypsum 3 Lapis", "m²", luas_total_m2, 34000)
    jml_km = max(1, len(ruang_km))
    tambah(div7, "A.5.1.1.1", "Pemasangan Kloset Duduk / Jongkok Keramik Lengkap Aksesoris", "unit", float(jml_km), 1650000)
    tambah(div7, "A.5.1.1.19", "Pemasangan Keran Air, Jet Shower & Floor Drain Stainless", "set", float(jml_km), 425000)
    titik_listrik = max(8, int(round(luas_total_m2 / 3.8)))
    tambah(div7, "MEP.01", "Instalasi Titik Lampu, Saklar, Stop Kontak & MCB Box", "titik", float(titik_listrik), 265000)

    subtotal = sum(it["jumlah_harga"] for it in items)
    ppn = round(subtotal * 0.11, 0)
    grand_total = subtotal + ppn
    harga_per_m2 = round(grand_total / max(1.0, luas_total_m2), 0)

    return {
        "wilayah": wilayah,
        "ikk": ikk,
        "jumlah_lantai": 2 if is_2lt else 1,
        "luas_lt1_m2": round(luas_lt1_m2, 2),
        "luas_lt2_m2": round(luas_lt2_m2, 2),
        "luas_total_m2": round(luas_total_m2, 2),
        "items": items,
        "subtotal": subtotal,
        "ppn": ppn,
        "grand_total": grand_total,
        "harga_per_m2": harga_per_m2,
    }


def ekspor_rab_excel(rumah, hasil_rab: Dict[str, Any], nama_proyek: str = "Rumah Tinggal", pemilik: str = "Pemilik") -> bytes:
    """Mengekspor hasil perhitungan RAB menjadi file Excel (.XLSX) dengan rumus aktif."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "RAB Konstruksi"

    # Style palette
    fill_header = PatternFill("solid", fgColor="1E293B")
    fill_divisi = PatternFill("solid", fgColor="E2E8F0")
    fill_total = PatternFill("solid", fgColor="DBEAFE")
    font_title = Font(name="Calibri", size=14, bold=True, color="0F172A")
    font_sub = Font(name="Calibri", size=10, color="334155")
    font_th = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_div = Font(name="Calibri", size=10, bold=True, color="0F172A")
    font_td = Font(name="Calibri", size=10, color="1E293B")
    font_tot = Font(name="Calibri", size=11, bold=True, color="0F172A")

    thin = Side(style="thin", color="CBD5E1")
    border_cell = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Judul & Identitas Proyek
    ws["A1"] = "RENCANA ANGGARAN BIAYA (RAB) PEKERJAAN KONSTRUKSI"
    ws["A1"].font = font_title
    ws["A2"] = f"Proyek: {nama_proyek} ({hasil_rab['jumlah_lantai']} Lantai — Luas Total {hasil_rab['luas_total_m2']:.2f} m²)"
    ws["A2"].font = font_sub
    ws["A3"] = f"Pemilik: {pemilik}  |  Acuan Harga: {hasil_rab['wilayah']} (IKK = {hasil_rab['ikk']:.2f}×)"
    ws["A3"].font = font_sub

    row = 5
    headers = ["No", "Kode AHSP", "Uraian Pekerjaan", "Satuan", "Volume", "Harga Satuan (Rp)", "Jumlah Harga (Rp)"]
    for col_idx, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col_idx, value=h)
        c.fill = fill_header
        c.font = font_th
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border_cell
    ws.row_dimensions[row].height = 26

    row += 1
    current_div = None
    no_urut = 0
    div_start_row = row
    div_total_cells: List[str] = []

    def tutup_divisi(r_akhir: int):
        nonlocal row
        if r_akhir < div_start_row:
            return
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        lbl_cell = ws.cell(row=row, column=1, value=f"Jumlah {current_div}")
        lbl_cell.font = font_div
        lbl_cell.alignment = Alignment(horizontal="right", vertical="center")
        tot_cell = ws.cell(row=row, column=7, value=f"=SUM(G{div_start_row}:G{r_akhir})")
        tot_cell.font = font_div
        tot_cell.number_format = "#,##0"
        for c_i in range(1, 8):
            ws.cell(row=row, column=c_i).fill = fill_divisi
            ws.cell(row=row, column=c_i).border = border_cell
        div_total_cells.append(f"G{row}")
        row += 1

    for it in hasil_rab["items"]:
        if it["divisi"] != current_div:
            if current_div is not None:
                tutup_divisi(row - 1)
            current_div = it["divisi"]
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
            c_div = ws.cell(row=row, column=1, value=current_div)
            c_div.font = font_div
            c_div.fill = fill_divisi
            for c_i in range(1, 8):
                ws.cell(row=row, column=c_i).border = border_cell
            row += 1
            div_start_row = row
            no_urut = 0

        no_urut += 1
        vals = [no_urut, it["kode"], it["uraian"], it["satuan"], it["volume"], it["harga_satuan"], f"=ROUND(E{row}*F{row},0)"]
        for c_i, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=c_i, value=val)
            c.font = font_td
            c.border = border_cell
            if c_i in (1, 2, 4):
                c.alignment = Alignment(horizontal="center", vertical="center")
            elif c_i in (5, 6, 7):
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.number_format = "#,##0.00" if c_i == 5 else "#,##0"
        row += 1

    if current_div is not None:
        tutup_divisi(row - 1)

    row += 1
    formula_sub = "=" + "+".join(div_total_cells) if div_total_cells else "=0"
    r_sub = row
    r_ppn = row + 1
    r_tot = row + 2
    r_m2 = row + 3

    rekap = [
        ("SUBTOTAL BIAYA KONSTRUKSI", formula_sub, False),
        ("PPN 11%", f"=ROUND(G{r_sub}*0.11,0)", False),
        ("TOTAL RENCANA ANGGARAN BIAYA (RAB)", f"=G{r_sub}+G{r_ppn}", True),
        (f"ESTIMASI BIAYA PER M² ({hasil_rab['luas_total_m2']:.2f} m²)", f"=ROUND(G{r_tot}/{max(1.0, hasil_rab['luas_total_m2'])},0)", False),
    ]
    for offset_r, (label_rk, fml, is_bold) in enumerate(rekap):
        rr = row + offset_r
        ws.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=6)
        c_lbl = ws.cell(row=rr, column=1, value=label_rk)
        c_val = ws.cell(row=rr, column=7, value=fml)
        c_lbl.font = font_tot if is_bold else font_div
        c_val.font = font_tot if is_bold else font_div
        c_lbl.alignment = Alignment(horizontal="right", vertical="center")
        c_val.alignment = Alignment(horizontal="right", vertical="center")
        c_val.number_format = "#,##0"
        for c_i in range(1, 8):
            ws.cell(row=rr, column=c_i).border = border_cell
            if is_bold:
                ws.cell(row=rr, column=c_i).fill = fill_total

    widths = [6, 14, 52, 10, 12, 18, 20]
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()