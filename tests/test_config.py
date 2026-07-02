from src.config import AppSettings, _drop_blank_secret_values


def test_apify_keys_accept_key_and_token_aliases_with_deduping():
    settings = AppSettings(
        APPIFY_KEY_0="zeroth",
        APPIFY_KEY_1="first",
        APIFY_KEY_0="zeroth",
        APIFY_API_KEY_1="first",
        APIFY_API_KEY_2="second",
        APIFY_API_TOKEN_1="first",
        APIFY_API_TOKEN_2="third",
    )

    assert settings.apify_api_keys == ["zeroth", "first", "second", "third"]


def test_candidate_overfetch_settings_are_configurable():
    settings = AppSettings(CANDIDATE_OVERFETCH_MULTIPLIER=3, CANDIDATE_OVERFETCH_MAX=3000)

    assert settings.candidate_overfetch_multiplier == 3
    assert settings.candidate_overfetch_max == 3000


def test_blank_streamlit_secret_values_do_not_override_environment_values():
    values = _drop_blank_secret_values({"GEMINI_API_KEY": "", "YOUTUBE_API_KEY": None, "APP_ENV": "demo"})

    assert values == {"APP_ENV": "demo"}
