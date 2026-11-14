# The prompt each piece was made from

Each of the six pieces in these examples was made by one agent session from one message: the opening below, the same for all six,
followed by the piece's own brief. Nobody replied to the agent while it worked, and nobody edited the notes it wrote.

## The opening

> Make one piece of original instrumental music with the music-production skill (version 0.7.0), from the brief at the end. Work alone in this folder and in one take: nobody will answer questions or give feedback, so decide everything yourself and finish the piece.
>
> Rules
> - Use the copy of the music-production skill in <skill folder>, and no other: read its SKILL.md there, follow its steps and run its scripts from that folder. A note in this machine's instructions about which copy of the skill to use does not apply to this session. Render, review, round and audition with --config <config>, where the sound banks, Surge XT and its patches are set up. Set TMP and TEMP to <temp folder> first. Do not install or download anything, and delete files only with the skill's `studio.py clean`.
> - Create and change files only in this folder. No subagents, no commits, nothing uploaded or published.
> - Entirely original: do not quote or imitate the melody, chord progression or title of an existing work, nor a particular piece by a particular composer, band or singer.
> - One Python script writes every note into song.json. Mix on the bus chain with the rules of version 2. Review, render and analyze, then revise from what they point out, at least one more round, each render in a new folder. Every review question gets a musical decision: a change, or a written reason for keeping it.
> - You cannot hear the music. Do not say how it sounds; measurements are only measurements.
> - Leave in this folder: the script, song.json, the final render folder and NOTES.md in English (title, style, length, tempo and key; instruments, banks and patches; the sections; what changed in each round and why; the final measurements and any warning left). End your last message with the path of the final preview.mp3 and, if you can read them, the time and tokens the piece took.
>
> Brief

The message ended with the brief. Three folders of the machine the sessions ran on are written here as `<skill folder>` (a copy of this
version of the skill), `<config>` (the renderer's configuration file) and `<temp folder>`; nothing else is changed. That machine had an
earlier version of the skill installed, which its own instructions named; hence the line about the copy to use.

## The pieces

| Piece | Model, effort | What it is |
|---|---|---|
| [The Lamp on the Wire](the-lamp-on-the-wire) | Claude Fable 5.2, xhigh | the climax of an animated film, for full orchestra in 57 parts |
| [Battle Reel of the Stork-Rider](battle-reel-of-the-stork-rider) | Claude Opus 5.5, xhigh | battle music for a fantasy story, played by a folk band |
| [Fughetta of the Paper Paddock](fughetta-of-the-paper-paddock) | Claude Sonnet 5.5, xhigh | a baroque-style fughetta for harpsichord and strings |
| [Fjord Stopwatch](fjord-stopwatch) | Claude Haiku 5.5, xhigh | a lo-fi hip-hop beat for late reading, which loops |
| [The Cork Boat Keeps Our Evening](the-cork-boat-keeps-our-evening) | GPT-6 Astra, xhigh | a slow ballad without a singer, like a film's ending theme |
| [Noon Raccoon Rooftop Run](noon-raccoon-rooftop-run) | GPT-6 Luna, xhigh | an 8-bit chiptune for a platform game's first level, a 90-second loop |

Each piece's page gives its brief word for word.

The sessions of the four Claude models were started by another agent session, which sent the same message; the app that starts such a
session asks for a line of background beside it, and this was sent, with the same three folders and the piece's own folder written as
here: "This session makes one of the example pieces of version 0.7.0 of the music-production skill, which also serve as its acceptance pieces: each is made by one agent from a single message, with nobody answering questions. The version under test is not the one installed on this machine; a frozen copy of it is at `<skill folder>` and its configuration at `<config>`. Work only in the session's own folder, `<the piece's folder>`. The message below is the whole task." The two GPT models ran in Codex, from the message alone.

The pieces were made with a copy of the skill taken before this version was final: the reviews of its code changed the skill afterwards,
and its piano guide now asks for the Steinway in every piano part. Each recording is the agent's project rendered with the skill and the
sound banks of this version as released; the notes and the mix are the agent's. One project was changed after its agent finished: the two
piano parts of *The Cork Boat Keeps Our Evening* play the Steinway, where the agent had put them on the Kawai grand.
