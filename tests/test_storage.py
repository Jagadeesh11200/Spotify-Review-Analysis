import json

from src.models import FeedbackRecord
from src.quality import apply_quality
from src.storage import create_session_dir, save_manifest, save_source_records


def test_storage_writes_source_and_manifest(tmp_path):
    session_id, session_dir = create_session_dir(tmp_path)
    record = apply_quality(
        FeedbackRecord(
            source="reddit",
            source_query="spotify recommendations",
            external_id="reddit_post:1",
            text=(
                "Spotify recommendations keep repeating the same songs from my old playlists, "
                "which makes new music discovery feel impossible unless I manually search."
            ),
            language="en",
        ),
        min_words=20,
    )

    source_result = save_source_records(
        session_dir=session_dir,
        source="reddit",
        records=[record],
        searches=["spotify recommendations"],
        date_range={"from": "2026-06-01", "to": "2026-06-19"},
    )
    manifest_path = save_manifest(session_dir, session_id, [source_result], {"limit_per_source": 300})

    source_payload = json.loads((session_dir / "reddit.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads(open(manifest_path, encoding="utf-8").read())

    assert source_payload["usable_count"] == 1
    assert manifest_payload["total_usable"] == 1
