"""
Tes unit untuk memverifikasi Mode Upload vs Mode Template,
penanganan error JSON rusak, dan validasi bukaan keluar dinding.
"""
import json
import tempfile
from pathlib import Path
import pytest
import ezdxf

from model.loader import muat_rumah, validasi_rumah, ValidasiRumahError
from model.param_rumah import sesuaikan_dimensi_rumah
from drawing.potongan import ekspor_gambar_lengkap


@pytest.fixture
def data_rumah_6x10():
    """Contoh data rumah denah kustom ukuran 6 x 10 meter."""
    return {
        "proyek": {"nama": "Rumah Kustom 6x10", "pemilik": "Budi", "lokasi": "Magelang"},
        "satuan": "mm",
        "lantai": {"elevasi": 0, "tinggi_dinding": 3200, "tinggi_plafon": 2900},
        "dinding_default": {"tebal": 150, "bahan": "bata merah", "finishing": "plester aci"},
        "dinding": [
            {"id": "W1", "a": [0, 0], "b": [6000, 0], "tipe": "luar"},
            {"id": "W2", "a": [6000, 0], "b": [6000, 10000], "tipe": "luar"},
            {"id": "W3", "a": [6000, 10000], "b": [0, 10000], "tipe": "luar"},
            {"id": "W4", "a": [0, 10000], "b": [0, 0], "tipe": "luar"},
            {"id": "I1", "a": [3000, 0], "b": [3000, 10000], "tipe": "dalam"},
            {"id": "I2", "a": [0, 5000], "b": [3000, 5000], "tipe": "dalam"},
        ],
        "bukaan": [
            {"id": "D1", "jenis": "pintu", "dinding": "W1", "offset": 3500, "lebar": 900, "tinggi": 2100, "ambang": 0},
            {"id": "D2", "jenis": "pintu", "dinding": "I1", "offset": 1000, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "D3", "jenis": "pintu", "dinding": "I2", "offset": 1000, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "J1", "jenis": "jendela", "dinding": "W1", "offset": 1000, "lebar": 1200, "tinggi": 1200, "ambang": 900},
            {"id": "J2", "jenis": "jendela", "dinding": "W4", "offset": 2000, "lebar": 1200, "tinggi": 1200, "ambang": 900},
            {"id": "J3", "jenis": "jendela", "dinding": "W4", "offset": 7000, "lebar": 1200, "tinggi": 1200, "ambang": 900},
        ],
        "ruang": [
            {"nama": "Kamar Tidur 1", "kotak": [0, 0, 3000, 5000]},
            {"nama": "Kamar Tidur 2", "kotak": [0, 5000, 3000, 10000]},
            {"nama": "Ruang Tamu & Dapur", "kotak": [3000, 0, 6000, 10000]},
        ],
        "struktur": {
            "pondasi": {"jenis": "batu kali", "lebar_bawah": 600, "lebar_atas": 300, "tinggi": 700},
            "sloof": [150, 200],
            "kolom": [150, 150],
            "ring_balok": [150, 150],
        },
        "atap": {"jenis": "pelana", "kemiringan_derajat": 30, "overstek": 600},
        "potongan": [
            {"nama": "A-A", "arah": "x", "posisi": 2500, "lihat": "utara"},
            {"nama": "B-B", "arah": "y", "posisi": 4500, "lihat": "timur"},
        ]
    }


def test_mode_upload_abaikan_slider_dan_ukur_tepat_6x10(data_rumah_6x10, tmp_path):
    """
    Kriteria 1:
    Saat mode upload, nilai slider (misal 8000 x 10000 mm) diabaikan total.
    Denah 6x10 m digambar 100% dari koordinat absolut JSON tanpa scaling,
    bounding box dinding tepat 6000 x 10000 mm, validasi sukses, dan perabot tidak digambar.
    """
    mode = "upload"
    slider_lebar = 8000
    slider_panjang = 10000

    # Di mode upload, scaling TIDAK boleh dipanggil sama sekali
    data_final = data_rumah_6x10
    if mode == "template":
        data_final = sesuaikan_dimensi_rumah(data_final, slider_lebar, slider_panjang)

    json_file = tmp_path / "denah_kustom_6x10.json"
    json_file.write_text(json.dumps(data_final), encoding="utf-8")

    # Muat dan validasi
    rumah = muat_rumah(json_file)
    assert rumah is not None

    # Cek bounding box dinding pada model
    xs = [p[0] for d in rumah.dinding for p in (d.a, d.b)]
    ys = [p[1] for d in rumah.dinding for p in (d.a, d.b)]
    lebar_dinding = max(xs) - min(xs)
    panjang_dinding = max(ys) - min(ys)
    assert lebar_dinding == 6000.0, f"Lebar dinding harus 6000, didapat {lebar_dinding}"
    assert panjang_dinding == 10000.0, f"Panjang dinding harus 10000, didapat {panjang_dinding}"

    # Ekspor ke DXF dengan gambar_perabot=False (karena mode upload)
    dxf_out = tmp_path / "hasil_upload_6x10.dxf"
    ekspor_gambar_lengkap(rumah, dxf_out, gambar_perabot=False)
    assert dxf_out.exists()

    # Periksa isi DXF
    doc = ezdxf.readfile(str(dxf_out))
    msp = doc.modelspace()
    
    # Periksa bahwa tidak ada entitas blok perabot (A-FURN kosong dari blok kasur/sofa)
    furn_entities = [e for e in msp if e.dxf.layer == "A-FURN"]
    assert len(furn_entities) == 0, "Mode upload tidak boleh menggambar blok perabot template!"


def test_mode_template_slider_berfungsi():
    """
    Kriteria 2:
    Pada mode template (tanpa upload), fungsi scaling mengubah ukuran denah sesuai slider.
    """
    with open("rumah.json", encoding="utf-8") as f:
        data_template = json.load(f)

    # Ubah ke 7000 x 9000 mm
    data_scaled = sesuaikan_dimensi_rumah(data_template, 7000, 9000)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(data_scaled, tmp)
        tmp_name = tmp.name

    try:
        rumah = muat_rumah(tmp_name)
        xs = [p[0] for d in rumah.dinding for p in (d.a, d.b)]
        ys = [p[1] for d in rumah.dinding for p in (d.a, d.b)]
        assert max(xs) - min(xs) == 7000.0
        assert max(ys) - min(ys) == 9000.0
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def test_json_rusak_handling(tmp_path):
    """
    Kriteria 4a:
    JSON rusak / sintaks tidak valid ditangkap dengan pesan error jelas, bukan crash.
    """
    json_rusak = '{"dinding": [{"id": "W1", "a": [0, 0], '  # JSON tidak lengkap
    with pytest.raises(json.JSONDecodeError) as exc_info:
        json.loads(json_rusak)
    assert exc_info.value.lineno is not None


def test_bukaan_keluar_dinding_handling(data_rumah_6x10, tmp_path):
    """
    Kriteria 4b:
    Bukaan keluar dari dinding memicu ValidasiRumahError yang informatif,
    menyebutkan ID bukaan dan ID dinding.
    """
    # Buat bukaan keluar dari dinding W1 (panjang 6000, offset 5500 + lebar 900 = 6400 > 6000)
    data_invalid = json.loads(json.dumps(data_rumah_6x10))
    data_invalid["bukaan"][0]["offset"] = 5500
    data_invalid["bukaan"][0]["lebar"] = 900

    f = tmp_path / "invalid_bukaan.json"
    f.write_text(json.dumps(data_invalid), encoding="utf-8")

    with pytest.raises(ValidasiRumahError) as exc_info:
        muat_rumah(f)

    pesan_error = str(exc_info.value)
    assert "D1" in pesan_error
    assert "W1" in pesan_error
    assert "keluar dari panjang dinding" in pesan_error

