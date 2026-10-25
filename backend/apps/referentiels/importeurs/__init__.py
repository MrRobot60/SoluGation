from .base import ErreurImport, Importeur
from .hygiene_anssi import HygieneAnssi
from .iso27001 import Iso27001
from .nist_csf import NistCsf
from .owasp_asvs import OwaspAsvs

IMPORTEURS: dict[str, type[Importeur]] = {i.code: i for i in (HygieneAnssi, NistCsf, OwaspAsvs, Iso27001)}

__all__ = ["IMPORTEURS", "ErreurImport", "Importeur"]
