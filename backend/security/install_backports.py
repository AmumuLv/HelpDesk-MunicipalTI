"""Install verified, ABI-compatible backports and retain an honest inventory.

Distribution package versions are not rewritten. Raw package scanners may keep
reporting those versions; the artifact hashes record which binaries were patched.
"""
import glob
import hashlib
import json
import sysconfig
from pathlib import Path
import shutil

sources = {
    "libxml2.so.2": {
        "fix": "https://github.com/GNOME/libxml2/commit/d1686f91dbda141a752200419d35639fd6b38340",
        "cves": ["CVE-2026-86140"],
        "python_bindings": False,
    },
    "libz.so.1": {
        "fix": "https://github.com/madler/zlib/commit/df84af25dc1942490e1d1c899a07619152a46148",
        "cves": ["CVE-2026-85091"],
    },
    "libexpat.so.1": {
        "fixes": [
            "https://github.com/libexpat/libexpat/commit/bfc28346fa3efeb8ca56c17437d24a7344e5feab",
            "https://github.com/libexpat/libexpat/commit/621cb2c78b253ee023a86bc91d6ddb048481c04c",
            "https://github.com/libexpat/libexpat/commit/1bac53c4fc460a03cd9860f39501c7979f6750ae",
        ],
        "cves": ["CVE-2026-117610", "CVE-2026-118370"],
    },
}
for soname, evidence in sources.items():
    matches = glob.glob("/usr/lib/*-linux-gnu/" + soname)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one distribution library: {soname}")
    target = Path(matches[0]).resolve(strict=True)
    shutil.copyfile(Path(__file__).parent / soname, target)
    evidence["path"] = str(target)
    evidence["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()

module = (Path(sysconfig.get_path('stdlib')) / 'lib-dynload' / ('pyexpat' + sysconfig.get_config_var('EXT_SUFFIX'))).resolve(strict=True)
shutil.copyfile(Path(__file__).parent / 'pyexpat.so', module)
sources['libexpat.so.1']['python_module'] = {
    'path': str(module), 'sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
    'source': 'https://github.com/python/cpython/tree/v3.12.16/Modules',
}

destination = Path("/usr/local/share/helpdesk/security-backports.json")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
