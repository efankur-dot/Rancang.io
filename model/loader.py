import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union

from .bukaan import Bukaan
from .dinding import Dinding
from .ruang import Ruang
from .rumah import Rumah


class ValidasiRumahError(ValueError):
    """Exception yang dilemparkan ketika validasi rumah.json gagal."""
    pass


def validasi_rumah(rumah: Rumah) -> None:
    """
    Memvalidasi data rumah berdasarkan aturan:
    1. ID dinding yang dirujuk bukaan harus ada.
    2. Bukaan tidak boleh keluar dari panjang dinding (offset >= 0, lebar > 0, offset + lebar <= panjang dinding).
    3. Bukaan pada satu dinding tidak boleh tumpang tindih satu sama lain.
    """
    peta_dinding: Dict[str, Dinding] = {d.id: d for d in rumah.dinding}
    bukaan_per_dinding: Dict[str, List[Bukaan]] = defaultdict(list)

    # 1. Validasi keberadaan dinding dan batas panjang dinding untuk setiap bukaan
    for b in rumah.bukaan:
        # Aturan: ID dinding yang dirujuk bukaan harus ada
        if b.dinding not in peta_dinding:
            raise ValidasiRumahError(
                f"Validasi gagal: Bukaan '{b.id}' merujuk pada dinding '{b.dinding}' yang tidak ditemukan."
            )

        d = peta_dinding[b.dinding]

        # Aturan: Bukaan tidak boleh keluar dari panjang dinding
        if b.offset < 0:
            raise ValidasiRumahError(
                f"Validasi gagal: Bukaan '{b.id}' memiliki offset negatif ({b.offset}). "
                f"Bukaan tidak boleh keluar dari pangkal dinding '{d.id}'."
            )
        if b.lebar <= 0:
            raise ValidasiRumahError(
                f"Validasi gagal: Bukaan '{b.id}' memiliki lebar {b.lebar}. "
                f"Lebar bukaan harus lebih besar dari 0."
            )

        panjang_dinding = d.panjang
        akhir_bukaan = b.akhir
        if akhir_bukaan > panjang_dinding + 1e-6:
            raise ValidasiRumahError(
                f"Validasi gagal: Bukaan '{b.id}' (rentang {b.offset:.2f} s.d. {akhir_bukaan:.2f}) "
                f"keluar dari panjang dinding '{d.id}' ({panjang_dinding:.2f})."
            )

        bukaan_per_dinding[b.dinding].append(b)

    # 2. Validasi tumpang tindih bukaan pada dinding yang sama
    for id_dinding, daftar_bukaan in bukaan_per_dinding.items():
        if len(daftar_bukaan) <= 1:
            continue

        # Urutkan bukaan berdasarkan posisi awal (offset)
        urutan = sorted(daftar_bukaan, key=lambda item: (item.offset, item.akhir))
        for i in range(len(urutan) - 1):
            curr = urutan[i]
            nxt = urutan[i + 1]

            # Terjadi overlap jika awal bukaan berikutnya lebih kecil dari akhir bukaan saat ini
            if nxt.offset < curr.akhir - 1e-6:
                raise ValidasiRumahError(
                    f"Validasi gagal: Bukaan '{curr.id}' ({curr.offset} - {curr.akhir}) dan "
                    f"'{nxt.id}' ({nxt.offset} - {nxt.akhir}) pada dinding '{id_dinding}' "
                    f"saling tumpang tindih."
                )


def muat_rumah(path: Union[str, Path]) -> Rumah:
    """
    Membaca berkas JSON rumah dan memvalidasinya.
    Mengembalikan objek Rumah jika valid.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Berkas tidak ditemukan: {path_obj.resolve()}")

    with open(path_obj, "r", encoding="utf-8") as f:
        data = json.load(f)

    daftar_dinding = [
        Dinding(
            id=d["id"],
            a=d["a"],
            b=d["b"],
            tipe=d.get("tipe", "luar"),
            tebal=d.get("tebal"),
            bahan=d.get("bahan"),
            finishing=d.get("finishing"),
        )
        for d in data.get("dinding", [])
    ]

    daftar_bukaan = [
        Bukaan(
            id=b["id"],
            jenis=b["jenis"],
            dinding=b["dinding"],
            offset=b["offset"],
            lebar=b["lebar"],
            tinggi=b["tinggi"],
            ambang=b.get("ambang", 0.0),
            ayun_ke=b.get("ayun_ke"),
            engsel=b.get("engsel"),
            bahan=b.get("bahan"),
        )
        for b in data.get("bukaan", [])
    ]

    daftar_ruang = [
        Ruang(
            nama=r["nama"],
            kotak=r["kotak"],
            lantai=r.get("lantai"),
            plafon=r.get("plafon"),
            keramik_dinding_tinggi=r.get("keramik_dinding_tinggi"),
        )
        for r in data.get("ruang", [])
    ]

    rumah = Rumah(
        proyek=data.get("proyek", {}),
        satuan=data.get("satuan", "mm"),
        lantai=data.get("lantai", {}),
        dinding_default=data.get("dinding_default", {}),
        dinding=daftar_dinding,
        bukaan=daftar_bukaan,
        ruang=daftar_ruang,
        struktur=data.get("struktur", {}),
        atap=data.get("atap", {}),
        potongan=data.get("potongan", []),
    )

    validasi_rumah(rumah)
    return rumah

