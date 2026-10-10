import json

import pytest

from exam_practice import build, catalog, registry


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "exams"
    for code in ("keep", "demo"):
        exam_dir = root / code
        build.write_exam(exam_dir, {"code": code, "title": f"Old {code}", "stats": {}, "questions": [{"n": 1}]})
        (exam_dir / "raw").mkdir()
        (exam_dir / "raw" / "manifest.json").write_text(json.dumps({"code": code, "title": f"Old {code}"}), encoding="utf-8")
    build.write_index(root)
    reg = root / "registry.json"
    registry.save(reg, [{"code": "demo", "name": "Old demo", "url": "u"}, {"code": "keep", "name": "Old keep", "url": "k"}])
    return root, reg


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_rename_updates_data_manifest_registry_and_index(store):
    root, reg = store
    catalog.rename(root, reg, "demo", "Tên mới")
    assert read(root / "demo" / "data.json")["title"] == "Tên mới"
    assert read(root / "demo" / "data.json")["questions"] == [{"n": 1}]
    assert read(root / "demo" / "exam.json")["title"] == "Tên mới"
    assert "Tên mới" in (root / "demo" / "data.js").read_text(encoding="utf-8")
    assert read(root / "demo" / "raw" / "manifest.json")["title"] == "Tên mới"
    assert {e["code"]: e["name"] for e in registry.load(reg)} == {"demo": "Tên mới", "keep": "Old keep"}
    assert {e["code"]: e["title"] for e in read(root / "index.json")} == {"demo": "Tên mới", "keep": "Old keep"}


def test_rename_unregistered_exam_leaves_registry_alone(store):
    root, reg = store
    registry.save(reg, [])
    catalog.rename(root, reg, "demo", "X")
    assert registry.load(reg) == []


def test_delete_removes_folder_registry_entry_and_index_entry(store):
    root, reg = store
    catalog.delete(root, reg, "demo")
    assert not (root / "demo").exists()
    assert [e["code"] for e in registry.load(reg)] == ["keep"]
    assert [e["code"] for e in read(root / "index.json")] == ["keep"]


@pytest.mark.parametrize("code", ["missing", "..", "../exams", "Demo", ""])
def test_unknown_or_unsafe_code_is_not_found(store, code):
    root, reg = store
    with pytest.raises(catalog.ExamNotFound):
        catalog.delete(root, reg, code)
    assert (root / "demo").exists() and (root / "keep").exists()
