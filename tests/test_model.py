import pytest
from model.dinding import Dinding
from model.bukaan import Bukaan
from model.ruang import Ruang
from model.rumah import Rumah


def test_dinding_properties():
    # Uji dinding horizontal
    d1 = Dinding(id="W1", a=(0, 0), b=(6000, 0), tipe="luar")
    assert d1.panjang == 6000.0

    # Uji dinding vertikal
    d2 = Dinding(id="W2", a=(6000, 0), b=(6000, 3000), tipe="dalam")
    assert d2.panjang == 3000.0

    # Uji dinding diagonal (segitiga 3-4-5)
    d3 = Dinding(id="W3", a=[0, 0], b=[3000, 4000])
    assert d3.panjang == 5000.0
    assert isinstance(d3.a, tuple)
    assert isinstance(d3.b, tuple)


def test_bukaan_properties():
    b = Bukaan(
        id="D1",
        jenis="pintu",
        dinding="W1",
        offset="1000",
        lebar="800",
        tinggi="2100",
        ambang="0"
    )
    assert b.offset == 1000.0
    assert b.lebar == 800.0
    assert b.tinggi == 2100.0
    assert b.ambang == 0.0
    assert b.akhir == 1800.0


def test_ruang_properties():
    r = Ruang(
        nama="Kamar Tidur 1",
        kotak=[0, 0, 3000, 4000],
        lantai="keramik 40x40"
    )
    assert r.panjang == 3000.0
    assert r.lebar == 4000.0
    assert r.luas == 12000000.0


def test_rumah_helpers():
    d1 = Dinding(id="W1", a=(0, 0), b=(3000, 0))
    d2 = Dinding(id="W2", a=(3000, 0), b=(3000, 3000))
    b1 = Bukaan(id="D1", jenis="pintu", dinding="W1", offset=500, lebar=800, tinggi=2100)
    b2 = Bukaan(id="J1", jenis="jendela", dinding="W1", offset=1500, lebar=1000, tinggi=1200)
    b3 = Bukaan(id="D2", jenis="pintu", dinding="W2", offset=500, lebar=800, tinggi=2100)

    rumah = Rumah(
        dinding=[d1, d2],
        bukaan=[b1, b2, b3]
    )

    assert rumah.cari_dinding("W1") == d1
    assert rumah.cari_dinding("W99") is None

    bukaan_w1 = rumah.bukaan_pada_dinding("W1")
    assert len(bukaan_w1) == 2
    assert b1 in bukaan_w1
    assert b2 in bukaan_w1

    bukaan_w2 = rumah.bukaan_pada_dinding("W2")
    assert len(bukaan_w2) == 1
    assert b3 in bukaan_w2

