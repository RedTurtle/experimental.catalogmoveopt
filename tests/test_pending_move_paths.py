"""Unit tests for the transaction-local path registry."""

import transaction


def _get():
    from experimental.catalogmoveopt.patches import _pending_move_paths

    return _pending_move_paths()


class TestPendingMovePaths:
    def setup_method(self):
        transaction.abort()

    def teardown_method(self):
        transaction.abort()

    def test_returns_dict(self):
        assert isinstance(_get(), dict)

    def test_same_object_within_transaction(self):
        """Two calls in the same transaction return the same dict instance."""
        assert _get() is _get()

    def test_fresh_dict_after_abort(self):
        """Aborting the transaction discards the registry."""
        oid = b"\x00" * 8
        _get()[oid] = "/old/path"
        transaction.abort()
        assert oid not in _get()

    def test_stores_and_pops(self):
        oid = b"\x00" * 8
        registry = _get()
        registry[oid] = "/some/path"
        assert _get().pop(oid) == "/some/path"
        assert oid not in _get()

    def test_multiple_oids_independent(self):
        oid_a = b"\x01" * 8
        oid_b = b"\x02" * 8
        _get()[oid_a] = "/a"
        _get()[oid_b] = "/b"
        assert _get()[oid_a] == "/a"
        assert _get()[oid_b] == "/b"

    def test_pop_missing_returns_none(self):
        assert _get().pop(b"\xff" * 8, None) is None
