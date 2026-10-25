from .base import ErreurImport, Importeur
from .hygiene_anssi import HygieneAnssi
from .ii901 import Ii901
from .iso27001 import Iso27001
from .nist_csf import NistCsf
from .owasp_asvs import OwaspAsvs
from .rgs import Rgs

IMPORTEURS: dict[str, type[Importeur]] = {i.code: i for i in (HygieneAnssi, NistCsf, OwaspAsvs, Ii901, Rgs, Iso27001)}

__all__ = ["IMPORTEURS", "ErreurImport", "Importeur"]
