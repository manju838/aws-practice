import prompting as p


def item(role, text):
    return {"role": role, "content": text}


def test_history_must_start_with_user_and_alternate():
    items = [item("assistant", "orphan"), item("user", "q1"), item("assistant", "a1"),
             item("assistant", "dup"), item("user", "q2"), item("assistant", "a2")]
    msgs = p.history_to_messages(items)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == [{"text": "q1"}]


def test_dangling_user_turn_is_dropped_so_the_new_question_can_follow():
    msgs = p.build_messages([item("user", "q1"), item("assistant", "a1"), item("user", "lost")], "q2")
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[-1]["content"] == [{"text": "q2"}]


def test_blank_and_unknown_items_are_skipped():
    assert p.history_to_messages([item("user", "  "), item("system", "x")]) == []


def test_system_prompt_includes_sources_and_handles_no_chunks():
    with_chunks = p.build_system_prompt([{"text": "ResNet uses skip connections.", "source": "docs/resnet.pdf", "score": 0.8}])
    assert 'source="docs/resnet.pdf"' in with_chunks and "skip connections" in with_chunks
    assert "no relevant excerpts" in p.build_system_prompt([])


def test_retrieval_query_adds_previous_question_for_followups():
    hist = [item("user", "What is ResNet?"), item("assistant", "A network...")]
    assert p.retrieval_query(hist, "What problem does it solve?") == "What is ResNet?\nWhat problem does it solve?"
    assert p.retrieval_query([], "What is ResNet?") == "What is ResNet?"


def test_extract_text_ignores_non_text_blocks():
    resp = {"output": {"message": {"content": [{"reasoningContent": {}}, {"text": "Hello "}, {"text": "world"}]}}}
    assert p.extract_text(resp) == "Hello world"
