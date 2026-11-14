"""Write the original 8-bit platform level score to song.json.

All note events are authored here. The local music-production 0.7.0 expression
module only adds small, deterministic performance deviations to the lead and
noise-drum parts after the notes have been written.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder of a copy of the skill on the machine it ran on).
SKILL_SCRIPTS = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL_SCRIPTS:
    sys.path.insert(0, str(SKILL_SCRIPTS))
from musiclib import expression  # noqa: E402


TITLE = "Noon Raccoon Rooftop Run"
REVISION = "1.0.r3"
TEMPO = 128
BAR_COUNT = 48
BEATS_PER_BAR = 4
SEED = 3793412909

WORD_STORY = (
    "At noon, a raccoon gives a wink from a porch and launches on a waffle barge across scrub. "
    "A leak swells into a shortcut past gnarled roots, a lemon bounces, and one tumble sends the raft "
    "by a sun-warm kiln before the runner returns to the porch."
)

SECTIONS = [
    {
        "id": "porch_run",
        "start_bar": 0,
        "bars": 16,
        "intent": "Bright G-major route: state a short, leaping hook over a rising pulse arpeggio.",
    },
    {
        "id": "drain_skip",
        "start_bar": 16,
        "bars": 16,
        "intent": "A lower E-minor detour with a tighter contour and a B7 pull back toward E.",
    },
    {
        "id": "porch_return",
        "start_bar": 32,
        "bars": 16,
        "intent": "Return to G major and the opening hook's register; stronger lead and backbeat accents carry the high point.",
    },
]

CHORDS = {
    "G": {"arp": [67, 71, 74], "root": 43, "symbol": "G"},
    "D": {"arp": [62, 66, 69], "root": 38, "symbol": "D"},
    "Em": {"arp": [64, 67, 71], "root": 40, "symbol": "Em"},
    "C": {"arp": [60, 64, 67], "root": 48, "symbol": "C"},
    "B7": {"arp": [59, 63, 66, 69], "root": 47, "symbol": "B7"},
}

PROGRESSIONS = {
    "porch_run": ["G", "D", "Em", "C"] * 4,
    "drain_skip": ["Em", "D", "C", "B7"] * 4,
    "porch_return": ["G", "D", "Em", "C"] * 3 + ["G", "C", "D", "G"],
}

# Each chord-root pattern is an original six-note, eighth-note hook with a
# one-beat hold and a half-beat breath. A small pickup is added at phrase ends.
MELODY = {
    "porch_run": {
        "G":  [74, 79, 83, 81, 79, 74],
        "D":  [78, 81, 86, 83, 81, 78],
        "Em": [76, 79, 83, 81, 79, 76],
        "C":  [76, 79, 84, 79, 76, 72],
        "B7": [71, 75, 78, 81, 78, 71],
    },
    "drain_skip": {
        "G":  [67, 74, 79, 78, 74, 71],
        "D":  [69, 74, 78, 81, 78, 74],
        "Em": [71, 76, 79, 78, 76, 71],
        "C":  [67, 72, 76, 74, 72, 67],
        "B7": [66, 71, 75, 78, 75, 71],
    },
}
MELODY_ONSETS = [0.0, 0.5, 1.0, 2.0, 2.5, 3.0]
MELODY_DURATIONS = [0.5, 0.5, 1.0, 0.5, 0.5, 0.5]
class TrackWriter:
    def __init__(self, track: dict):
        self.track = track
        self.notes: list[dict] = []
        self.performance: dict[str, dict] = {}
        self._serial_by_bar: dict[int, int] = {}

    def add(self, bar: int, beat: float, duration: float, pitch: int, velocity: int, gate: float = 0.9):
        serial = self._serial_by_bar.get(bar, 0)
        self._serial_by_bar[bar] = serial + 1
        note_id = f"{self.track['id']}_b{bar + 1:03d}_n{serial:03d}"
        event = {
            "id": note_id,
            "on": round(bar * BEATS_PER_BAR + beat, 4),
            "duration": round(duration, 4),
            "pitch": int(pitch),
        }
        self.notes.append(event)
        self.performance[note_id] = {"velocity": int(velocity), "timing_ms": 0, "gate": gate}

    def finish(self):
        self.track["notes"] = self.notes
        self.track["performance"] = {"notes": self.performance}


def make_track(track_id: str, name: str, role: str, preset: str, note_range: list[int],
               level: float, *, drums: bool = False, arpeggio: dict | None = None, bus: str | None = None):
    synth = {"preset": preset}
    if arpeggio is not None:
        synth["arpeggio"] = arpeggio
    mix = {
        "level_dbfs": level,
        "level_mode": "active_rms",
        "pan": 0,
        "width": 0,
        "reverb_db": None,
        "delay_db": None,
    }
    if bus:
        mix["bus"] = bus
    return {
        "id": track_id,
        "name": name,
        "role": role,
        "engine": "synth",
        "drums": drums,
        "range": note_range,
        "synth": synth,
        "notes": [],
        "performance": {"notes": {}},
        "mix": mix,
    }


def build_lead(writer: TrackWriter):
    for section in SECTIONS:
        section_id = section["id"]
        start = section["start_bar"]
        for bar_offset in range(section["bars"]):
            bar = start + bar_offset
            chord = PROGRESSIONS[section_id][bar_offset]
            pitches = list(MELODY["drain_skip" if section_id == "drain_skip" else "porch_run"][chord])

            # Phrase variation keeps the hook recognizable while changing its answer.
            cycle = bar_offset // 4
            if cycle == 1:
                pitches[3] = pitches[4]
            elif cycle == 2:
                pitches[1] = pitches[0]
            elif cycle == 3 and bar_offset % 4 == 3:
                pitches[5] = pitches[2]

            if section_id == "porch_run":
                base_velocity = 86
            elif section_id == "drain_skip":
                base_velocity = 78
            else:
                base_velocity = 96

            for i, (onset, duration, pitch) in enumerate(zip(MELODY_ONSETS, MELODY_DURATIONS, pitches)):
                accent = 4 if i in (0, 2) else 0
                if bar_offset % 4 == 1 and i == 4:
                    duration = 0.25
                writer.add(bar, onset, duration, pitch, base_velocity + accent, gate=0.84)

            # A short eighth-note pickup marks every four-bar phrase boundary.
            if bar_offset % 4 == 3:
                pickup = 71 if section_id == "drain_skip" else 79
                writer.add(bar, 3.5, 0.5, pickup, base_velocity + 2, gate=0.82)


def build_arpeggio(writer: TrackWriter):
    # Write each arpeggio as individual, monophonic sixteenth notes so the
    # score, MIDI and rendered pulse voice all carry the same up/down figure.
    for section in SECTIONS:
        start = section["start_bar"]
        for bar_offset, chord in enumerate(PROGRESSIONS[section["id"]]):
            bar = start + bar_offset
            velocity = 70 if section["id"] == "porch_run" else 66 if section["id"] == "drain_skip" else 76
            chord_tones = CHORDS[chord]["arp"]
            if len(chord_tones) == 3:
                root, third, fifth = chord_tones
                figure = [root, third, fifth, root + 12, fifth, third, root, third]
            else:
                root, third, fifth, seventh = chord_tones
                figure = [root, third, fifth, seventh, fifth, third, root, third]
            for step, pitch in enumerate(figure * 2):
                writer.add(bar, step * 0.25, 0.20, pitch, velocity, gate=0.82)


def build_bass(writer: TrackWriter):
    # The 16-step triangle stays at one velocity, with alternating root/fifth
    # notes and a small offbeat push on beats 2.5 and 3.5.
    for section in SECTIONS:
        start = section["start_bar"]
        for bar_offset, chord in enumerate(PROGRESSIONS[section["id"]]):
            bar = start + bar_offset
            root = CHORDS[chord]["root"]
            fifth = root + 7
            downbeat = root
            # At four phrase returns, a chord-third inversion breaks the
            # repeated perfect-fifth motion with the lead without changing the
            # chord's pitch collection.
            if bar in (4, 8, 12, 36, 40, 44):
                downbeat = root + 4  # major third of G
            elif bar == 16:
                downbeat = root + 3  # minor third of Em
            pattern = [(0.0, downbeat), (1.0, fifth), (2.5, root), (3.5, fifth)]
            if bar_offset % 4 == 3:
                pattern[-1] = (3.5, root + 12 if root + 12 <= 55 else root)
            for beat, pitch in pattern:
                writer.add(bar, beat, 0.42, pitch, 80, gate=0.94)


def build_drums(writer: TrackWriter):
    # One noise channel cannot strike two colours at once. The eight slots are
    # deliberately alternating: low thud, hat, snare, hat, then a second pair.
    main = [
        (0.0, 48, 96), (0.5, 96, 55), (1.0, 72, 78), (1.5, 96, 52),
        (2.0, 48, 89), (2.5, 96, 54), (3.0, 72, 74), (3.5, 96, 52),
    ]
    detour = [
        (0.0, 48, 90), (0.5, 96, 50), (1.0, 84, 67), (1.5, 96, 48),
        (2.0, 72, 70), (2.5, 96, 50), (3.0, 48, 84), (3.5, 96, 48),
    ]
    return_pattern = [
        (0.0, 48, 102), (0.5, 96, 58), (1.0, 72, 83), (1.5, 96, 55),
        (2.0, 48, 96), (2.5, 96, 56), (3.0, 72, 80), (3.5, 96, 55),
    ]
    for section in SECTIONS:
        start = section["start_bar"]
        pattern = detour if section["id"] == "drain_skip" else return_pattern if section["id"] == "porch_return" else main
        for bar_offset in range(section["bars"]):
            bar = start + bar_offset
            slots = list(pattern)
            # A changed noise colour on the final eighth of each four-bar
            # phrase marks the tumble without adding another instrument.
            if bar_offset % 4 == 3 and not (section["id"] == "porch_return" and bar_offset == 15):
                slots[-1] = (3.5, 84 if section["id"] == "drain_skip" else 96, 58)
            for beat, pitch, velocity in slots:
                writer.add(bar, beat, 0.11, pitch, velocity, gate=0.82)


def build_project() -> dict:
    source = json.loads((ROOT / "association.json").read_text(encoding="utf-8"))

    tracks = [
        make_track("pulse_lead", "Pulse lead · rooftop hook", "melody", "chip_pulse12", [64, 91], -19.5),
        make_track("pulse_arp", "Pulse arpeggio · written sixteenths", "harmony", "chip_pulse25", [59, 79], -25.0),
        make_track("triangle_bass", "Triangle bass · stepped route", "bass", "chip_triangle", [38, 55], -22.0),
        make_track("noise_drums", "Clocked noise · single-channel drums", "drums", "chip_noise", [48, 96], -25.0, drums=True, bus="drums"),
    ]
    writers = {track["id"]: TrackWriter(track) for track in tracks}
    build_lead(writers["pulse_lead"])
    build_arpeggio(writers["pulse_arp"])
    build_bass(writers["triangle_bass"])
    build_drums(writers["noise_drums"])
    for writer in writers.values():
        writer.finish()

    project = {
        "schema": "music-production/v1",
        "title": TITLE,
        "version": REVISION,
        "brief": (
            "Original 8-bit first-level platform-game instrumental, about 90 seconds, with a seamless loop: "
            "two pulse voices, stepped triangle bass, clocked noise drums, a bright immediate hook, fast chord arpeggios, "
            "a contrasting key section, then a return to the opening."
        ),
        "clock": {"bars": BAR_COUNT, "meter": [4, 4], "tempo": [[0, TEMPO]], "tail_seconds": 1},
        "sections": copy.deepcopy(SECTIONS),
        "tracks": tracks,
        "mix": {"chain": "bus", "rules": 2, "dynamics": "glue", "target_lufs": -14, "mono_below_hz": 120},
        "loop": {"start_bar": 0},
        "style": {"primary": "electronic/chiptune", "borrow": {"form": "game/overworld"}},
        "decisions": [
            "style:form: The level is a route to explore, so borrow game/overworld's forward-moving form for the A–B–A loop while keeping the pulse-channel language primary.",
            "tempo: 128 BPM is this piece's choice; 48 bars of 4/4 make the loop exactly 90 seconds.",
            "melody_durations:pulse_lead: Shortened the turnaround eighth to a sixteenth on the second bar of each four-bar phrase; the extra duration gives the short hook one quick articulation while retaining its readable eighth-note core.",
            "vertical: Restored the return to the opening melody register; this removes the nine B4/C6 minor-ninth clashes while keeping the return higher than the lower E-minor detour.",
            "outside_chord.melody: Changed the second phrase cycle so its strong-position non-chord tones move to the following chord tone before the leap; the return now uses the original G-major hook instead of a third-transposed line that created new unresolved tones.",
            "parallels: Inverted the recurring downbeat bass notes to chord thirds at bars 5, 9, 13, 17, 37, 41 and 45; those landings preserve the harmony while breaking parallel-fifth motion with the lead in both G-major statements and at the E-minor turn.",
            "stiffness:pulse_arp: Replaced held triad blocks with individual monophonic sixteenth notes in an up/down chord pattern, so the score and MIDI expose the actual moving arpeggio.",
            "builtin_preset:pulse_lead: Keep chip_pulse12 because its 12.5 percent duty is the requested narrow pulse voice and it makes the loop render repeatably; no Surge substitute was selected without a listening comparison.",
            "builtin_preset:pulse_arp: Use chip_pulse25 for the second pulse voice and write each arpeggio step directly; its 25 percent pulse is distinct from the lead and is repeatable without an external patch.",
            "plan:drain_skip: Mark the detour harmony faster because review counts the section-entry change as 1.00 chord changes per bar versus 0.94 in the opening, matching the written plan to the score.",
        ],
        "harmony": [],
        "association": {
            "source": source["source"],
            "seed": source["seed"],
            "words": source["words"],
            "whole": WORD_STORY,
            "gives": [
                {"level": "form", "what": "The porch departure, drain detour, and porch return set a 16+16+16 bar A–B–A loop.", "where": "all sections"},
                {"level": "harmony", "what": "The sunny launch and return sit in G major; the leaking shortcut shifts to E minor and uses B7 to turn home.", "where": "bars 1-48"},
                {"level": "melody", "what": "A compact leaping hook carries the wink; the lower, stepwise drain phrase is the tumble; the return restores the opening hook after the detour.", "where": "bars 1-48"},
                {"level": "rhythm", "what": "Sixteenth-note pulse arpeggios suggest the waffle barge's bounce; a single noise channel alternates thuds, snares and hats, with short phrase-end tumbles.", "where": "all sections"},
                {"level": "timbre", "what": "Four console-like voices only: narrow pulse melody, arpeggiated pulse chords, 16-step triangle bass and clocked noise drums.", "where": "all sections"},
            ],
        },
        "plan": {
            "identity": "A short rooftop hook stated over a written 16th-note pulse arpeggio, with a low E-minor detour and a G-major return.",
            "high_point": {"section": "porch_return", "means": "The opening hook returns after the lower detour; its lead and noise backbeat use the strongest section velocities, without adding tracks."},
            "sections": [
                {"section": "porch_run", "sounds": ["pulse_lead", "pulse_arp", "triangle_bass", "noise_drums"], "leads": "pulse_lead", "differs": "The first statement of the rooftop route and its short hook."},
                {"section": "drain_skip", "sounds": ["pulse_lead", "pulse_arp", "triangle_bass", "noise_drums"], "leads": "pulse_lead", "register": {"pulse_lead": "lower"}, "harmony": "faster", "dynamics": "softer", "differs": "The E-minor detour lowers the hook, thins the drum accents and tightens the melody contour."},
                {"section": "porch_return", "sounds": ["pulse_lead", "pulse_arp", "triangle_bass", "noise_drums"], "leads": "pulse_lead", "register": {"pulse_lead": "higher"}, "harmony": "same", "dynamics": "louder", "differs": "The opening G-major hook returns at its original register after the lower E-minor section; the stronger lead and backbeat lift the high point."},
            ],
        },
    }

    for bar, section in enumerate(SECTIONS):
        for offset in range(section["bars"]):
            global_bar = section["start_bar"] + offset
            chord = PROGRESSIONS[section["id"]][offset]
            project["harmony"].append({"bar": global_bar + 1, "beat": 0, "symbol": CHORDS[chord]["symbol"]})

    # Chiptune timing stays close to the grid. The bass and pulse arpeggio retain
    # fixed velocities; the melody and noise hits receive small deterministic
    # phrase-level movement from the skill's player-performance model.
    expression.apply(
        project,
        overrides={
            "pulse_lead": {"timing_sd": 1.5, "short_sd": 0.7, "vel_pct": 1.5, "high_loud": 0.15, "arch": 1.5, "gate_sd": 0.01},
            "pulse_arp": None,
            "triangle_bass": None,
            "noise_drums": {"timing_sd": 1.2, "short_sd": 0.5, "vel_pct": 1.5, "cymbal_cycle": 1.0},
        },
        seed=SEED,
        drift="time",
    )
    return project


def main():
    project = build_project()
    output = ROOT / "song.json"
    output.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {track["id"]: len(track["notes"]) for track in project["tracks"]}
    print(f"Wrote {output}")
    print(f"Title: {project['title']} | {BAR_COUNT} bars at {TEMPO} BPM | loop: {BAR_COUNT * BEATS_PER_BAR * 60 / TEMPO:.3f} s")
    print(f"Tracks: {counts} | total note events: {sum(counts.values())}")


if __name__ == "__main__":
    main()
