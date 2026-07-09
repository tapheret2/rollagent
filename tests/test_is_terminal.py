from rollagent.models import is_terminal

def test_is_terminal():
    assert is_terminal("final")
    assert is_terminal("reverted")
    assert not is_terminal("pending")
