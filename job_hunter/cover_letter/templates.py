"""Cover letter templates and structure."""

LETTER_STRUCTURE = {
    "en": {
        "greeting_with_name": "Dear {hiring_manager},",
        "greeting_generic": "Dear Hiring Manager,",
        "closing": "Thank you for considering my application. I look forward to the opportunity to discuss how I can contribute to {company}.",
        "signature": "Sincerely,\n{name}\n{email} | {phone}\nLinkedIn: {linkedin}"
    },
    "he": {
        "greeting_with_name": "לכבוד {hiring_manager},",
        "greeting_generic": "לכבוד צוות הגיוס,",
        "closing": "תודה על ההתייחסות לפנייתי. אשמח להזדמנות לשוחח על האופן שבו אוכל לתרום ל{company}.",
        "signature": "בברכה,\n{name}\n{email} | {phone}\nלינקדאין: {linkedin}"
    }
}

COMPANY_TONES = {
    "formal": ["Intel", "IBM", "Applied Materials", "Elbit Systems", "Cisco", "GM"],
    "startup": ["Hailo", "NextSilicon", "Arbe", "Vayyar", "Valens"],
    "balanced": []
}


def get_company_tone(company: str) -> str:
    """Determine the appropriate tone for a company."""
    for tone, companies in COMPANY_TONES.items():
        if any(c.lower() in company.lower() for c in companies):
            return tone
    return "balanced"


TONE_INSTRUCTIONS = {
    "formal": "Use professional, formal language. Be respectful and structured.",
    "startup": "Be more personal and direct. Show enthusiasm and cultural fit.",
    "balanced": "Professional but personable. Confident without being stiff."
}
