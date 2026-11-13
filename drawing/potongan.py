"""Potongan dan tampak rumah (DXF) dari model Rumah, memakai ezdxf.

Fungsi utama: ekspor_gambar_lengkap(rumah, path)
  -> satu file DXF berisi denah, semua potongan di rumah.potongan, dan 4 tampak.
  -> mengembalikan (path, daerah) dengan daerah = {nama_gambar: (xmin, ymin, xmax, ymax)}.
Semua ukuran dalam mm. Skala gambar 1:100.
Mendukung detail arsitektur DED:
- Rangka atap kuda-kuda baja ringan (batang tarik, kaki kuda-kuda, web segitiga, king post), listplank, dan plafon gypsum + penggantung (ATAP_DETAIL).
- Detail bukaan terpotong: penampang kusen atas/bawah, daun pintu, dan kaca berprofil (KUSEN_POTONGAN).
- Elemen eksterior fasad depan: teras bertingkat, dak kanopi beton, tiang teras, carport rabat beton, pagar tembok, dan gerbang minimalis (EKSTERIOR).
- Ornamen fasad: motif roster ventilasi dan aksen tali air dinding modern (ORNAMEN_FASAD).
"""
import math
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment as TA

from drawing.denah import gambar_denah

DIM = "ARCH_100"          # gaya dimensi dari denah.py
TINGGI_TEKS = 130


# ----------------------------------------------------------------- bantu
def _layer(doc):
    daftar = [
        ("A-SECT-WALL", 7), ("S-BETON", 6), ("S-PONDASI", 8), ("A-ROOF", 30),
        ("A-ELEV", 7), ("A-GROUND", 94), ("A-ANNO-LEVL", 3), ("A-WALL-PATT", 8),
        ("A-GLAZ", 4), ("A-DOOR", 1), ("A-ANNO-DIMS", 1), ("A-ANNO-TEXT", 2),
        ("ATAP_DETAIL", 140),    # Cyan/Biru muda (Kuda-kuda truss, listplank, rangka plafon)
        ("KUSEN_POTONGAN", 1),   # Merah (Penampang kusen & daun bukaan terpotong)
        ("EKSTERIOR", 8),        # Abu-abu (Carport, teras, kanopi, pagar tembok & gerbang)
        ("ORNAMEN_FASAD", 2),    # Kuning (Roster ventilasi & tali air fasad modern)
    ]
    for nama, warna in daftar:
        if nama not in doc.layers:
            doc.layers.add(nama, color=warna)


def _poly(msp, pts, layer, tutup=True):
    return msp.add_lwpolyline(pts, close=tutup, dxfattribs={"layer": layer})


def _garis(msp, p1, p2, layer="A-ANNO-TEXT"):
    return msp.add_line(p1, p2, dxfattribs={"layer": layer})


def _arsir(msp, pts, pola, skala, layer, sudut=0):
    h = msp.add_hatch(color=256, dxfattribs={"layer": layer})
    if str(pola).upper() == "SOLID":
        h.set_solid_fill()
    else:
        h.set_pattern_fill(pola, scale=skala, angle=sudut)
    h.paths.add_polyline_path(pts, is_closed=True)


def _teks(msp, isi, pos, tinggi=TINGGI_TEKS, rata=TA.LEFT, layer="A-ANNO-TEXT"):
    msp.add_text(isi, height=tinggi, dxfattribs={"layer": layer}).set_placement(pos, align=rata)


def _penunjuk(msp, target, awal):
    """Garis penunjuk dari teks ke objek, dengan titik di ujung objek."""
    _garis(msp, awal, target)
    msp.add_circle(target, radius=30, dxfattribs={"layer": "A-ANNO-TEXT"})


def _elevasi(msp, x, y, label):
    """Tanda elevasi: segitiga + garis + teks."""
    _poly(msp, [(x, y), (x - 110, y + 170), (x + 110, y + 170)], "A-ANNO-LEVL")
    _garis(msp, (x - 150, y + 170), (x + 1100, y + 170), "A-ANNO-LEVL")
    _teks(msp, label, (x + 180, y + 215), layer="A-ANNO-LEVL")


def _dim_h(msp, x1, x2, y_titik, y_garis):
    msp.add_linear_dim(base=(x1, y_garis), p1=(x1, y_titik), p2=(x2, y_titik), angle=0,
                       dimstyle=DIM, override={"dimdec": 0}, dxfattribs={"layer": "A-ANNO-DIMS"}).render()


def _dim_v(msp, x_titik, z1, z2, x_garis):
    msp.add_linear_dim(base=(x_garis, z1), p1=(x_titik, z1), p2=(x_titik, z2), angle=90,
                       dimstyle=DIM, override={"dimdec": 0}, dxfattribs={"layer": "A-ANNO-DIMS"}).render()


def _judul(msp, isi, x_tengah, y, skala="1 : 100"):
    _teks(msp, isi, (x_tengah, y), tinggi=260, rata=TA.MIDDLE_CENTER)
    _teks(msp, f"Skala {skala}", (x_tengah, y - 330), tinggi=130, rata=TA.MIDDLE_CENTER)
    _garis(msp, (x_tengah - 1800, y - 150), (x_tengah + 1800, y - 150))


def _dasar(rumah):
    """Ukuran dasar yang dipakai semua gambar."""
    xs = [p[0] for d in rumah.dinding for p in (d.a, d.b)]
    ys = [p[1] for d in rumah.dinding for p in (d.a, d.b)]
    st = rumah.struktur
    pf = st.get("pondasi", {})
    sl = st.get("sloof", [150, 200])
    rg = st.get("ring_balok", [150, 150])
    return dict(
        minx=min(xs), maxx=max(xs), miny=min(ys), maxy=max(ys),
        t=float(rumah.dinding_default.get("tebal", 150)),
        H=float(rumah.lantai.get("tinggi_dinding", 3000)),
        Hp=float(rumah.lantai.get("tinggi_plafon", 2800)),
        lb=float(pf.get("lebar_bawah", 600)), la=float(pf.get("lebar_atas", 300)), tp=float(pf.get("tinggi", 700)),
        bs=float(sl[0]), hs=float(sl[1]), rw=float(rg[0]), rh=float(rg[1]),
        th=math.tan(math.radians(rumah.atap.get("kemiringan_derajat", 30))),
        deg=rumah.atap.get("kemiringan_derajat", 30),
        ov=float(rumah.atap.get("overstek", 600)),
        nok=rumah.atap.get("arah_nok", "x"),
        penutup=rumah.atap.get("penutup", "genteng"), rangka=rumah.atap.get("rangka", "baja ringan"),
        Z_TANAH=-400.0,
    )


def _z_atap(b, c, c_min, c_max):
    """Tinggi bidang atap pelana pada koordinat c (tegak lurus nok)."""
    half = (c_max - c_min) / 2
    return b["H"] + (half - abs(c - (c_min + c_max) / 2)) * b["th"]


def _interval_kurang(awal, akhir, lubang):
    """Potong [awal, akhir] dengan daftar lubang [(z0, z1)], kembalikan sisa segmen."""
    seg = [(awal, akhir)]
    for z0, z1 in sorted(lubang):
        baru = []
        for a, b in seg:
            if z1 <= a or z0 >= b:
                baru.append((a, b))
                continue
            if z0 > a:
                baru.append((a, z0))
            if z1 < b:
                baru.append((z1, b))
        seg = baru
    return seg


# ----------------------------------------------------------------- detail potongan & fasad
def gambar_ornamen_roster(msp, x0, y0, lebar, tinggi, ukuran_roster=200, jarak=25, layer="ORNAMEN_FASAD"):
    return
    """Menggambar grid dinding roster ventilasi arsitektural minimalis modern."""
    nx = max(1, int((lebar + jarak) // (ukuran_roster + jarak)))
    ny = max(1, int((tinggi + jarak) // (ukuran_roster + jarak)))
    for r in range(ny):
        for c in range(nx):
            rx = x0 + c * (ukuran_roster + jarak)
            ry = y0 + r * (ukuran_roster + jarak)
            # Bingkai luar roster
            _poly(msp, [(rx, ry), (rx + ukuran_roster, ry), (rx + ukuran_roster, ry + ukuran_roster), (rx, ry + ukuran_roster)], layer)
            # Lubang ventilasi tengah & silang
            ins = 40
            ibox = [(rx + ins, ry + ins), (rx + ukuran_roster - ins, ry + ins),
                    (rx + ukuran_roster - ins, ry + ukuran_roster - ins), (rx + ins, ry + ukuran_roster - ins)]
            _poly(msp, ibox, layer)
            _garis(msp, (rx + ins, ry + ins), (rx + ukuran_roster - ins, ry + ukuran_roster - ins), layer)
            _garis(msp, (rx + ins, ry + ukuran_roster - ins), (rx + ukuran_roster - ins, ry + ins), layer)


def gambar_tali_air(msp, x0, y0, lebar, tinggi, interval=250, layer="ORNAMEN_FASAD"):
    """Menggambar aksen garis alur tali air (groove lines) horizontal pada dinding fasad."""
    cur_y = y0 + interval
    while cur_y <= y0 + tinggi - 50:
        _garis(msp, (x0, cur_y), (x0 + lebar, cur_y), layer)
        _garis(msp, (x0, cur_y + 12), (x0 + lebar, cur_y + 12), layer)
        cur_y += interval


def gambar_kuda_kuda_potongan(msp, u_a, u_b, u_t, c_min, c_max, H, th, z_e, z_r, X, Z, sepanjang=False, zc=None, potong=None, T=130):
    """
    Menggambar detail rangka atap kuda-kuda baja ringan profesional (chords & web segitiga).
    """
    lyr = "ATAP_DETAIL"
    if not sepanjang:
        # 1. Batang Tarik Bawah (Bottom Chord) C75 ganda di atas ring balok
        _garis(msp, (X(c_min), Z(H)), (X(c_max), Z(H)), lyr)
        _garis(msp, (X(c_min), Z(H + 75)), (X(c_max), Z(H + 75)), lyr)

        # 2. Batang Miring Atas (Top Chords) Kiri & Kanan
        _garis(msp, (X(u_a), Z(z_e)), (X(u_t), Z(z_r)), lyr)
        _garis(msp, (X(u_b), Z(z_e)), (X(u_t), Z(z_r)), lyr)
        _garis(msp, (X(u_a), Z(z_e - 75)), (X(u_t), Z(z_r - 75)), lyr)
        _garis(msp, (X(u_b), Z(z_e - 75)), (X(u_t), Z(z_r - 75)), lyr)

        # 3. Tiang Raja Tengah (King Post)
        _garis(msp, (X(u_t - 25), Z(H + 75)), (X(u_t - 25), Z(z_r - 20)), lyr)
        _garis(msp, (X(u_t + 25), Z(H + 75)), (X(u_t + 25), Z(z_r - 20)), lyr)

        # 4. Batang Web Segitiga (Truss Diagonals & Struts) Bentang Kiri
        bentang_kiri = max(100.0, u_t - c_min)
        n_seg = max(2, min(5, int(round(bentang_kiri / 800))))
        du = bentang_kiri / n_seg
        for i in range(1, n_seg):
            u_i = c_min + i * du
            z_top_i = H + (u_i - c_min) * th
            # Batang vertikal
            _garis(msp, (X(u_i), Z(H + 75)), (X(u_i), Z(z_top_i - 65)), lyr)
            # Batang diagonal zig-zag
            u_prev = c_min + (i - 1) * du
            z_top_prev = H + (u_prev - c_min) * th
            if i % 2 == 1:
                _garis(msp, (X(u_prev), Z(H + 75)), (X(u_i), Z(z_top_i - 65)), lyr)
            else:
                _garis(msp, (X(u_i), Z(H + 75)), (X(u_prev), Z(z_top_prev - 65)), lyr)

        # 5. Batang Web Segitiga Bentang Kanan (Simetris)
        bentang_kanan = max(100.0, c_max - u_t)
        n_seg_r = max(2, min(5, int(round(bentang_kanan / 800))))
        du_r = bentang_kanan / n_seg_r
        for i in range(1, n_seg_r):
            u_i = c_max - i * du_r
            z_top_i = H + (c_max - u_i) * th
            # Batang vertikal
            _garis(msp, (X(u_i), Z(H + 75)), (X(u_i), Z(z_top_i - 65)), lyr)
            # Batang diagonal zig-zag
            u_prev = c_max - (i - 1) * du_r
            z_top_prev = H + (c_max - u_prev) * th
            if i % 2 == 1:
                _garis(msp, (X(u_prev), Z(H + 75)), (X(u_i), Z(z_top_i - 65)), lyr)
            else:
                _garis(msp, (X(u_i), Z(H + 75)), (X(u_prev), Z(z_top_prev - 65)), lyr)

        # 6. Reng Baja Ringan (Garis-garis penumpu genteng)
        for side, u_start, u_end in [(-1, u_t, u_a), (1, u_t, u_b)]:
            cur_u = u_t
            step = 320 * side
            while (cur_u > u_a if side < 0 else cur_u < u_b):
                zu = z_r - abs(cur_u - u_t) * th
                _garis(msp, (X(cur_u - 20), Z(zu + 5)), (X(cur_u + 20), Z(zu + 5)), lyr)
                cur_u += step
    else:
        # Potongan memanjang: Balok gording dan ikatan angin (bracing)
        if zc is not None and potong and len(potong) > 1:
            # Balok nok & gording memanjang
            _garis(msp, (X(u_a), Z(zc - 80)), (X(u_b), Z(zc - 80)), lyr)
            _garis(msp, (X(u_a), Z(H + 60)), (X(u_b), Z(H + 60)), lyr)
            # Rangka kuda-kuda melintang di atas tiap pertemuan dinding
            for w in potong:
                _poly(msp, [(X(w["u"] - 40), Z(H)), (X(w["u"] + 40), Z(H)),
                            (X(w["u"] + 40), Z(zc)), (X(w["u"] - 40), Z(zc))], lyr)
            # Ikatan angin (X-bracing) diagonal
            for w1, w2 in zip(potong, potong[1:]):
                _garis(msp, (X(w1["u"] + 40), Z(H + 60)), (X(w2["u"] - 40), Z(zc - 80)), lyr)
                _garis(msp, (X(w1["u"] + 40), Z(zc - 80)), (X(w2["u"] - 40), Z(H + 60)), lyr)


def gambar_listplank(msp, u_a, u_b, z_e, X, Z):
    """Menggambar papan listplank GRC t=25 mm, h=200 mm pada ujung overstek atap."""
    lyr = "ATAP_DETAIL"
    # Listplank kiri
    p_kiri = [(X(u_a - 25), Z(z_e - 60)), (X(u_a), Z(z_e - 60)),
              (X(u_a), Z(z_e + 140)), (X(u_a - 25), Z(z_e + 140))]
    _poly(msp, p_kiri, lyr)
    # Listplank kanan
    p_kanan = [(X(u_b), Z(z_e - 60)), (X(u_b + 25), Z(z_e - 60)),
               (X(u_b + 25), Z(z_e + 140)), (X(u_b), Z(z_e + 140))]
    _poly(msp, p_kanan, lyr)


def gambar_detail_plafon(msp, potong, Hp, H, X, Z):
    """Menggambar detail plafon gypsum 9 mm, list cornice, rangka hollow 40x40, dan rod hanger."""
    lyr = "ATAP_DETAIL"
    for w1, w2 in zip(potong, potong[1:]):
        x1, x2 = w1["u"] + w1["t"] / 2, w2["u"] - w2["t"] / 2
        if x2 - x1 < 100:
            continue
        # Papan Gypsum 9 mm
        _garis(msp, (X(x1), Z(Hp)), (X(x2), Z(Hp)), lyr)
        _garis(msp, (X(x1), Z(Hp + 9)), (X(x2), Z(Hp + 9)), lyr)

        # List profil sudut gypsum (cornice 50x50 mm)
        _poly(msp, [(X(x1), Z(Hp)), (X(x1 + 50), Z(Hp)), (X(x1), Z(Hp - 50))], lyr)
        _poly(msp, [(X(x2), Z(Hp)), (X(x2 - 50), Z(Hp)), (X(x2), Z(Hp - 50))], lyr)

        # Rangka hollow metal furing 40x40 mm tiap 600 mm dan kawat penggantung ke ring balok
        xh = x1 + 400
        while xh < x2 - 200:
            hk = [(X(xh - 20), Z(Hp + 9)), (X(xh + 20), Z(Hp + 9)),
                  (X(xh + 20), Z(Hp + 49)), (X(xh - 20), Z(Hp + 49))]
            _poly(msp, hk, lyr)
            # Rod hanger vertikal naik ke struktur atas
            _garis(msp, (X(xh), Z(Hp + 49)), (X(xh), Z(H)), lyr)
            xh += 600


def gambar_detail_bukaan_potongan(msp, u, t, q, X, Z):
    """
    Mengisi area dinding bukaan terpotong dengan kusen penampang, daun pintu, dan kaca berprofil.
    """
    lyr = "KUSEN_POTONGAN"
    z0, z1 = q.ambang, q.ambang + q.tinggi
    kw = 50.0  # tebal kusen standar

    if q.jenis == "pintu":
        # 1. Kusen Atas (Head Jamb 50 mm x tebal dinding)
        k_atas = [(X(u - t / 2), Z(z1 - kw)), (X(u + t / 2), Z(z1 - kw)),
                  (X(u + t / 2), Z(z1)), (X(u - t / 2), Z(z1))]
        _poly(msp, k_atas, lyr)
        _arsir(msp, k_atas, "ANSI31", 10, lyr)

        # 2. Penampang Daun Pintu (Tebal 35 mm merapat ke sisi dalam kusen)
        d_pts = [(X(u - t / 2 + 15), Z(z0)), (X(u - t / 2 + 50), Z(z0)),
                 (X(u - t / 2 + 50), Z(z1 - kw)), (X(u - t / 2 + 15), Z(z1 - kw))]
        _poly(msp, d_pts, lyr)
        _arsir(msp, d_pts, "SOLID", 1, lyr)

        # 3. Handel pintu di elevasi +1000 mm
        _garis(msp, (X(u - t / 2 + 50), Z(z0 + 1000)), (X(u - t / 2 + 85), Z(z0 + 1000)), lyr)
        _garis(msp, (X(u - t / 2 + 85), Z(z0 + 960)), (X(u - t / 2 + 85), Z(z0 + 1030)), lyr)

        # 4. Garis transisi lantai
        _garis(msp, (X(u - t / 2), Z(z0)), (X(u + t / 2), Z(z0)), lyr)

    elif q.jenis == "jendela":
        # 1. Kusen Atas (Head Jamb)
        k_atas = [(X(u - t / 2), Z(z1 - kw)), (X(u + t / 2), Z(z1 - kw)),
                  (X(u + t / 2), Z(z1)), (X(u - t / 2), Z(z1))]
        _poly(msp, k_atas, lyr)
        _arsir(msp, k_atas, "ANSI31", 10, lyr)

        # 2. Kusen Bawah (Sill Jamb)
        k_bwh = [(X(u - t / 2), Z(z0)), (X(u + t / 2), Z(z0)),
                 (X(u + t / 2), Z(z0 + kw)), (X(u - t / 2), Z(z0 + kw))]
        _poly(msp, k_bwh, lyr)
        _arsir(msp, k_bwh, "ANSI31", 10, lyr)

        # 3. Rangka Profil Daun Jendela (Casement 35x35 mm atas & bawah)
        r_atas = [(X(u - 17.5), Z(z1 - kw - 35)), (X(u + 17.5), Z(z1 - kw - 35)),
                  (X(u + 17.5), Z(z1 - kw)), (X(u - 17.5), Z(z1 - kw))]
        r_bwh = [(X(u - 17.5), Z(z0 + kw)), (X(u + 17.5), Z(z0 + kw)),
                 (X(u + 17.5), Z(z0 + kw + 35)), (X(u - 17.5), Z(z0 + kw + 35))]
        _poly(msp, r_atas, lyr)
        _poly(msp, r_bwh, lyr)

        # 4. Kaca Jendela (Garis ganda t=5 mm di tengah)
        z_kaca0 = z0 + kw + 35
        z_kaca1 = z1 - kw - 35
        _garis(msp, (X(u - 3), Z(z_kaca0)), (X(u - 3), Z(z_kaca1)), lyr)
        _garis(msp, (X(u + 3), Z(z_kaca0)), (X(u + 3), Z(z_kaca1)), lyr)

        # 5. Kilau Kaca (Garis diagonal aksen pantulan)
        zg = (z0 + z1) / 2
        _garis(msp, (X(u - 35), Z(zg - 80)), (X(u + 35), Z(zg - 20)), lyr)
        _garis(msp, (X(u - 35), Z(zg + 20)), (X(u + 35), Z(zg + 80)), lyr)


def gambar_eksterior_fasad(msp, Wb, H, Zt, daftar, X, Z):
    """
    Menambahkan elemen eksterior fasad depan: teras bertingkat, kanopi dak beton,
    tiang teras, carport rabat beton, pagar tembok dan pintu gerbang besi hollow.
    """
    lyr = "EKSTERIOR"
    orn = "ORNAMEN_FASAD"

    # Cari posisi pintu utama
    pintu_list = [q for _, _, q in daftar if q.jenis == "pintu"]
    if pintu_list:
        u_pintu = next(u0 for u0, _, q in daftar if q.jenis == "pintu")
    else:
        u_pintu = Wb * 0.55

    # 1. Teras Depan Bertingkat
    xt1 = max(100.0, u_pintu - 600.0)
    xt2 = min(Wb - 100.0, u_pintu + 1600.0)
    # Trap 1: FFL -0.10
    _poly(msp, [(X(xt1 - 150), Z(Zt)), (X(xt2 + 150), Z(Zt)), (X(xt2 + 150), Z(-100)), (X(xt1 - 150), Z(-100))], lyr)
    # Trap 2: FFL -0.05
    _poly(msp, [(X(xt1), Z(-100)), (X(xt2), Z(-100)), (X(xt2), Z(-50)), (X(xt1), Z(-50))], lyr)
    # Lantai Teras Utama: FFL ±0.00
    _poly(msp, [(X(xt1 + 80), Z(-50)), (X(xt2 - 80), Z(-50)), (X(xt2 - 80), Z(0)), (X(xt1 + 80), Z(0))], lyr)

    # 2. Tiang Kolom Teras Minimalis & Dak Kanopi Beton
    w_tiang = 250.0
    x_tiang1 = xt2 - w_tiang
    x_tiang2 = xt2
    _poly(msp, [(X(x_tiang1), Z(0)), (X(x_tiang2), Z(0)), (X(x_tiang2), Z(2800)), (X(x_tiang1), Z(2800))], lyr)
    # Tali air pada tiang teras
    gambar_tali_air(msp, X(x_tiang1), Z(400), w_tiang, 2300, interval=250, layer=orn)

    # Dak Kanopi Beton Teras t=100 mm
    kanopi_pts = [(X(xt1 - 100), Z(2800)), (X(xt2 + 150), Z(2800)),
                  (X(xt2 + 150), Z(2900)), (X(xt1 - 100), Z(2900))]
    _poly(msp, kanopi_pts, lyr)
    _arsir(msp, kanopi_pts, "AR-CONC", 1.5, lyr)

    # Lampu tempel dinding minimalis teras
    _poly(msp, [(X(u_pintu - 180), Z(1700)), (X(u_pintu - 80), Z(1700)),
                (X(u_pintu - 80), Z(1900)), (X(u_pintu - 180), Z(1900))], lyr)

    # 3. Ornamen Fasad: Sekat Secondary Skin Dinding Roster
    xr_pos = xt1 - 700.0
    if xr_pos > 200.0:
        gambar_ornamen_roster(msp, X(xr_pos), Z(250), 550, 2400, ukuran_roster=170, jarak=20, layer=orn)

    # Tali air aksen pada bidang dinding samping
    if u_pintu > 1800.0:
        gambar_tali_air(msp, X(80), Z(200), min(1200.0, u_pintu - 300.0), H - 400, interval=280, layer=orn)

    # 4. Area Carport Samping
    # Carport ditempatkan di sisi yang berlawanan dengan teras
    xc1 = -1800.0 if xt1 < Wb / 2 else 0.0
    xc2 = 0.0 if xt1 < Wb / 2 else max(2400.0, xt1 - 200.0)
    # Garis lantai carport elevasi -200 mm
    _garis(msp, (X(xc1), Z(Zt + 200)), (X(xc2), Z(Zt + 200)), lyr)
    # Rabat beton tali air / pola paving carport modular tiap 600 mm
    cur_cp = xc1 + 600.0
    while cur_cp < xc2:
        _garis(msp, (X(cur_cp), Z(Zt)), (X(cur_cp), Z(Zt + 200)), lyr)
        cur_cp += 600.0

    # Tiang & Balok Kanopi Carport Minimalis
    _poly(msp, [(X(xc1), Z(Zt + 200)), (X(xc1 + 100), Z(Zt + 200)),
                (X(xc1 + 100), Z(3000)), (X(xc1), Z(3000))], lyr)
    _poly(msp, [(X(xc1), Z(2920)), (X(xc2), Z(2920)),
                (X(xc2), Z(3000)), (X(xc1), Z(3000))], lyr)

    # 5. Pagar Tembok Depan & Pintu Gerbang Minimalis
    # Dinding pagar samping kiri
    _poly(msp, [(X(xc1 - 300), Z(Zt)), (X(xc1), Z(Zt)), (X(xc1), Z(Zt + 1200)), (X(xc1 - 300), Z(Zt + 1200))], lyr)
    _poly(msp, [(X(xc1 - 350), Z(Zt + 1200)), (X(xc1 + 50), Z(Zt + 1200)),
                (X(xc1 + 50), Z(Zt + 1280)), (X(xc1 - 350), Z(Zt + 1280))], lyr)

    # Pintu Gerbang Besi Hollow Geser (Sliding Gate) di depan carport
    w_gate = xc2 - xc1
    if w_gate > 800:
        # Bingkai gerbang
        _poly(msp, [(X(xc1), Z(Zt + 60)), (X(xc2), Z(Zt + 60)),
                    (X(xc2), Z(Zt + 1350)), (X(xc1), Z(Zt + 1350))], lyr)
        # Kisi-kisi hollow vertikal tiap 120 mm
        xg = xc1 + 120
        while xg < xc2 - 60:
            _garis(msp, (X(xg), Z(Zt + 60)), (X(xg), Z(Zt + 1350)), lyr)
            xg += 120
        # Roda gerbang bawah
        msp.add_circle((X(xc1 + 200), Z(Zt + 30)), radius=25, dxfattribs={"layer": lyr})
        msp.add_circle((X(xc2 - 200), Z(Zt + 30)), radius=25, dxfattribs={"layer": lyr})
        _garis(msp, (X(xc1 - 50), Z(Zt + 10)), (X(xc2 + 100), Z(Zt + 10)), lyr)

    # Dinding pagar depan rendah di sisi teras
    x_pagar1 = xc2
    x_pagar2 = Wb + 400.0
    _poly(msp, [(X(x_pagar1), Z(Zt)), (X(x_pagar2), Z(Zt)),
                (X(x_pagar2), Z(Zt + 950)), (X(x_pagar1), Z(Zt + 950))], lyr)
    _poly(msp, [(X(x_pagar1 - 20), Z(Zt + 950)), (X(x_pagar2 + 50), Z(Zt + 950)),
                (X(x_pagar2 + 50), Z(Zt + 1010)), (X(x_pagar1 - 20), Z(Zt + 1010))], lyr)
    # Tali air pada tembok pagar
    gambar_tali_air(msp, X(x_pagar1 + 50), Z(Zt + 150), x_pagar2 - x_pagar1 - 100, 700, interval=200, layer=orn)


# ----------------------------------------------------------------- potongan
def gambar_potongan(rumah, msp, sec, ox, oy):
    """Gambar satu potongan. Titik u=0 diletakkan di x=ox, tinggi z=0 di y=oy. Kembalikan bbox."""
    b = _dasar(rumah)
    arah, pos, nama = sec["arah"], float(sec["posisi"]), sec["nama"]
    H, Hp, rh, hs, tp, lb, la, bs = b["H"], b["Hp"], b["rh"], b["hs"], b["tp"], b["lb"], b["la"], b["bs"]
    X, Z = (lambda u: ox + u), (lambda z: oy + z)

    # ---- dinding yang terpotong bidang potong
    potong = []
    for d in rumah.dinding:
        (ax, ay), (bx, by) = d.a, d.b
        if arah == "x" and abs(ax - bx) < 1e-6 and min(ay, by) - 1e-6 <= pos <= max(ay, by) + 1e-6:
            u, s = ax, abs(pos - ay)
        elif arah == "y" and abs(ay - by) < 1e-6 and min(ax, bx) - 1e-6 <= pos <= max(ax, bx) + 1e-6:
            u, s = ay, abs(pos - ax)
        else:
            continue
        bk = [q for q in rumah.bukaan if q.dinding == d.id and q.offset - 1e-6 <= s <= q.akhir + 1e-6]
        potong.append(dict(u=u, t=float(d.tebal or b["t"]), bukaan=bk))
    potong.sort(key=lambda w: w["u"])
    if not potong:
        return None
    u_min, u_max = potong[0]["u"], potong[-1]["u"]

    # ---- geometri atap (dihitung dulu agar dinding pelana bisa menyambung)
    ov, th, T = b["ov"], b["th"], 130
    if b["nok"] == "x":
        c_min, c_max, sepanjang = b["miny"], b["maxy"], (arah == "x")
        u_a, u_b = b["minx"] - ov, b["maxx"] + ov
    else:
        c_min, c_max, sepanjang = b["minx"], b["maxx"], (arah == "y")
        u_a, u_b = b["miny"] - ov, b["maxy"] + ov
    zc = _z_atap(b, pos, c_min, c_max) if sepanjang else None
    ujung = (b["minx"], b["maxx"]) if arah == "x" else (b["miny"], b["maxy"])

    # ---- elemen tiap dinding terpotong
    contoh = {}
    for w in potong:
        u, t = w["u"], w["t"]
        lubang = [(q.ambang, q.ambang + q.tinggi) for q in w["bukaan"]]
        for z0, z1 in _interval_kurang(0, H - rh, lubang):
            pts = [(X(u - t / 2), Z(z0)), (X(u + t / 2), Z(z0)), (X(u + t / 2), Z(z1)), (X(u - t / 2), Z(z1))]
            _poly(msp, pts, "A-SECT-WALL")
            _arsir(msp, pts, "ANSI31", 25, "A-WALL-PATT")

        # Detail bukaan terpotong (kusen, daun pintu, kaca berprofil)
        for q in w["bukaan"]:
            gambar_detail_bukaan_potongan(msp, u, t, q, X, Z)
            z0, z1 = q.ambang, q.ambang + q.tinggi
            if q.jenis == "jendela":
                contoh.setdefault("jendela", (X(u), Z((z0 + z1) / 2), q.bahan))
            elif q.jenis == "pintu":
                contoh.setdefault("pintu", (X(u), Z((z0 + z1) / 2), q.bahan))

        if sepanjang and any(abs(u - e) < 1e-6 for e in ujung) and zc > H:   # dinding pelana
            gp = [(X(u - t / 2), Z(H)), (X(u + t / 2), Z(H)), (X(u + t / 2), Z(zc)), (X(u - t / 2), Z(zc))]
            _poly(msp, gp, "A-SECT-WALL")
            _arsir(msp, gp, "ANSI31", 25, "A-WALL-PATT")

        # ring balok, sloof, pondasi, aanstamping, pasir
        rb = [(X(u - t / 2), Z(H - rh)), (X(u + t / 2), Z(H - rh)), (X(u + t / 2), Z(H)), (X(u - t / 2), Z(H))]
        _poly(msp, rb, "S-BETON")
        _arsir(msp, rb, "AR-CONC", 1.5, "S-BETON")
        sf = [(X(u - bs / 2), Z(-hs)), (X(u + bs / 2), Z(-hs)), (X(u + bs / 2), Z(0)), (X(u - bs / 2), Z(0))]
        _poly(msp, sf, "S-BETON")
        _arsir(msp, sf, "AR-CONC", 1.5, "S-BETON")
        pd = [(X(u - la / 2), Z(-hs)), (X(u + la / 2), Z(-hs)), (X(u + lb / 2), Z(-hs - tp)), (X(u - lb / 2), Z(-hs - tp))]
        _poly(msp, pd, "S-PONDASI")
        _arsir(msp, pd, "ANSI37", 30, "S-PONDASI")
        an = [(X(u - lb / 2), Z(-hs - tp - 150)), (X(u + lb / 2), Z(-hs - tp - 150)), (X(u + lb / 2), Z(-hs - tp)), (X(u - lb / 2), Z(-hs - tp))]
        _poly(msp, an, "S-PONDASI")
        _arsir(msp, an, "GRAVEL", 12, "S-PONDASI")
        ps = [(X(u - lb / 2), Z(-hs - tp - 200)), (X(u + lb / 2), Z(-hs - tp - 200)), (X(u + lb / 2), Z(-hs - tp - 150)), (X(u - lb / 2), Z(-hs - tp - 150))]
        _poly(msp, ps, "S-PONDASI")
    z_dasar = -hs - tp - 200

    # ---- lantai dan plafon detail
    for w1, w2 in zip(potong, potong[1:]):
        x1, x2 = w1["u"] + w1["t"] / 2, w2["u"] - w2["t"] / 2
        if x2 - x1 < 100:
            continue
        lt = [(X(x1), Z(-150)), (X(x2), Z(-150)), (X(x2), Z(0)), (X(x1), Z(0))]
        _poly(msp, lt, "A-SECT-WALL")
        _arsir(msp, lt, "AR-SAND", 4, "A-SECT-WALL")

    # Gambar detail plafon gypsum, cornice, rangka hollow, dan kawat penggantung
    gambar_detail_plafon(msp, potong, Hp, H, X, Z)

    # tanah
    t_kiri, t_kanan = u_min - potong[0]["t"] / 2 - 1500, u_max + potong[-1]["t"] / 2 + 1500
    _garis(msp, (X(t_kiri), Z(b["Z_TANAH"])), (X(u_min - lb / 2), Z(b["Z_TANAH"])), "A-GROUND")
    _garis(msp, (X(u_max + lb / 2), Z(b["Z_TANAH"])), (X(t_kanan), Z(b["Z_TANAH"])), "A-GROUND")
    for zz in (b["Z_TANAH"] - 150, b["Z_TANAH"] - 300):
        _garis(msp, (X(t_kiri + 400), Z(zz)), (X(u_min - lb / 2 - 200), Z(zz)), "A-GROUND")
        _garis(msp, (X(u_max + lb / 2 + 200), Z(zz)), (X(t_kanan - 400), Z(zz)), "A-GROUND")

    # ---- atap: penutup, rangka kuda-kuda truss baja ringan & listplank
    if sepanjang:   # nok sejajar sumbu u: atap terpotong menjadi pita datar
        pita = [(X(u_a), Z(zc)), (X(u_b), Z(zc)), (X(u_b), Z(zc + T)), (X(u_a), Z(zc + T))]
        z_puncak = zc + T
        z_e = zc
        u_t = (u_a + u_b) / 2
    else:           # nok tegak lurus u: profil pelana
        u_t = (c_min + c_max) / 2
        z_e = H - ov * th
        z_r = H + ((c_max - c_min) / 2) * th
        u_a, u_b = c_min - ov, c_max + ov
        pita = [(X(u_a), Z(z_e)), (X(u_t), Z(z_r)), (X(u_b), Z(z_e)), (X(u_b), Z(z_e + T)), (X(u_t), Z(z_r + T)), (X(u_a), Z(z_e + T))]
        z_puncak = z_r + T
    _poly(msp, pita, "A-ROOF")
    _arsir(msp, pita, "ANSI31", 20, "A-ROOF")

    # Gambar Rangka Kuda-Kuda Baja Ringan & Listplank
    gambar_kuda_kuda_potongan(msp, u_a, u_b, u_t, c_min, c_max, H, th, z_e, z_r if not sepanjang else zc, X, Z, sepanjang=sepanjang, zc=zc, potong=potong, T=T)
    gambar_listplank(msp, u_a, u_b, z_e, X, Z)

    # ---- dimensi horizontal (as ke as) dan tinggi
    xs_as = [w["u"] for w in potong]
    for a1, a2 in zip(xs_as, xs_as[1:]):
        _dim_h(msp, X(a1), X(a2), Z(z_dasar), Z(z_dasar - 450))
    if len(xs_as) > 2:
        _dim_h(msp, X(xs_as[0]), X(xs_as[-1]), Z(z_dasar), Z(z_dasar - 950))
    x_r = X(u_max) + potong[-1]["t"] / 2 + 900
    for z, lab in [(b["Z_TANAH"], "-0.40 (tanah asli)"), (0, "±0.00 (lantai)"), (Hp, f"+{Hp/1000:.2f} (plafon)"),
                   (H, f"+{H/1000:.2f} (ring balok)"), (z_puncak, f"+{z_puncak/1000:.2f} (atap)"), (z_dasar, f"{z_dasar/1000:.2f} (dasar pondasi)")]:
        _elevasi(msp, x_r, Z(z), lab)
    x_d = x_r + 2300
    _dim_v(msp, x_r, Z(z_dasar), Z(0), x_d)
    _dim_v(msp, x_r, Z(0), Z(Hp), x_d)
    _dim_v(msp, x_r, Z(Hp), Z(H), x_d)
    _dim_v(msp, x_r, Z(0), Z(z_puncak), x_d + 800)

    # ---- keterangan bahan (kolom kiri, rata kanan)
    w1 = potong[0]
    x_ref = X(u_min) - w1["t"] / 2 - 1800
    lub1 = [(q.ambang, q.ambang + q.tinggi) for q in w1["bukaan"]]
    z_bata = next((a + (c - a) / 2 for a, c in _interval_kurang(0, H - rh, lub1) if c - a > 400 and a > 0), 1400)
    ket = [(H - rh / 2, "Ring balok 15/15 beton K-300"), (z_bata, "Pasangan bata merah 1/2 bata, plester + aci + cat"),
           (-hs / 2, f"Sloof {b['bs']:.0f}/{hs:.0f} beton K-300"), (-hs - tp / 2, "Pondasi batu kali 1:4"),
           (-hs - tp - 75, "Aanstamping batu belah t=15 cm"), (-hs - tp - 175, "Pasir urug t=5 cm")]
    if "jendela" in contoh:
        ket.append((contoh["jendela"][1] - oy, "Jendela " + (contoh["jendela"][2] or "aluminium + kaca")))
    if "pintu" in contoh:
        ket.append((contoh["pintu"][1] - oy, "Pintu " + (contoh["pintu"][2] or "kayu solid panel")))
    ket.sort(key=lambda k: -k[0])
    zlast = None
    for z, isi in ket:
        zt = z if zlast is None or zlast - z >= 190 else zlast - 190
        _teks(msp, isi, (x_ref, Z(zt) - 45), rata=TA.RIGHT)
        _penunjuk(msp, (X(w1["u"]), Z(z)), (x_ref + 80, Z(zt)))
        zlast = zt
    # lantai dan plafon: teks di dalam ruang
    if len(potong) > 1:
        ruang = max(zip(potong, potong[1:]), key=lambda p: p[1]["u"] - p[0]["u"])
        xc = (ruang[0]["u"] + ruang[1]["u"]) / 2
        _teks(msp, "Lantai keramik 40x40 + spesi", (X(xc), Z(500)), rata=TA.MIDDLE_CENTER)
        _penunjuk(msp, (X(xc), Z(-60)), (X(xc), Z(430)))
        _teks(msp, "Plafon gypsum 9 mm + rangka hollow", (X(xc), Z(Hp - 450)), rata=TA.MIDDLE_CENTER)
        _penunjuk(msp, (X(xc), Z(Hp)), (X(xc), Z(Hp - 380)))
    xa = X((u_min + u_max) / 2)
    _teks(msp, f"Rangka atap {b['rangka']} (kuda-kuda truss C75) + {b['penutup']}", (xa, Z(z_puncak + 650)), rata=TA.MIDDLE_CENTER)
    _penunjuk(msp, (xa, Z(z_puncak - 40)), (xa, Z(z_puncak + 580)))

    _judul(msp, f"POTONGAN {nama}", X((u_min + u_max) / 2), Z(z_dasar - 1700))
    return (x_ref - 5200, Z(z_dasar - 2400), x_d + 1800, Z(z_puncak + 1000))


# ----------------------------------------------------------------- tampak
def gambar_tampak(rumah, msp, sisi, ox, oy):
    b = _dasar(rumah)
    H, t, ov, th = b["H"], b["t"], b["ov"], b["th"]
    minx, maxx, miny, maxy = b["minx"], b["maxx"], b["miny"], b["maxy"]
    if sisi == "depan":
        sama = lambda d: abs(d.a[1] - miny) < 1e-6 and abs(d.b[1] - miny) < 1e-6
        u = lambda p: p[0] - minx
        Wb = maxx - minx
    elif sisi == "belakang":
        sama = lambda d: abs(d.a[1] - maxy) < 1e-6 and abs(d.b[1] - maxy) < 1e-6
        u = lambda p: maxx - p[0]
        Wb = maxx - minx
    elif sisi == "kanan":
        sama = lambda d: abs(d.a[0] - maxx) < 1e-6 and abs(d.b[0] - maxx) < 1e-6
        u = lambda p: p[1] - miny
        Wb = maxy - miny
    else:
        sama = lambda d: abs(d.a[0] - minx) < 1e-6 and abs(d.b[0] - minx) < 1e-6
        u = lambda p: maxy - p[1]
        Wb = maxy - miny
    X, Z = (lambda v: ox + v), (lambda z: oy + z)
    Zt = b["Z_TANAH"]

    # badan dinding dan plint (pada sisi yang atapnya menutupi, dinding berhenti di bawah lisplank)
    sejajar = (b["nok"] == "x") == (sisi in ("depan", "belakang"))
    z_e = H - ov * th
    z_top = min(H, z_e - 160) if sejajar else H
    _poly(msp, [(X(-t / 2), Z(0)), (X(Wb + t / 2), Z(0)), (X(Wb + t / 2), Z(z_top)), (X(-t / 2), Z(z_top))], "A-ELEV")
    pl = [(X(-t / 2 - 40), Z(Zt)), (X(Wb + t / 2 + 40), Z(Zt)), (X(Wb + t / 2 + 40), Z(0)), (X(-t / 2 - 40), Z(0))]
    _poly(msp, pl, "A-ELEV")
    _arsir(msp, pl, "ANSI37", 30, "S-PONDASI")
    _garis(msp, (X(-t / 2 - 2200), Z(Zt)), (X(Wb + t / 2 + 2200), Z(Zt)), "A-GROUND")

    # bukaan pada sisi ini
    daftar = []
    for d in rumah.dinding:
        if not sama(d):
            continue
        L = math.hypot(d.b[0] - d.a[0], d.b[1] - d.a[1])
        dx, dy = (d.b[0] - d.a[0]) / L, (d.b[1] - d.a[1]) / L
        for q in rumah.bukaan:
            if q.dinding != d.id or q.jenis == "bukaan":
                continue
            p1 = (d.a[0] + dx * q.offset, d.a[1] + dy * q.offset)
            p2 = (d.a[0] + dx * q.akhir, d.a[1] + dy * q.akhir)
            u0, u1 = sorted([u(p1), u(p2)])
            daftar.append((u0, u1, q))
    contoh = {}
    for u0, u1, q in daftar:
        z0, z1 = q.ambang, q.ambang + q.tinggi
        if q.jenis == "pintu":
            lyr = "A-DOOR"
            _poly(msp, [(X(u0), Z(z0)), (X(u1), Z(z0)), (X(u1), Z(z1)), (X(u0), Z(z1))], lyr)
            _poly(msp, [(X(u0 + 60), Z(z0)), (X(u1 - 60), Z(z0)), (X(u1 - 60), Z(z1 - 60)), (X(u0 + 60), Z(z1 - 60))], lyr)
            h = z1 - z0
            for a, c in [(z0 + 250, z0 + 0.45 * h), (z0 + 0.55 * h, z1 - 300)]:
                _poly(msp, [(X(u0 + 200), Z(a)), (X(u1 - 200), Z(a)), (X(u1 - 200), Z(c)), (X(u0 + 200), Z(c))], lyr)
            msp.add_circle((X(u1 - 140), Z(z0 + 0.5 * h)), radius=25, dxfattribs={"layer": lyr})
            contoh.setdefault("pintu", (u0, u1, z0, z1, q.bahan))
        else:
            lyr = "A-GLAZ"
            _poly(msp, [(X(u0), Z(z0)), (X(u1), Z(z0)), (X(u1), Z(z1)), (X(u0), Z(z1))], lyr)
            _poly(msp, [(X(u0 + 50), Z(z0 + 50)), (X(u1 - 50), Z(z0 + 50)), (X(u1 - 50), Z(z1 - 50)), (X(u0 + 50), Z(z1 - 50))], lyr)
            if u1 - u0 > 1000:
                _garis(msp, (X((u0 + u1) / 2), Z(z0 + 50)), (X((u0 + u1) / 2), Z(z1 - 50)), lyr)
            _poly(msp, [(X(u0 - 40), Z(z0 - 40)), (X(u1 + 40), Z(z0 - 40)), (X(u1 + 40), Z(z0)), (X(u0 - 40), Z(z0))], lyr)
            contoh.setdefault("jendela", (u0, u1, z0, z1, q.bahan))

    # atap
    if sejajar:
        c_span = (maxy - miny) if b["nok"] == "x" else (maxx - minx)
        z_r = H + (c_span / 2) * th
        rect = [(X(-ov - t / 2), Z(z_e)), (X(Wb + ov + t / 2), Z(z_e)), (X(Wb + ov + t / 2), Z(z_r)), (X(-ov - t / 2), Z(z_r))]
        _poly(msp, rect, "A-ROOF")
        _arsir(msp, rect, "ANSI31", 30, "A-ROOF")
        # Listplank horizontal depan/belakang
        _poly(msp, [(X(-ov - t / 2), Z(z_e - 160)), (X(Wb + ov + t / 2), Z(z_e - 160)), (X(Wb + ov + t / 2), Z(z_e)), (X(-ov - t / 2), Z(z_e))], "A-ROOF")
        _garis(msp, (X(-ov - t / 2), Z(z_r - 60)), (X(Wb + ov + t / 2), Z(z_r - 60)), "A-ROOF")
        z_puncak, z_tengah = z_r, (z_e + z_r) / 2
    else:
        z_r = H + (Wb / 2) * th
        band = [(X(-ov), Z(z_e)), (X(Wb / 2), Z(z_r)), (X(Wb + ov), Z(z_e)), (X(Wb + ov), Z(z_e - 150)), (X(Wb / 2), Z(z_r - 150)), (X(-ov), Z(z_e - 150))]
        _poly(msp, band, "A-ROOF")
        _arsir(msp, band, "ANSI31", 30, "A-ROOF")
        _poly(msp, [(X(-t / 2), Z(H)), (X(Wb / 2), Z(z_r - 150)), (X(Wb + t / 2), Z(H))], "A-ELEV")
        z_puncak, z_tengah = z_r, (z_e + z_r) / 2

    # Detail Khusus Fasad Depan: Teras, Carport, Pagar & Gerbang, Ornamen Roster
    if sisi == "depan":
        gambar_eksterior_fasad(msp, Wb, H, Zt, daftar, X, Z)
    elif sisi in ("kanan", "kiri"):
        # Berikan aksen alur tali air minimalis pada bidang dinding samping
        gambar_tali_air(msp, X(150), Z(400), min(1800, Wb - 300), H - 600, interval=250, layer="ORNAMEN_FASAD")

    # dimensi
    titik = sorted({0.0, float(Wb)} | {v for u0, u1, _ in daftar for v in (u0, u1)})
    y_t = Z(Zt)
    for a1, a2 in zip(titik, titik[1:]):
        if a2 - a1 > 1:
            _dim_h(msp, X(a1), X(a2), y_t, Z(Zt - 450))
    _dim_h(msp, X(0), X(Wb), y_t, Z(Zt - 950))
    x_r = X(Wb) + ov + t / 2 + 800
    for z, lab in [(Zt, "-0.40 (tanah asli)"), (0, "±0.00 (lantai)"), (H, f"+{H/1000:.2f} (puncak dinding)"),
                   (z_e, f"+{z_e/1000:.2f} (tepi atap)"), (z_puncak, f"+{z_puncak/1000:.2f} (nok)")]:
        _elevasi(msp, x_r, Z(z), lab)
    x_d = x_r + 2500
    _dim_v(msp, x_r, Z(Zt), Z(0), x_d)
    _dim_v(msp, x_r, Z(0), Z(H), x_d)
    _dim_v(msp, x_r, Z(H), Z(z_puncak), x_d)
    _dim_v(msp, x_r, Z(0), Z(z_puncak), x_d + 800)

    # keterangan bahan
    x_ref = X(-ov - t / 2) - 700
    ket = [(z_tengah, f"Atap {b['penutup']} + rangka {b['rangka']}", -ov + 60),
           (H * 0.85, "Dinding bata merah 1/2 bata, plester + aci + cat", -t / 2 + 60),
           (Zt / 2, "Plint pasangan batu kali", -t / 2)]
    if "pintu" in contoh:
        u0, u1, z0, z1, bhn = contoh["pintu"]
        ket.append(((z0 + z1) / 2 - 300, "Pintu: " + (bhn or "kusen kayu, daun panel"), (u0 + u1) / 2))
    if "jendela" in contoh:
        u0, u1, z0, z1, bhn = contoh["jendela"]
        ket.append(((z0 + z1) / 2, "Jendela: " + (bhn or "kusen aluminium + kaca"), (u0 + u1) / 2))
    if sisi == "depan":
        ket.append((1800, "Sekat secondary skin dinding roster ventilasi", 400))
        ket.append((Zt + 700, "Pintu gerbang geser besi hollow & pagar minimalis", -400))
    # urutkan turun dan beri jarak antar teks
    ket.sort(key=lambda k: -k[0])
    zlast = None
    for z, isi, uu in ket:
        zt = z if zlast is None or zlast - z >= 230 else zlast - 230
        _teks(msp, isi, (x_ref, Z(zt) - 40), rata=TA.RIGHT)
        _penunjuk(msp, (X(uu), Z(z)), (x_ref + 80, Z(zt)))
        zlast = zt
    nama = {"depan": "TAMPAK DEPAN", "belakang": "TAMPAK BELAKANG", "kanan": "TAMPAK KANAN", "kiri": "TAMPAK KIRI"}[sisi]
    _judul(msp, nama, X(Wb / 2), Z(Zt - 1700))
    return (x_ref - 5200, Z(Zt - 2400), x_d + 1800, Z(z_puncak + 800))


# ----------------------------------------------------------------- lembar lengkap
def ekspor_gambar_lengkap(rumah, path="hasil/gambar_lengkap.dxf", gambar_perabot: bool = True, **kwargs):
    """Denah + potongan + empat tampak dalam satu DXF. Kembalian: (path, {nama: bbox})."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    gambar_denah(rumah, msp, gambar_perabot=gambar_perabot)
    _layer(doc)
    b = _dasar(rumah)

    daerah = {"Denah": (b["minx"] - 3500, b["miny"] - 3500, b["maxx"] + 3500, b["maxy"] + 3500)}
    lebar_sel, tinggi_sel = 24000, 12500
    y_baris = b["miny"] - 11500
    ox0 = b["minx"] + 6500
    for i, sec in enumerate(rumah.potongan):
        bb = gambar_potongan(rumah, msp, sec, ox0 + i * lebar_sel, y_baris)
        if bb:
            daerah[f"Potongan {sec['nama']}"] = bb
    y_baris -= tinggi_sel + 1000
    for i, sisi in enumerate(["depan", "belakang", "kanan", "kiri"]):
        kol, baris = i % 2, i // 2
        daerah[f"Tampak {sisi}"] = gambar_tampak(rumah, msp, sisi, ox0 + kol * lebar_sel, y_baris - baris * (tinggi_sel - 1500))

    try:
        doc.saveas(str(path))
    except PermissionError:
        path = path.with_name(path.stem + "_baru" + path.suffix)
        doc.saveas(str(path))
    return path, daerah
