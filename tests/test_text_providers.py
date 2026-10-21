import pytest
from core.models import Bible, VolumePlan, ChapterScript, ProjectSettings
from providers.text_mock import MockTextProvider
from providers.text_anthropic import clean_json_string


def test_clean_json_string():
    raw_markdown = '```json\n{"key": "value"}\n```'
    assert clean_json_string(raw_markdown) == '{"key": "value"}'

    raw_text_with_chatter = 'Here is your response:\n{"title": "Manga"}\nHope this helps!'
    assert clean_json_string(raw_text_with_chatter) == '{"title": "Manga"}'


def test_mock_text_provider_bible():
    provider = MockTextProvider()
    bible = provider.generate_structured("Generate bible", Bible)
    assert isinstance(bible, Bible)
    assert len(bible.characters) >= 2
    assert bible.characters[0].visual_descriptor != ""


def test_mock_text_provider_volume_and_script():
    provider = MockTextProvider()
    volume = provider.generate_structured("Generate volume", VolumePlan)
    assert isinstance(volume, VolumePlan)
    assert len(volume.chapters) == 5

    script = provider.generate_structured("Generate chapter 1", ChapterScript)
    assert isinstance(script, ChapterScript)
    assert len(script.pages) >= 2
    assert len(script.pages[0].panels) >= 1

