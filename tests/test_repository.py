"""Repository tests: packaging, links, privacy, the examples and the skill's own selfcheck.

Run from the repository root: python -m pytest -q tests
Set MUSIC_SKILL_CONFIG to a renderer configuration written by bootstrap.py to include the render checks."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'music-production'
SCRIPTS = SKILL / 'scripts'
BEFORE_AFTER = ROOT / 'examples' / 'before-after'
AGENT_PIECES = {  # folder: the agent's script and its arguments as the example's README gives them, {out} the output
    'fughetta-on-a-lantern-theme': ('compose_baroque.py', ['{out}']),
    'platform-in-the-snowmelt': ('compose.py', ['{out}', 'r6']),
    'sodium-lights': ('compose.py', ['--output', '{out}', '--revision', 'r6']),
    'sprinkle-satellite': ('compose.py', ['{out}']),
}
CONFIG = os.environ.get('MUSIC_SKILL_CONFIG')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def frontmatter():
    yaml = pytest.importorskip('yaml')
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    assert m, 'SKILL.md starts with a YAML frontmatter'
    # a strict parser, as the agents' skill loaders use: an unquoted value holding ": " does not load
    return text, yaml.safe_load(m.group(1))


def test_skill_frontmatter():
    text, front = frontmatter()
    assert front['name'] == SKILL.name and re.fullmatch(r'[a-z0-9-]{1,64}', front['name'])
    assert 0 < len(front['description']) <= 1024
    assert '<' not in front['description'] and '>' not in front['description']
    assert len(front.get('compatibility', '')) <= 500
    assert all(isinstance(v, str) for v in front['metadata'].values())
    assert len(text.splitlines()) < 500


def test_plugin_manifests_agree():
    _, front = frontmatter()
    claude, codex = load(ROOT / '.claude-plugin' / 'plugin.json'), load(ROOT / '.codex-plugin' / 'plugin.json')
    assert front['metadata']['version'] == claude['version'] == codex['version']
    for path in claude['skills']:
        assert (ROOT / path / 'SKILL.md').is_file()
    for key in ('name', 'version', 'description', 'author', 'homepage', 'repository', 'license', 'keywords'):
        assert codex[key] == claude[key], key
    ui = codex['interface']
    assert len(ui['displayName']) <= 30 and len(ui['shortDescription']) <= 30 and len(ui['longDescription']) <= 4000
    assert len(ui['defaultPrompt']) <= 3 and all(len(p) <= 128 for p in ui['defaultPrompt'])
    assert re.fullmatch(r'#[0-9A-Fa-f]{6}', ui['brandColor'])
    markets = load(ROOT / '.claude-plugin' / 'marketplace.json'), load(ROOT / '.agents' / 'plugins' / 'marketplace.json')
    assert all(m['name'] == claude['name'] and [p['name'] for p in m['plugins']] == [claude['name']] for m in markets)


def image_size(path):
    """(width, height) of a PNG from its header, or of an SVG from its viewBox."""
    if path.suffix == '.svg':
        w, h = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', path.read_text(encoding='utf-8')).groups()
        return float(w), float(h)
    data = path.read_bytes()[:24]
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


def test_listing_icons():
    """Every icon a listing names exists, is square and at least 48 px; Claude's directory wants 512 to 2048 px."""
    claude, codex = load(ROOT / '.claude-plugin' / 'plugin.json'), load(ROOT / '.codex-plugin' / 'plugin.json')
    for rel in (claude['icon'], codex['interface']['composerIcon'], codex['interface']['logo']):
        w, h = image_size(ROOT / rel)
        assert w == h >= 48, (rel, w, h)
    w, _ = image_size(ROOT / claude['icon'])
    assert 512 <= w <= 2048 and (ROOT / claude['icon']).stat().st_size < 2_000_000
    assert all((ROOT / rel).is_file() for rel in codex['interface'].get('screenshots', []))


def test_skill_carries_its_codex_icons():
    """The skill's own Codex metadata travels with the folder: its icons are inside it, the brand's own."""
    yaml = pytest.importorskip('yaml')
    ui = yaml.safe_load((SKILL / 'agents' / 'openai.yaml').read_text(encoding='utf-8'))['interface']
    for key, brand in (('icon_small', 'icon-small.svg'), ('icon_large', 'icon-512.png')):
        assert (SKILL / ui[key]).read_bytes() == (ROOT / 'assets' / 'brand' / brand).read_bytes(), key


def test_skill_folder_carries_the_licence():
    """The skill is often copied on its own, without the repository round it: its folder keeps the licence."""
    assert (SKILL / 'LICENSE').read_text(encoding='utf-8') == (ROOT / 'LICENSE').read_text(encoding='utf-8')


def test_markdown_links_resolve():
    """Markdown links and the HTML images and links in the READMEs' headers point at files that exist."""
    bad = []
    for md in [*ROOT.glob('*.md'), *(ROOT / 'examples').rglob('*.md'), *SKILL.rglob('*.md')]:
        text = md.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)#\s]+)', text) + re.findall(r'(?:src|srcset|href)="([^"#]+)"', text):
            if not re.match(r'[a-z]+:', target) and not (md.parent / target).exists():
                bad.append(f'{md.relative_to(ROOT)} -> {target}')
    assert not bad, bad


def heading_anchor(heading):
    """GitHub's anchor for a heading, from its text as rendered: inline code kept as its text, raw HTML tags outside
    it dropped (GFM renders `<name>` written bare as a tag, so a heading's text loses it), link markup dropped, then
    lower case, punctuation other than hyphens and underscores removed, spaces to hyphens."""
    parts = re.split(r'(`[^`]+`)', heading.strip())
    text = ''.join(part[1:-1] if part.startswith('`') else re.sub(r'</?[A-Za-z][A-Za-z0-9-]*(\s[^<>]*)?/?>', '', part)
                   for part in parts)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text).lower()
    return re.sub(r'[^\w\- ]', '', text).replace(' ', '-')


def test_markdown_section_links_resolve():
    """Links to a section (file.md#anchor, or #anchor within a file) in the skill name a heading that exists."""
    def anchors(path):
        seen, found, code = {}, set(), False
        for line in path.read_text(encoding='utf-8').splitlines():
            code = code ^ line.startswith('```')
            if not code and re.match(r'#{1,6} ', line):
                a = heading_anchor(line.lstrip('#'))
                found.add(a if a not in seen else f'{a}-{seen[a]}')
                seen[a] = seen.get(a, 0) + 1
        return found
    bad = []
    for md in SKILL.rglob('*.md'):
        for target, anchor in re.findall(r'\]\(([^)#\s]*)#([^)\s]+)\)', md.read_text(encoding='utf-8')):
            dest = md.parent / target if target else md
            if not re.match(r'[a-z]+:', target) and dest.suffix == '.md' and anchor not in anchors(dest):
                bad.append(f'{md.relative_to(ROOT)} -> {target}#{anchor}')
    assert not bad, bad


def test_readmes_offer_every_language():
    """Each README links to every other one, so a reader can switch from any of them."""
    readmes = sorted(p.name for p in ROOT.glob('README*.md'))
    assert len(readmes) == 5, readmes
    for name in readmes:
        text = (ROOT / name).read_text(encoding='utf-8')
        assert all(other in text for other in readmes if other != name), name


# FreePats credits its SF2 assembly with this address; the selfcheck tests that an absolute archive member is refused.
ALLOWED = ("'C:/x.sf2'",)
PERSONAL = [re.compile(p) for p in (
    r'(?<![A-Za-z])[A-Za-z]:[\\/](?!/)', r'[\\/]Users[\\/]', r'[\\/]home[\\/]\w', r'\bsk-[A-Za-z0-9_-]{16,}',
    r'[\w.+-]+@[\w-]+\.[\w.]+', r'(?i)api[_-]?key\s*[:=]\s*[\'"]?\w{12,}')]


def repository_files():
    """The repository's own files: git's list in a checkout (a local .venv or render is not part of it), every file in
    an unpacked archive, and in a tree git lists nothing of (an export not staged yet, whose files the tests checked
    none of: an empty out.wav reached the export so)."""
    try:
        listed = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
        files = [ROOT / f for f in listed.split('\0') if f]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    return [p for p in ROOT.rglob('*') if p.is_file() and not {'.git', '__pycache__', '.pytest_cache'} & set(p.relative_to(ROOT).parts)]


def test_no_personal_data():
    """Nothing of the people who made it: no paths on their machines, no keys, no addresses."""
    hits = []
    for p in repository_files():
        if not p.is_file() or {'.git', '__pycache__', '.pytest_cache'} & set(p.parts) or p.resolve() == Path(__file__).resolve():
            continue
        if p.suffix == '.mp3':
            data = p.read_bytes()
            size = (data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9]) if data[:3] == b'ID3' else 0
            if re.search(rb'[A-Za-z]:\\|/Users/|/home/|@', data[10:10 + size]):  # the ID3 tags, not the audio
                hits.append(f'{p.relative_to(ROOT)}: a path or address in the tags')
            continue
        if p.suffix not in ('.py', '.md', '.json', '.txt', '.yaml', '.yml', '.toml', '.cfg', '.svg', ''):
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            for allowed in ALLOWED:
                line = line.replace(allowed, '')
            if any(b.search(line) for b in PERSONAL):
                hits.append(f'{p.relative_to(ROOT)}:{i}: {line.strip()[:100]}')
    assert not hits, '\n'.join(hits)


def test_example_projects():
    sys.path.insert(0, str(SCRIPTS))
    from musiclib.model import validate
    for folder in AGENT_PIECES:
        assert validate(load(ROOT / 'examples' / folder / 'song.json'))['seconds'] > 60, folder


@pytest.mark.parametrize('folder', AGENT_PIECES)
def test_agent_piece_script_writes_the_published_project(tmp_path, folder):
    """Each agent's script, run as its example's README says, writes a valid project equal to the published one."""
    script, args = AGENT_PIECES[folder]
    out = tmp_path / 'song.json'
    r = subprocess.run([sys.executable, str(ROOT / 'examples' / folder / script), *(a.replace('{out}', str(out)) for a in args)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    sys.path.insert(0, str(SCRIPTS))
    from musiclib.model import validate
    made = load(out)
    validate(made)  # the renderer's checks: a pitch written 60.0 equals 60 once parsed, but does not render
    assert made == load(ROOT / 'examples' / folder / 'song.json')


def test_examples_group_installs_the_examples_banks():
    """`fetch_soundbanks.py --only examples`, as each example's README says, installs the sound banks the examples'
    projects name, and only those."""
    named = {t['soundfont'] for f in (ROOT / 'examples').glob('*/*.json') for t in load(f).get('tracks', [])
             if t.get('soundfont') not in (None, 'default')}
    assert set(load(SKILL / 'references' / 'soundbank-lock.json')['groups']['examples']) == named


RECORDINGS = 'https://github.com/owoevan-dev/music-skill/releases/download/examples-3/'


def test_recordings_are_release_assets():
    """The example recordings are assets of the release examples-3: each language's README links the four pieces there,
    each example folder its own piece, and no recording is a repository file."""
    pieces = {f'{folder}.mp3' for folder in AGENT_PIECES}
    expected = {**{f'README{s}.md': pieces for s in ('', '.ja', '.ko', '.zh-CN', '.zh-TW')},
                **{f'examples/{folder}/README.md': {f'{folder}.mp3'} for folder in AGENT_PIECES}}
    for name, recordings in expected.items():
        links = re.findall(r'\]\(([^)\s]+\.mp3)\)', (ROOT / name).read_text(encoding='utf-8'))
        assert all(link.startswith(RECORDINGS) for link in links) and {link[len(RECORDINGS):] for link in links} == recordings, name
    assert not [p for p in repository_files() if p.is_file() and p.suffix.lower() in ('.mp3', '.wav', '.flac', '.ogg')]


def test_requirements_pin_numpy_by_hash():
    """requirements.txt names NumPy with the SHA-256 of every file PyPI publishes for the pinned version (pip's
    hash-checking mode), one pinned version per Python range and nothing else, so pip installs NumPy only as published."""
    lines = [l.strip() for l in (SKILL / 'requirements.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.lstrip().startswith('#')]
    entries, current = [], []
    for line in lines:
        current.append(line.rstrip('\\').strip())
        if not line.endswith('\\'):
            entries.append(' '.join(current))
            current = []
    assert not current and len(entries) == 2, entries
    for entry in entries:
        assert re.match(r'numpy==\d+\.\d+\.\d+; python_version [<>]=? "3\.\d+" ', entry), entry[:80]
        assert len(re.findall(r'--hash=sha256:[0-9a-f]{64}', entry)) >= 20, entry[:80]


def test_files_fit_the_plugin_directory():
    """The repository root is the plugin folder the Claude plugin directory checks: every file under 5 MiB, and nothing
    binary but images (its pre-submission checklist)."""
    for p in repository_files():
        if not p.is_file() or {'.git', '__pycache__', '.pytest_cache'} & set(p.parts):
            continue
        assert p.stat().st_size < 5 * 2**20, f'{p.relative_to(ROOT)} is 5 MiB or larger'
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
            assert b'\0' not in p.read_bytes(), f'{p.relative_to(ROOT)} is a binary file'


def test_before_after_example(tmp_path):
    """The before-and-after example as its README runs it: the script writes the published project, and the revision
    changes the flute's held note in bar 5 and nothing else."""
    r = subprocess.run([sys.executable, str(BEFORE_AFTER / 'porch_light.py'), str(tmp_path)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert r.returncode == 0, r.stderr[-2000:]
    before = load(BEFORE_AFTER / 'porch_light.json')
    assert load(tmp_path / 'song.json') == before and before['mix']['chain'] == 'bus'
    assert not any(t.get('soundfont') for t in before['tracks']), 'every part plays on the default bank'
    r = subprocess.run([sys.executable, str(SCRIPTS / 'studio.py'), 'revise', str(tmp_path / 'song.json'), '--track', 'flute',
                        '--note', 'flute_b005_n000', '--pitch', '76', '--output', str(tmp_path / 'song_r2.json')],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert r.returncode == 0, r.stderr[-2000:]
    after = load(tmp_path / 'song_r2.json')
    assert [h['note'] for h in after.pop('revision_history')] == ['flute_b005_n000']
    changed = [(n['id'], n['pitch'], m['pitch']) for t, u in zip(before['tracks'], after['tracks'])
               for n, m in zip(t['notes'], u['notes']) if n != m]
    assert changed == [('flute_b005_n000', 73, 76)]
    after['tracks'] = before['tracks']
    assert after == before


def test_selfcheck(tmp_path):
    work = tmp_path / 'selfcheck'
    cmd = [sys.executable, str(SCRIPTS / 'selfcheck.py'), '--work', str(work)] + (['--config', CONFIG] if CONFIG else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-3000:]
    report = load(work / 'selfcheck_report.json')
    assert report['status'] == 'PASS' and all(c['passed'] for c in report['checks'])
    assert len(report['checks']) == (152 if CONFIG else 122), [c['name'] for c in report['checks']]
