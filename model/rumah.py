from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .dinding import Dinding
from .bukaan import Bukaan
from .ruang import Ruang


@dataclass
class Rumah:
    """
    Representasi agregat keseluruhan model rumah.
    """
    proyek: Dict[str, Any] = field(default_factory=dict)
    satuan: str = "mm"
    lantai: Dict[str, Any] = field(default_factory=dict)
    dinding_default: Dict[str, Any] = field(default_factory=dict)
    dinding: List[Dinding] = field(default_factory=list)
    bukaan: List[Bukaan] = field(default_factory=list)
    ruang: List[Ruang] = field(default_factory=list)
    struktur: Dict[str, Any] = field(default_factory=dict)
    atap: Dict[str, Any] = field(default_factory=dict)
    potongan: List[Dict[str, Any]] = field(default_factory=list)

    def cari_dinding(self, dinding_id: str) -> Optional[Dinding]:
        """Mencari objek Dinding berdasarkan id."""
        for d in self.dinding:
            if d.id == dinding_id:
                return d
        return None

    def bukaan_pada_dinding(self, dinding_id: str) -> List[Bukaan]:
        """Mengambil daftar bukaan yang terletak pada dinding tertentu."""
        return [b for b in self.bukaan if b.dinding == dinding_id]

