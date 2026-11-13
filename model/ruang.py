from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class Ruang:
    """
    Representasi suatu ruangan pada denah rumah.
    kotak: batas koordinat bounding box [xmin, ymin, xmax, ymax]
    """
    nama: str
    kotak: Tuple[float, float, float, float]
    lantai: Optional[str] = None
    plafon: Optional[str] = None
    keramik_dinding_tinggi: Optional[float] = None

    def __post_init__(self):
        self.kotak = (
            float(self.kotak[0]),
            float(self.kotak[1]),
            float(self.kotak[2]),
            float(self.kotak[3]),
        )

    @property
    def panjang(self) -> float:
        """Dimensi panjang ruang pada sumbu X."""
        return abs(self.kotak[2] - self.kotak[0])

    @property
    def lebar(self) -> float:
        """Dimensi lebar ruang pada sumbu Y."""
        return abs(self.kotak[3] - self.kotak[1])

    @property
    def luas(self) -> float:
        """Menghitung luas ruang (panjang x lebar)."""
        return self.panjang * self.lebar

