"""Licensing: one license for the whole repository, the one from the CDRCA repo that is part of it."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_the_repository_license_is_exactly_cdrcas():
    assert (REPO / "LICENSE.md").read_bytes() == (REPO / "cdrca" / "LICENSE.md").read_bytes()
    assert "Islamic Open Source License" in (REPO / "LICENSE.md").read_text(encoding="utf-8")


def test_there_is_no_other_license_file_of_our_own():
    ours = [p for p in REPO.rglob("LICEN[CS]E*") if "node_modules" not in p.parts and p.is_file()]
    allowed = {REPO / "LICENSE.md", REPO / "LICENSES.md", REPO / "cdrca" / "LICENSE.md"}
    assert set(ours) <= allowed, sorted(set(ours) - allowed)


def test_no_document_still_claims_another_license():
    for md in REPO.rglob("*.md"):
        if "node_modules" in md.parts or "handoff" in md.parts:
            continue
        text = md.read_text(encoding="utf-8", errors="ignore")
        assert "MrMIB License" not in text, md
        assert "no license chosen" not in text.lower(), md


def test_the_third_party_list_names_the_ffmpeg_gpl_build():
    text = (REPO / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert "ffmpeg" in text and "GPL" in text
