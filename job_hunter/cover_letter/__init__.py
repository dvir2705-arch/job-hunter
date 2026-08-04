from .generator import CoverLetterGenerator, generate_cover_letter
from .history import CoverLetterHistory, CoverLetterRecord
from .templates import LETTER_STRUCTURE, get_company_tone

__all__ = [
    "CoverLetterGenerator",
    "generate_cover_letter",
    "CoverLetterHistory",
    "CoverLetterRecord",
    "get_company_tone",
    "LETTER_STRUCTURE",
]
