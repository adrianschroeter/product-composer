from productcomposer.core.PkgSelect import PkgSelect
from productcomposer.utils import rpmutils
from productcomposer.utils.rpmutils import (
    create_package_set,
    create_package_set_cached,
    link_rpms_to_tree,
)


class FakeRpm:
    name = "test-package"
    arch = "x86_64"
    canonfilename = "test-package.rpm"
    location = "/unused/test-package.rpm"
    provides = []

    def get_src_package(self):
        return None


class FakePool:
    updateinfos = []

    def __init__(self, rpm):
        self.rpm = rpm

    def lookup_all_updateinfos(self):
        return []

    def lookup_rpm(self, arch, name, op=None, epoch=None, version=None, release=None):
        if arch == "x86_64" and name == self.rpm.name:
            return self.rpm
        return None


def _supportstatus_in(pkgset, package):
    for sel in pkgset:
        if sel.name == package:
            return sel.supportstatus, sel.supportstatus_forced
    raise AssertionError(f"{package} not found")


def _supportstatus_for(yml, setname, package):
    return _supportstatus_in(create_package_set(yml, "x86_64", None, setname), package)


def _packageset(**kwargs):
    out = {
        "name": "main",
        "supportstatus": None,
        "flavors": None,
        "architectures": None,
        "add": None,
        "sub": None,
        "intersect": None,
        "packages": None,
    }
    out.update(kwargs)
    return out


def _link_supportstatus(yml, file_supportstatus, monkeypatch, package="test-package"):
    supportstatus = {}
    supportstatus_override = {package: file_supportstatus}
    rpm = FakeRpm()
    rpm.name = package
    rpm.canonfilename = f"{package}.rpm"
    rpm.location = f"/unused/{package}.rpm"

    monkeypatch.setattr(rpmutils, "link_entry_into_dir", lambda *args, **kwargs: None)
    link_rpms_to_tree(
        "/unused",
        yml,
        FakePool(rpm),
        "x86_64",
        None,
        {},
        supportstatus,
        supportstatus_override,
    )

    return supportstatus[package]


def test_file_supportstatus_overrides_normal_yaml_supportstatus(monkeypatch):
    yml = {
        "build_options": [],
        "content": ["main"],
        "packagesets": [
            _packageset(supportstatus="l2", packages=["test-package"]),
        ],
    }

    assert _link_supportstatus(yml, "unsupported", monkeypatch) == "unsupported"


def test_forced_yaml_supportstatus_overrides_file_supportstatus(monkeypatch):
    yml = {
        "build_options": [],
        "content": ["main"],
        "packagesets": [
            _packageset(supportstatus="=unsupported", packages=["test-package"]),
        ],
    }

    assert _link_supportstatus(yml, "l3", monkeypatch) == "unsupported"


def test_forced_supportstatus_is_not_overwritten_by_later_non_equal_selector(
    monkeypatch,
):
    yml = {
        "build_options": [],
        "content": ["main"],
        "packagesets": [
            _packageset(
                name="forced", supportstatus="=l2", packages=["test-package >= 1"]
            ),
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(name="main", add=["forced", "normal"]),
        ],
    }

    assert _link_supportstatus(yml, "unsupported", monkeypatch) == "l2"


def test_later_forced_non_equal_selector_overwrites_file_supportstatus(monkeypatch):
    yml = {
        "build_options": [],
        "content": ["main"],
        "packagesets": [
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(
                name="forced", supportstatus="=l2", packages=["test-package >= 1"]
            ),
            _packageset(name="main", add=["normal", "forced"]),
        ],
    }

    assert _link_supportstatus(yml, "unsupported", monkeypatch) == "l2"


def test_forced_supportstatus_survives_copy():
    sel = PkgSelect("test-package", supportstatus="l2", supportstatus_forced=True)

    copied = sel.copy()

    assert copied.supportstatus == "l2"
    assert copied.supportstatus_forced is True


def test_forced_supportstatus_is_applied_to_added_packages():
    yml = {
        "packagesets": [
            _packageset(name="forced", supportstatus="=l2", packages=["test-package"]),
        ],
    }

    assert _supportstatus_for(yml, "forced", "test-package") == ("l2", True)


def test_forced_supportstatus_survives_package_set_add():
    yml = {
        "packagesets": [
            _packageset(name="base", supportstatus="=l2", packages=["test-package"]),
            _packageset(name="main", add=["base"]),
        ],
    }

    assert _supportstatus_for(yml, "main", "test-package") == ("l2", True)


def test_duplicate_upgrade_does_not_mutate_source_package_set():
    yml = {
        "packagesets": [
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(name="forced", supportstatus="=l2", packages=["test-package"]),
            _packageset(name="main", add=["normal", "forced"]),
            _packageset(name="reuse-normal", add=["normal"]),
        ],
    }

    pkgsetcache = {}
    pkgsets_rawcache = {}
    main = create_package_set_cached(
        yml, "x86_64", None, "main", pkgsetcache, pkgsets_rawcache
    )
    reuse_normal = create_package_set_cached(
        yml, "x86_64", None, "reuse-normal", pkgsetcache, pkgsets_rawcache
    )

    assert _supportstatus_in(main, "test-package") == ("l2", True)
    assert _supportstatus_in(reuse_normal, "test-package") == (
        "unsupported",
        False,
    )


def test_forced_duplicate_supportstatus_upgrades_existing_selector():
    yml = {
        "packagesets": [
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(name="forced", supportstatus="=l2", packages=["test-package"]),
            _packageset(name="main", add=["normal", "forced"]),
        ],
    }

    assert _supportstatus_for(yml, "main", "test-package") == ("l2", True)


def test_existing_forced_supportstatus_is_not_downgraded_by_normal_duplicate():
    yml = {
        "packagesets": [
            _packageset(name="forced", supportstatus="=l2", packages=["test-package"]),
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(name="main", add=["forced", "normal"]),
        ],
    }

    assert _supportstatus_for(yml, "main", "test-package") == ("l2", True)


def test_forced_supportstatus_survives_intersect():
    yml = {
        "packagesets": [
            _packageset(name="forced", supportstatus="=l2", packages=["test-package"]),
            _packageset(name="filter", packages=["test-package"]),
            _packageset(name="main", add=["forced"], intersect=["filter"]),
        ],
    }

    assert _supportstatus_for(yml, "main", "test-package") == ("l2", True)


def test_forced_supportstatus_survives_intersect_duplicate_collapse():
    yml = {
        "packagesets": [
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(
                name="forced", supportstatus="=l2", packages=["test-package >= 1"]
            ),
            _packageset(name="filter", packages=["test-package >= 1"]),
            _packageset(
                name="main", add=["normal", "forced"], intersect=["filter"]
            ),
        ],
    }

    assert _supportstatus_for(yml, "main", "test-package") == ("l2", True)


def test_forced_supportstatus_survives_intersect_duplicate_collapse_reversed():
    yml = {
        "packagesets": [
            _packageset(
                name="forced", supportstatus="=l2", packages=["test-package >= 1"]
            ),
            _packageset(
                name="normal", supportstatus="unsupported", packages=["test-package"]
            ),
            _packageset(name="filter", packages=["test-package >= 1"]),
            _packageset(
                name="main", add=["forced", "normal"], intersect=["filter"]
            ),
        ],
    }

    assert _supportstatus_for(yml, "main", "test-package") == ("l2", True)
