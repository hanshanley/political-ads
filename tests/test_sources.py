import pytest

from political_ads.schema import in_window, message_key
from political_ads.sources import (
    SOURCES,
    cooper_transcripts,
    language_of,
    parse_post,
    transcript_blocks,
)


def post(title, content):
    return {
        "id": 12,
        "title": {"rendered": title},
        "content": {"rendered": content},
        "date": "2026-10-02T12:00:00",
        "link": "https://dccc.org/test-ad/",
    }


def test_only_ad_text_not_release_commentary():
    result = parse_post(
        post(
            "DCCC Releases New TV Ad in PA-10",
            "<p>Press spokesperson says corruption everywhere.</p><p>Transcript:</p>"
            "<p><strong>Narrator:</strong> These are the actual words of this test advertisement "
            "and not the words of the press spokesperson.</p><p>###</p>",
        ),
        SOURCES[1],
        "2026-10-26",
    )
    assert len(result) == 1
    assert result[0]["text"].startswith("Narrator:")
    assert "corruption everywhere" not in result[0]["text"]
    assert result[0]["race"] == "PA-10"
    assert result[0]["phase"] == "unknown"
    assert result[0]["date_basis"] == "release_date"


def test_interview_transcript_is_not_an_ad():
    assert (
        parse_post(
            post(
                "ICYMI: New interview about ads",
                "<p>Transcript:</p><p>" + "not ad text " * 20 + "</p>",
            ),
            SOURCES[0],
            "2026-10-26",
        )
        == []
    )


def test_transcript_highlights_and_metadata_are_not_full_ad_text():
    assert transcript_blocks("<p>Transcript highlights:</p><p>" + "interview " * 20) == []
    assert transcript_blocks("<p>Watch the ad here.</p>") == []


def test_multiple_creatives_are_kept_separate():
    blocks = transcript_blocks(
        "<p>Transcript:</p><p>"
        + "first message " * 20
        + "</p><p>###</p><p>Transcript:</p><p>"
        + "second message " * 20
        + "</p>"
    )
    assert len(blocks) == 2
    assert "second" not in blocks[0]


def test_next_video_title_and_spokesperson_are_not_ad_text():
    blocks = transcript_blocks(
        "<p>Transcript:</p><p>" + "first campaign message " * 10 + "</p>"
        '<div>“<a href="https://www.youtube.com/watch?v=second">Next title</a>”</div>'
        "<p>Transcript:</p><p>" + "second campaign message " * 10 + "</p>"
        "<p>DCCC National Engagement Director:</p><p>Press reaction is not the ad.</p>"
    )
    assert len(blocks) == 2
    assert "Next title" not in blocks[0]
    assert "Press reaction" not in blocks[1]


def test_delivery_overlap_and_invalid_dates():
    assert in_window("2025-12-28", "2026-01-03", "2026-10-26")
    assert not in_window("2025-12-01", "2025-12-31", "2026-10-26")
    assert not in_window("2026-11-04", None, "2026-12-01")
    with pytest.raises(ValueError):
        in_window("2026-10-02", "2026-09-30", "2026-10-26")


def test_dedup_does_not_remove_negation_or_changed_targets():
    assert message_key(" A  message\n") == message_key("a message")
    assert message_key("Support Smith") != message_key("Do not support Smith")
    assert message_key("Support Smith") != message_key("Support Jones")


def test_cooper_background_is_not_transcript():
    result = cooper_transcripts(
        "<p><em>Read a transcript of “Safe” below.</em></p>"
        "<p><em>I approve this message because your family matters.</em></p>"
        "<p>Michael Whatley did something else, according to our spokesperson.</p>"
    )
    assert result == ["I approve this message because your family matters."]


def test_english_scope_does_not_include_spanish():
    assert (
        language_of(
            "Yo no nací con ventajas. Soy Manny Rutinel. Crecí con Medicaid, hijo de una "
            "madre soltera. Apruebo este mensaje para que el Congreso trabaje para nosotros."
        )
        == "es"
    )


def test_language_detection_is_stable_across_collector_threads():
    from concurrent.futures import ThreadPoolExecutor

    text = "These are English words in a campaign advertisement about health insurance and prices."
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(language_of, [text] * 12)) == ["en"] * 12
