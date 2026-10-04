from app.scoring import score_contact, tier_for, title_key


def test_title_rules():
    assert title_key("VP Security") == "title_leadership"
    assert title_key("Chief Information Security Officer") == "title_leadership"
    assert title_key("Vulnerability Management Lead") == "title_vm_practitioner"
    assert title_key("CTO") == "title_cto"
    assert title_key("Technical Recruiter, Security") == "__drop__"
    assert title_key("GRC Analyst") == "__drop__"
    assert title_key("Software Engineer") is None


def test_tiers():
    assert tier_for(14) == "priority"
    assert tier_for(13) == "standard"
    assert tier_for(9) == "standard"
    assert tier_for(8) == "luma_only"
    assert tier_for(5) == "luma_only"
    assert tier_for(4) == "drop"


def test_priority_example():
    hits = {"thesis_ai_post": True, "vm_tool_frustration": True, "uses_scanner": True}
    r = score_contact("VP Security", 750, "Computer Software", hits)
    # 4 (title) + 2 (fit) + 4 + 3 + 2 = 15
    assert r.total == 15 and r.tier == "priority"
    assert r.thesis == 4 and r.pain == 11 and r.attendance == 0


def test_attendance_only_is_dropped():
    r = score_contact(None, None, None, {"bh_speaker": True, "bh_2026_post": True})
    assert r.total == 7 and r.tier == "drop"


def test_drop_title_short_circuits():
    r = score_contact("Head of Talent", 500, "SaaS", {"thesis_ai_post": True})
    assert r.tier == "drop" and r.total == 0


def test_non_classifiable_hits_are_ignored():
    r = score_contact("Engineer", None, None, {"title_leadership": True})
    assert r.total == 0
