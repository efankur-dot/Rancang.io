"""
Loader & Validator Model Geometri Rumah (Mendukung 1 Lantai & 2 Lantai).
Dilengkapi penyimpanan raw JSON & fallback atribut otomatis agar 100% kompatibel
dengan seluruh modul lama maupun baru (denah, potongan, detail, dan RAB).
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ValidasiRumahError(Exception):
    """Exception khusus apabila data geometri atau parameter bangunan tidak valid."""


def _ambil_level_lantai(val: Any, default: int = 1) -> int:
    """Mengambil nomor lantai (1 atau 2) secara aman meski field berisi nama material lantai."""
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float) and val.is_integer():
        return int(val)
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return default


def _fallback_atribut(raw: Dict[str, Any], name: str) -> Any:
    """Mengembalikan nilai dari raw JSON atau default aman agar tidak pernah AttributeError."""
    if name.startswith("_"):
        raise AttributeError(name)
    if name in raw:
        return raw[name]
    kata_angka = ("tinggi", "lebar", "panjang", "luas", "keliling", "tebal", "elevasi", "jumlah", "volume", "jarak", "offset", "ambang")
    if any(k in name.lower() for k in kata_angka):
        return 0.0
    return ""


@dataclass
class Dinding:
    id: str
    a: Tuple[float, float]
    b: Tuple[float, float]
    tebal: float = 150.0
    bahan: str = "bata merah 1:4"
    tinggi: Optional[float] = None
    lantai: int = 1
    jenis: str = "utama"
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getattr__(self, name: str) -> Any:
        return _fallback_atribut(self._raw, name)

    @property
    def panjang(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

    @property
    def arah(self) -> Tuple[float, float]:
        L = self.panjang
        return ((self.b[0] - self.a[0]) / L, (self.b[1] - self.a[1]) / L) if L > 0 else (1.0, 0.0)

    @property
    def normal(self) -> Tuple[float, float]:
        dx, dy = self.arah
        return (-dy, dx)


@dataclass
class Bukaan:
    id: str
    dinding: str
    jenis: str
    offset: float
    lebar: float
    tinggi: float
    ambang: float = 0.0
    ayun_ke: str = "dalam"
    engsel: str = "kiri"
    daun: int = 1
    bahan: str = ""
    lantai: int = 1
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getattr__(self, name: str) -> Any:
        return _fallback_atribut(self._raw, name)

    @property
    def akhir(self) -> float:
        return self.offset + self.lebar

    @property
    def luas(self) -> float:
        return self.lebar * self.tinggi


@dataclass
class Ruang:
    id: str = ""
    nama: str = ""
    kotak: Optional[List[float]] = None
    poligon: Optional[List[Tuple[float, float]]] = None
    label: Optional[Tuple[float, float]] = None
    elevasi: float = 0.0
    lantai: str = "keramik 40x40"
    plafon: str = "gypsum 9mm"
    lantai_finishing: str = "keramik 40x40"
    dinding_finishing: str = "cat tembok"
    keramik_dinding_tinggi: float = 0.0
    level: int = 1
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getattr__(self, name: str) -> Any:
        return _fallback_atribut(self._raw, name)

    @property
    def lebar(self) -> float:
        if self.kotak and len(self.kotak) == 4:
            return abs(float(self.kotak[2]) - float(self.kotak[0]))
        if self.poligon and len(self.poligon) >= 3:
            xs = [p[0] for p in self.poligon]
            return max(xs) - min(xs)
        return 0.0

    @property
    def panjang(self) -> float:
        if self.kotak and len(self.kotak) == 4:
            return abs(float(self.kotak[3]) - float(self.kotak[1]))
        if self.poligon and len(self.poligon) >= 3:
            ys = [p[1] for p in self.poligon]
            return max(ys) - min(ys)
        return 0.0

    @property
    def luas(self) -> float:
        if self.kotak and len(self.kotak) == 4:
            return self.lebar * self.panjang
        if self.poligon and len(self.poligon) >= 3:
            area = 0.0
            pts = self.poligon
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                area += x1 * y2 - x2 * y1
            return abs(area) / 2.0
        return 0.0

    @property
    def luas_m2(self) -> float:
        return self.luas / 1_000_000.0

    @property
    def keliling(self) -> float:
        if self.kotak and len(self.kotak) == 4:
            return 2.0 * (self.lebar + self.panjang)
        if self.poligon and len(self.poligon) >= 3:
            total = 0.0
            pts = self.poligon
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                total += math.hypot(x2 - x1, y2 - y1)
            return total
        return 0.0

    @property
    def pusat(self) -> Tuple[float, float]:
        if self.kotak and len(self.kotak) == 4:
            return ((float(self.kotak[0]) + float(self.kotak[2])) / 2.0,
                    (float(self.kotak[1]) + float(self.kotak[3])) / 2.0)
        if self.label:
            return self.label
        return (0.0, 0.0)


@dataclass
class Tangga:
    id: str = "TG1"
    bentuk: str = "L"
    asal: Tuple[float, float] = (0.0, 0.0)
    lebar: float = 900.0
    jumlah_anak_tangga: int = 17
    antrade: float = 250.0
    optrade: float = 200.0
    arah_naik: str = "utara"
    belok: str = "kiri"
    panjang_leg1: float = 2400.0
    panjang_leg2: float = 1650.0
    elevasi_bawah: float = 0.0
    elevasi_atas: float = 3400.0
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getattr__(self, name: str) -> Any:
        return _fallback_atribut(self._raw, name)


@dataclass
class Rumah:
    proyek: Dict[str, Any] = field(default_factory=dict)
    satuan: str = "mm"
    jumlah_lantai: int = 1
    lantai: Dict[str, Any] = field(default_factory=dict)
    lantai_2: Dict[str, Any] = field(default_factory=dict)
    dinding_default: Dict[str, Any] = field(default_factory=dict)
    dinding: List[Dinding] = field(default_factory=list)
    dinding_lt2: List[Dinding] = field(default_factory=list)
    bukaan: List[Bukaan] = field(default_factory=list)
    bukaan_lt2: List[Bukaan] = field(default_factory=list)
    ruang: List[Ruang] = field(default_factory=list)
    ruang_lt2: List[Ruang] = field(default_factory=list)
    tangga: Optional[Tangga] = None
    void: List[Dict[str, Any]] = field(default_factory=list)
    balkon: List[Dict[str, Any]] = field(default_factory=list)
    struktur: Dict[str, Any] = field(default_factory=dict)
    atap: Dict[str, Any] = field(default_factory=dict)
    potongan: List[Dict[str, Any]] = field(default_factory=list)
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getattr__(self, name: str) -> Any:
        return _fallback_atribut(self._raw, name)

    @property
    def batas(self) -> Tuple[float, float, float, float]:
        xs = [p[0] for d in self.dinding for p in (d.a, d.b)]
        ys = [p[1] for d in self.dinding for p in (d.a, d.b)]
        return (min(xs), min(ys), max(xs), max(ys)) if xs and ys else (0.0, 0.0, 6000.0, 6000.0)

    @property
    def semua_dinding(self) -> List[Dinding]:
        return list(self.dinding) + list(self.dinding_lt2)

    @property
    def semua_bukaan(self) -> List[Bukaan]:
        return list(self.bukaan) + list(self.bukaan_lt2)

    @property
    def semua_ruang(self) -> List[Ruang]:
        return list(self.ruang) + list(self.ruang_lt2)

    def dinding_by_id(self, did: str) -> Optional[Dinding]:
        for d in self.semua_dinding:
            if d.id == did:
                return d
        return None


def _parse_dinding(
    raw_list: List[Dict[str, Any]],
    tebal_default: float,
    bahan_default: str = "bata merah 1:4",
    lantai_default: int = 1,
) -> List[Dinding]:
    hasil: List[Dinding] = []
    seen_ids = set()
    for idx, item in enumerate(raw_list, start=1):
        did = str(item.get("id") or f"D{lantai_default}_{idx}")
        if did in seen_ids:
            raise ValidasiRumahError(f"ID dinding duplikat ditemukan: '{did}'.")
        seen_ids.add(did)

        a = item.get("a")
        b = item.get("b")
        if not (isinstance(a, (list, tuple)) and len(a) >= 2 and isinstance(b, (list, tuple)) and len(b) >= 2):
            raise ValidasiRumahError(f"Koordinat dinding '{did}' harus memiliki titik awal [x1, y1] dan akhir [x2, y2].")

        pa = (float(a[0]), float(a[1]))
        pb = (float(b[0]), float(b[1]))
        pjg = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        if pjg < 100.0:
            raise ValidasiRumahError(f"Panjang dinding '{did}' ({pjg:.0f} mm) terlalu pendek (minimal 100 mm).")

        tebal = float(item.get("tebal", tebal_default))
        if tebal <= 0:
            raise ValidasiRumahError(f"Tebal dinding '{did}' harus lebih besar dari 0 mm.")

        lt = _ambil_level_lantai(item.get("lantai"), lantai_default)
        tinggi_val = float(item["tinggi"]) if item.get("tinggi") is not None else None
        hasil.append(
            Dinding(
                id=did,
                a=pa,
                b=pb,
                tebal=tebal,
                bahan=str(item.get("bahan", bahan_default)),
                tinggi=tinggi_val,
                lantai=lt,
                jenis=str(item.get("jenis", "utama")),
                _raw=dict(item),
            )
        )
    return hasil


def _parse_bukaan(
    raw_list: List[Dict[str, Any]],
    peta_dinding: Dict[str, Dinding],
    tinggi_dinding: float,
    lantai_default: int = 1,
) -> List[Bukaan]:
    hasil: List[Bukaan] = []
    for idx, item in enumerate(raw_list, start=1):
        bid = str(item.get("id") or f"B{lantai_default}_{idx}")
        did = str(item.get("dinding", ""))
        if did not in peta_dinding:
            raise ValidasiRumahError(f"Bukaan '{bid}' merujuk ke dinding '{did}' yang tidak ditemukan.")

        d_obj = peta_dinding[did]
        jenis = str(item.get("jenis", "pintu")).lower()
        offset = float(item.get("offset", 0.0))
        lebar = float(item.get("lebar", 800.0))
        tinggi = float(item.get("tinggi", 2100.0))
        ambang = float(item.get("ambang", 0.0))

        if lebar <= 0 or tinggi <= 0:
            raise ValidasiRumahError(f"Dimensi bukaan '{bid}' harus positif.")
        if offset < -1e-6 or (offset + lebar) > (d_obj.panjang + 1e-3):
            raise ValidasiRumahError(
                f"Bukaan '{bid}' ({offset:.0f}..{offset + lebar:.0f} mm) melampaui panjang dinding '{did}' ({d_obj.panjang:.0f} mm)."
            )
        if (ambang + tinggi) > (tinggi_dinding + 1e-3):
            raise ValidasiRumahError(
                f"Tinggi bukaan '{bid}' ({ambang + tinggi:.0f} mm) melebihi tinggi dinding ({tinggi_dinding:.0f} mm)."
            )

        hasil.append(
            Bukaan(
                id=bid,
                dinding=did,
                jenis=jenis,
                offset=offset,
                lebar=lebar,
                tinggi=tinggi,
                ambang=ambang,
                ayun_ke=str(item.get("ayun_ke", "dalam")),
                engsel=str(item.get("engsel", "kiri")),
                daun=int(item.get("daun", 1)),
                bahan=str(item.get("bahan", "")),
                lantai=_ambil_level_lantai(item.get("lantai"), d_obj.lantai),
                _raw=dict(item),
            )
        )
    return hasil


def _parse_ruang(raw_list: List[Dict[str, Any]], lantai_default: int = 1) -> List[Ruang]:
    hasil: List[Ruang] = []
    for idx, item in enumerate(raw_list, start=1):
        rid = str(item.get("id") or f"R{lantai_default}_{idx}")
        nama = str(item.get("nama") or f"Ruang {idx}")
        kotak = item.get("kotak")
        poligon = item.get("poligon")
        label = item.get("label") or item.get("center")

        kotak_f = [float(v) for v in kotak] if isinstance(kotak, (list, tuple)) and len(kotak) == 4 else None
        poli_f = [(float(p[0]), float(p[1])) for p in poligon] if isinstance(poligon, (list, tuple)) and len(poligon) >= 3 else None
        lbl_f = (float(label[0]), float(label[1])) if isinstance(label, (list, tuple)) and len(label) >= 2 else None

        is_km = ("km" in nama.lower()) or ("wc" in nama.lower()) or ("mandi" in nama.lower())
        raw_lt = item.get("lantai")
        level_lt = _ambil_level_lantai(raw_lt, default=_ambil_level_lantai(item.get("level"), lantai_default))
        if isinstance(raw_lt, str) and not raw_lt.strip().isdigit():
            material_lt = raw_lt
        else:
            default_mat = "keramik 20x20" if is_km else "keramik 40x40"
            material_lt = str(item.get("lantai_finishing", default_mat))

        keramik_dinding = float(item.get("keramik_dinding_tinggi", 1500.0 if is_km else 0.0))

        hasil.append(
            Ruang(
                id=rid,
                nama=nama,
                kotak=kotak_f,
                poligon=poli_f,
                label=lbl_f,
                elevasi=float(item.get("elevasi", 0.0)),
                lantai=material_lt,
                plafon=str(item.get("plafon", "gypsum 9mm")),
                lantai_finishing=material_lt,
                dinding_finishing=str(item.get("dinding_finishing", "cat tembok")),
                keramik_dinding_tinggi=keramik_dinding,
                level=level_lt,
                _raw=dict(item),
            )
        )
    return hasil


def _parse_tangga(raw_tg: Optional[Dict[str, Any]], tinggi_lt1: float) -> Optional[Tangga]:
    if not raw_tg or not isinstance(raw_tg, dict):
        return None
    asal = raw_tg.get("asal", [0.0, 0.0])
    jml = max(8, int(raw_tg.get("jumlah_anak_tangga", 17)))
    elev_bwh = float(raw_tg.get("elevasi_bawah", 0.0))
    elev_ats = float(raw_tg.get("elevasi_atas", tinggi_lt1))
    optrade = float(raw_tg.get("optrade", round((elev_ats - elev_bwh) / jml, 1)))
    antrade = float(raw_tg.get("antrade", 250.0))
    lebar = float(raw_tg.get("lebar", 900.0))

    if lebar < 650.0:
        raise ValidasiRumahError(f"Lebar tangga ({lebar:.0f} mm) terlalu sempit (minimal 650 mm).")

    return Tangga(
        id=str(raw_tg.get("id", "TG1")),
        bentuk=str(raw_tg.get("bentuk", "L")),
        asal=(float(asal[0]), float(asal[1])),
        lebar=lebar,
        jumlah_anak_tangga=jml,
        antrade=antrade,
        optrade=optrade,
        arah_naik=str(raw_tg.get("arah_naik", "utara")).lower(),
        belok=str(raw_tg.get("belok", "kiri")).lower(),
        panjang_leg1=float(raw_tg.get("panjang_leg1", 2400.0)),
        panjang_leg2=float(raw_tg.get("panjang_leg2", 1650.0)),
        elevasi_bawah=elev_bwh,
        elevasi_atas=elev_ats,
        _raw=dict(raw_tg),
    )


def muat_rumah(path: str) -> Rumah:
    """Memuat dan memvalidasi berkas JSON rumah (1 lantai maupun 2 lantai)."""
    p = Path(path)
    if not p.exists():
        raise ValidasiRumahError(f"Berkas tidak ditemukan: {path}")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValidasiRumahError(f"Format JSON rusak pada baris {e.lineno}: {e.msg}") from e

    if not isinstance(data, dict):
        raise ValidasiRumahError("Root JSON harus berupa objek dictionary.")

    jumlah_lantai = int(data.get("jumlah_lantai", 1))
    if jumlah_lantai not in (1, 2):
        raise ValidasiRumahError("Jumlah lantai saat ini mendukung 1 atau 2 lantai.")

    lantai_1 = dict(data.get("lantai") or {})
    tinggi_lt1 = float(lantai_1.get("tinggi_dinding", 3000.0))
    plafon_lt1 = float(lantai_1.get("tinggi_plafon", 2800.0))
    if tinggi_lt1 < 2000.0 or plafon_lt1 > tinggi_lt1:
        raise ValidasiRumahError("Tinggi dinding Lantai 1 minimal 2000 mm dan tinggi plafon tidak boleh melebihi tinggi dinding.")
    lantai_1.setdefault("elevasi", 0.0)
    lantai_1.setdefault("tinggi_dinding", tinggi_lt1)
    lantai_1.setdefault("tinggi_plafon", plafon_lt1)

    lantai_2 = dict(data.get("lantai_2") or {})
    if jumlah_lantai == 2:
        tinggi_lt2 = float(lantai_2.get("tinggi_dinding", 3200.0))
        plafon_lt2 = float(lantai_2.get("tinggi_plafon", 2900.0))
        if tinggi_lt2 < 2000.0 or plafon_lt2 > tinggi_lt2:
            raise ValidasiRumahError("Tinggi dinding Lantai 2 minimal 2000 mm dan tinggi plafon tidak boleh melebihi tinggi dinding.")
        lantai_2.setdefault("elevasi", tinggi_lt1)
        lantai_2.setdefault("tinggi_dinding", tinggi_lt2)
        lantai_2.setdefault("tinggi_plafon", plafon_lt2)
    else:
        tinggi_lt2 = 0.0

    dinding_default = dict(data.get("dinding_default") or {"tebal": 150, "bahan": "bata merah 1:4"})
    tebal_def = float(dinding_default.get("tebal", 150.0))
    bahan_def = str(dinding_default.get("bahan", "bata merah 1:4"))

    raw_dinding = list(data.get("dinding") or [])
    if not raw_dinding:
        raise ValidasiRumahError("Daftar 'dinding' Lantai 1 tidak boleh kosong.")

    raw_d1 = [d for d in raw_dinding if _ambil_level_lantai(d.get("lantai"), 1) == 1]
    raw_d2_inline = [d for d in raw_dinding if _ambil_level_lantai(d.get("lantai"), 1) == 2]
    raw_d2 = list(data.get("dinding_lt2") or []) + raw_d2_inline

    dinding_1 = _parse_dinding(raw_d1, tebal_def, bahan_default=bahan_def, lantai_default=1)
    dinding_2 = _parse_dinding(raw_d2, tebal_def, bahan_default=bahan_def, lantai_default=2) if jumlah_lantai == 2 else []

    if jumlah_lantai == 2 and not dinding_2:
        raise ValidasiRumahError("Model rumah 2 lantai harus memiliki daftar 'dinding_lt2'.")

    peta_d1 = {d.id: d for d in dinding_1}
    peta_d2 = {d.id: d for d in dinding_2}
    peta_semua = {**peta_d1, **peta_d2}

    raw_bukaan = list(data.get("bukaan") or [])
    raw_b1 = [b for b in raw_bukaan if b.get("dinding") in peta_d1 and _ambil_level_lantai(b.get("lantai"), 1) == 1]
    raw_b2_inline = [b for b in raw_bukaan if b.get("dinding") in peta_d2 or _ambil_level_lantai(b.get("lantai"), 1) == 2]
    raw_b2 = list(data.get("bukaan_lt2") or []) + raw_b2_inline

    bukaan_1 = _parse_bukaan(raw_b1, peta_d1, tinggi_lt1, lantai_default=1)
    bukaan_2 = _parse_bukaan(raw_b2, peta_semua, tinggi_lt2 or tinggi_lt1, lantai_default=2) if jumlah_lantai == 2 else []

    raw_ruang = list(data.get("ruang") or [])
    raw_r1 = [r for r in raw_ruang if _ambil_level_lantai(r.get("lantai"), 1) == 1]
    raw_r2_inline = [r for r in raw_ruang if _ambil_level_lantai(r.get("lantai"), 1) == 2]
    raw_r2 = list(data.get("ruang_lt2") or []) + raw_r2_inline

    ruang_1 = _parse_ruang(raw_r1, lantai_default=1)
    ruang_2 = _parse_ruang(raw_r2, lantai_default=2) if jumlah_lantai == 2 else []

    tangga_obj = _parse_tangga(data.get("tangga"), tinggi_lt1) if jumlah_lantai == 2 else None

    struktur = dict(data.get("struktur") or {})
    struktur.setdefault("pondasi", {"lebar_bawah": 600, "lebar_atas": 300, "tinggi": 700})
    struktur.setdefault("footplat", {"lebar": 1000, "panjang": 1000, "tebal": 250, "kedalaman": 1200})
    struktur.setdefault("sloof", [150, 200] if jumlah_lantai == 1 else [200, 300])
    struktur.setdefault("balok_induk", [200, 350])
    struktur.setdefault("balok_anak", [150, 250])
    struktur.setdefault("pelat_lantai", {"tebal": 120, "mutu": "K-300"})
    struktur.setdefault("ring_balok", [150, 150] if jumlah_lantai == 1 else [150, 200])
    struktur.setdefault("kolom_praktis", [150, 150])
    struktur.setdefault("kolom_struktur", [250, 250])

    atap = dict(data.get("atap") or {})
    atap.setdefault("jenis", "pelana")
    atap.setdefault("kemiringan_derajat", 30)
    atap.setdefault("overstek", 600)
    atap.setdefault("arah_nok", "x")
    atap.setdefault("penutup", "genteng")
    atap.setdefault("rangka", "baja ringan")

    potongan = list(data.get("potongan") or [])
    if not potongan:
        xs = [p[0] for d in dinding_1 for p in (d.a, d.b)]
        ys = [p[1] for d in dinding_1 for p in (d.a, d.b)]
        potongan = [
            {"nama": "A-A", "arah": "x", "posisi": (min(ys) + max(ys)) / 2.0},
            {"nama": "B-B", "arah": "y", "posisi": (min(xs) + max(xs)) / 2.0},
        ]

    return Rumah(
        proyek=dict(data.get("proyek") or {}),
        satuan=str(data.get("satuan", "mm")),
        jumlah_lantai=jumlah_lantai,
        lantai=lantai_1,
        lantai_2=lantai_2,
        dinding_default=dinding_default,
        dinding=dinding_1,
        dinding_lt2=dinding_2,
        bukaan=bukaan_1,
        bukaan_lt2=bukaan_2,
        ruang=ruang_1,
        ruang_lt2=ruang_2,
        tangga=tangga_obj,
        void=list(data.get("void") or []),
        balkon=list(data.get("balkon") or []),
        struktur=struktur,
        atap=atap,
        potongan=potongan,
        _raw=dict(data),
    )