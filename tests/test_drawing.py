from pathlib import Path
import ezdxf
import pytest
from model import muat_rumah
from drawing import gambar_denah, ekspor_denah


def test_gambar_denah_msp():
    rumah = muat_rumah("rumah.json")
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()

    gambar_denah(rumah, msp)

    # Pastikan layer ada
    assert "A-WALL" in doc.layers
    assert "A-DOOR" in doc.layers
    assert "A-GLAZ" in doc.layers
    assert "A-ANNO-TEXT" in doc.layers

    # Periksa entitas yang tergambar di modelspace
    tipe_entitas = [e.dxftype() for e in msp]
    assert "LWPOLYLINE" in tipe_entitas
    assert "HATCH" in tipe_entitas
    assert "LINE" in tipe_entitas
    assert "ARC" in tipe_entitas
    assert "MTEXT" in tipe_entitas


def test_ekspor_denah_file(tmp_path):
    rumah = muat_rumah("rumah.json")
    out_file = tmp_path / "denah_uji.dxf"

    hasil = ekspor_denah(rumah, out_file)
    assert hasil.exists()
    assert hasil.stat().st_size > 0

    # Baca kembali dengan ezdxf untuk memvalidasi integritas file DXF
    doc_baca = ezdxf.readfile(str(hasil))
    assert doc_baca.dxfversion == "AC1032"  # R2018 DXF version code

