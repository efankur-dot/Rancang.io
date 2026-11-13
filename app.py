"""
Rancang.io — Aplikasi Streamlit
Isi data ukuran & material -> Gambar DXF (denah, potongan, tampak) + RAB Excel -> Buka di AutoCAD.
"""
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import ezdxf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

import importlib
import drawing.denah
import drawing.potongan
importlib.reload(drawing.denah)
importlib.reload(drawing.potongan)

from model.loader import muat_rumah, ValidasiRumahError
from model.param_rumah import sesuaikan_dimensi_rumah
from drawing.potongan import ekspor_gambar_lengkap
from boq.rab import buat_rab_excel, hitung_rab

# Pastikan folder output dibuat relatif terhadap lokasi proyek
FOLDER = Path("hasil")
FOLDER.mkdir(exist_ok=True, parents=True)
IS_WINDOWS = sys.platform.startswith("win")


def buka_di_autocad(path_dxf):
    """Buka DXF di AutoCAD lewat COM (Windows). Cadangan: aplikasi bawaan Windows."""
    path = str(Path(path_dxf).resolve())
    if not IS_WINDOWS:
        return "Buka otomatis hanya tersedia di Windows. Gunakan tombol Unduh."
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            acad = win32com.client.Dispatch("AutoCAD.Application")
        acad.Visible = True
        for _ in range(15):            # AutoCAD yang baru menyala sering masih sibuk
            try:
                acad.Documents.Open(path)
                acad.ZoomExtents()
                return "Terbuka di AutoCAD (COM)."
            except Exception:
                time.sleep(2)
    except Exception:
        pass
    os.startfile(path)                 # cadangan
    return "Terbuka dengan aplikasi bawaan Windows."


@st.cache_data(show_spinner="Menggambar pratinjau...")
def pratinjau(path_dxf, bbox, versi):
    """Render satu bagian gambar (bbox = xmin, ymin, xmax, ymax) menjadi PNG."""
    x0, y0, x1, y1 = bbox
    doc = ezdxf.readfile(str(path_dxf))
    fig = plt.figure(figsize=(12, max(3.0, 12 * (y1 - y0) / (x1 - x0))))
    ax = fig.add_axes([0, 0, 1, 1])
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


st.set_page_config(
    page_title="Rancang.io — Generator Gambar Rumah & RAB",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏠 Rancang.io — Generator Gambar Rumah ke AutoCAD & RAB")
st.caption("Aplikasi desain otomatis: denah, potongan, 4 tampak ke AutoCAD (DXF) dan RAB ke Excel.")

# -----------------------------------------------------------------
# 1. PISAHKAN MODE: UPLOAD vs TEMPLATE
# -----------------------------------------------------------------
sumber = st.sidebar.file_uploader("📂 Data rumah (JSON), kosongkan untuk rumah contoh", type="json")
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
        json_error = "Berkas template rumah.json tidak ditemukan."

# State: Bersihkan hasil gambar / RAB lama jika user mengganti file, upload baru, atau menghapus file
if st.session_state.get("current_source_id") != source_id:
    st.session_state["current_source_id"] = source_id
    st.session_state.pop("dxf", None)
    st.session_state.pop("daerah", None)
    st.session_state.pop("rab", None)
    st.session_state.pop("pesan", None)
    st.session_state.pop("dimensi_terakhir", None)
    st.session_state.pop("mode_terakhir", None)

# Jika ada error parsing JSON di awal
if json_error:
    st.error(f"❌ **Format JSON Rusak**: {json_error}")
    st.stop()

# Hitung dimensi bounding box dari data rumah
xs = [p[0] for d in data.get("dinding", []) for p in (d.get("a", [0, 0]), d.get("b", [0, 0]))] if data else []
ys = [p[1] for d in data.get("dinding", []) for p in (d.get("a", [0, 0]), d.get("b", [0, 0]))] if data else []
cur_lebar = int(round(max(xs) - min(xs))) if xs else 6000
cur_panjang = int(round(max(ys) - min(ys))) if ys else 6000

# -----------------------------------------------------------------
# 2. SIDEBAR FORM
# -----------------------------------------------------------------
with st.sidebar.form("input"):
    st.subheader("📐 Ukuran Bangunan")
    if mode == "upload":
        st.info("Ukuran mengikuti file JSON yang diunggah")
        st.caption(f"Dimensi terbaca: **{cur_lebar/1000:.2f} m × {cur_panjang/1000:.2f} m**")

    c_l, c_p = st.columns(2)
    with c_l:
        lebar = st.number_input(
            "Lebar (mm)",
            min_value=1000,
            max_value=30000,
            value=cur_lebar,
            step=500,
            disabled=(mode == "upload"),
            help="Lebar total denah arah sumbu X"
        )
    with c_p:
        panjang = st.number_input(
            "Panjang (mm)",
            min_value=1000,
            max_value=30000,
            value=cur_panjang,
            step=500,
            disabled=(mode == "upload"),
            help="Panjang total denah arah sumbu Y"
        )

    st.subheader("🏗️ Parameter Teknis")
    nama = st.text_input("Nama proyek", data.get("proyek", {}).get("nama", "Rumah Tinggal") if data else "Rumah Tinggal")
    tinggi = st.number_input("Tinggi dinding (mm)", 2000, 5000, int(data.get("lantai", {}).get("tinggi_dinding", 3000)) if data else 3000, 100)
    plafon = st.number_input("Tinggi plafon (mm)", 1800, 4500, int(data.get("lantai", {}).get("tinggi_plafon", 2800)) if data else 2800, 100)
    tebal = st.number_input("Tebal dinding (mm)", 50, 400, int(data.get("dinding_default", {}).get("tebal", 150)) if data else 150, 10)
    miring = st.number_input("Kemiringan atap (°)", 10, 60, int(data.get("atap", {}).get("kemiringan_derajat", 30)) if data else 30, 1)

    kirim = st.form_submit_button("🚀 Gambar ke AutoCAD & RAB", type="primary", use_container_width=True)

# -----------------------------------------------------------------
# 3. PEMROSESAN GAMBAR & RAB
# -----------------------------------------------------------------
if kirim and data:
    try:
        # Mode Template: Terapkan scaling secara parametrik
        if mode == "template":
            data = sesuaikan_dimensi_rumah(data, lebar, panjang)
            data["proyek"]["nama"] = nama
            data["lantai"]["tinggi_dinding"] = tinggi
            data["lantai"]["tinggi_plafon"] = plafon
            data["dinding_default"]["tebal"] = tebal
            data["atap"]["kemiringan_derajat"] = miring
            dim_info = f"{lebar/1000:.2f} m × {panjang/1000:.2f} m"
            gambar_perabot = True
        else:
            # Mode Upload: 100% koordinat absolut dari JSON, tanpa scaling/pembulatan apa pun
            dim_info = f"{cur_lebar/1000:.2f} m × {cur_panjang/1000:.2f} m"
            gambar_perabot = False

        json_path = FOLDER / "_input.json"
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        rumah = muat_rumah(str(json_path))
        hasil_dxf, daerah = ekspor_gambar_lengkap(rumah, FOLDER / "gambar_lengkap.dxf", gambar_perabot=gambar_perabot)
        st.session_state["dxf"] = str(hasil_dxf)
        st.session_state["daerah"] = daerah
        st.session_state["mode_terakhir"] = mode
        _, per_divisi, total = hitung_rab(rumah)
        st.session_state["rab"] = {
            "xlsx": str(buat_rab_excel(rumah, FOLDER / "RAB_rumah.xlsx")),
            "divisi": per_divisi,
            "total": total
        }
        st.session_state.pop("pesan", None)
        st.session_state["dimensi_terakhir"] = dim_info
    except ValidasiRumahError as e:
        st.error(f"❌ **Validasi Denah Gagal**: {e}")
    except json.JSONDecodeError as e:
        st.error(f"❌ **Format JSON Rusak**: {e}")
    except Exception as e:
        st.error(f"❌ **Gagal Menggambar**: {e}")

# -----------------------------------------------------------------
# 4. TAMPILAN UTAMA
# -----------------------------------------------------------------
dxf = st.session_state.get("dxf")
if dxf:
    dim_info = st.session_state.get("dimensi_terakhir", f"{cur_lebar/1000:.2f} m × {cur_panjang/1000:.2f} m")
    mode_dipakai = st.session_state.get("mode_terakhir", mode)
    st.success(f"✅ Gambar berhasil dibuat untuk ukuran **{dim_info}** ({mode_dipakai.upper()} mode, 1 file DXF berisi denah, potongan, & 4 tampak)")

    if mode_dipakai == "upload":
        st.info("ℹ️ Perabot hanya tersedia di rumah template.")

    if IS_WINDOWS:
        kiri, kanan = st.columns(2)
        with kiri:
            with open(dxf, "rb") as f:
                st.download_button("📥 Unduh DXF Lengkap", f, file_name=Path(dxf).name, mime="application/dxf", type="primary", use_container_width=True)
        with kanan:
            if st.button("🖥️ Buka Langsung di AutoCAD", use_container_width=True):
                st.session_state["pesan"] = buka_di_autocad(dxf)
    else:
        with open(dxf, "rb") as f:
            st.download_button("📥 Unduh DXF Lengkap", f, file_name=Path(dxf).name, mime="application/dxf", type="primary", use_container_width=True)

    if "pesan" in st.session_state:
        st.info(st.session_state["pesan"])

    daerah = st.session_state["daerah"]
    pilih = st.radio("👁️ Pilih tampilan gambar:", list(daerah), horizontal=True)
    st.image(pratinjau(dxf, tuple(daerah[pilih]), Path(dxf).stat().st_mtime))
else:
    # Tampilan awal jika belum mengklik Gambar
    if mode == "upload":
        st.info(f"📂 Berkas JSON **{sumber.name}** berhasil dimuat! Dimensi terbaca: **{cur_lebar/1000:.2f} m × {cur_panjang/1000:.2f} m**.")
        st.caption("Klik tombol **🚀 Gambar ke AutoCAD & RAB** di panel sebelah kiri untuk memproses denah.")
    else:
        st.info("💡 **Petunjuk Penggunaan:**")
        st.markdown("""
        1. Masukkan **Lebar** dan **Panjang** rumah sesuai kebutuhan di panel samping kiri (mode template).
        2. Sesuaikan tinggi dinding, plafon, tebal dinding, dan sudut atap jika perlu.
        3. Klik tombol **🚀 Gambar ke AutoCAD & RAB**.
        4. Jika ingin memakai denah sendiri, unggah file JSON di bagian atas panel samping.
        """)
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("Lebar Saat Ini", f"{cur_lebar / 1000:.2f} m")
        col_k2.metric("Panjang Saat Ini", f"{cur_panjang / 1000:.2f} m")
        col_k3.metric("Estimasi Tipe Rumah", f"Tipe {round((cur_lebar * cur_panjang)/1_000_000)}")

rab = st.session_state.get("rab")
if rab:
    rp = lambda x: "Rp " + f"{x:,.0f}".replace(",", ".")
    st.divider()
    st.subheader("📊 Estimasi Volume & Rencana Anggaran Biaya (RAB)")
    a, b, c = st.columns(3)
    a.metric("Jumlah Biaya Konstruksi", rp(rab["total"]["jumlah"]))
    b.metric("Overhead & Profit", rp(rab["total"]["overhead"]))
    c.metric("Total Biaya RAB (Termasuk PPN)", rp(rab["total"]["total"]))

    st.dataframe(pd.DataFrame({
        "Divisi Pekerjaan": list(rab["divisi"]),
        "Subtotal Biaya": [rp(v) for v in rab["divisi"].values()]
    }), hide_index=True, use_container_width=True)

    if IS_WINDOWS:
        k1, k2 = st.columns(2)
        with k1:
            with open(rab["xlsx"], "rb") as f:
                st.download_button("📥 Unduh RAB Lengkap (Excel .xlsx)", f, file_name="RAB_rumah.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   type="primary", use_container_width=True)
        with k2:
            if st.button("📊 Buka File RAB di Excel", use_container_width=True):
                os.startfile(str(Path(rab["xlsx"]).resolve()))
    else:
        with open(rab["xlsx"], "rb") as f:
            st.download_button("📥 Unduh RAB Lengkap (Excel .xlsx)", f, file_name="RAB_rumah.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               type="primary", use_container_width=True)

    st.caption("📌 Harga satuan mengacu pada HSPK & HSD Kab. Magelang 2024. Rumus di file Excel aktif dinamis.")
