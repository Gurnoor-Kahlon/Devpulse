from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import DemoPublication, Settings


def publication(**changes):
    return {
        "owner_id": str(uuid4()),
        "monitor_id": str(uuid4()),
        "configuration_version": 1,
        "slug": "controlled",
        "label": "Controlled fixture",
        "controlled_failure": True,
        **changes,
    }


def test_publication_is_explicit_bounded_and_unique():
    assert Settings(_env_file=None).demo_publications == ()
    item = publication()
    assert len(Settings(_env_file=None, demo_publications=[item]).demo_publications) == 1
    for items in ([item, item], [publication(slug=f"monitor-{i}") for i in range(11)]):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, demo_publications=items)
    for changes in (
        {"slug": "../private"},
        {"label": "bad\nlabel"},
        {"configuration_version": 0},
        {"url": "https://example.com"},
    ):
        with pytest.raises(ValidationError):
            DemoPublication(**publication(**changes))
    del item["controlled_failure"]
    with pytest.raises(ValidationError):
        DemoPublication(**item)
