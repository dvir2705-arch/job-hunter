from .generator import CoverLetterGenerator, generate_cover_letter
from .history import CoverLetterHistory, CoverLetterRecord
from .critic import CoverLetterCritic, get_critic
from .templates import get_company_tone, LETTER_STRUCTURE

__all__ = [
    'CoverLetterGenerator',
    'generate_cover_letter',
    'CoverLetterHistory',
    'CoverLetterRecord',
    'CoverLetterCritic',
    'get_critic',
    'get_company_tone',
    'LETTER_STRUCTURE'
]
