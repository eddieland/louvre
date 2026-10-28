"""The map kit's versions: each one served whole, its files' changes seen in review."""

import hashlib

from syrupy.assertion import SnapshotAssertion

from louvre.core import maps


def test_the_current_version_is_one_louvre_serves() -> None:
    assert maps.VERSION in maps.VERSIONS
    assert maps.KITS[maps.VERSION] == maps.FILES
    assert f"{maps.ROOT}{maps.VERSION}/" == maps.PATH


def test_a_file_is_found_in_its_own_version_only() -> None:
    media_type, data = maps.FILES["map.js"]

    assert maps.served(maps.VERSION, "map.js") == (media_type, data)
    assert maps.served("louvre-map-0", "map.js") is None
    assert maps.served("louvre-map-0", "glyphs/Noto Sans Regular/19968-20223.pbf") is None


def test_every_versions_files_are_held_to_their_hashes(snapshot: SnapshotAssertion) -> None:
    """Hold every version's files to their hashes, and every version to being served.

    A published map loads its version's files from Louvre, so a changed or dropped file redraws every map published
    with that version. Until 1.0 that is how the kit changes, in its one version (D008): the snapshot shows each change
    in review. From 1.0, put a change in a new version of the kit instead.
    """
    hashes = {
        version: {path: hashlib.sha256(data).hexdigest() for path, (_, data) in sorted(kit.items())}
        for version, kit in maps.KITS.items()
    }

    assert hashes == snapshot
