from dataclasses import dataclass
from typing import Optional


@dataclass
class Bukaan:
    """
    Representasi bukaan pada dinding (pintu, jendela, atau void bukaan).
    offset: jarak dari titik awal dinding (a) ke awal bukaan.
    lebar: dimensi lebar bukaan sepanjang garis dinding.
    tinggi: tinggi bukaan vertikal.
    ambang: tinggi elevasi ambang bawah bukaan dari lantai (sill height).
    """
    id: str
    jenis: str  # "pintu", "jendela", "bukaan"
    dinding: str  # ID dinding yang ditempati
    offset: float
    lebar: float
    tinggi: float
    ambang: float = 0.0
    ayun_ke: Optional[str] = None
    engsel: Optional[str] = None
    bahan: Optional[str] = None

    def __post_init__(self):
        self.offset = float(self.offset)
        self.lebar = float(self.lebar)
        self.tinggi = float(self.tinggi)
        self.ambang = float(self.ambang)

    @property
    def akhir(self) -> float:
        """Posisi ujung akhir bukaan dari titik awal dinding."""
        return self.offset + self.lebar

