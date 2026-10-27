import pytest

from political_ads.schema import in_window, message_key
from political_ads.sources import (
    SOURCES,
    cooper_transcripts,
    language_of,
    media_links,
    parse_post,
    transcript_blocks,
)


def test_public_media_links_normalize_video_hosts_and_include_gallery_popup_urls():
    assert media_links(
        '<a href="http://youtube.com/watch?feature=share&amp;v=5NTptJ2PpMw">Ad</a>'
        '<div data-popup="https://youtu.be/5NTptJ2PpMw"></div>'
        '<a href="https://youtube.com.evil.example/watch?v=5NTptJ2PpMw">Not a host</a>'
    ) == [
        "https://youtu.be/5NTptJ2PpMw",
        "https://youtube.com/watch?feature=share&v=5NTptJ2PpMw",
    ]


def test_union_scripts_require_federal_candidate_evidence_in_the_actual_ad():
    source = next(s for s in SOURCES if s.id == "ua-vote-pac")
    candidates = [
        {
            "candidate_id": "H6PA08277",
            "name": "FITZPATRICK, BRIAN",
            "party": "REP",
            "state": "PA",
            "office": "H",
            "district": "01",
        }
    ]
    release = post(
        "UA Launches Independent Expenditure in PA-1",
        "<p>A separate press statement about Brian Fitzpatrick.</p>"
        "<p>TRANSCRIPT:</p><p>Brian Fitzpatrick will work across party lines to "
        "lower costs for working families and protect Pennsylvania jobs.</p>",
    )
    ads = parse_post(release, source, "2026-10-26", candidates)
    assert len(ads) == 1
    assert ads[0]["alignment"] == "unknown"
    assert ads[0]["race"] == "PA-01"
    assert ads[0]["segments"][0]["federal_scope_candidate_ids"] == ["H6PA08277"]
    release["content"]["rendered"] = (
        "<p>Our group also supports Brian Fitzpatrick in Congress.</p>"
        "<p>TRANSCRIPT:</p><p>Our candidate for governor will work across party lines "
        "to lower costs for working families and protect local jobs.</p>"
    )
    assert not parse_post(release, source, "2026-10-26", candidates)
    with pytest.raises(ValueError, match="actual federal candidate registry"):
        parse_post(release, source, "2026-10-26")


def test_script_background_heading_allows_spacing_before_the_colon():
    script = (
        "A Navy veteran will fight corruption in Washington and bring down costs "
        "for working families across central Connecticut."
    )
    blocks = transcript_blocks(
        f"<p>AD TRANSCRIPT:</p><p>{script}</p><p>Background :</p>"
        "<p>The organization's previous election spending is not part of this script.</p>"
    )
    assert blocks == [script]


def test_wfw_sample_script_is_one_creative_not_all_announced_districts():
    source = next(s for s in SOURCES if s.id == "wfw")
    candidates = [
        {
            "candidate_id": "H0TX15124",
            "name": "DE LA CRUZ, MONICA",
            "party": "REP",
            "state": "TX",
            "office": "H",
            "district": "15",
        },
        {
            "candidate_id": "H8FL27076",
            "name": "SALAZAR, MARIA ELVIRA",
            "party": "REP",
            "state": "FL",
            "office": "H",
            "district": "27",
        },
    ]
    script = (
        "Congresswoman Monica De La Cruz is working to make housing affordable for "
        "families. Tell her to keep fighting for lower costs."
    )
    release = post(
        "Winning For Women Launches $500K Advocacy Campaign in 7 House Districts",
        "<p>The ads will run in seven House districts, including those represented by "
        "Maria Elvira Salazar and Monica De La Cruz.</p>"
        f"<p><strong>Sample Ad Transcript:</strong><br><br>{script}</p>"
        "<p><strong>Background</strong></p><p>Our group has raised millions of dollars.</p>",
    )
    ads = parse_post(release, source, "2026-10-27", candidates)
    assert len(ads) == 1
    assert ads[0]["text"] == script
    assert ads[0]["race"] == "TX-15"
    assert ads[0]["segments"][0]["federal_scope_candidate_ids"] == ["H0TX15124"]
    release["content"]["rendered"] = release["content"]["rendered"].replace(
        "The ads will run in seven House districts", "Our leaders represent seven House districts"
    )
    assert not parse_post(release, source, "2026-10-27", candidates)


def test_background_checks_in_script_are_not_a_background_heading():
    script = (
        "Background checks protect our communities and keep families safe. "
        "We need leaders who will work across party lines to get results."
    )
    assert transcript_blocks(f"<p>Ad Transcript:</p><p>{script}</p>") == [script]


def test_wfw_action_fund_separates_district_headings_from_two_primary_scripts():
    source = next(s for s in SOURCES if s.id == "wfw-af")
    candidates = [
        {
            "candidate_id": "H6TX08209",
            "name": "STEINMANN, JESSICA HART",
            "party": "REP",
            "state": "TX",
            "office": "H",
            "district": "08",
        },
        {
            "candidate_id": "H6TX09140",
            "name": "MEALER, ALEX",
            "party": "REP",
            "state": "TX",
            "office": "H",
            "district": "09",
        },
    ]
    first = (
        "Jessica Steinmann will stand up for Texas families and fight to lower costs. "
        "Send Jessica Steinmann to Congress."
    )
    second = (
        "Alex Mealer will fight for secure borders and protect American jobs. "
        "Send Alex Mealer to Congress to deliver results."
    )
    release = post(
        "WFW AF Launches Two Six-Figure Ad Campaigns",
        "<p>The ads run ahead of the Texas Republican primary.</p>"
        f"<p>Ad Transcript:</p><p>{first}</p>"
        "<p><strong>Alex Mealer — “Hard Line” — TX-09</strong></p><p>Watch Here</p>"
        f"<p>Ad Transcript:</p><p>{second}</p><p>Background</p>"
        "<p>This organization has raised millions of dollars.</p>",
    )
    ads = parse_post(release, source, "2026-10-27", candidates)
    assert [ad["text"] for ad in ads] == [first, second]
    assert [ad["race"] for ad in ads] == ["TX-08", "TX-09"]
    assert all(ad["phase"] == "primary" for ad in ads)
    assert ads[0]["segments"][0]["federal_scope_candidate_ids"] == ["H6TX08209"]
    assert ads[1]["segments"][0]["federal_scope_candidate_ids"] == ["H6TX09140"]


@pytest.mark.parametrize("delimiter", ["-", "–", "—"])
def test_standalone_transcript_dash_heading(delimiter):
    script = (
        "Working families deserve lower costs and leaders who will put their communities "
        "ahead of special interests in Washington."
    )
    assert transcript_blocks(f"<p>Transcript {delimiter}</p><p>{script}</p>") == [script]


@pytest.mark.parametrize(
    ("source_id", "title", "announcement"),
    [
        (
            "nrsc",
            "A candidate puts special interests first",
            "The National Republican Senatorial Committee (NRSC) today launched a new digital ad.",
        ),
        (
            "nrsc",
            "One year of a legislative achievement",
            "The National Republican Senatorial Committee (NRSC) is celebrating one year "
            "since a law was signed with a new voter outreach effort highlighting a digital ad.",
        ),
        (
            "rogers",
            "Rogers runs a six-figure buy",
            "Mike Rogers today launched a six-figure ad buy across streaming platforms.",
        ),
        (
            "sullivan",
            "ICYMI: Watch Dan Sullivan's new ad",
            "Senator Dan Sullivan (R-Alaska) released a new ad.",
        ),
        (
            "flint",
            "Send this lobbyist home",
            "Aaron Flint launched a new ad highlighting his opponent's record.",
        ),
    ],
)
def test_reviewed_publishers_own_ad_announcements_do_not_require_ad_in_headline(
    source_id, title, announcement
):
    source = next(s for s in SOURCES if s.id == source_id)
    script = (
        "Working families deserve lower costs and leaders who will put their communities "
        "ahead of special interests in Washington."
    )
    release = post(title, f"<p>{announcement}</p><p>TRANSCRIPT:</p><p>{script}</p><p>###</p>")
    ads = parse_post(release, source, "2026-10-27")
    assert len(ads) == 1
    assert ads[0]["text"] == script
    producer = {
        "nrsc": "NRSC",
        "rogers": "Mike Rogers",
        "sullivan": "Dan Sullivan",
        "flint": "Aaron Flint",
    }[source_id]
    for non_ad in (
        f"{producer} released a statement criticizing its opponent's new ad.",
        f"{producer} released a new video about the campaign.",
    ):
        release["content"]["rendered"] = f"<p>{non_ad}</p><p>TRANSCRIPT:</p><p>{script}</p>"
        assert not parse_post(release, source, "2026-10-27")


@pytest.mark.parametrize(
    "background",
    [
        "Stover is committed to representing his district. This is release background.",
        "To learn more about Stover's campaign, visit the website.",
    ],
)
def test_stover_script_excludes_post_script_campaign_boilerplate(background):
    source = next(s for s in SOURCES if s.id == "stover")
    script = (
        "I am running for Congress to lower costs for families and protect our communities.\n"
        "I am Brian Stover, and I approve this message."
    )
    release = post(
        "Brian Stover Releases New Television Ad",
        "<h2>FULL TRANSCRIPT OF “Take Out the Trash”</h2>"
        + "".join(f"<p>{line}</p>" for line in script.splitlines())
        + f"<p>{background}</p><p>The ad will air during a football game.</p>",
    )
    ads = parse_post(release, source, "2026-10-26")
    assert len(ads) == 1
    assert ads[0]["text"] == script
    assert ads[0]["race"] == "GA-14"


def test_smp_ad_quotes_exclude_spokesperson_commentary_and_keep_one_creative():
    source = next(s for s in SOURCES if s.id == "smp")
    release = post(
        "New Ad: A test",
        "<p>“A spokesperson attacks their opponent in this press statement,” our CEO said.</p>"
        "<p>“We need leaders who will lower costs and protect families,” Sheryl says "
        "in the ad. “That is why this election matters to all of us.”</p>",
    )
    ads = parse_post(release, source, "2026-10-26")
    assert len(ads) == 1
    assert "spokesperson" not in ads[0]["text"] and "Sheryl says" not in ads[0]["text"]
    assert ads[0]["text"].endswith("That is why this election matters to all of us.")
    assert ads[0]["segments"][0]["kind"] == "publisher_ad_copy"
    assert "publisher_ad_copy_completeness_unverified" in ads[0]["quality_flags"]


def test_lawler_body_identified_ad_quotes_survive_headline_gate_without_press_commentary():
    source = next(s for s in SOURCES if s.id == "lawler")
    spoken = (
        "Our communities deserve leaders who will lower costs and protect families "
        "instead of looking out for powerful special interests."
    )
    release = post(
        "A candidate has hundreds of thousands of reasons",
        f"<p>The ad opens with Conley’s own words: “{spoken}”</p>"
        "<p>“A campaign manager offers a separate press statement that is not "
        "spoken in this advertisement,” said the campaign manager.</p>",
    )
    result = parse_post(release, source, "2026-10-26")
    assert len(result) == 1
    assert result[0]["text"] == spoken
    assert result[0]["race"] == "NY-17"
    assert result[0]["segments"][0]["kind"] == "publisher_ad_copy"
    assert result[0]["quality_flags"] == ["publisher_ad_copy_completeness_unverified"]
    release["content"]["rendered"] = "<p>“Not an ad transcript,” the spokesperson said.</p>"
    assert not parse_post(release, source, "2026-10-26")


def test_salazar_explicit_ad_speech_excludes_separate_candidate_statement():
    source = next(s for s in SOURCES if s.id == "salazar")
    spoken = (
        "The safety of our children matters more than anything and I will keep fighting "
        "to protect families from new threats."
    )
    release = post(
        "Salazar launches second ad",
        f"<p>“{spoken}” Salazar says in the new ad.</p>"
        "<p>“This is a longer separate statement for the press and not dialogue "
        "from the advertisement,” Salazar said.</p>",
    )
    result = parse_post(release, source, "2026-10-26")
    assert len(result) == 1
    assert result[0]["text"] == spoken
    assert result[0]["race"] == "FL-27"
    assert result[0]["quality_flags"] == ["publisher_ad_copy_completeness_unverified"]


def test_salazar_flattened_release_excludes_press_quotes_and_preserves_conflicting_dates():
    source = next(s for s in SOURCES if s.id == "salazar")
    first = "One of my proudest moments was passing this law to protect children and families."
    continuation = "It gives parents the tools to protect their children."
    release = post(
        "Salazar launches second ad",
        "<p>FOR IMMEDIATE RELEASE September 23th, 2026</p>"
        f"<p>Introductory background. “{first}” Salazar says in the new ad.\ufeff "
        f"“{continuation}”\ufeff Some intervening release background. "
        "“A separate statement for reporters,” Salazar said. "
        "“This additional press statement is not part of the ad.”</p>",
    )
    release["date"] = "2026-09-26T16:42:17"
    result = parse_post(release, source, "2026-10-26")
    assert result[0]["text"] == first + "\n" + continuation
    assert result[0]["published"] == "2026-09-26"
    assert result[0]["segments"][0]["publisher_visible_release_date"] == "2026-09-23"
    assert "publisher_visible_release_date_differs_from_cms" in result[0]["quality_flags"]


def test_lawler_multiple_ad_descriptions_do_not_include_titles_or_join_creatives():
    source = next(s for s in SOURCES if s.id == "lawler")
    spoken = (
        "These are the spoken words of an advertisement that should be kept separate "
        "from another creative released on the same day."
    )
    release = post(
        "Two new ads",
        f"<p>In “First,” the family tells its story. “{spoken}”</p>"
        f"<p>“Second” opens with the candidate. “{spoken} We can do better.”</p>"
        "<p>“This is the separate reaction from the campaign spokesperson and must "
        "not be counted as ad text,” the spokesperson said.</p>",
    )
    result = parse_post(release, source, "2026-10-26")
    assert len(result) == 2
    assert result[0]["text"] == spoken
    assert result[1]["text"] == spoken + " We can do better."


def test_lcv_actual_scripts_not_teasers_commentary_or_all_release_video_links():
    source = next(s for s in SOURCES if s.id == "lcv-vf")
    text = (
        "These are the actual words of an advertisement about lower costs "
        "for working families across America."
    )
    heading = (
        '<p><b>IA-Sen: Test</b> <a href="http://youtube.com/watch?v=5NTptJ2PpMw">Watch</a>'
        "<br><i>Script below</i></p>"
    )
    release = post(
        "LCV Launches New Ads",
        heading + "<p>In this ad a spokesperson describes the campaign, not its exact script.</p>"
        '<p><a href="https://youtu.be/abcdefghijk">Another ad without a script</a></p>'
        "<p>###</p>" + heading + f"<p><i>{text}</i></p>"
        "<p>The campaign's press commentary resumes here.</p>",
    )
    release["publisher_classes"] = ["position-senate", "race-iowa"]
    result = parse_post(release, source, "2026-10-26")
    assert len(result) == 1
    assert result[0]["text"] == text
    assert result[0]["race"] == "IA-Senate"
    assert result[0]["chamber"] == "Senate"
    assert result[0]["media_urls"] == ["https://youtube.com/watch?v=5NTptJ2PpMw"]
    assert result[0]["release_title"] == release["title"]["rendered"]


def test_lcv_separate_script_marker_is_not_a_second_ad_and_ambiguous_race_stays_unknown():
    source = next(s for s in SOURCES if s.id == "lcv-vf")
    text = (
        "These are the actual words of a federal advertisement about costs "
        "for working families across America."
    )
    release = post(
        "LCV Announces an Investment",
        '<h3><a href="https://youtu.be/5NTptJ2PpMw">Watch: Test</a></h3>'
        f"<p><em>Script below</em></p><p><em>{text}</em></p>",
    )
    release["publisher_classes"] = ["race-nc-11", "race-va-01"]
    result = parse_post(release, source, "2026-10-26")
    assert len(result) == 1 and result[0]["text"] == text
    assert result[0]["race"] == "Unresolved" and result[0]["state"] == ""
    assert result[0]["chamber"] == "House"
    release["publisher_classes"] = ["race-governor"]
    assert parse_post(release, source, "2026-10-26") == []


def test_lcv_unmarked_italic_ad_copy_keeps_its_completeness_warning():
    source = next(s for s in SOURCES if s.id == "lcv-vf")
    result = parse_post(
        post(
            "LCV Launches New Ad in MI-04",
            '<p><a href="https://youtu.be/5NTptJ2PpMw">Watch</a></p>'
            "<p><i>These are the actual quoted words of the advertisement, not the "
            "description of the advertisement in the press release.</i></p>",
        ),
        source,
        "2026-10-26",
    )
    assert result[0]["race"] == "MI-04"
    assert result[0]["segments"][0]["kind"] == "publisher_ad_copy"
    assert result[0]["quality_flags"] == ["publisher_ad_copy_completeness_unverified"]


def test_lcv_social_footer_and_disclaimer_are_not_an_ad():
    source = next(s for s in SOURCES if s.id == "lcv-vf")
    disclaimer = (
        "Paid for by the organizations named in this release and not authorized "
        "by any candidate or candidate committee."
    )
    for heading in (
        "<p>Visit us for more information or follow us on "
        '<a href="https://youtube.com/@ourchannel">YouTube</a>.</p>',
        '<p><a href="https://youtu.be/5NTptJ2PpMw">Watch: Ad</a></p>',
    ):
        release = post("New ad in MI-04", heading + f"<p><i>{disclaimer}</i></p>")
        assert parse_post(release, source, "2026-10-26") == []


def test_lcv_explicit_unlinked_script_and_spaced_senate_heading_are_recovered():
    source = next(s for s in SOURCES if s.id == "lcv-vf")
    text = (
        "These are the actual words of an advertisement about lower costs "
        "for working families across America."
    )
    release = post(
        "LCV Announces an Investment",
        f"<p><b>WATCH: Making Money</b><i>Script below</i></p><p><i>{text}</i></p>",
    )
    release["publisher_classes"] = ["position-senate", "race-new-hampshire"]
    result = parse_post(release, source, "2026-10-26")
    assert len(result) == 1 and result[0]["text"] == text
    assert result[0]["race"] == "NH-Senate"
    release["content"]["rendered"] = (
        f'<p><a href="https://youtu.be/5NTptJ2PpMw">IA Senate: Window</a></p><p><i>{text}</i></p>'
    )
    assert parse_post(release, source, "2026-10-26")[0]["race"] == "IA-Senate"


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


@pytest.mark.parametrize(
    "heading", ["SCRIPT:", "Script:", "AD SCRIPT (30):", "The full text of the ad is below:"]
)
def test_explicit_script_headings_are_not_missed(heading):
    text = (
        "Narrator: Working families deserve lower costs and better health care, "
        "not more broken promises from Washington."
    )
    assert transcript_blocks(f"<p>{heading}</p><p>{text}</p><p>###</p>") == [text]


def test_barr_full_text_after_introduction_excludes_unlabeled_release_background():
    source = next(s for s in SOURCES if s.id == "barr")
    text = (
        "Riley Gaines: These are the actual words spoken in the advertisement "
        "supporting Andy Barr in Kentucky."
    )
    approval = "Barr: I'm Andy Barr and I approve this message."
    result = parse_post(
        post(
            "New Barr Ad: Kentucky",
            "<p>The campaign is airing this ad across Kentucky. "
            f"The full text of the ad is below:</p><p>{text}</p><p>{approval}</p>"
            "<p>Andy Barr is championing legislation in Congress.</p>"
            "<p>New polling from a university shows a lead.</p><p>###</p>",
        ),
        source,
        "2026-10-26",
    )
    assert result[0]["text"] == f"{text}\n{approval}"
    assert result[0]["segments"][0]["kind"] == "publisher_transcript"
    assert result[0]["race"] == "KY-Senate"


def test_interview_script_remains_excluded_and_ends_the_previous_ad():
    text = (
        "These are the actual words of a campaign advertisement about lower health care costs "
        "for working families."
    )
    assert transcript_blocks(
        f"<p>Script:</p><p>{text}</p><p>Interview script:</p>"
        "<p>Interviewer: This interview is not an advertisement.</p>"
    ) == [text]


def test_targeting_list_after_nrcc_script_is_not_spoken_ad_copy():
    text = (
        "Democrats had a chance to stand up for Americans, but they stayed seated. "
        "They are completely out of touch."
    )
    assert transcript_blocks(
        f"<p>SCRIPT:</p><p>{text}</p>"
        "<p>Below is a list of vulnerable Democrats who will be targeted with the ad campaign:</p>"
        "<p>CA-13: Adam Gray</p><p>CA-45: Derek Tran</p>"
    ) == [text]


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


def test_horizontal_rule_ends_script_before_next_ad_description():
    first = (
        "Narrator: These are the actual words of the first ad "
        "supporting our candidate for Congress."
    )
    second = (
        "Narrator: These are the actual words of the second ad about our candidate's "
        "opponent in the primary."
    )
    source = next(s for s in SOURCES if s.id == "young-kim")
    ads = parse_post(
        post(
            "Campaign Launches New Ads",
            "<p>The ad buy that runs through the June 2nd primary.</p>"
            f"<p>First transcript:</p><p>{first}</p><hr>"
            "<p>The second ad titled Truth contrasts the candidates. This is press commentary.</p>"
            f"<p>Second transcript:</p><p>{second}</p><p>###</p>",
        ),
        source,
        "2026-10-26",
    )
    assert [ad["text"] for ad in ads] == [first, second]
    assert all(ad["phase"] == "primary" and ad["race"] == "CA-40" for ad in ads)


def test_marshall_transcript_container_excludes_unmarked_release_attack():
    text = (
        "A patient: Our senator helped my family when the insurance company "
        "would not cover the care we needed."
    )
    ads = parse_post(
        post(
            "Campaign Releases New Ad",
            f'<h2 class="release__heading">Transcript:</h2>'
            f'<p class="release__lines">{text}</p>'
            "<p>Our opponent is the most extreme candidate this state has ever seen.</p>",
        ),
        next(s for s in SOURCES if s.id == "marshall"),
        "2026-10-26",
    )
    assert ads[0]["text"] == text
    assert ads[0]["race"] == "KS-Senate"
    assert not ads[0]["quality_flags"]


def test_duration_headings_watch_links_and_candidate_biography_are_not_copy():
    first = (
        "These are the actual words of the first advertisement about lowering health costs "
        "and protecting local families."
    )
    second = (
        "These are the actual words of the second advertisement about fighting for our families "
        "and lowering their costs."
    )
    assert transcript_blocks(
        f"<p>AD TRANSCRIPT (15s):</p><p>{first}</p>"
        "<p>WATCH ‘SECOND’</p>"
        f"<p>Transcript (30):</p><p>{second}</p>"
        "<p>Nancy Lacore served our nation for 35 years in the Navy.</p>"
    ) == [first, second]
    assert transcript_blocks(
        f"<p>Ad transcript:</p><p>{first}</p>"
        "<p>You can watch the new Spanish language TX-15 ad here.</p>"
        f"<p>Spanish ad transcript:</p><p>{second}</p>"
        "<p>To learn more about the campaign, visit our website.</p>"
    ) == [first, second]


def test_phone_tree_transcript_is_not_the_ad_promoting_the_phone_number():
    assert (
        transcript_blocks(
            "<p>Phone Tree Transcript:</p><p>" + "Press one for voting information. " * 10 + "</p>"
        )
        == []
    )


def test_multi_district_release_does_not_assign_every_script_the_first_race():
    result = parse_post(
        post("New Ads in OH-09 and OH-10", "<p>Transcript:</p><p>" + "actual ad text " * 10),
        SOURCES[1],
        "2026-10-26",
    )
    assert result[0]["race"] == "Unresolved"


@pytest.mark.parametrize("speaker", ["Abdul El-Sayed", "Voiceover", "Josh, a UAW autoworker"])
def test_new_ad_after_debate_can_include_clearly_separated_publisher_copy(speaker):
    text = (
        f"{speaker}: We need to work together to lower costs for families across Michigan "
        "and improve health care."
    )
    source = next(s for s in SOURCES if s.id == "el-sayed")
    ads = parse_post(
        post(
            "NEW AD: Campaign Releases Ad Following Debate",
            f"<p>WATCH ‘COSTS’ HERE</p><p>{text}</p><p>###</p>",
        ),
        source,
        "2026-10-26",
    )
    assert ads[0]["text"] == text
    assert "publisher_ad_copy_completeness_unverified" in ads[0]["quality_flags"]


def test_watch_link_followed_by_press_commentary_is_not_ad_copy():
    source = next(s for s in SOURCES if s.id == "el-sayed")
    assert (
        parse_post(
            post(
                "NEW AD: Costs",
                "<p>WATCH HERE</p><p>Our spokesperson says this is an important campaign "
                "announcement about the cost of living for families in Michigan.</p><p>###</p>",
            ),
            source,
            "2026-10-26",
        )
        == []
    )


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
