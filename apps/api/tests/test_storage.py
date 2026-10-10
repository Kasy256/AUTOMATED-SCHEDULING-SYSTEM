import asyncio
from uuid import uuid4

import pytest

from cartlyf_api.storage import S3ObjectStore, org_object_key, owned_by
from support import make_settings


def test_keys_are_prefixed_by_org() -> None:
    org = uuid4()
    key = org_object_key(org, "imports", "abc", "source.csv")
    assert key == f"org/{org}/imports/abc/source.csv"
    assert owned_by(key, org)
    assert not owned_by(key, uuid4())
    assert not owned_by(f"org/{org}x/imports/a", org)


@pytest.mark.integration
def test_put_then_get_round_trips(minio_settings: dict[str, object]) -> None:
    settings = make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0", **minio_settings)
    store = S3ObjectStore(settings)
    key = org_object_key(uuid4(), "imports", "x", "source.csv")

    async def run() -> bytes:
        await store.put(key, b"code,name\nR1,Room 1\n", "text/csv")
        return await store.get(key)

    assert asyncio.run(run()) == b"code,name\nR1,Room 1\n"
