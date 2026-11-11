# The prompt each piece was made from

Each of the seven pieces in these examples was made by one agent session from one message: the opening below, the same for all seven, followed by the
piece's own brief. Nobody replied to the agent while it worked, and nothing was edited afterwards. All seven are published; none was picked from several.

## The opening

> Make one piece of original instrumental music with the music-production skill (version 0.6.0), from the brief at the end. Work alone in this folder and in one take: nobody will answer questions or give feedback, so decide everything yourself and finish the piece.
>
> Rules
> - Use the installed music-production skill and follow the steps of its SKILL.md. Render, review, round and audition with --config <config>, where the sound banks, Surge XT and its patches are set up. Set TMP and TEMP to <temp folder> first. Do not install or download anything, and delete files only with the skill's `studio.py clean`.
> - Create and change files only in this folder. No subagents, no commits, nothing uploaded or published.
> - Entirely original: do not quote or imitate the melody, chord progression or title of an existing work, nor a particular piece by a particular composer, band or singer.
> - One Python script writes every note into song.json. Mix on the bus chain with the rules of version 2. Review, render and analyze, then revise from what they point out, at least one more round, each render in a new folder. Every review question gets a musical decision: a change, or a written reason for keeping it.
> - You cannot hear the music. Do not say how it sounds; measurements are only measurements.
> - Leave in this folder: the script, song.json, the final render folder and NOTES.md in English (title, style, length, tempo and key; instruments, banks and patches; the sections; what changed in each round and why; the final measurements and any warning left). End your last message with the path of the final preview.mp3 and, if you can read them, the time and tokens the piece took.
>
> Brief

The message ended with the brief. Two folders of the machine the sessions ran on are written here as `<config>` (the renderer's configuration file) and
`<temp folder>`; nothing else is changed.

## The pieces

| Piece | Model, effort | What it is |
|---|---|---|
| [Stormglass Gambit](stormglass-gambit) | Claude Fable 5.2, xhigh | a looping synth battle theme for a game |
| [Cairnfire](cairnfire) | Claude Fable 5.2, xhigh | a concert overture for full orchestra, in 36 parts |
| [Glass Towers, Low Gear](glass-towers-low-gear) | Claude Opus 5.5, xhigh | city pop: a night drive through a lit city |
| [The Stone Vault Turns to Light](the-stone-vault-turns-to-light) | GPT-6 Astra, xhigh | a toccata for pipe organ |
| [Paper Lantern Hours](paper-lantern-hours) | Claude Sonnet 5.5, medium | a lo-fi hip-hop beat that loops |
| [Fughetta in D minor](fughetta-in-d-minor) | Claude Opus 5.5, medium | a baroque-style fughetta for harpsichord and strings |
| [Skybutton Speedway](skybutton-speedway) | GPT-6 Luna, max | an 8-bit chiptune for a title screen, a 90-second loop |

Each piece's page gives its brief word for word.

The sessions of *Paper Lantern Hours* and *Fughetta in D minor* were started by another agent session, which sent the same message; the app that starts
such a session asks for a line of background beside it, and this was sent: "This session makes one piece of music for a showcase of the
music-production skill. Everything it needs is in the prompt; there is no other context, and nobody will reply during the work."
