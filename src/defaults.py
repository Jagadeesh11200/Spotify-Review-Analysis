DEFAULT_MIN_WORDS = 20
DEFAULT_TARGET_USABLE_PER_SOURCE = 50
DEFAULT_LIMIT_PER_SOURCE = DEFAULT_TARGET_USABLE_PER_SOURCE
DEFAULT_CANDIDATE_RECORDS_PER_SOURCE = 100
DEFAULT_RAW_OVERFETCH_MULTIPLIER = 8
DEFAULT_REDDIT_COMMENT_DEPTH = 2
DEFAULT_REDDIT_COMMENTS_PER_POST = 20
DEFAULT_YOUTUBE_VIDEOS_PER_QUERY = 8
SPOTIFY_APP_STORE_ID = "324684580"
SPOTIFY_PLAY_STORE_APP_ID = "com.spotify.music"

APP_STORE_SEARCHES = []

PLAY_STORE_SEARCHES = []

REDDIT_SEARCHES = [
    "spotify recommendations",
    "spotify algorithm",
    "spotify discover weekly",
    "spotify same songs",
    "spotify music discovery",
    "spotify discover weekly recommendations",
    "spotify algorithm same songs over and over",
    "spotify cant find new music similar artists",
    "spotify recommendations dont match my taste",
    "spotify genre wrong mainstream boring",
    "spotify ai dj repeats songs",
    "spotify taste profile ruined recommendations",
    "spotify music discovery workaround playlist radio",
    "spotify switched to apple music recommendations discovery",
]

YOUTUBE_SEARCHES = [
    "Spotify recommendations same songs",
    "Spotify algorithm bad recommendations",
    "Spotify Discover Weekly got worse",
    "Spotify AI DJ repeating songs",
    "Spotify taste profile recommendations",
    "Why Spotify keeps playing the same songs",
    "Spotify music discovery alternatives",
    "How to discover new music on Spotify",
]

SPOTIFY_COMMUNITY_SEARCHES = [
    "recommendations",
    "music discovery",
    "algorithm recommendations",
    "repeating songs",
    "playlist recommendations",
    "bad recommendations",
    "same songs recommendations",
    "Discover Weekly same songs",
    "AI DJ repeats songs",
    "taste profile recommendations",
    "autoplay repeats same songs",
    "radio recommendations same artists",
    "feature request music discovery",
]

SOURCE_LABELS = {
    "app_store": "App Store",
    "play_store": "Play Store",
    "reddit": "Reddit",
    "youtube": "YouTube",
    "spotify_community": "Spotify Community",
}

DEFAULT_SEARCHES_BY_SOURCE = {
    "app_store": APP_STORE_SEARCHES,
    "play_store": PLAY_STORE_SEARCHES,
    "reddit": REDDIT_SEARCHES,
    "youtube": YOUTUBE_SEARCHES,
    "spotify_community": SPOTIFY_COMMUNITY_SEARCHES,
}

SOURCE_GROUPS = [
    {
        "name": "App reviews",
        "tag": "Stores",
        "description": "High-volume public reviews from mobile app stores.",
        "sources": ["app_store", "play_store"],
    },
    {
        "name": "Discussion forums",
        "tag": "Apify",
        "description": "Search-led Reddit discussions.",
        "sources": ["reddit"],
    },
    {
        "name": "Video and community",
        "tag": "Long-form",
        "description": "YouTube comments and Spotify Community threads.",
        "sources": ["youtube", "spotify_community"],
    },
]
