import json

import src.data.loader as loader


def test_load_posts_merges_crawled_and_council(tmp_path, monkeypatch):
    data_dir = tmp_path

    (data_dir / "crawled.json").write_text(
        json.dumps(
            [
                {"id": 1, "title": "A"},
                {"id": 2, "title": "B"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "council.json").write_text(
        json.dumps(
            [
                {"id": 2, "title": "B (dup)"},
                {"id": 3, "title": "C"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(loader, "DATA_DIR", data_dir)

    posts = loader.load_posts()
    assert [str(p.get("id")) for p in posts] == ["1", "2", "3"]
    assert posts[2]["title"] == "C"


def test_filter_posts_by_year_author_keyword_and_limit():
    posts = [
        {"id": "1", "title": "Winter Budget", "author": "kim", "date": "2025-01-02", "content": "hello"},
        {"id": "2", "title": "Minutes", "author": "lee", "date": "2024-12-31", "content": "world"},
        {"id": "3", "title": "No Year", "author": "kim", "date": "02-07", "content": "misc"},
    ]

    assert [p["id"] for p in loader.filter_posts(posts, year=2025)] == ["1"]
    assert [p["id"] for p in loader.filter_posts(posts, author="kim")] == ["1", "3"]
    assert [p["id"] for p in loader.filter_posts(posts, keyword="budget")] == ["1"]
    assert [p["id"] for p in loader.filter_posts(posts, keyword="WORLD")] == ["2"]
    assert [p["id"] for p in loader.filter_posts(posts, author="kim", limit=1)] == ["1"]


def test_get_post_stats_counts_by_year_author_and_files():
    posts = [
        {"id": "1", "author": "kim", "date": "2025-01-02", "files": [{"name": "a.pdf"}, {"name": "b.xlsx"}]},
        {"id": "2", "author": "lee", "date": "2024-12-31", "files": []},
        {"id": "3", "author": "kim", "date": "02-07", "files": [{"name": "c.docx"}]},
    ]

    stats = loader.get_post_stats(posts)

    assert stats["total_posts"] == 3
    assert stats["total_files"] == 3
    assert stats["by_year"] == {2024: 1, 2025: 1}
    assert stats["by_author"]["kim"] == 2
    assert stats["by_author"]["lee"] == 1
    assert stats["year_range"] == "2024 ~ 2025"


def test_list_files_filters_by_keyword_and_year():
    posts = [
        {
            "id": "1",
            "title": "t1",
            "date": "2025-01-02",
            "files": [{"name": "예산.xlsx", "size": "1KB", "local_path": "x"}],
        },
        {
            "id": "2",
            "title": "t2",
            "date": "2025-02-02",
            "files": [{"name": "회의록.pdf", "size": "2KB", "local_path": "y"}],
        },
    ]

    files = loader.list_files(posts, keyword="예산", year=2025)
    assert len(files) == 1
    assert files[0]["post_id"] == "1"
    assert files[0]["file_name"] == "예산.xlsx"

    assert loader.list_files(posts, keyword="예산", year=2024) == []
