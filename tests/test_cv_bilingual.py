"""Tests for bilingual CV support: schema normalization, language detection, and RTL rendering."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from job_hunter.cv.adapter import detect_cv_language
from job_hunter.cv.parser import normalize_cv_schema

# ===========================================================================
# Schema normalization tests
# ===========================================================================


class TestNormalizeCvSchema:
    """Test normalize_cv_schema maps field aliases to canonical names."""

    def test_experience_title_to_position(self):
        cv = {"experience": [{"title": "Sales Manager", "company": "HOKA"}]}
        result = normalize_cv_schema(cv)
        assert result["experience"][0]["position"] == "Sales Manager"
        assert "title" not in result["experience"][0]

    def test_experience_start_date_to_start(self):
        cv = {"experience": [{"start_date": "2023", "end_date": "2025"}]}
        result = normalize_cv_schema(cv)
        assert result["experience"][0]["start"] == "2023"
        assert result["experience"][0]["end"] == "2025"
        assert "start_date" not in result["experience"][0]

    def test_experience_description_to_highlights_list(self):
        cv = {"experience": [{"description": "Managed a team of 5 people."}]}
        result = normalize_cv_schema(cv)
        assert result["experience"][0]["highlights"] == ["Managed a team of 5 people."]
        assert "description" not in result["experience"][0]

    def test_experience_empty_description_to_empty_highlights(self):
        cv = {"experience": [{"description": ""}]}
        result = normalize_cv_schema(cv)
        assert result["experience"][0]["highlights"] == []

    def test_experience_existing_highlights_untouched(self):
        cv = {
            "experience": [{"position": "Dev", "highlights": ["Built API", "Led team"]}]
        }
        result = normalize_cv_schema(cv)
        assert result["experience"][0]["highlights"] == ["Built API", "Led team"]

    def test_education_build_year_from_dates(self):
        cv = {
            "education": [
                {"institution": "BGU", "start_date": "2023", "end_date": "Present"}
            ]
        }
        result = normalize_cv_schema(cv)
        assert result["education"][0]["year"] == "2023 – Present"
        assert "_start_date" not in result["education"][0]

    def test_education_existing_year_preserved(self):
        cv = {
            "education": [
                {"institution": "BGU", "degree": "BSc", "year": "2023-Present"}
            ]
        }
        result = normalize_cv_schema(cv)
        assert result["education"][0]["year"] == "2023-Present"

    def test_military_title_to_role_and_period(self):
        cv = {
            "military": [
                {
                    "title": "Logistics NCO",
                    "company": "IDF",
                    "start_date": "2017",
                    "end_date": "2020",
                }
            ]
        }
        result = normalize_cv_schema(cv)
        assert result["military"][0]["role"] == "Logistics NCO"
        assert result["military"][0]["unit"] == "IDF"
        assert result["military"][0]["period"] == "2017 – 2020"

    def test_military_description_to_highlights(self):
        cv = {"military": [{"description": "Served 137 days in combat."}]}
        result = normalize_cv_schema(cv)
        assert result["military"][0]["highlights"] == ["Served 137 days in combat."]

    def test_volunteering_aliases(self):
        cv = {
            "volunteering": [
                {
                    "name": "Scouts",
                    "title": "Leader",
                    "start_date": "2015",
                    "end_date": "2017",
                }
            ]
        }
        result = normalize_cv_schema(cv)
        assert result["volunteering"][0]["organization"] == "Scouts"
        assert result["volunteering"][0]["role"] == "Leader"
        assert result["volunteering"][0]["period"] == "2015 – 2017"

    def test_idempotent_on_canonical_schema(self):
        """Dvir's CV already uses canonical field names — should pass through unchanged."""
        cv = {
            "name": "Dvir Salomon",
            "title": "Electrical Engineering Student",
            "experience": [
                {
                    "company": "Acme",
                    "position": "Engineer",
                    "start": "2022",
                    "end": "Present",
                    "highlights": ["Led migration"],
                }
            ],
            "education": [
                {
                    "institution": "BGU",
                    "degree": "BSc EE",
                    "year": "2023-Present",
                    "gpa": "82",
                    "highlights": ["Linear Algebra: 100"],
                }
            ],
            "military": [
                {
                    "unit": "401st",
                    "role": "Combat",
                    "period": "2019-2022",
                    "highlights": ["Certificate of Excellence"],
                }
            ],
        }
        result = normalize_cv_schema(cv)
        assert result == cv

    def test_ben_full_experience_normalized(self):
        """Ben's actual schema should be fully normalized."""
        ben_exp = {
            "title": "\u05de\u05e4\u05e2\u05d9\u05dc \u05d7\u05e0\u05d5\u05ea",
            "company": "HOKA",
            "start_date": "\u05d0\u05d5\u05d2\u05d5\u05e1\u05d8 2025",
            "end_date": "\u05d4\u05d9\u05d5\u05dd",
            "description": "\u05de\u05db\u05d9\u05e8\u05d5\u05ea \u05e9\u05d8\u05d7",
        }
        cv = {"experience": [ben_exp]}
        result = normalize_cv_schema(cv)
        exp = result["experience"][0]
        assert (
            exp["position"] == "\u05de\u05e4\u05e2\u05d9\u05dc \u05d7\u05e0\u05d5\u05ea"
        )
        assert exp["company"] == "HOKA"
        assert exp["start"] == "\u05d0\u05d5\u05d2\u05d5\u05e1\u05d8 2025"
        assert exp["end"] == "\u05d4\u05d9\u05d5\u05dd"
        assert exp["highlights"] == [
            "\u05de\u05db\u05d9\u05e8\u05d5\u05ea \u05e9\u05d8\u05d7"
        ]

    def test_does_not_modify_original(self):
        """Normalization should not mutate the input dict."""
        cv = {"experience": [{"title": "Dev", "start_date": "2023"}]}
        normalize_cv_schema(cv)
        assert "title" in cv["experience"][0]  # original unchanged

    def test_no_sections_passthrough(self):
        """CV with no array sections passes through cleanly."""
        cv = {"name": "Test", "summary": "Hello"}
        result = normalize_cv_schema(cv)
        assert result == cv

    def test_skip_rename_if_target_exists(self):
        """If both 'title' and 'position' exist, keep 'position' and drop 'title'."""
        cv = {"experience": [{"title": "Old", "position": "Correct", "company": "X"}]}
        result = normalize_cv_schema(cv)
        assert result["experience"][0]["position"] == "Correct"


# ===========================================================================
# Language detection tests
# ===========================================================================


class TestDetectCvLanguage:

    def test_hebrew_cv_detected(self):
        cv = {
            "name": "\u05d1\u05df \u05e7\u05dd",
            "summary": "\u05d1\u05e2\u05dc \u05e0\u05d9\u05e1\u05d9\u05d5\u05df \u05de\u05d5\u05db\u05d7",
        }
        assert detect_cv_language(cv) == "he"

    def test_english_cv_detected(self):
        cv = {
            "name": "Dvir Salomon",
            "summary": "Electrical Engineering student with Python expertise",
        }
        assert detect_cv_language(cv) == "en"

    def test_empty_cv_defaults_to_english(self):
        assert detect_cv_language({}) == "en"

    def test_mixed_text_majority_hebrew(self):
        cv = {
            "name": "\u05d3\u05d1\u05d9\u05e8 \u05e9\u05dc\u05de\u05d4",
            "summary": "\u05de\u05e4\u05ea\u05d7 Python \u05d5-Docker",
        }
        assert detect_cv_language(cv) == "he"


# ===========================================================================
# System prompt language tests
# ===========================================================================


class TestAdapterLanguagePrompt:

    def test_system_prompt_includes_hebrew_instructions(self):
        with patch("job_hunter.cv.adapter.get_profile") as mock_profile:
            mock_profile.return_value = MagicMock(
                cv_title="", hard_rules={}, education=None, university="", degree=""
            )
            from job_hunter.cv.adapter import _build_system_prompt

            prompt = _build_system_prompt(lang="he")
            assert (
                "\u05e2\u05d1\u05e8\u05d9\u05ea" in prompt
            )  # Hebrew word in instruction
            assert "Hebrew" in prompt

    def test_system_prompt_includes_english_instructions(self):
        with patch("job_hunter.cv.adapter.get_profile") as mock_profile:
            mock_profile.return_value = MagicMock(
                cv_title="", hard_rules={}, education=None, university="", degree=""
            )
            from job_hunter.cv.adapter import _build_system_prompt

            prompt = _build_system_prompt(lang="en")
            assert "English" in prompt


# ===========================================================================
# Template rendering tests
# ===========================================================================


class TestTemplateRendering:

    def _make_renderer(self):
        from job_hunter.cv.renderer import CVRenderer

        templates_dir = Path(__file__).parent.parent / "templates"
        return CVRenderer(templates_dir=templates_dir)

    def test_english_rendering_ltr(self):
        renderer = self._make_renderer()
        cv = {
            "name": "Test User",
            "title": "Developer",
            "contact": {"email": "test@test.com", "phone": "123"},
            "summary": "A developer.",
            "experience": [],
            "education": [],
            "skills": ["Python"],
        }
        html = renderer.render_html(cv, lang="en")
        assert 'lang="en"' in html
        assert 'dir="ltr"' in html
        assert "Summary" in html

    def test_hebrew_rendering_rtl(self):
        renderer = self._make_renderer()
        cv = {
            "name": "\u05d1\u05df",
            "title": "\u05de\u05e4\u05ea\u05d7",
            "contact": {"email": "test@test.com", "phone": "123"},
            "summary": "\u05ea\u05e7\u05e6\u05d9\u05e8",
            "experience": [],
            "education": [],
            "skills": ["Python"],
        }
        html = renderer.render_html(cv, lang="he")
        assert 'lang="he"' in html
        assert 'dir="rtl"' in html
        assert (
            "\u05ea\u05e7\u05e6\u05d9\u05e8" in html
        )  # Hebrew section title for Summary

    def test_hebrew_section_titles(self):
        renderer = self._make_renderer()
        cv = {
            "name": "Test",
            "title": "Dev",
            "contact": {"email": "t@t.com", "phone": "1"},
            "summary": "x",
            "experience": [
                {
                    "position": "Dev",
                    "company": "X",
                    "start": "2023",
                    "end": "Now",
                    "highlights": ["Did stuff"],
                }
            ],
            "education": [{"institution": "U", "degree": "BSc", "year": "2023"}],
            "skills": ["Python"],
            "military": [
                {
                    "unit": "IDF",
                    "role": "Soldier",
                    "period": "2020",
                    "highlights": ["Served"],
                }
            ],
        }
        html = renderer.render_html(cv, lang="he")
        assert (
            "\u05e0\u05d9\u05e1\u05d9\u05d5\u05df \u05ea\u05e2\u05e1\u05d5\u05e7\u05ea\u05d9"
            in html
        )  # ניסיון תעסוקתי
        assert "\u05d4\u05e9\u05db\u05dc\u05d4" in html  # השכלה
        assert "\u05db\u05d9\u05e9\u05d5\u05e8\u05d9\u05dd" in html  # כישורים
        assert (
            "\u05e9\u05d9\u05e8\u05d5\u05ea \u05e6\u05d1\u05d0\u05d9" in html
        )  # שירות צבאי

    def test_default_lang_is_english(self):
        renderer = self._make_renderer()
        cv = {
            "name": "Test",
            "title": "Dev",
            "contact": {"email": "t@t.com", "phone": "1"},
            "summary": "x",
            "education": [],
            "skills": [],
        }
        html = renderer.render_html(cv)  # no lang argument
        assert 'lang="en"' in html
        assert "Summary" in html
