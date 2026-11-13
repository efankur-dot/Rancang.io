import json
import pytest
from pathlib import Path
from model import (
    Rumah,
    Dinding,
    Bukaan,
    Ruang,
    muat_rumah,
    validasi_rumah,
    ValidasiRumahError,
)


def test_muat_rumah_json_sukses():
    """Memastikan rumah.json default dapat dimuat dan divalidasi tanpa error."""
    path = Path("rumah.json")
    assert path.exists(), "File rumah.json harus ada."

    rumah = muat_rumah(path)
    assert isinstance(rumah, Rumah)
    assert len(rumah.dinding) == 10
    assert len(rumah.bukaan) == 14
    assert len(rumah.ruang) == 6
    assert rumah.satuan == "mm"
    assert rumah.proyek["nama"] == "Rumah Tipe 36"


def test_file_tidak_ditemukan():
    """Memastikan FileNotFoundError jika path file tidak valid."""
    with pytest.raises(FileNotFoundError):
        muat_rumah("tidak_ada.json")


def test_validasi_id_dinding_harus_ada():
    """Aturan 3: Bukaan tidak boleh merujuk ID dinding yang tidak ada."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(3000, 0))
        ],
        bukaan=[
            Bukaan(id="D1", jenis="pintu", dinding="W_TIDAK_ADA", offset=500, lebar=800, tinggi=2100)
        ]
    )

    with pytest.raises(ValidasiRumahError, match="merujuk pada dinding 'W_TIDAK_ADA' yang tidak ditemukan"):
        validasi_rumah(rumah)


def test_validasi_bukaan_keluar_panjang_dinding():
    """Aturan 1: Bukaan melebihi panjang dinding."""
    # Dinding panjang 3000, bukaan di 2500 lebar 800 (akhir = 3300 > 3000)
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(3000, 0))
        ],
        bukaan=[
            Bukaan(id="D1", jenis="pintu", dinding="W1", offset=2500, lebar=800, tinggi=2100)
        ]
    )

    with pytest.raises(ValidasiRumahError, match="keluar dari panjang dinding 'W1'"):
        validasi_rumah(rumah)


def test_validasi_bukaan_offset_negatif():
    """Aturan 1: Offset bukaan bernilai negatif."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(3000, 0))
        ],
        bukaan=[
            Bukaan(id="D1", jenis="pintu", dinding="W1", offset=-100, lebar=800, tinggi=2100)
        ]
    )

    with pytest.raises(ValidasiRumahError, match="offset negatif"):
        validasi_rumah(rumah)


def test_validasi_bukaan_lebar_tidak_valid():
    """Aturan 1: Lebar bukaan harus > 0."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(3000, 0))
        ],
        bukaan=[
            Bukaan(id="D1", jenis="pintu", dinding="W1", offset=500, lebar=0, tinggi=2100)
        ]
    )

    with pytest.raises(ValidasiRumahError, match="Lebar bukaan harus lebih besar dari 0"):
        validasi_rumah(rumah)


def test_validasi_bukaan_tepat_di_ujung_dinding():
    """Bukaan yang tepat berakhir di ujung dinding (offset + lebar == panjang) harus valid."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(3000, 0))
        ],
        bukaan=[
            Bukaan(id="D1", jenis="pintu", dinding="W1", offset=2200, lebar=800, tinggi=2100)
        ]
    )
    # Tidak melempar error
    validasi_rumah(rumah)


def test_validasi_tumpang_tindih_pada_dinding_sama():
    """Aturan 2: Bukaan pada dinding yang sama tidak boleh tumpang tindih."""
    # Dinding W1: bukaan 1 di [500, 1500], bukaan 2 di [1200, 2000] (overlap di 1200-1500)
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(4000, 0))
        ],
        bukaan=[
            Bukaan(id="B1", jenis="pintu", dinding="W1", offset=500, lebar=1000, tinggi=2100),
            Bukaan(id="B2", jenis="jendela", dinding="W1", offset=1200, lebar=800, tinggi=1200),
        ]
    )

    with pytest.raises(ValidasiRumahError, match="saling tumpang tindih"):
        validasi_rumah(rumah)


def test_validasi_tumpang_tindih_acak_urutan():
    """Memastikan deteksi tumpang tindih tetap berjalan meskipun urutan deklarasi terbalik."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(4000, 0))
        ],
        bukaan=[
            Bukaan(id="B2", jenis="jendela", dinding="W1", offset=1200, lebar=800, tinggi=1200),
            Bukaan(id="B1", jenis="pintu", dinding="W1", offset=500, lebar=1000, tinggi=2100),
        ]
    )

    with pytest.raises(ValidasiRumahError, match="saling tumpang tindih"):
        validasi_rumah(rumah)


def test_validasi_bukaan_bersebelahan_tanpa_tumpang_tindih():
    """Bukaan yang menempel pas (ujung bukaan 1 == awal bukaan 2) tidak dianggap overlap."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(4000, 0))
        ],
        bukaan=[
            Bukaan(id="B1", jenis="pintu", dinding="W1", offset=500, lebar=1000, tinggi=2100),   # [500, 1500]
            Bukaan(id="B2", jenis="jendela", dinding="W1", offset=1500, lebar=800, tinggi=1200), # [1500, 2300]
        ]
    )
    # Harus valid tanpa error
    validasi_rumah(rumah)


def test_validasi_bukaan_pada_dinding_berbeda_tidak_saling_mempengaruhi():
    """Offset sama tetapi pada dinding berbeda harus valid."""
    rumah = Rumah(
        dinding=[
            Dinding(id="W1", a=(0, 0), b=(3000, 0)),
            Dinding(id="W2", a=(3000, 0), b=(3000, 3000)),
        ],
        bukaan=[
            Bukaan(id="B1", jenis="pintu", dinding="W1", offset=500, lebar=800, tinggi=2100),
            Bukaan(id="B2", jenis="pintu", dinding="W2", offset=500, lebar=800, tinggi=2100),
        ]
    )
    validasi_rumah(rumah)

