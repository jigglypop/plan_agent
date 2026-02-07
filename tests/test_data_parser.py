import src.data.parser as parser


def test_parse_file_returns_none_for_missing_or_unsupported(tmp_path):
    assert parser.parse_file(str(tmp_path / "missing.pdf")) is None

    p = tmp_path / "note.txt"
    p.write_text("hello", encoding="utf-8")
    assert parser.parse_file(str(p)) is None


def test_parse_post_files_prefers_local_path_and_calls_parse_file(tmp_path, monkeypatch):
    f = tmp_path / "x.pdf"
    f.write_bytes(b"not a real pdf")

    monkeypatch.setattr(parser, "parse_file", lambda filepath: "hello")

    post = {"id": "123", "files": [{"name": "x.pdf", "local_path": str(f)}]}
    out = parser.parse_post_files(post)

    assert "[첨부: x.pdf]" in out
    assert "hello" in out


def test_parse_post_files_skips_images_without_parsing(tmp_path, monkeypatch):
    f = tmp_path / "img.png"
    f.write_bytes(b"png")

    def _should_not_be_called(_filepath: str):
        raise AssertionError("parse_file should not be called for SKIP extensions")

    monkeypatch.setattr(parser, "parse_file", _should_not_be_called)

    post = {"id": "123", "files": [{"name": "img.png", "local_path": str(f)}]}
    assert parser.parse_post_files(post) == ""


def test_enrich_posts_with_files_sets_file_content(tmp_path, monkeypatch):
    posts = [
        {"id": "1", "files": [{"name": "a.pdf", "local_path": str(tmp_path / "a.pdf")}]},
        {"id": "2", "files": []},
    ]

    monkeypatch.setattr(parser, "parse_post_files", lambda post: "file text" if post.get("id") == "1" else "")

    out = parser.enrich_posts_with_files(posts)
    assert out[0]["file_content"] == "file text"
    assert "file_content" not in out[1]
