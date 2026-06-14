import pytest

from app.services.feeds import clean_html, valid_article_link
from app.services.llm import SummaryGenerationError, normalize_five_lines


def test_clean_html_removes_markup_scripts_and_normalizes_spacing():
    value = "<p>Model <b>routing</b></p><script>bad()</script><p>&amp; guardrails</p>"
    assert clean_html(value) == "Model routing & guardrails"


def test_normalize_five_lines_enforces_and_formats_output():
    result = normalize_five_lines("1. One\n- Two\n• Three\n4) Four\nFive")
    assert result.splitlines() == ["• One", "• Two", "• Three", "• Four", "• Five"]


def test_normalize_five_lines_rejects_wrong_count():
    with pytest.raises(SummaryGenerationError):
        normalize_five_lines("One\nTwo")


@pytest.mark.parametrize("link", ["http://example.com/post", "javascript:alert(1)", "", "/relative"])
def test_valid_article_link_rejects_non_https_links(link):
    assert not valid_article_link(link)
