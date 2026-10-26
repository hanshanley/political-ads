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


def test_rebuttal_post_does_not_attribute_opponent_speech_clips_as_publisher_ads():
    assert (
        parse_post(
            post(
                "Bohannans’ Tax Ad Called a “Misleading Joke”",
                "<p>Transcript:</p><p>" + "opponent speech clip " * 20 + "</p>",
            ),
            next(source for source in SOURCES if source.id == "nrcc"),
            "2026-10-26",
        )
        == []
    )


def test_rogers_heading_typo_and_campaign_footer_are_not_spoken_copy():
    source = next(source for source in SOURCES if source.id == "rogers")
    text = "We will work together to lower costs and make health care affordable for our families."
    ads = parse_post(
        post(
            "Rogers Releases New Ad",
            f"<p><strong>Read the transcript below:r</strong></p><p>{text}</p>"
            "<p>Learn more about Mike Rogers and his plan to Get Michigan Working Again.</p>",
        ),
        source,
        "2026-10-26",
    )
    assert ads[0]["text"] == text


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


def test_on_background_and_candidate_biography_are_not_ad_copy():
    text = (
        "We work for our families and will always fight to lower costs "
        "for everyone in Pennsylvania."
    )
    for footer in ("ON BACKGROUND:", "About Sean McCann:"):
        assert transcript_blocks(
            f"<p>Transcript:</p><p>{text}</p><p>{footer}</p>"
            "<p>This is press material rather than a line in the advertisement.</p>"
        ) == [text]


def test_radio_script_is_explicit_ad_text():
    text = (
        "This is our radio advertisement asking everyone to vote "
        "and make their voices heard this November."
    )
    assert transcript_blocks(
        f"<p>Press introduction.</p><p>Radio Script:</p><p>{text}</p><p>###</p>"
    ) == [text]
    assert transcript_blocks(
        f"<p>Read the transcript for “Goodwill” here:</p><p>{text}</p><p>###</p>"
    ) == [text]


def test_candidate_quoted_copy_stops_before_background_and_speaker_credit():
    source = next(s for s in SOURCES if s.id == "hinson")
    quote = (
        "“We should work together to lower prices and help our families afford the care they need.”"
    )
    ads = parse_post(
        post(
            "Hinson Releases New Ad",
            f"<p>[<a href='https://example.org/video'>Watch Here</a>]</p>"
            f"<p><em>{quote} – Ashley Hinson</em><br>Press background is not ad text.</p>",
        ),
        source,
        "2026-10-26",
    )
    assert ads[0]["text"] == quote
    assert ads[0]["segments"][0]["kind"] == "publisher_ad_copy"
    assert ads[0]["quality_flags"] == ["publisher_ad_copy_completeness_unverified"]
    assert ads[0]["race"] == "IA-Senate"
    assert (
        parse_post(
            post("Hinson Releases New Ad", f"<p><em>{quote}</em></p>"),
            source,
            "2026-10-26",
        )
        == []
    )


def test_ossoff_bracketed_ad_script_excludes_press_commentary():
    source = next(s for s in SOURCES if s.id == "ossoff")
    text = "[Sen. Ossoff] We need to lower healthcare costs and fight for the people of Georgia."
    ads = parse_post(
        post("New Ossoff TV Ad", f"<p>Press reaction.</p><p>{text}</p><p>###</p>"),
        source,
        "2026-10-26",
    )
    assert ads[0]["text"] == text
    assert ads[0]["quality_flags"] == ["publisher_ad_copy_completeness_unverified"]
    earlier = "[Sgt. Austin] We must protect our children and hold the powerful accountable."
    ads = parse_post(
        post(
            "New Ossoff TV Ad",
            f"<p>Press reaction.</p><p>{earlier}</p><p>{text}</p><p>###</p>",
        ),
        source,
        "2026-10-26",
    )
    assert ads[0]["text"] == earlier + "\n" + text
    assert (
        parse_post(
            post(
                "New Ossoff TV Ad",
                "<p>[Sen. Ossoff] I approve this message.</p><p>###</p>",
            ),
            source,
            "2026-10-26",
        )
        == []
    )


def test_mccann_watch_marker_ends_at_script_separator():
    source = next(s for s in SOURCES if s.id == "mccann")
    text = "I approve this message because we need to change Washington and work for our families."
    ads = parse_post(
        post(
            "McCann Releases New Ad",
            f"<p>Press introduction.</p><p>WATCH THE AD HERE</p><p>{text}</p>"
            "<p>###</p><p>About Sean McCann: Biography does not belong to the ad.</p>",
        ),
        source,
        "2026-10-26",
    )
    assert ads[0]["text"] == text
