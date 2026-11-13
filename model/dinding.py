from dataclasses import dataclass
import math
from typing import Sequence, Tuple, Optional


@dataclass
class Dinding:
    """
    Representasi dinding denah rumah.
    a: koordinat titik awal (x, y)
    b: koordinat titik akhir (x, y)
    """
    id: str
    a: Tuple[float, float]
    b: Tuple[float, float]
    tipe: str = "luar"  # "luar" atau "dalam"
    tebal: Optional[float] = None
    bahan: Optional[str] = None
    finishing: Optional[str] = None

    def __post_init__(self):
        self.a = (float(self.a[0]), float(self.a[1]))
        self.b = (float(self.b[0]), float(self.b[1]))

    @property
    def panjang(self) -> float:
        """Menghitung panjang dinding berdasarkan jarak Euclidean titik a dan b."""
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

