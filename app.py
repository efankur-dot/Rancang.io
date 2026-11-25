"""
Rancang.io — Aplikasi Streamlit (Architectural CAD & BOQ Studio)
Isi data ukuran & wilayah -> Gambar DXF (denah, potongan, 4 tampak) + RAB Excel -> Buka di AutoCAD.
"""
import copy
import hashlib
import importlib
import io
import json
import os
import sys
import time
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

import drawing.denah
import drawing.potongan
importlib.reload(drawing.denah)
importlib.reload(drawing.potongan)

from boq.rab import buat_rab_excel, hitung_rab
from drawing.potongan import ekspor_gambar_lengkap
from model.loader import ValidasiRumahError, muat_rumah
from model.param_rumah import sesuaikan_dimensi_rumah

# Pastikan folder output dibuat relatif terhadap lokasi proyek
FOLDER = Path("hasil")
FOLDER.mkdir(exist_ok=True, parents=True)
IS_WINDOWS = sys.platform.startswith("win")

# Database Koefisien Wilayah (Indeks Kemahalan Konstruksi relatif terhadap Kab. Magelang = 1.00)
KOEFISIEN_WILAYAH = {
    "Kab. Magelang (Basis HSPK 2024)": 1.00,
    "Kota Yogyakarta": 1.03,
    "Kab. Sleman / Bantul": 1.02,
    "Kota Surakarta (Solo)": 1.02,
    "Kota Semarang": 1.06,
    "Kota Bandung": 1.12,
    "Kota Surabaya": 1.14,
    "Kota Malang": 1.08,
    "DKI Jakarta": 1.24,
    "Kota Denpasar (Bali)": 1.18,
    "Kota Medan": 1.10,
    "Kota Makassar": 1.13,
    "Kota Balikpapan / Kawasan IKN": 1.26,
}

PRESET_TIPE_RUMAH = {
    "Sesuai Data / Custom": None,
    "Tipe 36 — Standar (6.0 m × 6.0 m)": (6000, 6000),
    "Tipe 45 — Menengah (6.0 m × 7.5 m)": (6000, 7500),
    "Tipe 54 — Keluarga (6.0 m × 9.0 m)": (6000, 9000),
    "Tipe 60 — Luas (6.0 m × 10.0 m)": (6000, 10000),
    "Tipe 72 — Lebar (8.0 m × 9.0 m)": (8000, 9000),
}


def buka_di_autocad(path_dxf):
    """Buka DXF di AutoCAD lewat COM (Windows). Cadangan: aplikasi bawaan Windows."""
    path = str(Path(path_dxf).resolve())
    if not IS_WINDOWS:
        return "Buka otomatis hanya tersedia di Windows. Gunakan tombol Unduh DXF."
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            acad = win32com.client.Dispatch("AutoCAD.Application")
        acad.Visible = True
        for _ in range(15):
            try:
                acad.Documents.Open(path)
                acad.ZoomExtents()
                return "Berhasil terbuka di AutoCAD."
            except Exception:
                time.sleep(2)
    except Exception:
        pass
    os.startfile(path)
    return "Terbuka menggunakan aplikasi penampil CAD bawaan Windows."


@st.cache_data(show_spinner=False)
def pratinjau(path_dxf, bbox, versi):
    """Render satu bagian gambar dari file DXF (bbox = xmin, ymin, xmax, ymax) menjadi PNG."""
    x0, y0, x1, y1 = bbox
    doc = ezdxf.readfile(str(path_dxf))
    fig = plt.figure(figsize=(12, max(3.2, 12 * (y1 - y0) / max(1, (x1 - x0)))))
    ax = fig.add_axes([0, 0, 1, 1])
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return buf.getvalue()


@st.cache_data(show_spinner=False)
def render_live_blueprint(data_json_str, lebar_mm, panjang_mm, is_template):
    """Render pratinjau sketsa denah 2D secara instan sebelum proses generate DXF."""
    raw_data = json.loads(data_json_str)
    if is_template:
        preview_data = sesuaikan_dimensi_rumah(copy.deepcopy(raw_data), lebar_mm, panjang_mm)
    else:
        preview_data = raw_data

    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=120)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    dinding_list = preview_data.get("dinding", [])
    xs, ys = [], []

    for d in dinding_list:
        a = d.get("a", [0, 0])
        b = d.get("b", [0, 0])
        xs.extend([a[0], b[0]])
        ys.extend([a[1], b[1]])
        # Garis dinding utama
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#0F172A", linewidth=3.2, solid_capstyle="butt", zorder=3)
        # Titik simpul kolom di ujung dinding
        ax.scatter([a[0], b[0]], [a[1], b[1]], color="#1D4ED8", s=24, zorder=4)

    # Render bukaan (pintu / jendela) jika tersedia
    for bkn in preview_data.get("bukaan", []):
        pos = bkn.get("posisi") or bkn.get("a")
        if isinstance(pos, list) and len(pos) >= 2:
            ax.scatter([pos[0]], [pos[1]], color="#0284C7", marker="s", s=30, zorder=5)

    # Label ruangan jika tersedia
    for rg in preview_data.get("ruang", []):
        nama_r = rg.get("nama", "")
        titik = rg.get("label") or rg.get("center")
        if nama_r and isinstance(titik, list) and len(titik) >= 2:
            ax.text(
                titik[0], titik[1], nama_r.upper(),
                fontsize=7.5, fontweight="bold", color="#475569",
                ha="center", va="center", zorder=6
            )

    if xs and ys:
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        pad_x = max(600, (xmax - xmin) * 0.14)
        pad_y = max(600, (ymax - ymin) * 0.16)
        ax.set_xlim(xmin - pad_x, xmax + pad_x)
        ax.set_ylim(ymin - pad_y, ymax + pad_y)

        # Anotasi dimensi total (Lebar & Panjang)
        ax.annotate(
            "", xy=(xmin, ymin - pad_y * 0.45), xytext=(xmax, ymin - pad_y * 0.45),
            arrowprops=dict(arrowstyle="<->", color="#1D4ED8", lw=1.2)
        )
        ax.text(
            (xmin + xmax) / 2, ymin - pad_y * 0.65,
            f"LEBAR: {(xmax - xmin)/1000:.2f} m ({int(xmax - xmin)} mm)",
            ha="center", va="top", fontsize=8, fontweight="bold", color="#1D4ED8"
        )

        ax.annotate(
            "", xy=(xmin - pad_x * 0.45, ymin), xytext=(xmin - pad_x * 0.45, ymax),
            arrowprops=dict(arrowstyle="<->", color="#1D4ED8", lw=1.2)
        )
        ax.text(
            xmin - pad_x * 0.62, (ymin + ymax) / 2,
            f"PANJANG: {(ymax - ymin)/1000:.2f} m",
            ha="right", va="center", rotation=90, fontsize=8, fontweight="bold", color="#1D4ED8"
        )

    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linestyle="--", linewidth=0.5, color="#CBD5E1", alpha=0.8)
    ax.tick_params(axis="both", labelsize=7, colors="#64748B")
    for spine in ax.spines.values():
        spine.set_edgecolor("#CBD5E1")
        spine.set_linewidth(0.8)

    ax.set_title("PRATINJAU GEOMETRI DENAH (REAL-TIME WIREFRAME)", fontsize=9, fontweight="bold", color="#334155", pad=10)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return buf.getvalue()


def analisis_geometri_cepat(data_rumah, lebar_mm, panjang_mm, is_template):
    """Inspeksi kelengkapan simpul, panjang dinding, dan peringatan bentang kolom."""
    if not data_rumah:
        return {}
    d_cek = sesuaikan_dimensi_rumah(copy.deepcopy(data_rumah), lebar_mm, panjang_mm) if is_template else data_rumah
    dinding = d_cek.get("dinding", [])
    simpul = set()
    total_panjang_mm = 0.0
    bentang_lebar = []

    for idx, d in enumerate(dinding, start=1):
        a = d.get("a", [0, 0])
        b = d.get("b", [0, 0])
        simpul.add((round(a[0]), round(a[1])))
        simpul.add((round(b[0]), round(b[1])))
        pjg = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        total_panjang_mm += pjg
        if pjg > 3500:
            bentang_lebar.append(f"Segmen Dinding #{idx} memiliki bentang {pjg/1000:.2f} m (> 3.50 m, disarankan kolom praktis tambahan)")

    return {
        "jumlah_segmen": len(dinding),
        "jumlah_simpul": len(simpul),
        "total_panjang_m": total_panjang_mm / 1000.0,
        "jumlah_bukaan": len(d_cek.get("bukaan", [])),
        "peringatan_bentang": bentang_lebar,
        "data_aktif": d_cek,
    }


# -----------------------------------------------------------------
# KONFIGURASI HALAMAN & CUSTOM STUDIO CSS
# -----------------------------------------------------------------
st.set_page_config(
    page_title="Rancang.io — CAD & BOQ Automation Studio",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Sembunyikan elemen template bawaan Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}
    .stAppDeployButton {display: none;}

    /* Layout utama */
    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3rem;
        max-width: 1240px;
    }

    /* Header Studio Arsitektur */
    .studio-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: #FFFFFF;
        padding: 1.4rem 1.8rem;
        border-radius: 12px;
        margin-bottom: 1.25rem;
        border-left: 5px solid #2563EB;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    }
    .studio-badge {
        display: inline-block;
        background-color: rgba(37, 99, 235, 0.25);
        color: #93C5FD;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        padding: 3px 10px;
        border-radius: 4px;
        border: 1px solid rgba(147, 197, 253, 0.3);
        margin-bottom: 0.45rem;
    }
    .studio-title {
        font-size: 1.55rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.01em;
        color: #F8FAFC;
    }
    .studio-subtitle {
        font-size: 0.88rem;
        color: #CBD5E1;
        margin-top: 0.25rem;
        margin-bottom: 0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }

    /* Kartu KPI Metrik */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.76rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0F172A;
    }

    /* Tombol */
    .stButton > button, .stDownloadButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.18s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(29, 78, 216, 0.2);
    }

    /* Tabs Navigasi */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid #CBD5E1;
        margin-bottom: 0.8rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 18px;
        font-weight: 600;
        font-size: 0.9rem;
        color: #475569;
    }
    .stTabs [aria-selected="true"] {
        color: #1D4ED8 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="studio-header">
    <div class="studio-badge">RANCANG.IO // CAD &amp; BOQ AUTOMATION STUDIO</div>
    <h1 class="studio-title">Generator Gambar Kerja AutoCAD &amp; RAB Konstruksi</h1>
    <p class="studio-subtitle">Otomasi denah arsitektural, potongan, 4 sisi tampak (.DXF), dan estimasi Rencana Anggaran Biaya (.XLSX) lintas wilayah.</p>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 1. SUMBER DATA: UPLOAD JSON vs TEMPLATE PARAMETRIK
# -----------------------------------------------------------------
st.sidebar.markdown("### Konfigurasi Proyek")
sumber = st.sidebar.file_uploader(
    "Unggah Denah Kustom (.JSON)",
    type="json",
    help="Biarkan kosong jika ingin menggunakan model denah parametrik bawaan."
)
mode = "upload" if sumber is not None else "template"

json_error = None
if mode == "upload":
    file_bytes = sumber.getvalue()
    file_hash = hashlib.md5(file_bytes).hexdigest()[:10]
    source_id = f"upload_{sumber.name}_{file_hash}"
    try:
        data = json.loads(file_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        data = None
        json_error = f"Berkas JSON tidak valid (baris {e.lineno}, kolom {e.colno}): {e.msg}"
    except Exception as e:
        data = None
        json_error = f"Gagal membaca berkas: {e}"
else:
    template_path = Path("rumah.json")
    if template_path.exists():
        template_bytes = template_path.read_bytes()
        file_hash = hashlib.md5(template_bytes).hexdigest()[:10]
        source_id = f"template_{file_hash}"
        data = json.loads(template_bytes.decode("utf-8"))
    else:
        source_id = "template_none"
        data = None
        json_error = "Berkas template rumah.json tidak ditemukan di direktori proyek."

# Reset state hasil lama jika sumber data berubah
if st.session_state.get("current_source_id") != source_id:
    st.session_state["current_source_id"] = source_id
    for k in ("dxf", "daerah", "rab", "pesan", "dimensi_terakhir", "mode_terakhir", "wilayah_terakhir"):
        st.session_state.pop(k, None)

if json_error:
    st.error(f"**Kesalahan Format Input JSON:** {json_error}")
    st.stop()

# Hitung dimensi bounding box awal dari data
xs = [p[0] for d in data.get("dinding", []) for p in (d.get("a", [0, 0]), d.get("b", [0, 0]))] if data else []
ys = [p[1] for d in data.get("dinding", []) for p in (d.get("a", [0, 0]), d.get("b", [0, 0]))] if data else []
base_lebar = int(round(max(xs) - min(xs))) if xs else 6000
base_panjang = int(round(max(ys) - min(ys))) if ys else 6000

# Preset cepat khusus mode template
preset_lebar, preset_panjang = base_lebar, base_panjang
if mode == "template":
    pilihan_preset = st.sidebar.selectbox(
        "Preset Tipe Bangunan",
        options=list(PRESET_TIPE_RUMAH.keys()),
        index=0,
        help="Pilih ukuran standar tipe rumah untuk mengisi dimensi secara otomatis."
    )
    if PRESET_TIPE_RUMAH[pilihan_preset] is not None:
        preset_lebar, preset_panjang = PRESET_TIPE_RUMAH[pilihan_preset]

# -----------------------------------------------------------------
# 2. SIDEBAR FORM PARAMETER
# -----------------------------------------------------------------
with st.sidebar.form("input_form"):
    with st.expander("1. Dimensi & Geometri", expanded=True):
        if mode == "upload":
            st.caption(f"Mengikuti koordinat JSON: **{base_lebar/1000:.2f} m × {base_panjang/1000:.2f} m**")

        c_l, c_p = st.columns(2)
        with c_l:
            lebar = st.number_input(
                "Lebar (mm)",
                min_value=1000,
                max_value=30000,
                value=preset_lebar,
                step=500,
                disabled=(mode == "upload"),
                help="Lebar total denah arah sumbu X (mm)"
            )
        with c_p:
            panjang = st.number_input(
                "Panjang (mm)",
                min_value=1000,
                max_value=30000,
                value=preset_panjang,
                step=500,
                disabled=(mode == "upload"),
                help="Panjang total denah arah sumbu Y (mm)"
            )

        c_td, c_tp = st.columns(2)
        with c_td:
            tinggi = st.number_input(
                "Tinggi Dinding",
                min_value=2000,
                max_value=5000,
                value=int(data.get("lantai", {}).get("tinggi_dinding", 3000)),
                step=100,
                help="Satuan milimeter (mm)"
            )
        with c_tp:
            plafon = st.number_input(
                "Tinggi Plafon",
                min_value=1800,
                max_value=4500,
                value=int(data.get("lantai", {}).get("tinggi_plafon", 2800)),
                step=100,
                help="Satuan milimeter (mm)"
            )

        c_tb, c_at = st.columns(2)
        with c_tb:
            tebal = st.number_input(
                "Tebal Dinding",
                min_value=50,
                max_value=400,
                value=int(data.get("dinding_default", {}).get("tebal", 150)),
                step=10,
                help="Satuan milimeter (mm)"
            )
        with c_at:
            miring = st.number_input(
                "Sudut Atap (°)",
                min_value=10,
                max_value=60,
                value=int(data.get("atap", {}).get("kemiringan_derajat", 30)),
                step=1
            )

    with st.expander("2. Identitas & Lokasi RAB", expanded=True):
        nama = st.text_input(
            "Nama Proyek",
            value=data.get("proyek", {}).get("nama", "Rumah Tinggal Sederhana")
        )
        wilayah_terpilih = st.selectbox(
            "Wilayah Acuan Harga (IKK)",
            options=list(KOEFISIEN_WILAYAH.keys()),
            index=0,
            help="Menyesuaikan indeks harga satuan material dan upah berdasarkan wilayah konstruksi."
        )

    kirim = st.form_submit_button(
        "Generate Gambar Kerja & RAB",
        type="primary",
        use_container_width=True
    )

# -----------------------------------------------------------------
# 3. PEMROSESAN GAMBAR DXF & KALKULASI RAB
# -----------------------------------------------------------------
if kirim and data:
    try:
        with st.status("Memproses geometri arsitektural dan kalkulasi RAB...", expanded=True) as status:
            st.write("1/3 Menyesuaikan parameter dimensi dan memvalidasi koordinat struktur...")
            data_proses = copy.deepcopy(data)
            if mode == "template":
                data_proses = sesuaikan_dimensi_rumah(data_proses, lebar, panjang)
                data_proses.setdefault("proyek", {})["nama"] = nama
                data_proses.setdefault("lantai", {})["tinggi_dinding"] = tinggi
                data_proses.setdefault("lantai", {})["tinggi_plafon"] = plafon
                data_proses.setdefault("dinding_default", {})["tebal"] = tebal
                data_proses.setdefault("atap", {})["kemiringan_derajat"] = miring
                dim_info = f"{lebar/1000:.2f} m × {panjang/1000:.2f} m"
                gambar_perabot = True
            else:
                dim_info = f"{base_lebar/1000:.2f} m × {base_panjang/1000:.2f} m"
                gambar_perabot = False

            json_path = FOLDER / "_input.json"
            json_path.write_text(json.dumps(data_proses, indent=2, ensure_ascii=False), encoding="utf-8")
            rumah = muat_rumah(str(json_path))

            st.write("2/3 Mengekspor Denah, Potongan, dan 4 Tampak ke file AutoCAD (.DXF)...")
            hasil_dxf, daerah = ekspor_gambar_lengkap(
                rumah,
                FOLDER / "gambar_lengkap.dxf",
                gambar_perabot=gambar_perabot
            )

            st.write(f"3/3 Menghitung volume pekerjaan dan menyesuaikan indeks wilayah ({wilayah_terpilih})...")
            _, per_divisi, total = hitung_rab(rumah)
            ikk = KOEFISIEN_WILAYAH[wilayah_terpilih]

            # Terapkan koefisien wilayah pada ringkasan RAB
            divisi_wilayah = {k: v * ikk for k, v in per_divisi.items()}
            total_wilayah = {
                "jumlah": total["jumlah"] * ikk,
                "overhead": total["overhead"] * ikk,
                "total": total["total"] * ikk,
            }
            xlsx_path = buat_rab_excel(rumah, FOLDER / "RAB_rumah.xlsx")

            st.session_state["dxf"] = str(hasil_dxf)
            st.session_state["daerah"] = daerah
            st.session_state["mode_terakhir"] = mode
            st.session_state["dimensi_terakhir"] = dim_info
            st.session_state["wilayah_terakhir"] = wilayah_terpilih
            st.session_state["ikk_terakhir"] = ikk
            st.session_state["rab"] = {
                "xlsx": str(xlsx_path),
                "divisi": divisi_wilayah,
                "total": total_wilayah,
            }
            st.session_state.pop("pesan", None)
            status.update(
                label=f"Selesai! Dokumen CAD dan RAB ({wilayah_terpilih}) siap diunduh.",
                state="complete",
                expanded=False
            )

    except ValidasiRumahError as e:
        st.error(f"**Validasi Geometri Gagal:** {e}")
    except json.JSONDecodeError as e:
        st.error(f"**Format JSON Tidak Valid:** {e}")
    except Exception as e:
        st.error(f"**Terjadi Kesalahan Pemrosesan:** {e}")

# -----------------------------------------------------------------
# 4. RINGKASAN METRIK UTAMA (KPI CARDS)
# -----------------------------------------------------------------
aktif_lebar = lebar if mode == "template" else base_lebar
aktif_panjang = panjang if mode == "template" else base_panjang
luas_m2 = (aktif_lebar * aktif_panjang) / 1_000_000
rab = st.session_state.get("rab")
rp = lambda x: "Rp " + f"{x:,.0f}".replace(",", ".")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Dimensi Bangunan", f"{aktif_lebar/1000:.2f} m × {aktif_panjang/1000:.2f} m")
m2.metric("Luas & Tipe Lantai", f"{luas_m2:.1f} m² (Tipe {round(luas_m2)})")
m3.metric("Indeks Wilayah (IKK)", f"{KOEFISIEN_WILAYAH[wilayah_terpilih]:.2f}×")
m4.metric("Estimasi Total RAB", rp(rab["total"]["total"]) if rab else "Belum Dihitung")

st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------
# 5. WORKSPACE TABS
# -----------------------------------------------------------------
tab_cad, tab_rab, tab_validasi = st.tabs([
    "Viewport Gambar Kerja (DXF)",
    "Rincian Anggaran Biaya (RAB)",
    "Validasi Geometri & Inspeksi"
])

# === TAB 1: VIEWPORT GAMBAR KERJA ===
with tab_cad:
    dxf = st.session_state.get("dxf")
    if dxf:
        dim_info = st.session_state.get("dimensi_terakhir", f"{aktif_lebar/1000:.2f} m × {aktif_panjang/1000:.2f} m")
        mode_dipakai = st.session_state.get("mode_terakhir", mode)

        st.success(
            f"File AutoCAD (.DXF) siap untuk ukuran **{dim_info}** "
            f"(Mode {mode_dipakai.upper()} — mencakup Denah, Potongan, dan 4 Sisi Tampak)."
        )

        if IS_WINDOWS:
            b1, b2 = st.columns(2)
            with b1:
                with open(dxf, "rb") as f:
                    st.download_button(
                        "Unduh File AutoCAD (.DXF)",
                        f,
                        file_name=Path(dxf).name,
                        mime="application/dxf",
                        type="primary",
                        use_container_width=True
                    )
            with b2:
                if st.button("Buka Langsung di AutoCAD", use_container_width=True):
                    st.session_state["pesan"] = buka_di_autocad(dxf)
        else:
            with open(dxf, "rb") as f:
                st.download_button(
                    "Unduh File AutoCAD (.DXF)",
                    f,
                    file_name=Path(dxf).name,
                    mime="application/dxf",
                    type="primary",
                    use_container_width=True
                )

        if "pesan" in st.session_state:
            st.info(st.session_state["pesan"])

        daerah = st.session_state["daerah"]
        pilih = st.radio("Pilih Lembar Gambar Kerja:", list(daerah), horizontal=True)
        st.image(
            pratinjau(dxf, tuple(daerah[pilih]), Path(dxf).stat().st_mtime),
            use_container_width=True
        )