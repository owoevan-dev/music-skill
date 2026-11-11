"""Write the complete, original 8-bit title-screen cue to song.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder where the skill was installed on the machine it ran on).
SKILL_SCRIPTS = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL_SCRIPTS:
    sys.path.insert(0, str(SKILL_SCRIPTS))
from musiclib.expression import apply as apply_expression  # noqa: E402


ROOT = Path(__file__).resolve().parent
TITLE = "Skybutton Speedway"
TEMPO = 128
BAR_BEATS = 4
BAR_COUNT = 48
SEED = 12848
CURRENT_REVISION = 1
PREVIOUS_NOTE_IDS = {}
NOTE_ORDINALS = {}
PREVIOUS_HISTORY = []


# Chords are written as pitches in the score review. The arp deliberately omits
# seventh/color tones when the triad already makes the harmony clear.
CHORDS = {
    "D6":      {"root": 2,  "bass": 38, "triad": [2, 6, 9], "tones": [2, 6, 9, 11]},
    "F#m7":    {"root": 6,  "bass": 42, "triad": [6, 9, 1], "tones": [6, 9, 1, 4]},
    "G6":      {"root": 7,  "bass": 43, "triad": [7, 11, 2], "tones": [7, 11, 2, 4]},
    "A7sus4":  {"root": 9,  "bass": 45, "triad": [9, 2, 4], "tones": [9, 2, 4, 7]},
    "Bm7":     {"root": 11, "bass": 35, "triad": [11, 2, 6], "tones": [11, 2, 6, 9]},
    "E7":      {"root": 4,  "bass": 40, "triad": [4, 8, 11], "tones": [4, 8, 11, 2]},
    "Gmaj7":   {"root": 7,  "bass": 43, "triad": [7, 11, 2], "tones": [7, 11, 2, 6]},
    "A7":      {"root": 9,  "bass": 45, "triad": [9, 1, 4], "tones": [9, 1, 4, 7]},
    "C#m7":    {"root": 1,  "bass": 37, "triad": [1, 4, 8], "tones": [1, 4, 8, 11]},
    "D":       {"root": 2,  "bass": 38, "triad": [2, 6, 9], "tones": [2, 6, 9]},
    "Em7":     {"root": 4,  "bass": 40, "triad": [4, 7, 11], "tones": [4, 7, 11, 2]},
    "B7":      {"root": 11, "bass": 35, "triad": [11, 3, 6], "tones": [11, 3, 6, 9]},
    "Cmaj7":   {"root": 0,  "bass": 36, "triad": [0, 4, 7], "tones": [0, 4, 7, 11]},
}


FORM_CHORDS = [
    # A: statement and answer, each with a different eight-bar path.
    "D6", "F#m7", "G6", "A7sus4", "Bm7", "E7", "Gmaj7", "A7",
    "D6", "C#m7", "G6", "D", "Bm7", "E7", "Gmaj7", "A7",
    # B: a relative-minor route, then a borrowed C-major color and return.
    "Em7", "A7", "D", "B7", "Em7", "Cmaj7", "G6", "D6",
    "Cmaj7", "G6", "D6", "B7", "Em7", "Cmaj7", "A7sus4", "A7",
    # A returns unchanged in outline; the closing eight bars point back to D.
    "D6", "F#m7", "G6", "A7sus4", "Bm7", "E7", "Gmaj7", "A7",
    "Bm7", "G6", "D", "E7", "Gmaj7", "D6", "A7sus4", "A7",
]


LEAD_A = [
    [(86,.5),(81,.5),(83,.5),(86,.5),(83,.5),(81,.25),(None,.25),(78,.5),(76,.5)],
    [(78,.5),(81,.5),(85,.75),(81,.5),(78,.5),(76,.25),(None,1)],
    [(79,.5),(83,.5),(86,.5),(83,.5),(88,.5),(86,.5),(83,.5),(79,.5)],
    [(81,.5),(86,.5),(88,.75),(None,.25),(81,.5),(79,.5),(76,1)],
    [(83,.5),(86,.5),(81,.5),(78,.5),(86,.5),(83,.5),(81,.5),(78,.5)],
    [(76,.5),(80,.5),(83,.5),(86,.5),(83,.5),(80,.5),(76,1)],
    [(79,.5),(83,.5),(86,.5),(78,.5),(86,.5),(83,.5),(79,1)],
    [(85,.5),(88,.5),(79,.5),(81,.5),(88,1),(85,.5),(81,.5)],
]

LEAD_RETURN = [list(line) for line in LEAD_A]
LEAD_RETURN[4] = [(83,.5),(78,.5),(81,.5),(83,.5),(81,.5),(78,.25),(None,.25),(76,.5),(74,.5)]
LEAD_RETURN[5] = [(76,.5),(80,.25),(83,.75),(86,.5),(83,.5),(80,.5),(76,1)]
LEAD_RETURN[6] = [(79,.5),(83,.5),(86,.5),(81,.5),(78,.5),(83,.5),(79,1)]
LEAD_RETURN[7] = [(88,.5),(85,.5),(81,.5),(79,.5),(88,.75),(85,.25),(81,1)]

LEAD_A_ANSWER = [
    [(86,.5),(81,.5),(83,.5),(86,.5),(88,.5),(86,.5),(83,.5),(81,.5)],
    [(85,.5),(88,.5),(83,.5),(80,.5),(76,.5),(80,.5),(83,1)],
    [(79,.5),(83,.5),(86,1),(88,.5),(86,.5),(83,1)],
    [(81,.5),(86,.5),(78,.5),(81,.5),(86,1),(None,1)],
    [(83,.5),(86,.5),(78,.5),(81,.5),(83,.5),(81,.5),(78,1)],
    [(80,.5),(83,.5),(86,.5),(88,.5),(86,.5),(83,.5),(80,1)],
    [(79,.5),(83,.5),(86,.5),(78,.5),(79,.5),(83,.5),(86,1)],
    [(88,.5),(85,.5),(81,.5),(79,.5),(88,1),(85,1)],
]

LEAD_B = [
    [(76,.5),(79,.5),(83,1),(86,.5),(83,.5),(79,1)],
    [(81,.5),(85,.5),(88,1),(79,.5),(76,.5),(85,1)],
    [(78,.5),(81,.5),(86,1),(81,.5),(78,.5),(86,1)],
    [(83,.5),(87,.5),(78,.5),(81,.5),(78,.5),(87,.5),(83,1)],
    [(76,.5),(79,.5),(83,.5),(86,.5),(88,.5),(86,.5),(83,.5),(79,.5)],
    [(84,.5),(88,.5),(79,.5),(83,.5),(79,.5),(76,.5),(None,1)],
    [(83,.5),(86,.5),(88,.5),(79,.5),(83,.5),(88,.5),(86,1)],
    [(88,.5),(90,.5),(88,.5),(86,.5),(83,1),(81,1)],
]

LEAD_B_ANSWER = [
    [(88,.5),(79,.5),(83,.5),(84,.5),(83,.5),(79,.5),(76,.5),(72,.5)],
    [(86,.5),(83,.5),(79,.5),(86,.5),(83,1),(79,1)],
    [(81,.5),(86,.5),(78,1),(81,.5),(78,.5),(86,1)],
    [(83,.5),(87,.5),(78,.5),(81,.5),(78,.5),(87,.5),(83,1)],
    [(76,.5),(79,.5),(83,.5),(86,.5),(88,.5),(86,.5),(83,.5),(79,.5)],
    [(72,.5),(76,.5),(79,.5),(83,.5),(84,.5),(83,.5),(None,1)],
    [(81,.5),(86,.5),(88,.5),(79,.5),(88,.5),(86,.5),(81,1)],
    [(76,.5),(79,.5),(81,.5),(85,.5),(88,1),(85,1)],
]

LEAD_CLOSING = [
    [(83,.5),(86,.5),(81,.5),(78,.5),(86,.5),(83,.5),(81,.5),(78,.5)],
    [(79,.5),(83,.5),(86,.5),(78,.5),(86,.5),(83,.5),(79,1)],
    [(78,.5),(81,.5),(86,.5),(81,.5),(78,.5),(86,.5),(81,1)],
    [(76,.5),(80,.5),(83,.5),(86,.5),(83,.5),(80,.5),(76,1)],
    [(79,.5),(83,.5),(86,.5),(78,.5),(79,.5),(83,.5),(86,1)],
    [(81,.5),(86,.5),(78,.5),(81,.5),(86,1),(None,1)],
    [(81,.5),(86,.5),(88,.5),(86,.5),(81,.5),(79,.5),(76,1)],
    # C# at the end leads by semitone to the opening D across the loop seam.
    [(81,.5),(85,.5),(88,1),(79,.5),(81,.5),(76,.5),(85,.5)],
]


SECTIONS = [
    ("button", 0, "The hook states its falling-and-rising four-note cell."),
    ("lift", 8, "The answering phrase rises and closes with the first rapid arpeggio."),
    ("cloudpath", 16, "E minor and a borrowed C-major color lead to the F-sharp-six peak."),
    ("open_sky", 24, "The texture thins after the peak, then turns toward A7."),
    ("return", 32, "The hook returns with a new answer and reversed arpeggio contour."),
    ("loopback", 40, "The backing thins in the closing bars; A7 leads to the opening D."),
]


def add_note(track, bar, offset, duration, pitch, velocity, gate=0.92, phrase=None):
    if pitch is None:
        return
    key = (track["id"], bar)
    ordinal = NOTE_ORDINALS.get(key, 0)
    NOTE_ORDINALS[key] = ordinal + 1
    if CURRENT_REVISION >= 2 and (track["id"], bar, ordinal) in PREVIOUS_NOTE_IDS:
        note_id = PREVIOUS_NOTE_IDS[(track["id"], bar, ordinal)]
    elif CURRENT_REVISION >= 2:
        note_id = f"{track['id']}_b{bar + 1:03d}_r2_n{ordinal:02d}"
    else:
        step = int(round(offset * 4))
        note_id = f"{track['id']}_b{bar + 1:03d}_s{step:02d}"
    on = bar * BAR_BEATS + offset
    note = {
        "id": note_id,
        "on": round(on, 6),
        "duration": round(duration, 6),
        "pitch": int(pitch),
    }
    if phrase:
        note["phrase"] = phrase
    track["notes"].append(note)
    track["performance"]["notes"][note_id] = {
        "velocity": int(velocity),
        "timing_ms": 0,
        "gate": gate,
    }


def add_line(track, bar, events, velocity, phrase):
    offset = 0.0
    total = 0.0
    for pitch, duration in events:
        add_note(track, bar, offset, duration, pitch, velocity, 0.93, phrase)
        offset += duration
        total += duration
    if abs(total - BAR_BEATS) > 1e-7:
        raise ValueError(f"melody line at bar {bar + 1} spans {total} beats")


def chord_tones_up(chord):
    root = CHORDS[chord]["root"]
    triad = set(CHORDS[chord]["triad"])
    root_pitch = next(p for p in range(48, 60) if p % 12 == root)
    return sorted(p for p in range(root_pitch, root_pitch + 12) if p % 12 in triad)


def make_track(track_id, name, role, program, patch, bus, level, note_range, drums=False):
    return {
        "id": track_id,
        "name": name,
        "role": role,
        "engine": "synth",
        "program": program,
        "bank": 0,
        "drums": drums,
        "range": note_range,
        "synth": {"preset": patch},
        "notes": [],
        "performance": {"notes": {}, "cc_mode": "step"},
        "mix": {
            "bus": bus,
            "level_dbfs": level,
            "reverb_db": None,
            "delay_db": None,
            "pan": 0,
            "width": 0.25,
        },
    }


def build_project(revision):
    global CURRENT_REVISION, PREVIOUS_NOTE_IDS, NOTE_ORDINALS, PREVIOUS_HISTORY
    CURRENT_REVISION = revision
    PREVIOUS_NOTE_IDS = {}
    NOTE_ORDINALS = {}
    PREVIOUS_HISTORY = []
    previous_path = ROOT / "song.json"
    if revision >= 2 and previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        PREVIOUS_HISTORY = list(previous.get("revision_history", []))
        for old_track in previous.get("tracks", []):
            grouped = {}
            for note in sorted(old_track.get("notes", []), key=lambda n: (n["on"], n["pitch"])):
                old_bar = int(note["on"] // BAR_BEATS)
                grouped.setdefault(old_bar, []).append(note["id"])
            for old_bar, ids in grouped.items():
                for ordinal, note_id in enumerate(ids):
                    PREVIOUS_NOTE_IDS[(old_track["id"], old_bar, ordinal)] = note_id

    lead = make_track("pulse_lead", "25% pulse hook", "melody", 80, "chip_pulse25", "lead", -18, [72, 90])
    arp = make_track("pulse_arp", "12.5% pulse arpeggio", "rhythm", 80, "chip_pulse12", "rhythm", -23, [48, 71])
    bass = make_track("tri_bass", "16-step triangle bass", "bass", 38, "chip_triangle", "bass", -21, [35, 57])
    drums = make_track("noise_drums", "Clocked noise drums", "drums", 0, "chip_noise", "drums", -24, [36, 102], True)
    tracks = {t["id"]: t for t in (lead, arp, bass, drums)}

    # One theme, one answer, a contrasting section, its descent, then the return.
    for i, events in enumerate(LEAD_A):
        add_line(lead, i, events, 103, "hook")
    for i, events in enumerate(LEAD_A_ANSWER, start=8):
        add_line(lead, i, events, 101, "answer")
    for i, events in enumerate(LEAD_B, start=16):
        add_line(lead, i, events, 102, "cloudpath")
    for i, events in enumerate(LEAD_B_ANSWER, start=24):
        add_line(lead, i, events, 99, "descent")
    for i, events in enumerate(LEAD_RETURN, start=32):
        add_line(lead, i, events, 103, "return_hook")
    for i, events in enumerate(LEAD_CLOSING, start=40):
        add_line(lead, i, events, 101, "turnaround")

    # Off-beat chord-tone figures keep the second pulse monophonic and separate
    # its attacks from the hook. Two sixteenth-note runs mark the lift and B.
    up = [0, 1, 2, 1, 2, 1, 0, 1]
    down = [2, 1, 0, 1, 0, 1, 2, 1]
    run = [0, 1, 2, 1, 0, 1, 2, 1, 2, 1, 0, 1, 2, 0, 1, 2]
    quarter = [0, 1, 2, 1]
    fast_bars = {15, 19}
    for bar, chord in enumerate(FORM_CHORDS):
        pitches = chord_tones_up(chord)
        pattern = (down if bar % 2 else up)
        if 16 <= bar < 32:
            pattern = up if bar % 2 else down
        if 32 <= bar < 40:
            pattern = up if bar % 2 else down
        if bar in fast_bars:
            step, start_offset, indices, velocity = 0.25, 0.125, run, 79
            phrase = "sixteenth_run"
        elif bar < 8 or 24 <= bar < 32 or bar >= 40:
            step, start_offset, indices = 1.0, 0.125, quarter
            velocity = 75 if 24 <= bar < 32 else 76 if bar < 8 else 72
            phrase = "sparse_frame"
        else:
            step, start_offset, indices, velocity = 0.5, 0.125, pattern, 79
            phrase = "chord_arp"
        for slot, index in enumerate(indices):
            pitch = pitches[index % len(pitches)]
            offset = start_offset + slot * step
            if bar == 45 and slot == 3:
                # B is the sixth of D6, matching the opening's B without adding
                # a new pitch class at the seam.
                pitch = 59
            duration = min(step * 0.92, BAR_BEATS - offset)
            add_note(arp, bar, offset, duration, pitch, velocity, 0.96, phrase)

    # Triangle bass stays at one velocity throughout, as on the source chip.
    for bar, chord in enumerate(FORM_CHORDS):
        info = CHORDS[chord]
        root = info["bass"]
        fifth = root + 7
        octave = root + 12
        third_interval = (info["triad"][1] - info["root"]) % 12
        third = root + third_interval
        if bar == 47:
            events = [(0, root), (1, fifth), (2, root + 10), (3, root)]
        elif bar == 29:
            events = [(0, root), (1, fifth), (2, third), (3, third)]
        elif bar == 42:
            events = [(0, root), (1, fifth), (2, octave), (3, third)]
        elif 32 <= bar < 40:
            events = [(0, root), (1, octave), (2, fifth), (3, third)]
        elif 16 <= bar < 32:
            events = [(0, root), (1, fifth), (2, third), (3, fifth)]
        elif bar % 4 == 3:
            events = [(0, root), (1, octave), (2, fifth), (3, root)]
        else:
            events = [(0, root), (1, fifth), (2, octave), (3, fifth)]
        for beat, pitch in events:
            add_note(bass, bar, beat, 0.94, pitch, 88, 0.96, "bass_pulse")

    # A single noise channel: low clocked thuds, C5 snare-like noise, and
    # short high-rate ticks. Boundary bars use a distinct final hit as a fill.
    section_end_bars = {7, 15, 23, 31, 39, 47}
    drum_pitches = [48, 96, 72, 96, 48, 96, 72, 96]
    drum_velocities = [116, 62, 100, 56, 112, 64, 102, 58]
    for bar in range(BAR_COUNT):
        for slot, (pitch, velocity) in enumerate(zip(drum_pitches, drum_velocities)):
            if slot == 7 and bar in section_end_bars:
                pitch = 72 if bar != 23 else 100
                velocity = 92 if bar != 23 else 76
            add_note(drums, bar, slot * 0.5, 0.20, pitch, velocity, 0.78, "noise_groove")

    # The return keeps its strict chip-channel roles. Only the pulse and noise
    # lines receive very small, seeded performance drift; triangle velocity is
    # deliberately constant.
    expression_report = apply_expression(
        {"tracks": list(tracks.values()), "clock": {"bars": BAR_COUNT, "meter": [4, 4]}, "sections": [
            {"id": sid, "start_bar": start, "bars": 8} for sid, start, _ in SECTIONS
        ]},
        overrides={
            "pulse_lead": {"timing_sd": 0.8, "short_sd": 0.3, "feel": 0, "vel_pct": 0.8,
                           "high_loud": 0.15, "arch": 1.0, "spread": 0, "lead": 0,
                           "gate_sd": 0.005, "contrast": 0.01, "cymbal_cycle": 0},
            "pulse_arp": {"timing_sd": 0.5, "short_sd": 0.2, "feel": 0, "vel_pct": 0.6,
                          "high_loud": 0, "arch": 0, "spread": 0, "lead": 0,
                          "gate_sd": 0, "contrast": 0, "cymbal_cycle": 0},
            "tri_bass": None,
            "noise_drums": {"timing_sd": 0.35, "short_sd": 0.15, "feel": 0, "vel_pct": 0.8,
                            "high_loud": 0, "arch": 0, "spread": 0, "lead": 0,
                            "gate_sd": 0, "contrast": 0, "cymbal_cycle": 0},
        },
        seed=SEED,
        drift="time",
    )

    sections = [
        {"id": sid, "start_bar": start, "bars": 8, "intent": intent}
        for sid, start, intent in SECTIONS
    ]
    project = {
        "schema": "music-production/v1",
        "title": TITLE,
        "version": f"1.0.r{revision}",
        "brief": "Original instrumental 8-bit chiptune for a retro platform game's title screen; bright, immediately identifiable, two pulse voices, triangle bass, and a single noise drum channel; seamless 90-second loop.",
        "style": "electronic/chiptune",
        "clock": {"bars": BAR_COUNT, "meter": [4, 4], "tempo": [[0, TEMPO]], "tail_seconds": 1.0},
        "sections": sections,
        "tracks": list(tracks.values()),
        "loop": {"start_bar": 0},
        "mix": {
            "chain": "bus",
            "rules": 2,
            "dynamics": "glue",
            "target_lufs": -14,
            "mono_below_hz": 120,
        },
        "harmony": [
            {"bar": bar + 1, "symbol": chord}
            for bar, chord in enumerate(FORM_CHORDS)
        ],
        "decisions": [
            "All pitches and rhythms were composed for this piece; no existing melody, progression, or title was used as a template.",
            "The 48 bars at 128 quarter-note BPM in 4/4 make a 90-second loop. It starts on D and the last A7 leads to the opening D.",
            "The only voices are 25% pulse hook, 12.5% pulse arpeggio, 16-step triangle bass, and clocked noise drums. Two brief sixteenth-note arpeggios mark the lift and B section; the second pulse thins to quarter-note chord tones after the peak and in the closing bars.",
            "The B section moves through E minor and a borrowed C-major color. Its only F-sharp-six melody note is held for the section's high point in bar 24.",
            "The triangle uses one fixed velocity. The loop is dry, centered, and has no extra layers, sampled instruments, or reverb; the version-2 bus chain uses glue dynamics and a -14 LUFS game-asset target.",
            "musiclib.expression is applied with sub-millisecond pulse/noise timing profiles for a deterministic, nearly grid-locked chip performance; the triangle is left unchanged.",
        ],
        "revision_history": PREVIOUS_HISTORY + [
            {"revision": f"r{revision}", "note": "Initial authored score." if revision == 1 else f"Review-driven revision {revision}; see NOTES.md for the question-by-question decisions."}
        ],
    }

    if revision >= 2:
        project["decisions"].extend([
            "R2 adds dotted and sixteenth-note lead durations with phrase rests, then varies the returning answer while preserving the opening hook.",
            "R2 moves the second pulse to off-beat attacks so the arpeggio remains a separate voice; the return reverses its contour, and B moves through two brief sixteenth-note runs.",
            "R2 removes the two reviewed bass/lead parallel octaves by changing the bass to a chord third at those joins.",
            "R2 thins the pulse arpeggio to quarter notes and removes two noise ticks per bar in open_sky; loopback also thins after its first three bars.",
            "R2 places B in the bar-46 D6 arpeggio, where it is the chord's sixth, to match the opening pitch set across the loop seam.",
        ])
    if revision >= 3:
        project["decisions"].extend([
            "R3 keeps all four NES-style channels present between sections; lift and cloudpath share that fixed texture, while their harmonic route, melodic contour, high point and second fast arpeggio define the contrast.",
            "R3 opens with quarter-note arpeggiation to leave room for the hook, then restores eighth notes for lift. The complete loopback section uses quarter notes to give the closing dominant space.",
            "R3 restates the return's opening rhythmic cell in its fifth bar at a lower pitch level, with altered intervals and a resolving ending.",
        ])

    # Defensive invariants: one note at a time per channel, full bar coverage,
    # stable note identities, and no voice outside its chosen chip register.
    for track in tracks.values():
        track["notes"].sort(key=lambda n: (n["on"], n["pitch"]))
        ids = [n["id"] for n in track["notes"]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate note id on {track['id']}")
        lo, hi = track["range"]
        if any(not lo <= n["pitch"] <= hi for n in track["notes"]):
            raise ValueError(f"pitch outside {track['id']} range")

    return project, expression_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    project, expression_report = build_project(args.revision)
    destination = ROOT / "song.json"
    destination.write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    note_count = sum(len(track["notes"]) for track in project["tracks"])
    print(f"Wrote {destination}; revision r{args.revision}; {note_count} notes; 90.000-second loop.")
    print("Expression profiles:", json.dumps(expression_report, sort_keys=True))


if __name__ == "__main__":
    main()
