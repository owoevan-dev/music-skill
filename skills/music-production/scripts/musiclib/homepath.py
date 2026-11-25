"""MIT. A path given on a command line or in MUSIC_SKILL_CONFIG with its leading "~" read as the user's home (0.10).

PowerShell hands a native program "~" as it is, and argparse's Path does not expand it, so "~/.music-skill/config.json"
named a folder called "~".  Only "~" alone, or before a slash or a backslash, is the home: Path.expanduser also reads
"~name" as another user's home, so a file named "~notes.json" (which 0.9.3 took as it is) stopped with an error (the Astra
review of 0.10's step 2).  Kept out of musiclib.files, which a cached synthesis depends on (render.SYNTHESIS)."""
from pathlib import Path


def at_home(path):
    """`path` with a leading "~" (alone, or before "/" or "\\") as the user's home; any other path as it is; None stays None."""
    if path is None:
        return None
    text = str(path)
    if text == '~':
        return Path.home()
    if text.startswith(('~/', '~\\')):
        # the rest without its leading separators: "~//a.json" joined as "/a.json" was the drive's own a.json, while the
        # same spelling given to --config (a Path, which merges the slashes) was the home's (the Astra review of the whole)
        return Path.home() / text[2:].lstrip('/\\')
    return Path(path)
