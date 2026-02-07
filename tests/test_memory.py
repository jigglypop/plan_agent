from src.agent.memory import Memory


def test_memory_save_load_and_clear(tmp_path):
    db_path = tmp_path / "memory.db"
    mem = Memory(db_path=str(db_path))

    mem.save("s1", "user", "hi")
    mem.save("s1", "assistant", "yo")
    mem.save("s1", "tool", "ignored")
    mem.save("s1", "user", "")

    assert mem.load("s1", limit=10) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]

    mem.clear("s1")
    assert mem.load("s1") == []


def test_memory_list_sessions(tmp_path):
    db_path = tmp_path / "memory.db"
    mem = Memory(db_path=str(db_path))

    mem.save("a", "user", "1")
    mem.save("a", "assistant", "2")
    mem.save("b", "user", "3")

    sessions = mem.list_sessions(limit=10)
    ids = {s["session_id"] for s in sessions}
    assert ids == {"a", "b"}
