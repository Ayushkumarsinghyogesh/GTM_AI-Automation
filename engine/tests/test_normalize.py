import json
from pathlib import Path

from app.normalize import norm_domain, norm_linkedin, normalize, parse_employees

SAMPLE = json.loads((Path(__file__).resolve().parents[2] / "samples" / "clearcue_webhook.json").read_text())


def test_helpers():
    assert norm_linkedin("https://in.linkedin.com/in/Priya-Nair-Sec/?utm=x") == "https://www.linkedin.com/in/priya-nair-sec"
    assert norm_linkedin("https://example.com/x") is None
    assert norm_domain("https://www.NorthwindCloud.io/about") == "northwindcloud.io"
    assert parse_employees("501-1000") == 750
    assert parse_employees("1,001-5,000") == 3000
    assert parse_employees(320) == 320
    assert parse_employees("n/a") is None


def test_sample_payload():
    evs = normalize(SAMPLE)
    assert len(evs) == 1
    e = evs[0]
    assert e.contact_key == "https://www.linkedin.com/in/priya-nair-sec"
    assert e.first_name == "Priya" and e.title == "VP Security"
    assert e.company_key == "northwindcloud.io" and e.employees == 750
    assert "Tenable" in e.signal_text
    assert len(e.signal_hash) == 40


def test_no_identity_returns_empty():
    assert normalize({"person": {"first_name": "X"}, "signal": {"text": "hi"}}) == []


def test_multiple_signals_share_contact():
    p = {"person": {"linkedin_url": "https://linkedin.com/in/a"}, "signals": [{"text": "one"}, {"text": "two"}]}
    evs = normalize(p)
    assert len(evs) == 2 and evs[0].contact_key == evs[1].contact_key
    assert evs[0].signal_hash != evs[1].signal_hash
