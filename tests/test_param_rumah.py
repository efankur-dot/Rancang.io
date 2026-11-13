import json
from pathlib import Path
import tempfile
import pytest

from model import muat_rumah, sesuaikan_dimensi_rumah, validasi_rumah


def test_sesuaikan_dimensi_default():
    with open("rumah.json", encoding="utf-8") as f:
        data = json.load(f)

    # Sesuaikan dengan ukuran default 6x6 m
    baru = sesuaikan_dimensi_rumah(data, 6000, 6000)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(baru, tmp)
        tmp_name = tmp.name

    try:
        rumah = muat_rumah(tmp_name)
        assert len(rumah.dinding) == 10
        assert len(rumah.bukaan) == 14
        assert len(rumah.ruang) == 6
    finally:
        Path(tmp_name).unlink(missing_ok=True)


@pytest.mark.parametrize("lebar,panjang", [
    (6000, 6000),
    (6000, 8000),
    (7000, 8000),
    (7500, 9000),
    (8000, 10000),
    (9000, 12000),
    (6000, 10000),
])
def test_berbagai_ukuran_rumah_valid(lebar, panjang):
    with open("rumah.json", encoding="utf-8") as f:
        data = json.load(f)

    baru = sesuaikan_dimensi_rumah(data, lebar, panjang)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(baru, tmp)
        tmp_name = tmp.name

    try:
        rumah = muat_rumah(tmp_name)
        assert len(rumah.dinding) == 10
        # Cek bounding box
        xs = [p[0] for d in rumah.dinding for p in (d.a, d.b)]
        ys = [p[1] for d in rumah.dinding for p in (d.a, d.b)]
        assert max(xs) == lebar
        assert max(ys) == panjang
    finally:
        Path(tmp_name).unlink(missing_ok=True)

