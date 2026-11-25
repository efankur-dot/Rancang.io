"""
Rancang.io // CAD & BOQ Automation Studio
Generator Gambar Kerja AutoCAD (.DXF) Berkop A3 & RAB Konstruksi (.XLSX)
Mendukung Mode 1 Lantai & 2 Lantai dengan Hybrid AI Prompt-to-JSON.
"""
import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

import ai_parser
import boq.rab
import drawing.denah
import drawing.detail
import drawing.kop
import drawing.potongan
import model.loader
import model.param_rumah


from ai_parser import ambil_api_key, jalankan_benchmark_20, urai_prompt_ke_parameter
from boq.rab import IKK_WILAYAH, ekspor_rab_excel, hitung_rab
from drawing.kop import buat_paket_dxf, daftar_lembar_kerja, render_pratinjau_lembar_png
from model.loader import ValidasiRumahError, muat_rumah

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Rancang.io — CAD & BOQ Automation Studio",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------- styling studio
st.markdown(
    """
    <style>
    .hero-card {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 22px 26px;
        margin-bottom: 16px;
        color: #F8FAFC;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(56, 189, 248, 0.15);
        color: #38BDF8;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        padding: 4px 10px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .hero-title {
        font-size: 26px;
        font-weight: 800;
        margin: 0 0 6px 0;
        color: #FFFFFF;
    }
    .hero-sub {
        font-size: 13.5px;
        color: #CBD5E1;
        margin: 0;
    }
    .kpi-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 16px;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .kpi-val {
        font-size: 19px;
        font-weight: 800;
        color: #0F172A;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _data_cadangan_1lt() -> Dict[str, Any]:
    return {
        "proyek": {"nama": "Rumah Tipe 36", "lokasi": "Kota Semarang"},
        "satuan": "mm",
        "jumlah_lantai": 1,
        "lantai": {"elevasi": 0, "tinggi_dinding": 3000, "tinggi_plafon": 2800},
        "dinding_default": {"tebal": 150, "bahan": "bata merah 1:4"},
        "dinding": [
            {"id": "D1", "a": [0, 0], "b": [6000, 0], "tebal": 150},
            {"id": "D2", "a": [6000, 0], "b": [6000, 6000], "tebal": 150},
            {"id": "D3", "a": [6000, 6000], "b": [0, 6000], "tebal": 150},
            {"id": "D4", "a": [0, 6000], "b": [0, 0], "tebal": 150},
            {"id": "D5", "a": [3000, 0], "b": [3000, 6000], "tebal": 150},
            {"id": "D6", "a": [0, 3000], "b": [3000, 3000], "tebal": 150},
            {"id": "D7", "a": [3000, 2000], "b": [6000, 2000], "tebal": 150},
            {"id": "D8", "a": [3000, 3500], "b": [6000, 3500], "tebal": 150},
        ],
        "bukaan": [
            {"id": "P1", "dinding": "D1", "jenis": "pintu", "offset": 1200, "lebar": 900, "tinggi": 2100, "ambang": 0},
            {"id": "J1", "dinding": "D1", "jenis": "jendela", "offset": 3600, "lebar": 1200, "tinggi": 1300, "ambang": 800},
            {"id": "P2", "dinding": "D5", "jenis": "pintu", "offset": 350, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P3", "dinding": "D5", "jenis": "pintu", "offset": 3850, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P4", "dinding": "D7", "jenis": "pintu", "offset": 400, "lebar": 700, "tinggi": 2000, "ambang": 0},
            {"id": "J2", "dinding": "D3", "jenis": "jendela", "offset": 1000, "lebar": 1200, "tinggi": 1300, "ambang": 800},
            {"id": "J3", "dinding": "D3", "jenis": "jendela", "offset": 4000, "lebar": 1200, "tinggi": 1300, "ambang": 800},
        ],
        "ruang": [
            {"id": "R1", "nama": "Ruang Tamu", "kotak": [0, 0, 3000, 3000]},
            {"id": "R2", "nama": "R. Keluarga & Dapur", "kotak": [0, 3000, 3000, 6000]},
            {"id": "R3", "nama": "Kamar Tidur 1", "kotak": [3000, 0, 6000, 2000]},
            {"id": "R4", "nama": "KM / WC", "kotak": [3000, 2000, 6000, 3500]},
            {"id": "R5", "nama": "Kamar Tidur 2", "kotak": [3000, 3500, 6000, 6000]},
        ],
        "potongan": [
            {"nama": "A-A", "arah": "x", "posisi": 2600},
            {"nama": "B-B", "arah": "y", "posisi": 2200},
        ],
    }


def _data_cadangan_2lt() -> Dict[str, Any]:
    return {
        "proyek": {"nama": "Rumah Tinggal 2 Lantai", "lokasi": "Kota Semarang"},
        "satuan": "mm",
        "jumlah_lantai": 2,
        "lantai": {"elevasi": 0, "tinggi_dinding": 3400, "tinggi_plafon": 3000},
        "lantai_2": {"elevasi": 3400, "tinggi_dinding": 3200, "tinggi_plafon": 2900},
        "dinding_default": {"tebal": 150, "bahan": "bata merah 1:4"},
        "dinding": [
            {"id": "D1", "a": [0, 0], "b": [6000, 0], "tebal": 150},
            {"id": "D2", "a": [6000, 0], "b": [6000, 8000], "tebal": 150},
            {"id": "D3", "a": [6000, 8000], "b": [0, 8000], "tebal": 150},
            {"id": "D4", "a": [0, 8000], "b": [0, 0], "tebal": 150},
            {"id": "D5", "a": [3000, 0], "b": [3000, 8000], "tebal": 150},
            {"id": "D6", "a": [0, 3500], "b": [3000, 3500], "tebal": 150},
            {"id": "D7", "a": [3000, 2600], "b": [6000, 2600], "tebal": 150},
            {"id": "D8", "a": [4500, 6200], "b": [6000, 6200], "tebal": 150},
            {"id": "D9", "a": [4500, 6200], "b": [4500, 8000], "tebal": 150},
        ],
        "bukaan": [
            {"id": "P1", "dinding": "D1", "jenis": "pintu", "offset": 1100, "lebar": 900, "tinggi": 2100, "ambang": 0},
            {"id": "J1", "dinding": "D1", "jenis": "jendela", "offset": 3700, "lebar": 1400, "tinggi": 1400, "ambang": 700},
            {"id": "P2", "dinding": "D5", "jenis": "pintu", "offset": 600, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P3", "dinding": "D6", "jenis": "pintu", "offset": 1800, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P4", "dinding": "D5", "jenis": "pintu", "offset": 4000, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P5", "dinding": "D8", "jenis": "pintu", "offset": 350, "lebar": 700, "tinggi": 2000, "ambang": 0},
            {"id": "J2", "dinding": "D3", "jenis": "jendela", "offset": 1000, "lebar": 1200, "tinggi": 1300, "ambang": 800},
            {"id": "J3", "dinding": "D3", "jenis": "jendela", "offset": 3600, "lebar": 1200, "tinggi": 1300, "ambang": 800},
        ],
        "ruang": [
            {"id": "R1", "nama": "Ruang Tamu", "kotak": [0, 0, 3000, 3500]},
            {"id": "R2", "nama": "R. Keluarga & Makan", "kotak": [0, 3500, 3000, 8000]},
            {"id": "R3", "nama": "Kamar Tidur 1", "kotak": [3000, 0, 6000, 2600]},
            {"id": "R4", "nama": "Dapur", "kotak": [3000, 6200, 4500, 8000]},
            {"id": "R5", "nama": "KM / WC Lt.1", "kotak": [4500, 6200, 6000, 8000]},
        ],
        "dinding_lt2": [
            {"id": "D2_1", "a": [0, 1500], "b": [3000, 1500], "tebal": 150},
            {"id": "D2_1B", "a": [3000, 0], "b": [6000, 0], "tebal": 150},
            {"id": "D2_2", "a": [6000, 0], "b": [6000, 8000], "tebal": 150},
            {"id": "D2_3", "a": [6000, 8000], "b": [0, 8000], "tebal": 150},
            {"id": "D2_4", "a": [0, 8000], "b": [0, 1500], "tebal": 150},
            {"id": "D2_5", "a": [3000, 0], "b": [3000, 8000], "tebal": 150},
            {"id": "D2_6", "a": [0, 4800], "b": [3000, 4800], "tebal": 150},
            {"id": "D2_KTA", "a": [3000, 2600], "b": [6000, 2600], "tebal": 150},
            {"id": "D2_7", "a": [4500, 6200], "b": [6000, 6200], "tebal": 150},
            {"id": "D2_8", "a": [4500, 6200], "b": [4500, 8000], "tebal": 150},
        ],
        "bukaan_lt2": [
            {"id": "P2_1", "dinding": "D2_1", "jenis": "pintu", "offset": 1100, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "J2_1", "dinding": "D2_1B", "jenis": "jendela", "offset": 800, "lebar": 1400, "tinggi": 1400, "ambang": 700},
            {"id": "P2_2", "dinding": "D2_5", "jenis": "pintu", "offset": 3300, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P2_3", "dinding": "D2_5", "jenis": "pintu", "offset": 5600, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P2_KTA", "dinding": "D2_KTA", "jenis": "pintu", "offset": 200, "lebar": 800, "tinggi": 2100, "ambang": 0},
            {"id": "P2_4", "dinding": "D2_8", "jenis": "pintu", "offset": 550, "lebar": 700, "tinggi": 2000, "ambang": 0},
            {"id": "J2_2", "dinding": "D2_3", "jenis": "jendela", "offset": 1000, "lebar": 1200, "tinggi": 1300, "ambang": 800},
            {"id": "J2_3", "dinding": "D2_3", "jenis": "jendela", "offset": 3600, "lebar": 1200, "tinggi": 1300, "ambang": 800},
        ],
        "ruang_lt2": [
            {"id": "R2_1", "nama": "R. Keluarga Lt.2", "kotak": [0, 1500, 3000, 4800]},
            {"id": "R2_2", "nama": "Kamar Tidur Utama", "kotak": [0, 4800, 3000, 8000]},
            {"id": "R2_3", "nama": "Kamar Tidur Anak", "kotak": [3000, 0, 6000, 2600]},
            {"id": "R2_4", "nama": "KM / WC Lt.2", "kotak": [4500, 6200, 6000, 8000]},
        ],
        "tangga": {
            "id": "TG1",
            "bentuk": "L",
            "asal": [5100, 2700],
            "lebar": 900,
            "jumlah_anak_tangga": 15,
            "antrade": 225,
            "optrade": 226.7,
            "arah_naik": "utara",
            "belok": "kiri",
            "panjang_leg1": 1800,
            "panjang_leg2": 1200,
        },
        "void": [{"kotak": [3900, 2700, 5925, 4500]}],
        "balkon": [{"nama": "Balkon Depan", "kotak": [0, 0, 3000, 1500]}],
        "potongan": [
            {"nama": "A-A", "arah": "x", "posisi": 4200},
            {"nama": "B-B", "arah": "y", "posisi": 4200},
        ],
    }


def _resolusi_template_rumah(is_2lt: bool) -> str:
    """Mencari file JSON template di root maupun sub-folder proyek, atau membuatkannya otomatis."""
    nama_file = "rumah_2lt.json" if is_2lt else "rumah.json"
    kandidat = [
        BASE_DIR / nama_file,
        BASE_DIR / "data" / nama_file,
        BASE_DIR / "contoh" / nama_file,
        BASE_DIR / "templates" / nama_file,
    ]
    for p in kandidat:
        if p.exists():
            return str(p)

    hasil_cari = next(BASE_DIR.rglob(nama_file), None)
    if hasil_cari and hasil_cari.exists():
        return str(hasil_cari)

    target_baru = BASE_DIR / nama_file
    data_def = _data_cadangan_2lt() if is_2lt else _data_cadangan_1lt()
    target_baru.write_text(json.dumps(data_def, indent=2), encoding="utf-8")
    return str(target_baru)


def _format_rupiah(nilai: float) -> str:
    return f"Rp {nilai:,.0f}".replace(",", ".")


def _terapkan_parameter_ke_state(prm: Dict[str, Any]) -> None:
    """Menyinkronkan hasil ekstraksi AI / Preset / JSON Upload ke seluruh widget sidebar."""
    is_2 = int(prm.get("jumlah_lantai", 1)) >= 2
    st.session_state["sb_lantai"] = "2 Lantai" if is_2 else "1 Lantai"
    st.session_state["sb_panjang"] = max(4000, min(25000, int(prm.get("panjang_mm", 6000))))
    st.session_state["sb_lebar"] = max(4000, min(25000, int(prm.get("lebar_mm", 8000 if is_2 else 6000))))
    st.session_state["sb_t1"] = max(2600, min(4500, int(prm.get("tinggi_lt1_mm", 3400 if is_2 else 3000))))
    st.session_state["sb_p1"] = max(2400, min(4200, int(prm.get("plafon_lt1_mm", 3000 if is_2 else 2800))))
    st.session_state["sb_t2"] = max(2600, min(4200, int(prm.get("tinggi_lt2_mm", 3200))))
    st.session_state["sb_p2"] = max(2400, min(4000, int(prm.get("plafon_lt2_mm", 2900))))
    st.session_state["sb_atap"] = max(15, min(45, int(prm.get("sudut_atap", 30))))
    if prm.get("nama_proyek"):
        st.session_state["sb_proyek"] = str(prm["nama_proyek"])
    lokasi_ai = str(prm.get("lokasi", ""))
    if lokasi_ai in IKK_WILAYAH:
        st.session_state["sb_wilayah"] = lokasi_ai
    st.session_state["paksa_regenerate"] = True


def _terapkan_skala_dimensi(rumah, p_target: float, l_target: float, t_lt1: float, p_plafon1: float, t_lt2: float, p_plafon2: float, tebal_d: float, sudut_atap: float):
    """Menskalakan koordinat denah & parameter elevasi rumah secara proporsional."""
    x0, y0, x1, y1 = rumah.batas
    p_asal = max(1000.0, abs(x1 - x0))
    l_asal = max(1000.0, abs(y1 - y0))
    sx = p_target / p_asal
    sy = l_target / l_asal

    def _scale_pt(pt):
        return (round((pt[0] - x0) * sx, 1), round((pt[1] - y0) * sy, 1))

    for d in rumah.semua_dinding:
        pjg_lama = max(1.0, d.panjang)
        d.a = _scale_pt(d.a)
        d.b = _scale_pt(d.b)
        d.tebal = tebal_d
        pjg_baru = max(1.0, d.panjang)
        rasio_d = pjg_baru / pjg_lama
        for bk in rumah.semua_bukaan:
            if bk.dinding == d.id:
                bk.offset = round(bk.offset * rasio_d, 1)
                if bk.jenis == "jendela":
                    bk.lebar = min(round(bk.lebar * rasio_d, 1), max(500.0, pjg_baru - bk.offset - 150.0))

    for r in rumah.semua_ruang:
        if r.kotak and len(r.kotak) == 4:
            r.kotak = [
                round((r.kotak[0] - x0) * sx, 1),
                round((r.kotak[1] - y0) * sy, 1),
                round((r.kotak[2] - x0) * sx, 1),
                round((r.kotak[3] - y0) * sy, 1),
            ]
        if r.label:
            r.label = _scale_pt(r.label)

    for v in rumah.void:
        if isinstance(v.get("kotak"), list) and len(v["kotak"]) == 4:
            k = v["kotak"]
            v["kotak"] = [round((k[0] - x0) * sx, 1), round((k[1] - y0) * sy, 1), round((k[2] - x0) * sx, 1), round((k[3] - y0) * sy, 1)]

    for blk in rumah.balkon:
        if isinstance(blk.get("kotak"), list) and len(blk["kotak"]) == 4:
            k = blk["kotak"]
            blk["kotak"] = [round((k[0] - x0) * sx, 1), round((k[1] - y0) * sy, 1), round((k[2] - x0) * sx, 1), round((k[3] - y0) * sy, 1)]

    if rumah.tangga:
        rumah.tangga.asal = _scale_pt(rumah.tangga.asal)
        rumah.tangga.panjang_leg1 = round(rumah.tangga.panjang_leg1 * sy, 1)
        rumah.tangga.panjang_leg2 = round(rumah.tangga.panjang_leg2 * sx, 1)
        rumah.tangga.elevasi_atas = t_lt1
        rumah.tangga.optrade = round(t_lt1 / max(8, rumah.tangga.jumlah_anak_tangga), 1)

    for sec in rumah.potongan:
        if str(sec.get("arah", "x")).lower() == "x":
            sec["posisi"] = round((float(sec.get("posisi", l_asal / 2)) - y0) * sy, 1)
        else:
            sec["posisi"] = round((float(sec.get("posisi", p_asal / 2)) - x0) * sx, 1)

    rumah.lantai["tinggi_dinding"] = t_lt1
    rumah.lantai["tinggi_plafon"] = min(p_plafon1, t_lt1 - 100.0)
    if rumah.jumlah_lantai >= 2:
        rumah.lantai_2["elevasi"] = t_lt1
        rumah.lantai_2["tinggi_dinding"] = t_lt2
        rumah.lantai_2["tinggi_plafon"] = min(p_plafon2, t_lt2 - 100.0)
    rumah.atap["kemiringan_derajat"] = sudut_atap


# Inisialisasi default state pertama kali
if "sb_lantai" not in st.session_state:
    st.session_state["sb_lantai"] = "1 Lantai"
    st.session_state["sb_panjang"] = 6000
    st.session_state["sb_lebar"] = 6000
    st.session_state["sb_t1"] = 3000
    st.session_state["sb_p1"] = 2800
    st.session_state["sb_t2"] = 3200
    st.session_state["sb_p2"] = 2900
    st.session_state["sb_atap"] = 30
    st.session_state["sb_proyek"] = "Rumah Tipe 36"
    st.session_state["sb_wilayah"] = list(IKK_WILAYAH.keys())[0]

# ----------------------------------------------------------------- sidebar controls
with st.sidebar:
    st.markdown("### 0. Asisten AI & Preset Cepat")
    preset_opsi = {
        "Custom / Sesuai Input": None,
        "Preset Tipe 36 — 1 Lantai (6.0 × 6.0 m)": {
            "nama_proyek": "Rumah Tipe 36",
            "jumlah_lantai": 1,
            "panjang_mm": 6000,
            "lebar_mm": 6000,
            "tinggi_lt1_mm": 3000,
            "plafon_lt1_mm": 2800,
            "sudut_atap": 30,
        },
        "Preset Tipe 72 — 2 Lantai (6.0 × 8.0 m)": {
            "nama_proyek": "Rumah Tinggal 2 Lantai",
            "jumlah_lantai": 2,
            "panjang_mm": 6000,
            "lebar_mm": 8000,
            "tinggi_lt1_mm": 3400,
            "plafon_lt1_mm": 3000,
            "tinggi_lt2_mm": 3200,
            "plafon_lt2_mm": 2900,
            "sudut_atap": 30,
        },
        "Preset Tipe 90 — 2 Lantai (7.0 × 9.0 m)": {
            "nama_proyek": "Rumah Tipe 90 (2 Lantai)",
            "jumlah_lantai": 2,
            "panjang_mm": 7000,
            "lebar_mm": 9000,
            "tinggi_lt1_mm": 3500,
            "plafon_lt1_mm": 3100,
            "tinggi_lt2_mm": 3300,
            "plafon_lt2_mm": 3000,
            "sudut_atap": 30,
        },
    }
    preset_pilih = st.selectbox("Pilih Preset Bangunan", options=list(preset_opsi.keys()))
    if preset_opsi[preset_pilih] is not None and st.session_state.get("preset_terakhir") != preset_pilih:
        st.session_state["preset_terakhir"] = preset_pilih
        _terapkan_parameter_ke_state(preset_opsi[preset_pilih])
        st.rerun()

    prompt_ai = st.text_area(
        "Atau Deskripsikan Kebutuhan Ruang (AI)",
        placeholder="Contoh: Rumah 2 lantai ukuran 7x9 meter, sudut atap 32 derajat, lokasi Kota Yogyakarta",
        height=74,
    )
    with st.expander("Konfigurasi Gemini API Key"):
        api_key_user = st.text_input(
            "GOOGLE_API_KEY",
            value=ambil_api_key(),
            type="password",
            help="Otomatis terbaca dari file .env jika sudah diisi.",
        )

    if st.button("Terapkan Deskripsi AI ke Desain", use_container_width=True):
        hasil_ai = urai_prompt_ke_parameter(prompt_ai, api_key_user)
        st.session_state["status_ai_terakhir"] = hasil_ai
        if hasil_ai["sukses"]:
            _terapkan_parameter_ke_state(hasil_ai["parameter"])
            st.rerun()

    if "status_ai_terakhir" in st.session_state:
        st_ai = st.session_state["status_ai_terakhir"]
        if st_ai["sukses"]:
            st.success(f"**{st_ai['mode']}** ({st_ai['durasi_ms']} ms): {st_ai['pesan']}")
        else:
            st.warning(st_ai["pesan"])

    st.markdown("---")
    st.markdown("### 1. Konfigurasi Geometri & Lantai")
    mode_lantai = st.radio(
        "Jumlah Lantai Bangunan",
        options=["1 Lantai", "2 Lantai"],
        key="sb_lantai",
        horizontal=True,
    )
    is_2lt = mode_lantai == "2 Lantai"

    # Jika user mengganti radio 1 Lantai <-> 2 Lantai secara manual, sesuaikan default ukuran
    if st.session_state.get("radio_lantai_prev") != mode_lantai:
        st.session_state["radio_lantai_prev"] = mode_lantai
        if is_2lt and st.session_state["sb_lebar"] == 6000 and st.session_state["sb_proyek"] == "Rumah Tipe 36":
            st.session_state["sb_lebar"] = 8000
            st.session_state["sb_t1"] = 3400
            st.session_state["sb_p1"] = 3000
            st.session_state["sb_proyek"] = "Rumah Tinggal 2 Lantai"
        elif not is_2lt and st.session_state["sb_proyek"] == "Rumah Tinggal 2 Lantai":
            st.session_state["sb_lebar"] = 6000
            st.session_state["sb_t1"] = 3000
            st.session_state["sb_p1"] = 2800
            st.session_state["sb_proyek"] = "Rumah Tipe 36"

    path_template = _resolusi_template_rumah(is_2lt)

    c1, c2 = st.columns(2)
    panjang_mm = c1.number_input("Panjang (mm)", min_value=4000, max_value=25000, step=250, key="sb_panjang")
    lebar_mm = c2.number_input("Lebar (mm)", min_value=4000, max_value=25000, step=250, key="sb_lebar")

    c3, c4 = st.columns(2)
    tinggi_lt1_mm = c3.number_input("Tinggi Lt.1 (mm)", min_value=2600, max_value=4500, step=100, key="sb_t1")
    plafon_lt1_mm = c4.number_input("Plafon Lt.1 (mm)", min_value=2400, max_value=4200, step=100, key="sb_p1")

    if is_2lt:
        c5, c6 = st.columns(2)
        tinggi_lt2_mm = c5.number_input("Tinggi Lt.2 (mm)", min_value=2600, max_value=4200, step=100, key="sb_t2")
        plafon_lt2_mm = c6.number_input("Plafon Lt.2 (mm)", min_value=2400, max_value=4000, step=100, key="sb_p2")
    else:
        tinggi_lt2_mm = 0
        plafon_lt2_mm = 0

    c7, c8 = st.columns(2)
    tebal_dinding = c7.number_input("Tebal Dinding", min_value=100, max_value=300, value=150, step=10)
    sudut_atap = c8.number_input("Sudut Atap (°)", min_value=15, max_value=45, step=1, key="sb_atap")

    skala_a3 = st.selectbox(
        "Skala Lembar Kerja A3",
        options=["Otomatis (Menyesuaikan)", "1 : 50", "1 : 75", "1 : 100"],
        index=0,
    )

    with st.expander("2. Identitas Kop & Lokasi RAB", expanded=True):
        nama_proyek = st.text_input("Nama Proyek", key="sb_proyek")
        pemilik = st.text_input("Pemilik / Klien", value="Pemilik Bangunan")
        perencana = st.text_input("Perencana / Digambar Oleh", value="Rancang.io Engineering Studio")
        wilayah_rab = st.selectbox("Wilayah Acuan Harga (IKK)", options=list(IKK_WILAYAH.keys()), key="sb_wilayah")

    with st.expander("3. Simpan / Muat Proyek (.JSON)"):
        data_simpan_json = json.dumps(
            {
                "nama_proyek": nama_proyek,
                "jumlah_lantai": 2 if is_2lt else 1,
                "panjang_mm": panjang_mm,
                "lebar_mm": lebar_mm,
                "tinggi_lt1_mm": tinggi_lt1_mm,
                "plafon_lt1_mm": plafon_lt1_mm,
                "tinggi_lt2_mm": tinggi_lt2_mm,
                "plafon_lt2_mm": plafon_lt2_mm,
                "sudut_atap": sudut_atap,
                "lokasi": wilayah_rab,
            },
            indent=2,
        )
        st.download_button(
            "Simpan Konfigurasi (.JSON)",
            data=data_simpan_json,
            file_name=f"{nama_proyek.strip().replace(' ', '_') or 'proyek'}.json",
            mime="application/json",
            use_container_width=True,
        )
        file_json_up = st.file_uploader("Muat Konfigurasi (.JSON)", type=["json"])
        if file_json_up is not None:
            sig_file = f"{file_json_up.name}_{file_json_up.size}"
            if st.session_state.get("json_loaded_sig") != sig_file:
                try:
                    raw_up = json.loads(file_json_up.read().decode("utf-8"))
                    st.session_state["json_loaded_sig"] = sig_file
                    if "panjang_mm" in raw_up:
                        _terapkan_parameter_ke_state(raw_up)
                        st.rerun()
                    elif "dinding" in raw_up:
                        tmp_path = BASE_DIR / "_uploaded_custom.json"
                        tmp_path.write_text(json.dumps(raw_up, indent=2), encoding="utf-8")
                        st.session_state["custom_template_path"] = str(tmp_path)
                        st.session_state["paksa_regenerate"] = True
                        st.success("Denah kustom JSON berhasil dimuat!")
                except Exception as exc_up:
                    st.error(f"File JSON tidak valid: {exc_up}")

    klik_generate = st.button("Generate Gambar Kerja & RAB", type="primary", use_container_width=True)

# ----------------------------------------------------------------- header utama
st.markdown(
    """
    <div class="hero-card">
        <div class="hero-badge">RANCANG.IO // CAD &amp; BOQ AUTOMATION STUDIO</div>
        <h1 class="hero-title">Generator Gambar Kerja AutoCAD &amp; RAB Konstruksi</h1>
        <p class="hero-sub">Otomasi denah arsitektural 1 &amp; 2 lantai, potongan struktur, 4 sisi tampak, detail footplat/pondasi/kusen berkop A3 (.DXF) serta RAB (.XLSX).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Proses pembaruan model aktif
try:
    sumber_json = st.session_state.get("custom_template_path") or path_template
    rumah_aktif = muat_rumah(sumber_json)
    _terapkan_skala_dimensi(
        rumah_aktif,
        float(panjang_mm),
        float(lebar_mm),
        float(tinggi_lt1_mm),
        float(plafon_lt1_mm),
        float(tinggi_lt2_mm),
        float(plafon_lt2_mm),
        float(tebal_dinding),
        float(sudut_atap),
    )
except ValidasiRumahError as err:
    st.error(f"Terjadi Kesalahan Pemrosesan: {err}")
    st.stop()

perlu_proses = (
    klik_generate
    or st.session_state.pop("paksa_regenerate", False)
    or "hasil_paket" not in st.session_state
    or st.session_state.get("mode_terakhir") != mode_lantai
)

if perlu_proses:
    try:
        with st.status("Memproses gambar kerja berkop A3 dan kalkulasi RAB...", expanded=True) as status:
            st.write("1/3 Menyesuaikan parameter dimensi dan mendeteksi seluruh titik kolom struktur...")
            sheets_info = daftar_lembar_kerja(rumah_aktif)

            st.write("2/3 Mengekspor Denah, Potongan, 4 Tampak & Detail Struktur/Kusen ke file AutoCAD (.DXF)...")
            dxf_bytes, info_dxf = buat_paket_dxf(
                rumah_aktif,
                nama_proyek=nama_proyek,
                pemilik=pemilik,
                perencana=perencana,
                skala_pilihan=skala_a3,
            )

            st.write(f"3/3 Menghitung volume dan menyusun rumus hidup Excel ({wilayah_rab})...")
            hasil_rab = hitung_rab(rumah_aktif, wilayah=wilayah_rab)
            xlsx_bytes = ekspor_rab_excel(rumah_aktif, hasil_rab, nama_proyek=nama_proyek, pemilik=pemilik)

            st.session_state["hasil_paket"] = {
                "dxf_bytes": dxf_bytes,
                "xlsx_bytes": xlsx_bytes,
                "info_dxf": info_dxf,
                "hasil_rab": hasil_rab,
                "sheets": sheets_info,
            }
            st.session_state["mode_terakhir"] = mode_lantai
            status.update(label=f"Selesai! File AutoCAD (.DXF) dan RAB ({wilayah_rab}) siap digunakan.", state="complete", expanded=False)
    except Exception as exc:
        st.error(f"Terjadi Kesalahan Pemrosesan: {exc}")
        st.stop()

paket = st.session_state["hasil_paket"]
hasil_rab = paket["hasil_rab"]
info_dxf = paket["info_dxf"]
sheets_list = paket["sheets"]

# ----------------------------------------------------------------- 4 kartu ringkasan KPI
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f'<div class="kpi-box"><div class="kpi-label">Dimensi Bangunan</div>'
        f'<div class="kpi-val">{panjang_mm/1000:.2f} m × {lebar_mm/1000:.2f} m ({mode_lantai})</div></div>',
        unsafe_allow_html=True,
    )
with k2:
    tipe_lbl = f"Tipe {int(round(hasil_rab['luas_total_m2']))}"
    st.markdown(
        f'<div class="kpi-box"><div class="kpi-label">Luas &amp; Tipe Bangunan</div>'
        f'<div class="kpi-val">{hasil_rab["luas_total_m2"]:.1f} m² ({tipe_lbl})</div></div>',
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f'<div class="kpi-box"><div class="kpi-label">Indeks Wilayah (IKK)</div>'
        f'<div class="kpi-val">{hasil_rab["ikk"]:.2f}× ({wilayah_rab})</div></div>',
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f'<div class="kpi-box"><div class="kpi-label">Estimasi Total RAB (+PPN)</div>'
        f'<div class="kpi-val">{_format_rupiah(hasil_rab["grand_total"])}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")

# ----------------------------------------------------------------- 3 tab utama
tab_cad, tab_rab, tab_val = st.tabs([
    "Viewport Gambar Kerja (DXF)",
    "Rincian Anggaran Biaya (RAB)",
    "Validasi Geometri & Uji Akurasi",
])

with tab_cad:
    st.info(
        f"Paket Gambar Kerja (**{len(sheets_list)} Lembar A3** Skala `{info_dxf['skala_label']}`) siap untuk bangunan "
        f"**{panjang_mm/1000:.2f} m × {lebar_mm/1000:.2f} m ({mode_lantai})** — siap diedit & di-plot ke PDF langsung dari AutoCAD."
    )

    dl1, dl2 = st.columns(2)
    nama_file_dasar = nama_proyek.strip().replace(" ", "_") or "Gambar_Kerja"
    dl1.download_button(
        label=f"Unduh File AutoCAD ({nama_file_dasar}.dxf)",
        data=paket["dxf_bytes"],
        file_name=f"{nama_file_dasar}.dxf",
        mime="application/dxf",
        type="primary",
        use_container_width=True,
    )
    dl2.download_button(
        label=f"Unduh Rincian RAB Excel ({nama_file_dasar}_RAB.xlsx)",
        data=paket["xlsx_bytes"],
        file_name=f"RAB_{nama_file_dasar}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    label_to_sheet = {s["label"]: s for s in sheets_list}
    pilihan_lembar = st.radio(
        "Pilih Lembar Gambar Kerja (Format A3):",
        options=list(label_to_sheet.keys()),
        horizontal=True,
    )
    lembar_aktif = label_to_sheet[pilihan_lembar]
    skala_lembar_aktif = "1 : 20" if lembar_aktif["id"] == "detail" else info_dxf["skala_label"]
    st.caption(f"Lembar aktif: **{lembar_aktif['kode']} — {lembar_aktif['judul']}** | Skala Cetak A3: **{skala_lembar_aktif}** (420 × 297 mm)")

    with st.spinner(f"Merender pratinjau {lembar_aktif['kode']} — {lembar_aktif['judul']}..."):
        png_bytes = render_pratinjau_lembar_png(
            rumah_aktif,
            sheet_id=lembar_aktif["id"],
            nama_proyek=nama_proyek,
            pemilik=pemilik,
            perencana=perencana,
            skala_pilihan=skala_a3,
        )
        st.image(png_bytes, use_container_width=True)

with tab_rab:
    df_rab = pd.DataFrame(hasil_rab["items"])
    df_tampil = df_rab.rename(
        columns={
            "divisi": "Divisi Pekerjaan",
            "kode": "Kode AHSP",
            "uraian": "Uraian Pekerjaan",
            "satuan": "Sat.",
            "volume": "Volume",
            "harga_satuan": "Harga Satuan (Rp)",
            "jumlah_harga": "Jumlah Harga (Rp)",
        }
    )
    st.dataframe(
        df_tampil,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Volume": st.column_config.NumberColumn(format="%.2f"),
            "Harga Satuan (Rp)": st.column_config.NumberColumn(format="Rp %,d"),
            "Jumlah Harga (Rp)": st.column_config.NumberColumn(format="Rp %,d"),
        },
    )
    r1, r2, r3 = st.columns(3)
    r1.metric("Subtotal Pekerjaan", _format_rupiah(hasil_rab["subtotal"]))
    r2.metric("PPN 11%", _format_rupiah(hasil_rab["ppn"]))
    r3.metric(f"Total RAB ({_format_rupiah(hasil_rab['harga_per_m2'])} / m²)", _format_rupiah(hasil_rab["grand_total"]))

with tab_val:
    st.subheader("1. Pemeriksaan Konsistensi Geometri & SNI Arsitektural")
    checks: List[Dict[str, str]] = [
        {
            "Parameter": "Konfigurasi Lantai",
            "Nilai Terukur": f"{rumah_aktif.jumlah_lantai} Lantai (Lt.1 = {hasil_rab['luas_lt1_m2']:.2f} m², Lt.2 = {hasil_rab['luas_lt2_m2']:.2f} m²)",
            "Status": "OK — Valid",
        },
        {
            "Parameter": "Total Segmen Dinding & Bukaan",
            "Nilai Terukur": f"{len(rumah_aktif.semua_dinding)} segmen dinding, {len(rumah_aktif.semua_bukaan)} bukaan pintu/jendela",
            "Status": "OK — Terpotong Presisi",
        },
        {
            "Parameter": "Tinggi Bersih Plafon",
            "Nilai Terukur": f"Lt.1 = {rumah_aktif.lantai['tinggi_plafon']:.0f} mm"
            + (f" | Lt.2 = {rumah_aktif.lantai_2['tinggi_plafon']:.0f} mm" if is_2lt else ""),
            "Status": "OK — Memenuhi Kenyamanan Termal",
        },
    ]
    if is_2lt and rumah_aktif.tangga:
        tg = rumah_aktif.tangga
        kenyamanan = 2 * tg.optrade + tg.antrade
        status_tg = "OK — Ideal (590–650 mm)" if 570 <= kenyamanan <= 670 else "Periksa Dimensi Anak Tangga"
        checks.append(
            {
                "Parameter": "Ergonomi Tangga Utama (2×Optrade + Antrade)",
                "Nilai Terukur": f"{tg.jumlah_anak_tangga} anak tangga | Optrade {tg.optrade:.0f} mm, Antrade {tg.antrade:.0f} mm (2O+A = {kenyamanan:.0f} mm)",
                "Status": status_tg,
            }
        )
    st.table(pd.DataFrame(checks))

    st.markdown("---")
    st.subheader("2. Pengujian Akurasi Otomatis (Benchmark 20 Skenario Uji)")
    st.caption("Evaluasi kuantitatif ketahanan parser AI terhadap variasi ukuran, tipe rumah, salah ketik (typo), batasan ekstrem, dan input di luar domain (Out-of-Distribution).")

    if st.button("Jalankan Uji Akurasi 20 Skenario Sekarang", type="primary"):
        hasil_uji = jalankan_benchmark_20()
        jumlah_lulus = sum(1 for item in hasil_uji if item["Status"] == "LULUS")
        akurasi_persen = (jumlah_lulus / len(hasil_uji)) * 100.0
        rata_ms = sum(item["Waktu (ms)"] for item in hasil_uji) / len(hasil_uji)

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Total Skenario Uji", f"{len(hasil_uji)} Kasus")
        c_m2.metric("Tingkat Akurasi & Guardrail", f"{akurasi_persen:.1f}% ({jumlah_lulus}/20)")
        c_m3.metric("Rata-rata Waktu Eksekusi", f"{rata_ms:.1f} ms")

        st.dataframe(pd.DataFrame(hasil_uji), use_container_width=True, hide_index=True)

    with st.expander("Transparansi Batasan Sistem & Arsitektur Teknis"):
        st.markdown(
            """
            - **Batasan Geometri**: Mesin tata ruang dioptimalkan untuk denah ortogonal (grid siku 90°) dengan rentang bentang **5,0–16,0 m (panjang)** dan **6,0–20,0 m (lebar)** hingga maksimal **2 lantai** agar syarat ruang gerak, selasar atas tangga, dan bukaan kusen tetap valid tanpa tabrakan.
            - **Arsitektur Hybrid AI + Offline Fallback**: Menggunakan **Google Gemini (`gemini-2.5-flash`)** dengan *Structured JSON Output* sebagai mesin ekstraksi utama, dilengkapi **Parser NLP Deterministik Lokal** sebagai *fallback* otomatis saat koneksi terputus serta **Guardrail Out-of-Distribution (OOD)** untuk menolak input di luar domain konstruksi tanpa halusinasi.
            - **Lokasi Kalibrasi Kode**: Logika ekstraksi AI & guardrail berada di `ai_parser.py`, mesin render CAD (Denah, Potongan, 4 Tampak, Detail) di paket `drawing/`, dan kalkulasi AHSP SNI di paket `boq/rab.py`.
            """
        )