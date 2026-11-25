"""
Modul Penyesuaian Dimensi Parametrik Rumah (1 Lantai & 2 Lantai).
Menskalakan koordinat dinding, bukaan, ruang, tangga, void, balkon, dan garis potongan
secara proporsional tanpa merusak dimensi fisik kusen maupun ergonomi anak tangga.
"""
import copy
import math
from typing import Any, Dict, List


def _skala_titik(pt: List[float], minx: float, miny: float, sx: float, sy: float) -> List[float]:
    return [
        round(minx + (float(pt[0]) - minx) * sx, 2),
        round(miny + (float(pt[1]) - miny) * sy, 2),
    ]


def _skala_kotak(kotak: List[float], minx: float, miny: float, sx: float, sy: float) -> List[float]:
    return [
        round(minx + (float(kotak[0]) - minx) * sx, 2),
        round(miny + (float(kotak[1]) - miny) * sy, 2),
        round(minx + (float(kotak[2]) - minx) * sx, 2),
        round(miny + (float(kotak[3]) - miny) * sy, 2),
    ]


def _skala_daftar_dinding(dinding_list: List[Dict[str, Any]], minx: float, miny: float, sx: float, sy: float) -> Dict[str, float]:
    panjang_baru: Dict[str, float] = {}
    for d in dinding_list:
        d["a"] = _skala_titik(d["a"], minx, miny, sx, sy)
        d["b"] = _skala_titik(d["b"], minx, miny, sx, sy)
        did = d.get("id")
        if did:
            panjang_baru[did] = math.hypot(d["b"][0] - d["a"][0], d["b"][1] - d["a"][1])
    return panjang_baru


def _skala_daftar_bukaan(
    bukaan_list: List[Dict[str, Any]],
    panjang_lama: Dict[str, float],
    panjang_baru: Dict[str, float],
) -> None:
    for bk in bukaan_list:
        did = bk.get("dinding")
        if did not in panjang_lama or did not in panjang_baru:
            continue
        l_lama = max(1.0, panjang_lama[did])
        l_baru = panjang_baru[did]
        rasio = l_baru / l_lama

        off_lama = float(bk.get("offset", 0.0))
        lbr_lama = float(bk.get("lebar", 800.0))

        # Pertahankan lebar standar pintu/jendela kecuali jika dinding menjadi sangat sempit
        lbr_baru = min(lbr_lama, max(500.0, l_baru - 200.0))
        tengah_lama = off_lama + lbr_lama / 2.0
        tengah_baru = tengah_lama * rasio
        off_baru = max(100.0, min(l_baru - lbr_baru - 100.0, tengah_baru - lbr_baru / 2.0))

        bk["offset"] = round(off_baru, 1)
        bk["lebar"] = round(lbr_baru, 1)


def _skala_daftar_ruang(ruang_list: List[Dict[str, Any]], minx: float, miny: float, sx: float, sy: float) -> None:
    for rg in ruang_list:
        if isinstance(rg.get("kotak"), list) and len(rg["kotak"]) == 4:
            rg["kotak"] = _skala_kotak(rg["kotak"], minx, miny, sx, sy)
        if isinstance(rg.get("poligon"), list):
            rg["poligon"] = [_skala_titik(p, minx, miny, sx, sy) for p in rg["poligon"]]
        if isinstance(rg.get("label"), list) and len(rg["label"]) >= 2:
            rg["label"] = _skala_titik(rg["label"], minx, miny, sx, sy)
        if isinstance(rg.get("center"), list) and len(rg["center"]) >= 2:
            rg["center"] = _skala_titik(rg["center"], minx, miny, sx, sy)


def sesuaikan_dimensi_rumah(data: Dict[str, Any], lebar_mm: float, panjang_mm: float) -> Dict[str, Any]:
    """
    Menskalakan seluruh geometri bangunan (1 lantai maupun 2 lantai) agar sesuai dengan
    target lebar_mm (sumbu X) dan panjang_mm (sumbu Y).
    """
    hasil = copy.deepcopy(data)
    d1_list = hasil.get("dinding", [])
    if not d1_list:
        return hasil

    xs = [float(p[0]) for d in d1_list for p in (d.get("a", [0, 0]), d.get("b", [0, 0]))]
    ys = [float(p[1]) for d in d1_list for p in (d.get("a", [0, 0]), d.get("b", [0, 0]))]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    w_lama = max(1.0, maxx - minx)
    h_lama = max(1.0, maxy - miny)
    sx = float(lebar_mm) / w_lama
    sy = float(panjang_mm) / h_lama

    # Catat panjang lama seluruh segmen dinding sebelum diskalakan
    panjang_lama: Dict[str, float] = {}
    for d in d1_list + hasil.get("dinding_lt2", []):
        did = d.get("id")
        if did:
            a, b = d["a"], d["b"]
            panjang_lama[did] = math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))

    # 1. Skala dinding Lantai 1 & Lantai 2
    p_baru_1 = _skala_daftar_dinding(d1_list, minx, miny, sx, sy)
    p_baru_2 = _skala_daftar_dinding(hasil.get("dinding_lt2", []), minx, miny, sx, sy)
    panjang_baru = {**p_baru_1, **p_baru_2}

    # 2. Skala bukaan (pintu/jendela) Lantai 1 & Lantai 2
    _skala_daftar_bukaan(hasil.get("bukaan", []), panjang_lama, panjang_baru)
    _skala_daftar_bukaan(hasil.get("bukaan_lt2", []), panjang_lama, panjang_baru)

    # 3. Skala ruang Lantai 1 & Lantai 2
    _skala_daftar_ruang(hasil.get("ruang", []), minx, miny, sx, sy)
    _skala_daftar_ruang(hasil.get("ruang_lt2", []), minx, miny, sx, sy)

    # 4. Skala void tangga & balkon Lantai 2
    for v in hasil.get("void", []):
        if isinstance(v.get("kotak"), list) and len(v["kotak"]) == 4:
            v["kotak"] = _skala_kotak(v["kotak"], minx, miny, sx, sy)

    for blk in hasil.get("balkon", []):
        if isinstance(blk.get("kotak"), list) and len(blk["kotak"]) == 4:
            blk["kotak"] = _skala_kotak(blk["kotak"], minx, miny, sx, sy)

    # 5. Skala posisi tangga & sinkronkan elevasi dengan tinggi lantai 1
    tg = hasil.get("tangga")
    if isinstance(tg, dict):
        if isinstance(tg.get("asal"), list) and len(tg["asal"]) >= 2:
            tg["asal"] = _skala_titik(tg["asal"], minx, miny, sx, sy)
        arah_naik = str(tg.get("arah_naik", "utara")).lower()
        if arah_naik in ("utara", "selatan"):
            tg["panjang_leg1"] = round(float(tg.get("panjang_leg1", 2400.0)) * sy, 1)
            tg["panjang_leg2"] = round(float(tg.get("panjang_leg2", 1650.0)) * sx, 1)
        else:
            tg["panjang_leg1"] = round(float(tg.get("panjang_leg1", 2400.0)) * sx, 1)
            tg["panjang_leg2"] = round(float(tg.get("panjang_leg2", 1650.0)) * sy, 1)

        tinggi_lt1 = float(hasil.get("lantai", {}).get("tinggi_dinding", 3400.0))
        jml_anak = max(10, int(tg.get("jumlah_anak_tangga", 17)))
        tg["elevasi_bawah"] = 0.0
        tg["elevasi_atas"] = tinggi_lt1
        tg["optrade"] = round(tinggi_lt1 / jml_anak, 1)

    # 6. Skala posisi garis potongan A-A / B-B
    for sec in hasil.get("potongan", []):
        arah = sec.get("arah", "x")
        pos = float(sec.get("posisi", 0.0))
        if arah == "x":
            sec["posisi"] = round(miny + (pos - miny) * sy, 1)
        else:
            sec["posisi"] = round(minx + (pos - minx) * sx, 1)

    return hasil