from exam_practice import registry
from exam_practice.parse import slug_code


def test_slug_code():
    assert slug_code("https://fuoverflow.com/threads/hcm202-q2-6.2757/") == "hcm202-q2-6"
    assert slug_code("https://fuoverflow.com/threads/hcm202-q2-6.2757") == "hcm202-q2-6"
    assert slug_code("") == ""


def test_load_missing_is_empty(tmp_path):
    assert registry.load(tmp_path / "nope.json") == []


def test_load_invalid_json_is_empty(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text("{not json", encoding="utf-8")
    assert registry.load(path) == []


def test_upsert_merges_by_code():
    entries = registry.upsert([], {"code": "hcm202-q2-6", "url": "u", "name": "A"})
    entries = registry.upsert(entries, {"code": "hcm202-q2-6", "name": "A2"})
    assert len(entries) == 1
    assert entries[0]["name"] == "A2"
    assert entries[0]["url"] == "u"


def test_save_sorts_and_roundtrips(tmp_path):
    path = tmp_path / "registry.json"
    registry.save(path, [{"code": "b"}, {"code": "a"}])
    assert [entry["code"] for entry in registry.load(path)] == ["a", "b"]
