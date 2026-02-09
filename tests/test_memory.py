"""
LangGraph SqliteSaver 체크포인터 기반 대화 영속성 테스트
"""
from langgraph.checkpoint.sqlite import SqliteSaver


def test_checkpointer_save_and_retrieve(tmp_path):
    """체크포인터가 thread별로 상태를 저장/복원하는지 확인"""
    db_path = tmp_path / "checkpoints.db"
    saver = SqliteSaver.from_conn_string(str(db_path))

    config_a = {"configurable": {"thread_id": "a"}}
    config_b = {"configurable": {"thread_id": "b"}}

    # thread "a"에 체크포인트 저장
    saver.put(config_a, {"messages": ["hi", "yo"]}, {"source": "test", "step": 0, "writes": {}, "parents": {}}, {})
    # thread "b"에 체크포인트 저장
    saver.put(config_b, {"messages": ["hello"]}, {"source": "test", "step": 0, "writes": {}, "parents": {}}, {})

    cp_a = saver.get(config_a)
    cp_b = saver.get(config_b)

    assert cp_a is not None
    assert cp_b is not None
    assert cp_a["channel_values"]["messages"] == ["hi", "yo"]
    assert cp_b["channel_values"]["messages"] == ["hello"]


def test_checkpointer_overwrite(tmp_path):
    """같은 thread에 여러 번 저장하면 최신 상태를 반환"""
    db_path = tmp_path / "checkpoints.db"
    saver = SqliteSaver.from_conn_string(str(db_path))

    config = {"configurable": {"thread_id": "s1"}}

    saver.put(config, {"messages": ["first"]}, {"source": "test", "step": 0, "writes": {}, "parents": {}}, {})
    saver.put(config, {"messages": ["first", "second"]}, {"source": "test", "step": 1, "writes": {}, "parents": {}}, {})

    cp = saver.get(config)
    assert cp is not None
    assert cp["channel_values"]["messages"] == ["first", "second"]
