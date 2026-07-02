# Source Collectors

This folder is reserved for live data collectors.

Collectors:

- `app_store.py`
- `apify_client.py`
- `play_store.py`
- `reddit.py`
- `spotify_community.py`
- `youtube.py`

Each collector should return normalized feedback records with:

- source
- external_id
- author or handle when available
- created_at
- text
- url
- rating when available
- language
- raw metadata
