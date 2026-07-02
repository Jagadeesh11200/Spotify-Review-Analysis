import json

from src.analysis.session_loader import load_usable_records


def test_load_usable_records_reads_only_usable_records(tmp_path):
    session = tmp_path / "session_1"
    session.mkdir()
    (session / "reddit.json").write_text(
        json.dumps(
            {
                "usable_records": [
                    {
                        "external_id": "r1",
                        "source": "reddit",
                        "text": "Spotify recommendations keep repeating the same songs and discovery feels stuck.",
                    }
                ],
                "records": [
                    {
                        "external_id": "bad",
                        "source": "reddit",
                        "text": "bad app",
                        "quality_passed": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records = load_usable_records(session)

    assert len(records) == 1
    assert records[0]["record_id"] == "r1"
