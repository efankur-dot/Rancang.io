"""
Modul penggambaran denah 2D teknis arsitektur menggunakan ezdxf dan shapely.
Mendukung:
- Kolom praktis 150x150 mm di setiap sudut, persimpangan T/X, dan bentang > 3.5 m (S-COLS).
- Dinding berarsir pasangan bata merah ANSI32 skala 10 (A-WALL-PATT) dengan garis plesteran (A-WALL).
- Kosen pintu & jendela presisi dengan ketebalan daun pintu dan kosen samping (A-DOOR, A-GLAZ).
- Filter otomatis pintu tidak logis pada dinding luar kamar tidur.
- Blok furnitur & sanitair interior skalatis, presisi, proporsional, dan rapi (A-FURN).
- Garis as dinding (A-GRID).
- Simbol notasi potongan A-A dan B-B berstandar arsitektur (A-ANNO-SECT).
- Dimensi ukuran otomatis 2 tingkat berstandar arsitektur / architectural tick (A-ANNO-DIMS).
- Label ruang lengkap dengan elevasi FFL dan luas bersih m2 (A-ANNO-TEXT).
"""

import math
from pathlib import Path
from typing import List, Optional, Tuple, Union

import ezdxf
from shapely.geometry import LineString, MultiPoint, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from model.rumah import Rumah


def siapkan_layer_dan_style(doc: ezdxf.document.Drawing) -> None:
    """Menyiapkan layer standar arsitektur dan gaya dimensi."""
    daftar_layer = [
        {"name": "S-COLS", "color": 1},        # Merah (Kontras tinggi untuk Kolom Struktur Beton)
        {"name": "A-WALL", "color": 7},        # Putih/Hitam (Garis Dinding/Plesteran)
        {"name": "A-WALL-PATT", "color": 6},   # Magenta (Arsiran Pasangan Bata ANSI32)
        {"name": "A-DOOR", "color": 1},        # Merah (Kusen & Daun Pintu)
        {"name": "A-GLAZ", "color": 4},        # Cyan (Kusen & Kaca Jendela)
        {"name": "A-FURN", "color": 30},       # Oranye/Kuning (Furnitur & Sanitair)
        {"name": "A-GRID", "color": 8},        # Abu-abu (Garis As Dinding)
        {"name": "A-ANNO-SECT", "color": 7},   # Putih (Simbol & Garis Potongan)
        {"name": "A-ANNO-DIMS", "color": 3},   # Hijau (Garis Dimensi & Ukuran)
        {"name": "A-ANNO-TEXT", "color": 2},   # Kuning (Label Ruang & Keterangan)
        {"name": "ATAP_DETAIL", "color": 140},  # Biru Muda / Cyan-Blue (Rangka Kuda-Kuda, Listplank, Plafon)
        {"name": "KUSEN_POTONGAN", "color": 1}, # Merah (Kusen & Daun Potongan)
        {"name": "EKSTERIOR", "color": 8},      # Abu-abu (Carport, Teras, Pagar & Gerbang)
        {"name": "ORNAMEN_FASAD", "color": 2},  # Kuning (Roster & Tali Air Fasad)
    ]
    for l in daftar_layer:
        if l["name"] not in doc.layers:
            doc.layers.add(name=l["name"], color=l["color"])
        else:
            doc.layers.get(l["name"]).dxf.color = l["color"]

    # Gaya Dimensi Arsitektur (Architectural Tick 45 derajat)
    if "ARCH_100" not in doc.dimstyles:
        ds = doc.dimstyles.new("ARCH_100")
        ds.dxf.dimtxt = 140      # Tinggi huruf teks ukuran
        ds.dxf.dimasz = 100      # Ukuran garis miring (tick)
        ds.dxf.dimexe = 100      # Perpanjangan garis batas dimensi
        ds.dxf.dimexo = 80       # Jarak offset garis dari objek dinding
        ds.dxf.dimgap = 50       # Jarak teks ke garis ukur
        ds.dxf.dimtad = 1        # Posisi teks di atas garis ukur
        ds.dxf.dimtih = 0        # Teks sejajar garis ukur (horizontal=False)
        ds.dxf.dimtoh = 0        # Teks luar sejajar garis ukur
        ds.dxf.dimclrd = 7       # Warna garis ukur
        ds.dxf.dimclre = 7       # Warna garis bantu ekstensi
        ds.dxf.dimclrt = 7       # Warna teks angka ukuran
        ds.set_tick(size=100)    # Mengaktifkan oblique architectural tick


def import_template_blocks(doc: ezdxf.document.Drawing) -> None:
    """Mengimpor definisi blok interior dari assets/template_blocks.dxf jika tersedia dan membersihkan teks bawaan."""
    template_path = Path("assets/template_blocks.dxf")
    if not template_path.exists():
        return

    try:
        from ezdxf.addons.importer import Importer
        src_doc = ezdxf.readfile(str(template_path))
        importer = Importer(src_doc, doc)
        blok_kunci = [
            b for b in ["SOFA-L", "SOFA-1", "TOILET-1", "30'' Single Sink PV", "bed 1- king size"]
            if b in src_doc.blocks and b not in doc.blocks
        ]
        if blok_kunci:
            importer.import_blocks(blok_kunci)
            importer.finalize()

        if "bed 1- king size" in doc.blocks:
            b_bed = doc.blocks["bed 1- king size"]
            for e in list(b_bed):
                if e.dxftype() in ("TEXT", "MTEXT"):
                    b_bed.delete_entity(e)

    except Exception as e:
        print(f"[CATATAN] Gagal memuat template blok: {e}")


def _saring_bukaan_valid(rumah: Rumah) -> None:
    """Menghapus pintu tidak logis pada dinding keliling luar kamar tidur (mis. di belakang kasur)."""
    if not rumah.dinding or not rumah.bukaan:
        return

    semua_x = [d.a[0] for d in rumah.dinding] + [d.b[0] for d in rumah.dinding]
    semua_y = [d.a[1] for d in rumah.dinding] + [d.b[1] for d in rumah.dinding]
    min_x, max_x = min(semua_x), max(semua_x)
    min_y, max_y = min(semua_y), max(semua_y)

    kamar_list = [
        r for r in rumah.ruang
        if "kamar" in r.nama.strip().lower() or "tidur" in r.nama.strip().lower()
    ]
    if not kamar_list:
        return

    bukaan_bersih = []
    for b in rumah.bukaan:
        if b.jenis != "pintu":
            bukaan_bersih.append(b)
            continue

        d = rumah.cari_dinding(b.dinding)
        if not d:
            bukaan_bersih.append(b)
            continue

        is_horiz_luar = abs(d.a[1] - d.b[1]) < 1e-3 and (
            abs(d.a[1] - min_y) < 1e-3 or abs(d.a[1] - max_y) < 1e-3
        )
        is_vert_luar = abs(d.a[0] - d.b[0]) < 1e-3 and (
            abs(d.a[0] - min_x) < 1e-3 or abs(d.a[0] - max_x) < 1e-3
        )

        if not (is_horiz_luar or is_vert_luar):
            bukaan_bersih.append(b)
            continue

        dx = d.b[0] - d.a[0]
        dy = d.b[1] - d.a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            bukaan_bersih.append(b)
            continue

        tengah = b.offset + b.lebar / 2.0
        mx = d.a[0] + (dx / L) * tengah
        my = d.a[1] + (dy / L) * tengah

        menempel_kamar = False
        for km in kamar_list:
            k = km.kotak
            kx0, kx1 = min(k[0], k[2]) - 200.0, max(k[0], k[2]) + 200.0
            ky0, ky1 = min(k[1], k[3]) - 200.0, max(k[1], k[3]) + 200.0
            if kx0 <= mx <= kx1 and ky0 <= my <= ky1:
                menempel_kamar = True
                break

        if not menempel_kamar:
            bukaan_bersih.append(b)

    rumah.bukaan = bukaan_bersih


def _tambah_titik_kolom_unik(daftar_titik: List[Tuple[float, float]], x: float, y: float, toleransi: float = 15.0) -> None:
    """Menambahkan koordinat kolom dengan pembulatan 1 mm dan anti-duplikasi dalam radius toleransi."""
    rx = float(round(x))
    ry = float(round(y))
    for ex, ey in daftar_titik:
        if math.hypot(rx - ex, ry - ey) <= toleransi:
            return
    daftar_titik.append((rx, ry))


def _titik_menabrak_bukaan(rumah: Rumah, dinding_id: str, jarak_dari_awal: float, margin: float = 180.0) -> bool:
    """Mengecek apakah posisi calon kolom praktis tengah bentang bertabrakan dengan pintu atau jendela."""
    for b in rumah.bukaan:
        if b.dinding == dinding_id:
            if (b.offset - margin) <= jarak_dari_awal <= (b.akhir + margin):
                return True
    return False


def _kumpulkan_titik_kolom(rumah: Rumah) -> List[Tuple[float, float]]:
    """
    Mendeteksi seluruh titik kolom praktis di:
    1. Seluruh ujung segmen dinding (sudut bangunan).
    2. Seluruh titik persimpangan geometris antar dinding (T-junction & X-crossing).
    3. Titik tengah bentang dinding panjang (> 3500 mm) yang bebas dari bukaan pintu/jendela.
    """
    titik_kolom: List[Tuple[float, float]] = []
    garis_dinding = []

    for d in rumah.dinding:
        _tambah_titik_kolom_unik(titik_kolom, d.a[0], d.a[1])
        _tambah_titik_kolom_unik(titik_kolom, d.b[0], d.b[1])
        garis_dinding.append((d, LineString([d.a, d.b])))

    n_garis = len(garis_dinding)
    for i in range(n_garis):
        for j in range(i + 1, n_garis):
            inter = garis_dinding[i][1].intersection(garis_dinding[j][1])
            if inter.is_empty:
                continue
            if isinstance(inter, Point):
                _tambah_titik_kolom_unik(titik_kolom, inter.x, inter.y)
            elif isinstance(inter, MultiPoint):
                for pt in inter.geoms:
                    _tambah_titik_kolom_unik(titik_kolom, pt.x, pt.y)

    bentang_maks = 3500.0
    for d, garis in garis_dinding:
        panjang_segmen = garis.length
        if panjang_segmen > bentang_maks:
            jumlah_bagi = math.ceil(panjang_segmen / bentang_maks)
            dx = d.b[0] - d.a[0]
            dy = d.b[1] - d.a[1]
            for k in range(1, jumlah_bagi):
                rasio = k / jumlah_bagi
                jarak = panjang_segmen * rasio
                if not _titik_menabrak_bukaan(rumah, d.id, jarak):
                    kx = d.a[0] + dx * rasio
                    ky = d.a[1] + dy * rasio
                    _tambah_titik_kolom_unik(titik_kolom, kx, ky, toleransi=250.0)

    return sorted(titik_kolom)


def hitung_kolom_union(rumah: Rumah):
    """Menghitung koordinat dan gabungan poligon seluruh kolom praktis untuk pemotongan dinding."""
    kolom_w, kolom_h = rumah.struktur.get("kolom", [150, 150])
    hx, hy = kolom_w / 2.0, kolom_h / 2.0
    titik_kolom = _kumpulkan_titik_kolom(rumah)
    kotak_kolom = [box(x - hx, y - hy, x + hx, y + hy) for x, y in titik_kolom]
    return titik_kolom, (unary_union(kotak_kolom) if kotak_kolom else None)


def gambar_kolom(rumah: Rumah, msp, titik_kolom: Optional[List[Tuple[float, float]]] = None):
    """Menggambar kolom praktis (150x150 mm) dengan arsiran solid merah dan silang diagonal di atas dinding."""
    kolom_w, kolom_h = rumah.struktur.get("kolom", [150, 150])
    hx, hy = kolom_w / 2.0, kolom_h / 2.0
    if titik_kolom is None:
        titik_kolom = _kumpulkan_titik_kolom(rumah)

    kotak_kolom = []
    for x, y in titik_kolom:
        kotak_kolom.append(box(x - hx, y - hy, x + hx, y + hy))

        p_bl = (x - hx, y - hy)
        p_br = (x + hx, y - hy)
        p_tr = (x + hx, y + hy)
        p_tl = (x - hx, y + hy)
        coords = [p_bl, p_br, p_tr, p_tl]

        # Arsiran Solid Merah pada Kolom Struktur
        hk = msp.add_hatch(dxfattribs={"layer": "S-COLS", "color": 256})
        hk.set_solid_fill()
        hk.paths.add_polyline_path(coords, is_closed=True)

        # Batas luar kolom tertutup & garis silang diagonal merah kontras
        msp.add_lwpolyline(coords, close=True, dxfattribs={"layer": "S-COLS", "color": 256})
        msp.add_line(p_bl, p_tr, dxfattribs={"layer": "S-COLS", "color": 256})
        msp.add_line(p_tl, p_br, dxfattribs={"layer": "S-COLS", "color": 256})

    return unary_union(kotak_kolom) if kotak_kolom else None


def gambar_dinding(rumah: Rumah, msp, kolom_union) -> None:
    """Menggambar dinding, potongan bukaan, dan arsiran bata ANSI32 skala 10."""
    tebal_default = rumah.dinding_default.get("tebal", 150)

    poligon_dinding = []
    for d in rumah.dinding:
        tebal = d.tebal if d.tebal is not None else tebal_default
        garis = LineString([d.a, d.b])
        poly = garis.buffer(tebal / 2, cap_style="flat")
        poligon_dinding.append(poly)

    dinding_gabungan = unary_union(poligon_dinding)

    pemotong_bukaan = []
    for b in rumah.bukaan:
        d = rumah.cari_dinding(b.dinding)
        if not d:
            continue
        dx = d.b[0] - d.a[0]
        dy = d.b[1] - d.a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            continue
        ux, uy = dx / L, dy / L
        p1 = (d.a[0] + ux * b.offset, d.a[1] + uy * b.offset)
        p2 = (d.a[0] + ux * b.akhir, d.a[1] + uy * b.akhir)

        tebal = d.tebal if d.tebal is not None else tebal_default
        cut_poly = LineString([p1, p2]).buffer((tebal + 20) / 2, cap_style="flat")
        pemotong_bukaan.append(cut_poly)

    if pemotong_bukaan:
        dinding_terpotong = dinding_gabungan.difference(unary_union(pemotong_bukaan))
    else:
        dinding_terpotong = dinding_gabungan

    # Kurangi dengan kolom agar dinding berhenti tepat di sisi muka kolom
    if kolom_union:
        dinding_akhir = dinding_terpotong.difference(kolom_union)
    else:
        dinding_akhir = dinding_terpotong

    if isinstance(dinding_akhir, Polygon):
        daftar_poligon = [dinding_akhir]
    elif isinstance(dinding_akhir, MultiPolygon):
        daftar_poligon = list(dinding_akhir.geoms)
    else:
        daftar_poligon = []

    for poly in daftar_poligon:
        luar_coords = list(poly.exterior.coords)
        msp.add_lwpolyline(luar_coords, close=True, dxfattribs={"layer": "A-WALL"})

        # Arsiran Pola Pasangan Bata Merah ANSI32 Skala 10
        hatch = msp.add_hatch(color=6, dxfattribs={"layer": "A-WALL-PATT"})
        hatch.set_pattern_fill("ANSI32", scale=10)
        hatch.paths.add_polyline_path(luar_coords, is_closed=True)

        for interior in poly.interiors:
            dalam_coords = list(interior.coords)
            msp.add_lwpolyline(dalam_coords, close=True, dxfattribs={"layer": "A-WALL"})
            hatch.paths.add_polyline_path(dalam_coords, is_closed=True)


def gambar_pintu(rumah: Rumah, msp) -> None:
    """Menggambar pintu lengkap dengan kosen samping 50x150 mm dan daun berketebalan."""
    tebal_default = rumah.dinding_default.get("tebal", 150)
    kosen_w = 50.0    # Lebar kosen (50 mm)
    tebal_daun = 35.0 # Ketebalan daun pintu (35 mm)

    for b in rumah.bukaan:
        if b.jenis != "pintu":
            continue
        d = rumah.cari_dinding(b.dinding)
        if not d:
            continue
        dx = d.b[0] - d.a[0]
        dy = d.b[1] - d.a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        t = d.tebal if d.tebal is not None else tebal_default
        w = t / 2

        p_awal = (d.a[0] + ux * b.offset, d.a[1] + uy * b.offset)
        p_akhir = (d.a[0] + ux * b.akhir, d.a[1] + uy * b.akhir)

        # 1. Kosen Awal (50x150 mm)
        c1_1 = (p_awal[0] - nx * w, p_awal[1] - ny * w)
        c1_2 = (p_awal[0] + nx * w, p_awal[1] + ny * w)
        c1_3 = (c1_2[0] + ux * kosen_w, c1_2[1] + uy * kosen_w)
        c1_4 = (c1_1[0] + ux * kosen_w, c1_1[1] + uy * kosen_w)
        msp.add_lwpolyline([c1_1, c1_2, c1_3, c1_4], close=True, dxfattribs={"layer": "A-DOOR"})

        # 2. Kosen Akhir (50x150 mm)
        c2_1 = (p_akhir[0] - nx * w, p_akhir[1] - ny * w)
        c2_2 = (p_akhir[0] + nx * w, p_akhir[1] + ny * w)
        c2_3 = (c2_2[0] - ux * kosen_w, c2_2[1] - uy * kosen_w)
        c2_4 = (c2_1[0] - ux * kosen_w, c2_1[1] - uy * kosen_w)
        msp.add_lwpolyline([c2_1, c2_2, c2_3, c2_4], close=True, dxfattribs={"layer": "A-DOOR"})

        # 3. Orientasi Ayunan ke Ruangan Tujuan
        sx, sy = nx, ny
        if b.ayun_ke:
            ruang_tujuan = next((r for r in rumah.ruang if r.nama.strip().lower() == b.ayun_ke.strip().lower()), None)
            if ruang_tujuan:
                mx = (p_awal[0] + p_akhir[0]) / 2
                my = (p_awal[1] + p_akhir[1]) / 2
                titik_uji = (mx + nx * 50, my + ny * 50)
                k = ruang_tujuan.kotak
                if not (min(k[0], k[2]) <= titik_uji[0] <= max(k[0], k[2]) and min(k[1], k[3]) <= titik_uji[1] <= max(k[1], k[3])):
                    sx, sy = -nx, -ny

        lebar_daun = b.lebar - kosen_w
        if b.engsel == "akhir":
            hx = p_akhir[0] - ux * kosen_w
            hy = p_akhir[1] - uy * kosen_w
            v_tutup = (-ux, -uy)
        else:
            hx = p_awal[0] + ux * kosen_w
            hy = p_awal[1] + uy * kosen_w
            v_tutup = (ux, uy)

        v_buka = (sx, sy)

        # 4. Daun Pintu Berketebalan
        p_buka = (hx + v_buka[0] * lebar_daun, hy + v_buka[1] * lebar_daun)
        vn_x, vn_y = -v_tutup[0], -v_tutup[1]
        dp1 = (hx, hy)
        dp2 = p_buka
        dp3 = (p_buka[0] + vn_x * tebal_daun, p_buka[1] + vn_y * tebal_daun)
        dp4 = (hx + vn_x * tebal_daun, hy + vn_y * tebal_daun)
        msp.add_lwpolyline([dp1, dp2, dp3, dp4], close=True, dxfattribs={"layer": "A-DOOR"})

        # 5. Busur Ayunan Pintu
        sudut_tutup = math.degrees(math.atan2(v_tutup[1], v_tutup[0])) % 360
        sudut_buka = math.degrees(math.atan2(v_buka[1], v_buka[0])) % 360
        if (sudut_buka - sudut_tutup) % 360 < 180:
            s_mulai, s_selesai = sudut_tutup, sudut_buka
        else:
            s_mulai, s_selesai = sudut_buka, sudut_tutup

        msp.add_arc((hx, hy), radius=lebar_daun, start_angle=s_mulai, end_angle=s_selesai, dxfattribs={"layer": "A-DOOR"})


def gambar_jendela(rumah: Rumah, msp) -> None:
    """Menggambar jendela lengkap dengan kosen samping 50x150 mm dan 3 garis kaca."""
    tebal_default = rumah.dinding_default.get("tebal", 150)
    kw = 50.0  # Lebar kosen (50 mm)

    for b in rumah.bukaan:
        if b.jenis != "jendela":
            continue
        d = rumah.cari_dinding(b.dinding)
        if not d:
            continue
        dx = d.b[0] - d.a[0]
        dy = d.b[1] - d.a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            continue
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        t = d.tebal if d.tebal is not None else tebal_default
        w = t / 2

        p1 = (d.a[0] + ux * b.offset, d.a[1] + uy * b.offset)
        p2 = (d.a[0] + ux * b.akhir, d.a[1] + uy * b.akhir)

        # Kosen Kiri
        k1_a = (p1[0] - nx * w, p1[1] - ny * w)
        k1_b = (p1[0] + nx * w, p1[1] + ny * w)
        k1_c = (k1_b[0] + ux * kw, k1_b[1] + uy * kw)
        k1_d = (k1_a[0] + ux * kw, k1_a[1] + uy * kw)
        msp.add_lwpolyline([k1_a, k1_b, k1_c, k1_d], close=True, dxfattribs={"layer": "A-GLAZ"})

        # Kosen Kanan
        k2_a = (p2[0] - nx * w, p2[1] - ny * w)
        k2_b = (p2[0] + nx * w, p2[1] + ny * w)
        k2_c = (k2_b[0] - ux * kw, k2_b[1] - uy * kw)
        k2_d = (k2_a[0] - ux * kw, k2_a[1] - uy * kw)
        msp.add_lwpolyline([k2_a, k2_b, k2_c, k2_d], close=True, dxfattribs={"layer": "A-GLAZ"})

        # Garis Kaca Tengah & Kusen Horisontal
        gp1 = (p1[0] + ux * kw, p1[1] + uy * kw)
        gp2 = (p2[0] - ux * kw, p2[1] - uy * kw)
        msp.add_line((gp1[0] + nx * w, gp1[1] + ny * w), (gp2[0] + nx * w, gp2[1] + ny * w), dxfattribs={"layer": "A-GLAZ"})
        msp.add_line(gp1, gp2, dxfattribs={"layer": "A-GLAZ"})
        msp.add_line((gp1[0] - nx * w, gp1[1] - ny * w), (gp2[0] - nx * w, gp2[1] - ny * w), dxfattribs={"layer": "A-GLAZ"})


def gambar_furnitur(rumah: Rumah, msp) -> None:
    """
    Menempatkan blok interior (sofa, kasur, meja dapur, sink, kompor, kloset)
    secara proporsional, skalatis standar rumah tipe 36, dan tidak menabrak dinding/pintu.
    """
    doc = msp.doc
    tersedia = set(b.name for b in doc.blocks)

    for r in rumah.ruang:
        nama = r.nama.strip().lower()

        if "tamu" in nama or "keluarga" in nama:
            if "SOFA-L" in tersedia:
                sofa_x = r.kotak[0] + 1400
                sofa_y = r.kotak[1] + 1800
                msp.add_blockref(
                    "SOFA-L",
                    insert=(sofa_x, sofa_y),
                    dxfattribs={
                        "layer": "A-FURN",
                        "xscale": 600,
                        "yscale": 600,
                        "zscale": 600,
                        "rotation": 180,
                    }
                )

        elif "kamar tidur 1" in nama:
            if "bed 1- king size" in tersedia:
                bed_x = r.kotak[0] + 1150
                bed_y = r.kotak[3] - 150
                msp.add_blockref(
                    "bed 1- king size",
                    insert=(bed_x, bed_y),
                    dxfattribs={
                        "layer": "A-FURN",
                        "xscale": 750,
                        "yscale": 850,
                        "zscale": 850,
                        "rotation": 0,
                    }
                )

        elif "kamar tidur 2" in nama:
            if "bed 1- king size" in tersedia:
                bed_x = r.kotak[0] + 1150
                bed_y = r.kotak[3] - 150
                msp.add_blockref(
                    "bed 1- king size",
                    insert=(bed_x, bed_y),
                    dxfattribs={
                        "layer": "A-FURN",
                        "xscale": 750,
                        "yscale": 850,
                        "zscale": 850,
                        "rotation": 0,
                    }
                )

        elif "dapur" in nama:
            c_x2 = r.kotak[2] - 75
            c_x1 = c_x2 - 600
            c_y1 = r.kotak[1] + 150
            c_y2 = r.kotak[3] - 100
            counter_pts = [
                (c_x1, c_y1),
                (c_x2, c_y1),
                (c_x2, c_y2),
                (c_x1, c_y2),
            ]
            msp.add_lwpolyline(counter_pts, close=True, dxfattribs={"layer": "A-FURN"})

            if "30'' Single Sink PV" in tersedia:
                msp.add_blockref(
                    "30'' Single Sink PV",
                    insert=(c_x2 - 55, c_y2 - 500),
                    dxfattribs={
                        "layer": "A-FURN",
                        "xscale": 25.4,
                        "yscale": 25.4,
                        "zscale": 25.4,
                        "rotation": 270,
                    }
                )

            kompor_y1 = c_y1 + 100
            kompor_y2 = kompor_y1 + 400
            kompor_box = [
                (c_x1 + 100, kompor_y1),
                (c_x2 - 100, kompor_y1),
                (c_x2 - 100, kompor_y2),
                (c_x1 + 100, kompor_y2),
            ]
            msp.add_lwpolyline(kompor_box, close=True, dxfattribs={"layer": "A-FURN"})
            k_mid_x = (c_x1 + c_x2) / 2
            msp.add_circle((k_mid_x, kompor_y1 + 100), radius=65, dxfattribs={"layer": "A-FURN"})
            msp.add_circle((k_mid_x, kompor_y1 + 300), radius=65, dxfattribs={"layer": "A-FURN"})

        elif "km" in nama or "wc" in nama:
            if "TOILET-1" in tersedia:
                toilet_x = (r.kotak[0] + r.kotak[2]) / 2 + 150
                toilet_y = r.kotak[3] - 150
                msp.add_blockref(
                    "TOILET-1",
                    insert=(toilet_x, toilet_y),
                    dxfattribs={
                        "layer": "A-FURN",
                        "xscale": 750,
                        "yscale": 750,
                        "zscale": 750,
                        "rotation": 0,
                    }
                )
            msp.add_circle((r.kotak[0] + 350, r.kotak[3] - 350), radius=50, dxfattribs={"layer": "A-FURN"})


def gambar_garis_as(rumah: Rumah, msp) -> None:
    """Menggambar garis as dinding (A-GRID)."""
    for d in rumah.dinding:
        dx = d.b[0] - d.a[0]
        dy = d.b[1] - d.a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            continue
        ux, uy = dx / L, dy / L
        g1 = (d.a[0] - ux * 200, d.a[1] - uy * 200)
        g2 = (d.b[0] + ux * 200, d.b[1] + uy * 200)
        msp.add_line(g1, g2, dxfattribs={"layer": "A-GRID"})


def gambar_garis_putus(msp, p1: Tuple[float, float], p2: Tuple[float, float], dash: float = 600.0, gap: float = 300.0, layer: str = "A-ANNO-SECT") -> None:
    """Menggambar garis putus-putus arsitektur manual yang rapi dan konsisten."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    L = math.hypot(dx, dy)
    if L == 0:
        return
    ux, uy = dx / L, dy / L
    cur = 0.0
    while cur < L:
        seg_end = min(cur + dash, L)
        msp.add_line(
            (p1[0] + ux * cur, p1[1] + uy * cur),
            (p1[0] + ux * seg_end, p1[1] + uy * seg_end),
            dxfattribs={"layer": layer}
        )
        cur += dash + gap


def gambar_simbol_potongan(rumah: Rumah, msp) -> None:
    """Menggambar simbol potongan A-A dan B-B berstandar arsitektur."""
    semua_x = [d.a[0] for d in rumah.dinding] + [d.b[0] for d in rumah.dinding]
    semua_y = [d.a[1] for d in rumah.dinding] + [d.b[1] for d in rumah.dinding]
    min_x, max_x = (min(semua_x), max(semua_x)) if semua_x else (0.0, 6000.0)
    min_y, max_y = (min(semua_y), max(semua_y)) if semua_y else (0.0, 6000.0)

    for p in rumah.potongan:
        nama = p.get("nama", "A-A")
        label = nama.split("-")[0]
        arah = p.get("arah", "x")
        posisi = p.get("posisi", 1500)
        lihat = p.get("lihat", "utara").lower()

        radius = 240.0
        offset_luar = 1800.0

        if arah == "x":
            x_min = min_x - offset_luar
            x_max = max_x + offset_luar
            y_pos = float(posisi)

            gambar_garis_putus(msp, (x_min, y_pos), (x_max, y_pos), dash=600, gap=300, layer="A-ANNO-SECT")

            for x_ujung in [x_min, x_max]:
                msp.add_circle((x_ujung, y_pos), radius=radius, dxfattribs={"layer": "A-ANNO-SECT"})
                mtext = msp.add_mtext(label, dxfattribs={"layer": "A-ANNO-SECT", "char_height": 200, "attachment_point": 5})
                mtext.set_location((x_ujung, y_pos))

                panah_arah = 1 if "utara" in lihat else -1
                tri = [
                    (x_ujung - 130, y_pos + panah_arah * radius),
                    (x_ujung + 130, y_pos + panah_arah * radius),
                    (x_ujung, y_pos + panah_arah * (radius + 260)),
                ]
                msp.add_lwpolyline(tri, close=True, dxfattribs={"layer": "A-ANNO-SECT"})
                h = msp.add_hatch(color=7, dxfattribs={"layer": "A-ANNO-SECT"})
                h.set_solid_fill()
                h.paths.add_polyline_path(tri, is_closed=True)

        else:
            y_min = min_y - offset_luar
            y_max = max_y + offset_luar
            x_pos = float(posisi)

            gambar_garis_putus(msp, (x_pos, y_min), (x_pos, y_max), dash=600, gap=300, layer="A-ANNO-SECT")

            for y_ujung in [y_min, y_max]:
                msp.add_circle((x_pos, y_ujung), radius=radius, dxfattribs={"layer": "A-ANNO-SECT"})
                mtext = msp.add_mtext(label, dxfattribs={"layer": "A-ANNO-SECT", "char_height": 200, "attachment_point": 5})
                mtext.set_location((x_pos, y_ujung))

                panah_arah = 1 if "timur" in lihat else -1
                tri = [
                    (x_pos + panah_arah * radius, y_ujung - 130),
                    (x_pos + panah_arah * radius, y_ujung + 130),
                    (x_pos + panah_arah * (radius + 260), y_ujung),
                ]
                msp.add_lwpolyline(tri, close=True, dxfattribs={"layer": "A-ANNO-SECT"})
                h = msp.add_hatch(color=7, dxfattribs={"layer": "A-ANNO-SECT"})
                h.set_solid_fill()
                h.paths.add_polyline_path(tri, is_closed=True)


def gambar_label_ruang(rumah: Rumah, msp) -> None:
    """Menggambar label nama ruang, elevasi FFL, dan luas bersih."""
    for r in rumah.ruang:
        cx = (r.kotak[0] + r.kotak[2]) / 2
        cy = (r.kotak[1] + r.kotak[3]) / 2

        nama_l = r.nama.lower()
        if "kamar" in nama_l:
            cx += 500
            cy -= 550
        elif "tamu" in nama_l:
            cy -= 700
        elif "km" in nama_l or "wc" in nama_l:
            cx -= 250
            cy -= 350
        elif "dapur" in nama_l:
            cx -= 300

        faktor_luas = 1_000_000 if rumah.satuan == "mm" else 1.0
        luas_m2 = r.luas / faktor_luas
        elevasi = rumah.lantai.get("elevasi", 0)
        tanda = "± 0.00" if elevasi == 0 else f"{elevasi:+.2f}"

        teks_label = f"{r.nama.upper()}\nFFL {tanda}\nL: {luas_m2:.2f} m²"
        mtext = msp.add_mtext(
            teks_label,
            dxfattribs={
                "layer": "A-ANNO-TEXT",
                "char_height": 130,
                "attachment_point": 5,
            }
        )
        mtext.set_location((cx, cy))


def gambar_dimensi_otomatis(rumah: Rumah, msp) -> None:
    """Menggambar garis dimensi ukuran otomatis (2 tingkat) pada 4 sisi luar denah."""
    semua_x = [d.a[0] for d in rumah.dinding] + [d.b[0] for d in rumah.dinding]
    semua_y = [d.a[1] for d in rumah.dinding] + [d.b[1] for d in rumah.dinding]
    if not semua_x or not semua_y:
        return

    min_x, max_x = min(semua_x), max(semua_x)
    min_y, max_y = min(semua_y), max(semua_y)

    # 1. Dimensi Sisi Bawah (Y = min_y)
    xs_bawah = sorted(set(d.a[0] for d in rumah.dinding if abs(d.a[1] - min_y) < 1e-3) |
                      set(d.b[0] for d in rumah.dinding if abs(d.b[1] - min_y) < 1e-3))
    if len(xs_bawah) > 1:
        for i in range(len(xs_bawah) - 1):
            x1, x2 = xs_bawah[i], xs_bawah[i + 1]
            if x2 > x1:
                dim = msp.add_linear_dim(
                    base=(x1, min_y - 600),
                    p1=(x1, min_y),
                    p2=(x2, min_y),
                    angle=0,
                    dimstyle="ARCH_100",
                    dxfattribs={"layer": "A-ANNO-DIMS"}
                )
                dim.render()

        dim_tot = msp.add_linear_dim(
            base=(min_x, min_y - 1100),
            p1=(min_x, min_y),
            p2=(max_x, min_y),
            angle=0,
            dimstyle="ARCH_100",
            dxfattribs={"layer": "A-ANNO-DIMS"}
        )
        dim_tot.render()

    # 2. Dimensi Sisi Atas (Y = max_y)
    xs_atas = sorted(set(d.a[0] for d in rumah.dinding if abs(d.a[1] - max_y) < 1e-3) |
                     set(d.b[0] for d in rumah.dinding if abs(d.b[1] - max_y) < 1e-3))
    if len(xs_atas) > 1:
        for i in range(len(xs_atas) - 1):
            x1, x2 = xs_atas[i], xs_atas[i + 1]
            if x2 > x1:
                dim = msp.add_linear_dim(
                    base=(x1, max_y + 600),
                    p1=(x1, max_y),
                    p2=(x2, max_y),
                    angle=0,
                    dimstyle="ARCH_100",
                    dxfattribs={"layer": "A-ANNO-DIMS"}
                )
                dim.render()

        dim_tot = msp.add_linear_dim(
            base=(min_x, max_y + 1100),
            p1=(min_x, max_y),
            p2=(max_x, max_y),
            angle=0,
            dimstyle="ARCH_100",
            dxfattribs={"layer": "A-ANNO-DIMS"}
        )
        dim_tot.render()

    # 3. Dimensi Sisi Kiri (X = min_x)
    ys_kiri = sorted(set(d.a[1] for d in rumah.dinding if abs(d.a[0] - min_x) < 1e-3) |
                     set(d.b[1] for d in rumah.dinding if abs(d.b[0] - min_x) < 1e-3))
    if len(ys_kiri) > 1:
        for i in range(len(ys_kiri) - 1):
            y1, y2 = ys_kiri[i], ys_kiri[i + 1]
            if y2 > y1:
                dim = msp.add_linear_dim(
                    base=(min_x - 600, y1),
                    p1=(min_x, y1),
                    p2=(min_x, y2),
                    angle=90,
                    dimstyle="ARCH_100",
                    dxfattribs={"layer": "A-ANNO-DIMS"}
                )
                dim.render()

        dim_tot = msp.add_linear_dim(
            base=(min_x - 1100, min_y),
            p1=(min_x, min_y),
            p2=(min_x, max_y),
            angle=90,
            dimstyle="ARCH_100",
            dxfattribs={"layer": "A-ANNO-DIMS"}
        )
        dim_tot.render()

    # 4. Dimensi Sisi Kanan (X = max_x)
    ys_kanan = sorted(set(d.a[1] for d in rumah.dinding if abs(d.a[0] - max_x) < 1e-3) |
                      set(d.b[1] for d in rumah.dinding if abs(d.b[0] - max_x) < 1e-3))
    if len(ys_kanan) > 1:
        for i in range(len(ys_kanan) - 1):
            y1, y2 = ys_kanan[i], ys_kanan[i + 1]
            if y2 > y1:
                dim = msp.add_linear_dim(
                    base=(max_x + 600, y1),
                    p1=(max_x, y1),
                    p2=(max_x, y2),
                    angle=90,
                    dimstyle="ARCH_100",
                    dxfattribs={"layer": "A-ANNO-DIMS"}
                )
                dim.render()

        dim_tot = msp.add_linear_dim(
            base=(max_x + 1100, min_y),
            p1=(max_x, min_y),
            p2=(max_x, max_y),
            angle=90,
            dimstyle="ARCH_100",
            dxfattribs={"layer": "A-ANNO-DIMS"}
        )
        dim_tot.render()


def gambar_denah(rumah: Rumah, msp, gambar_perabot: bool = True, **kwargs) -> None:
    """Menggambar denah rumah teknis lengkap ke modelspace (msp) ezdxf."""
    doc = msp.doc
    siapkan_layer_dan_style(doc)
    _saring_bukaan_valid(rumah)

    if gambar_perabot:
        import_template_blocks(doc)

    titik_kolom, kolom_union = hitung_kolom_union(rumah)
    gambar_dinding(rumah, msp, kolom_union)
    gambar_kolom(rumah, msp, titik_kolom)
    gambar_pintu(rumah, msp)
    gambar_jendela(rumah, msp)

    if gambar_perabot:
        gambar_furnitur(rumah, msp)

    gambar_garis_as(rumah, msp)
    gambar_simbol_potongan(rumah, msp)
    gambar_label_ruang(rumah, msp)
    gambar_dimensi_otomatis(rumah, msp)


def ekspor_denah(rumah: Rumah, path: Union[str, Path] = "hasil/denah.dxf", gambar_perabot: bool = True, **kwargs) -> Path:
    """Membuat berkas DXF R2018 teknis lengkap dan menyimpannya."""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4  # 4 = mm
    msp = doc.modelspace()

    gambar_denah(rumah, msp, gambar_perabot=gambar_perabot)

    try:
        doc.saveas(str(path_obj))
        return path_obj
    except PermissionError:
        alt_path = path_obj.parent / f"{path_obj.stem}_updated{path_obj.suffix}"
        doc.saveas(str(alt_path))
        print(f"[PERINGATAN] '{path_obj.name}' sedang dibuka di AutoCAD (file terkunci).")
        print(f"[ALTERNATIF] Hasil baru berhasil disimpan ke: '{alt_path.name}'.")
        return alt_path


def ekspor_gambar_lengkap(*args, **kwargs):
    """Fungsi delegasi ke drawing.potongan.ekspor_gambar_lengkap."""
    from drawing.potongan import ekspor_gambar_lengkap as _impl
    return _impl(*args, **kwargs)