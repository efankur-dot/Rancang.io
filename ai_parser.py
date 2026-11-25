"""
Modul Hybrid AI Prompt-to-JSON & Parametric Budget Optimizer.
Menggabungkan Symbolic NLP Engine (Zero-Token / Offline-First),
Constraint-Based Budget Optimizer, Guardrail Out-of-Distribution (OOD),
serta opsional Google Gemini API fallback.
"""
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def ambil_api_key(key_input: str = "") -> str:
    """Mengambil API Key dari input sidebar atau environment (opsional)."""
    if key_input and key_input.strip():
        return key_input.strip()
    return os.environ.get("GOOGLE_API_KEY", "").strip()


def _cek_relevansi_arsitektur(teks: str) -> Tuple[bool, str]:
    """Guardrail Anti-Halusinasi & Out-of-Distribution (OOD) untuk input acak/nyeleneh."""
    t = (teks or "").strip().lower()
    if len(t) < 4:
        return False, "Deskripsi terlalu singkat. Masukkan spesifikasi bangunan (misal: 'Rumah 2 lantai ukuran 6x8 m')."

    kata_kunci_valid = [
        "rumah", "lantai", "lt", "tipe", "type", "kamar", "ruang", "dapur", "wc", "km",
        "ukuran", "meter", "m", "cm", "mm", "atap", "balkon", "tangga", "lebar", "panjang",
        "tinggi", "plafon", "ruko", "toko", "teras", "garasi", "carport", "bangunan", "denah",
        "budget", "dana", "biaya", "rab", "juta", "jt", "miliar", "milyar",
        "semarang", "magelang", "jogja", "yogyakarta", "solo", "surabaya", "bandung", "jakarta",
    ]
    punya_angka = bool(re.search(r"\d", t))
    punya_konteks = any(re.search(rf"\b{k}\b", t) or (k in t and len(k) >= 4) for k in kata_kunci_valid)

    if not punya_konteks and not punya_angka:
        return (
            False,
            "Input terdeteksi di luar domain perencanaan bangunan (Out-of-Distribution). "
            "Sistem menolak memproses agar tidak terjadi halusinasi geometri.",
        )
    if not punya_konteks and punya_angka:
        return (
            False,
            "Angka terdeteksi tanpa konteks ruangan/bangunan. Sebutkan konteks seperti 'rumah 1 lantai 6x8 m'.",
        )
    return True, "Valid"


def _optimasi_dimensi_dari_budget(budget_rp: float, paksa_lantai: int, ikk: float) -> Tuple[int, int, int]:
    """
    Constraint-Based AI Optimizer: Menghitung jumlah lantai & dimensi (panjang x lebar)
    paling optimal agar estimasi RAB mendekati target budget pengguna.
    """
    biaya_per_m2_dasar = 4_450_000.0 * ikk
    luas_target = max(30.0, min(280.0, budget_rp / biaya_per_m2_dasar))

    if paksa_lantai in (1, 2):
        jml_lt = paksa_lantai
    else:
        jml_lt = 2 if luas_target >= 68.0 else 1

    luas_per_lantai = luas_target / jml_lt
    # Rasio ideal denah 1 : 1.25 dibulatkan ke kelipatan 500 mm (0.5 m)
    p_ideal = math.sqrt(luas_per_lantai / 1.25)
    p_mm = int(round((p_ideal * 1000) / 500.0) * 500)
    p_mm = max(5000, min(14000, p_mm))

    l_ideal = (luas_per_lantai * 1_000_000) / p_mm
    l_mm = int(round(l_ideal / 500.0) * 500)
    l_mm = max(6000, min(18000, l_mm))
    return jml_lt, p_mm, l_mm


def _parser_nlp_dan_optimizer(teks: str) -> Tuple[Dict[str, Any], str]:
    """
    Mesin Symbolic NLP & Parametric Optimizer (Zero-Token, Deterministik, < 2 ms).
    Mendukung ekstraksi dimensi langsung, tipe rumah, maupun optimasi berbasis budget.
    """
    t = teks.lower()

    # 1. Deteksi kota/lokasi & IKK wilayah
    lokasi = "Kota Semarang"
    ikk_estimasi = 1.06
    peta_kota = {
        "magelang": ("Kab. Magelang", 1.02),
        "jogja": ("Kota Yogyakarta", 1.04),
        "yogyakarta": ("Kota Yogyakarta", 1.04),
        "solo": ("Kota Surakarta", 1.03),
        "surakarta": ("Kota Surakarta", 1.03),
        "jakarta": ("DKI Jakarta", 1.18),
        "bandung": ("Kota Bandung", 1.08),
        "surabaya": ("Kota Surabaya", 1.10),
        "malang": ("Kota Malang", 1.05),
        "makassar": ("Kota Makassar", 1.07),
        "medan": ("Kota Medan", 1.09),
    }
    for k_kota, (nama_resmi, nilai_ikk) in peta_kota.items():
        if k_kota in t:
            lokasi = nama_resmi
            ikk_estimasi = nilai_ikk
            break

    # 2. Deteksi preferensi jumlah lantai
    paksa_lantai = 0
    if any(k in t for k in ("2 lantai", "dua lantai", "2 lt", "lt 2", "tingkat", "balkon", "tangga")):
        paksa_lantai = 2
    elif any(k in t for k in ("1 lantai", "satu lantai", "1 lt")):
        paksa_lantai = 1

    # 3. Cek apakah user memasukkan target BUDGET (misal: "budget 250 juta", "dana 400 jt", "1.2 miliar")
    m_budget_jt = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:juta|jt)\b", t)
    m_budget_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:miliar|milyar)\b", t)

    mode_keterangan = "Symbolic NLP Engine (Zero-Token)"
    if m_budget_jt or m_budget_m:
        if m_budget_m:
            budget_rp = float(m_budget_m.group(1).replace(",", ".")) * 1_000_000_000
        else:
            budget_rp = float(m_budget_jt.group(1).replace(",", ".")) * 1_000_000
        jumlah_lantai, panjang_mm, lebar_mm = _optimasi_dimensi_dari_budget(budget_rp, paksa_lantai, ikk_estimasi)
        mode_keterangan = "AI Budget & Geometri Optimizer"
    else:
        jumlah_lantai = paksa_lantai if paksa_lantai in (1, 2) else 1
        panjang_mm = 6000
        lebar_mm = 8000 if jumlah_lantai == 2 else 7000

        m_dim = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)", t)
        if m_dim:
            v1 = float(m_dim.group(1).replace(",", "."))
            v2 = float(m_dim.group(2).replace(",", "."))
            if v1 < 100 and v2 < 100:
                panjang_mm = int(round(v1 * 1000))
                lebar_mm = int(round(v2 * 1000))
            else:
                panjang_mm = int(round(v1))
                lebar_mm = int(round(v2))
        else:
            m_tipe = re.search(r"(?:tipe|type)\s*(\d+)", t)
            if m_tipe:
                luas = int(m_tipe.group(1))
                if luas <= 45:
                    jumlah_lantai = 1
                    panjang_mm, lebar_mm = 6000, max(6000, int(round((luas / 6.0) * 1000)))
                elif luas <= 80:
                    jumlah_lantai = 2
                    panjang_mm, lebar_mm = 6000, 7500
                else:
                    jumlah_lantai = 2
                    panjang_mm, lebar_mm = 7000, 9000

    panjang_mm = max(5000, min(16000, panjang_mm))
    lebar_mm = max(6000, min(20000, lebar_mm))

    # 4. Deteksi sudut atap
    sudut_atap = 30
    m_atap = re.search(r"(?:atap|kemiringan|sudut)\s*(\d{2})", t)
    if m_atap:
        sudut_atap = max(15, min(45, int(m_atap.group(1))))

    nama_proyek = f"Rumah Tinggal {jumlah_lantai} Lantai ({panjang_mm/1000:.1f}x{lebar_mm/1000:.1f}m)"
    if "ruko" in t or "toko" in t:
        nama_proyek = f"Ruko & Hunian {jumlah_lantai} Lantai"

    return {
        "nama_proyek": nama_proyek,
        "jumlah_lantai": jumlah_lantai,
        "panjang_mm": panjang_mm,
        "lebar_mm": lebar_mm,
        "tinggi_lt1_mm": 3400 if jumlah_lantai == 2 else 3200,
        "plafon_lt1_mm": 3000 if jumlah_lantai == 2 else 2850,
        "tinggi_lt2_mm": 3200,
        "plafon_lt2_mm": 2900,
        "sudut_atap": sudut_atap,
        "lokasi": lokasi,
    }, mode_keterangan


def _panggil_gemini_opsional(teks_prompt: str, api_key: str) -> Dict[str, Any]:
    """Integrasi Cloud Gemini opsional (hanya dipanggil jika user memasukkan API Key baru secara manual)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    instruksi = (
        "Ekstrak spesifikasi rumah menjadi JSON murni tanpa markdown dengan key: "
        '{"nama_proyek": str, "jumlah_lantai": 1 atau 2, "panjang_mm": int, "lebar_mm": int, '
        '"tinggi_lt1_mm": int, "plafon_lt1_mm": int, "tinggi_lt2_mm": int, "plafon_lt2_mm": int, '
        '"sudut_atap": int, "lokasi": str}. Angka pertama dimensi A x B wajib ke panjang_mm. '
        f"Input: {teks_prompt}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": instruksi}]}],
        "generationConfig": {"temperature": 0.0, "thinkingConfig": {"thinkingBudget": 0}},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        raw_txt = data["candidates"][0]["content"]["parts"][0]["text"]
        m_json = re.search(r"\{[\s\S]*\}", raw_txt)
        parsed = json.loads(m_json.group(0))
        parsed["jumlah_lantai"] = 2 if int(parsed.get("jumlah_lantai", 1)) >= 2 else 1
        parsed["panjang_mm"] = max(5000, min(16000, int(parsed.get("panjang_mm", 6000))))
        parsed["lebar_mm"] = max(6000, min(20000, int(parsed.get("lebar_mm", 8000))))
        parsed["sudut_atap"] = max(15, min(45, int(parsed.get("sudut_atap", 30))))
        return parsed


def urai_prompt_ke_parameter(teks_prompt: str, api_key_input: str = "") -> Dict[str, Any]:
    """
    Fungsi utama Hybrid AI (Offline-First & Zero-Token):
    1. Validasi Guardrail OOD / Anti-Halusinasi.
    2. Jika user menempelkan API Key baru di sidebar, coba Cloud Gemini; jika tidak atau kuota habis,
       langsung diproses oleh Symbolic NLP & Budget Optimizer tanpa error.
    """
    t0 = time.perf_counter()
    valid, pesan = _cek_relevansi_arsitektur(teks_prompt)
    if not valid:
        return {
            "sukses": False,
            "mode": "Guardrail OOD",
            "pesan": pesan,
            "durasi_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    key = ambil_api_key(api_key_input)
    if key:
        try:
            hasil_cloud = _panggil_gemini_opsional(teks_prompt, key)
            return {
                "sukses": True,
                "mode": "Hybrid Cloud Gemini + Local Guardrail",
                "pesan": "Spesifikasi bangunan berhasil diekstrak dan divalidasi.",
                "parameter": hasil_cloud,
                "durasi_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
        except Exception:
            pass  # Alihkan mulus ke mesin lokal tanpa menampilkan pesan error kuota

    hasil_lokal, mode_lokal = _parser_nlp_dan_optimizer(teks_prompt)
    return {
        "sukses": True,
        "mode": mode_lokal,
        "pesan": "Parameter bangunan & estimasi struktur berhasil disusun otomatis.",
        "parameter": hasil_lokal,
        "durasi_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def jalankan_benchmark_20() -> List[Dict[str, Any]]:
    """
    Menjalankan 20 skenario pengujian kuantitatif (Normal, Tipe Rumah, Budget Optimizer,
    Typo, Edge-Case, dan Out-of-Distribution) secara instan (< 15 ms, tanpa limit token).
    """
    kasus_uji = [
        ("Normal 1 Lantai", "Rumah 1 lantai ukuran 6x7 meter di Semarang", True, 1, 6000, 7000),
        ("Normal 2 Lantai", "Rumah tinggal 2 lantai dimensi 6x8 m", True, 2, 6000, 8000),
        ("Tipe 36 Standar", "Buatkan denah rumah tipe 36 minimalis", True, 1, 6000, 6000),
        ("Tipe 72 Tingkat", "Desain rumah type 72 dua lantai ada balkon", True, 2, 6000, 7500),
        ("Tipe 90 Mewah", "Rumah tipe 90 2 lantai 3 kamar tidur", True, 2, 7000, 9000),
        ("AI Budget Optimizer 1 Lt", "Rekomendasi rumah budget 220 juta di Magelang", True, 1, 6000, 8000),
        ("AI Budget Optimizer 2 Lt", "Optimasi rumah 2 lantai dana 450 juta di Yogyakarta", True, 2, 6500, 7500),
        ("Konversi Satuan Desimal", "Rumah 2 lantai ukuran 6,5 x 8,5 meter", True, 2, 6500, 8500),
        ("Input Satuan Milimeter", "Denah 1 lantai 7000x9000 mm atap 30 derajat", True, 1, 7000, 9000),
        ("Deteksi Lokasi Jogja", "Rumah 2 lantai 6x8 m lokasi Yogyakarta", True, 2, 6000, 8000),
        ("Deteksi Lokasi Magelang", "Rumah 1 lantai 6x8 meter di Magelang", True, 1, 6000, 8000),
        ("Deteksi Lokasi Jakarta", "Bangunan 2 lantai 7x10 m wilayah Jakarta", True, 2, 7000, 10000),
        ("Kemiringan Atap Curam", "Rumah 1 lantai 6x7 m sudut atap 38 derajat", True, 1, 6000, 7000),
        ("Concept Ruko 2 Lantai", "Ruko dan hunian 2 lantai ukuran 5x10 meter", True, 2, 5000, 10000),
        ("Kata Kunci Implisit Tangga", "Rumah ukuran 6x8 m pakai tangga dan balkon", True, 2, 6000, 8000),
        ("Input Typo Ringan", "rmh 2 lt uk 6x8 m atp 30", True, 2, 6000, 8000),
        ("Edge Case Lahan Terlalu Sempit", "Rumah 2 lantai ukuran 2x3 meter", True, 2, 5000, 6000),
        ("Edge Case Lahan Super Besar", "Rumah 2 lantai ukuran 25x30 meter", True, 2, 16000, 20000),
        ("OOD Topik Kuliner", "Tolong buatkan resep nasi goreng spesial", False, 0, 0, 0),
        ("OOD Input Kosong/Acak", "asdfghjkl", False, 0, 0, 0),
    ]

    laporan: List[Dict[str, Any]] = []
    for idx, (kategori, prompt, exp_valid, exp_lt, exp_p, exp_l) in enumerate(kasus_uji, start=1):
        res = urai_prompt_ke_parameter(prompt, api_key_input="")
        if not exp_valid:
            lulus = res["sukses"] is False
            catatan = "Ditolak wajar oleh Guardrail OOD" if lulus else "Gagal menolak OOD"
        else:
            p = res.get("parameter", {})
            lulus = (
                res["sukses"] is True
                and p.get("jumlah_lantai") == exp_lt
                and p.get("panjang_mm") == exp_p
                and p.get("lebar_mm") == exp_l
            )
            catatan = f"{p.get('jumlah_lantai')} Lt | {p.get('panjang_mm')}×{p.get('lebar_mm')} mm"

        laporan.append({
            "No": idx,
            "Kategori Uji": kategori,
            "Input Uji": prompt,
            "Output Sistem": catatan,
            "Waktu (ms)": res["durasi_ms"],
            "Status": "LULUS" if lulus else "MELESET",
        })
    return laporan