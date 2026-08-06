import uuid

from app.repositories.friendship_repository import canonical_pair


def test_canonical_pair_is_order_independent() -> None:
    first = uuid.UUID("00000000-0000-0000-0000-000000000002")
    second = uuid.UUID("00000000-0000-0000-0000-000000000001")

    assert canonical_pair(first, second) == (second, first)
    assert canonical_pair(second, first) == (second, first)
