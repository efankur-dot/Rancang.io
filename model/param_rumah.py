"""
Modul untuk menyesuaikan dimensi denah rumah secara parametrik (lebar dan panjang).
Memperbarui posisi dinding, bukaan, ruang, dan garis potongan secara otomatis
sehingga denah tetap valid dan proporsional untuk berbagai ukuran rumah.
"""
from typing import Dict, Any
import copy


def sesuaikan_dimensi_rumah(
    data: Dict[str, Any],
    lebar: float,
    panjang: float,
) -> Dict[str, Any]:
    """
    Menghasilkan dictionary data rumah baru dengan lebar (sumbu X) dan panjang (sumbu Y) yang ditentukan.
    Satuan dalam mm.
    """
    d = copy.deepcopy(data)

    L = float(lebar)
    P = float(panjang)

    # Titik grid as pembagi utama
    x_mid = round(L * 0.5)               # Batas kamar kiri vs ruang tamu/dapur
    x_cuci = round(x_mid + (L - x_mid) * 0.5)  # Batas KM vs R. Cuci
    y_mid = round(P * 0.5)               # Batas depan vs belakang
    y_service = round(y_mid + (P - y_mid) * 0.5)  # Batas dapur vs KM/cuci

    # 1. Update Dinding
    peta_dinding = {
        "W1": [[0.0, 0.0], [L, 0.0]],
        "W2": [[L, 0.0], [L, P]],
        "W3": [[L, P], [0.0, P]],
        "W4": [[0.0, P], [0.0, 0.0]],
        "I1a": [[x_mid, 0.0], [x_mid, y_mid]],
        "I1b": [[x_mid, y_mid], [x_mid, P]],
        "I2": [[0.0, y_mid], [x_mid, y_mid]],
        "I3": [[x_mid, y_mid], [L, y_mid]],
        "I4": [[x_mid, y_service], [L, y_service]],
        "I5": [[x_cuci, y_service], [x_cuci, P]],
    }

    for item in d.get("dinding", []):
        id_d = item.get("id")
        if id_d in peta_dinding:
            item["a"] = peta_dinding[id_d][0]
            item["b"] = peta_dinding[id_d][1]

    # 2. Update Ruang (kotak: [xmin, ymin, xmax, ymax])
    peta_ruang = {
        "kamar tidur 1": [0.0, 0.0, x_mid, y_mid],
        "ruang tamu": [x_mid, 0.0, L, y_mid],
        "kamar tidur 2": [0.0, y_mid, x_mid, P],
        "dapur": [x_mid, y_mid, L, y_service],
        "km": [x_mid, y_service, x_cuci, P],
        "r. cuci": [x_cuci, y_service, L, P],
    }

    for r in d.get("ruang", []):
        nama = r.get("nama", "").strip().lower()
        for kunci, box in peta_ruang.items():
            if kunci in nama:
                r["kotak"] = box
                break

    # 3. Update Bukaan (Pintu & Jendela)
    # Menjamin bukaan berada dalam batas dinding dan tidak tumpang tindih
    peta_bukaan = {
        # Pintu
        "D1": {"offset": round(x_mid + min(900.0, max(200.0, (L - x_mid) - 1100.0))), "lebar": 900.0},
        "D2": {"offset": round(max(200.0, y_mid - 1000.0)), "lebar": 800.0},
        "D3": {"offset": 200.0, "lebar": 800.0},
        "D4": {"offset": 200.0, "lebar": 800.0},
        "D5": {"offset": round((x_cuci - x_mid) + 200.0), "lebar": 800.0},
        "D6": {"offset": round((L - x_mid) + min(1700.0, max(200.0, x_mid - 1100.0))), "lebar": 900.0},
        "B1": {"offset": 200.0, "lebar": round(min(1800.0, max(800.0, (L - x_mid) - 400.0)))},
        # Jendela
        "J1": {"offset": round(max(200.0, (x_mid - 1200.0) / 2)), "lebar": 1200.0},
        "J2": {"offset": round(max(200.0, (P - y_mid - 1200.0) / 2)), "lebar": 1200.0},
        "J3": {"offset": round((P - y_mid) + max(200.0, (y_mid - 1200.0) / 2)), "lebar": 1200.0},
        "J4": {"offset": round(max(200.0, (y_mid - 1200.0) / 2)), "lebar": 1200.0},
        "J5": {"offset": round(y_mid + max(200.0, (y_service - y_mid - 1000.0) / 2)), "lebar": 1000.0},
        "J6": {"offset": round((L - x_cuci) + max(200.0, ((x_cuci - x_mid) - 600.0) / 2)), "lebar": 600.0},
        "J7": {"offset": round(max(200.0, ((L - x_cuci) - 600.0) / 2)), "lebar": 600.0},
    }

    for b in d.get("bukaan", []):
        id_b = b.get("id")
        if id_b in peta_bukaan:
            b["offset"] = peta_bukaan[id_b]["offset"]
            b["lebar"] = peta_bukaan[id_b]["lebar"]

    # 4. Update Garis Potongan
    for p in d.get("potongan", []):
        if p.get("arah") == "x":
            p["posisi"] = round(y_mid * 0.5)
        elif p.get("arah") == "y":
            p["posisi"] = round(x_mid + (L - x_mid) * 0.4)

    # 5. Update info proyek jika nama tipe default
    tipe_luas = round((L * P) / 1_000_000)
    if "proyek" in d and "nama" in d["proyek"]:
        d["proyek"]["nama"] = f"Rumah Tipe {tipe_luas} ({L/1000:.1f}x{P/1000:.1f} m)"

    return d

