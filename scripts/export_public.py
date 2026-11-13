"""Copy the public part of the project into a clone of the public repo.

    uv run scripts/export_public.py <folder>

The public repo is tiagojct/pythia-data. Clone it, run this script with the
clone as <folder>, then commit and push in the clone. The script copies only
the files in git (no keys, no caches), from the allowlist below. In <folder> it
replaces the folders data, prompts and coding as a whole, so files removed here
are removed there too. It does not remove files in scripts/.
The essay page (site/), the notes (OUTLINE.md, PLAN.md, CLAUDE.md) and the
project metadata stay private.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOW = ["config.toml", "pyproject.toml", "uv.lock", "prompts", "coding", "data",
         "scripts/run.py", "scripts/parse.py", "scripts/analyse_anchors.py",
         "scripts/code_timeline.py", "scripts/analyse_timeline.py", "scripts/canonical.py",
         "scripts/analyse_canonical.py", "scripts/plates.py", "scripts/handcheck_page.py",
         "scripts/analyse_readings.py", "scripts/export_public.py"]
PUBLIC = ROOT / "public"   # README.md and LICENSE of the public repo


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1]).resolve()
    if not (dest / ".git").exists():
        sys.exit(f"{dest} is not a git clone")
    files = subprocess.run(["git", "ls-files", *ALLOW], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.split()
    for top in {f.split("/")[0] for f in files} - {"scripts"}:
        target = dest / top
        if target.is_dir():
            shutil.rmtree(target)
    for f in files:
        (dest / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dest / f)
    for f in PUBLIC.iterdir():
        shutil.copy2(f, dest / f.name)
    print(f"copied {len(files)} files and {len(list(PUBLIC.iterdir()))} public files to {dest}")


if __name__ == "__main__":
    main()
