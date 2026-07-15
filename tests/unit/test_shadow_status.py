from app.api.shadow import read_state


def test_shadow_state_reader_handles_missing_and_valid_json(tmp_path):
    missing=read_state(tmp_path/"missing.json"); assert missing["available"] is False
    state=tmp_path/"state.json"; state.write_text('{"completed": 2}')
    assert read_state(state)=={"available":True,"completed":2}
