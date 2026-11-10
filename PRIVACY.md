# Privacy

music-skill is a skill: instructions and Python scripts that your agent runs. It has no server, no account and no telemetry.

- **What it reads**: the project, MIDI, audio and configuration files you point it at; the tools, banks and patches the configuration names; and its own files (the skill's references and lock files, the downloads, and the records it wrote in its folders). Nothing else on your disk is looked for.
- **What it writes**: renders, reviews, analyses, configurations and the downloaded tools and banks, in the folders you choose (pip runs without its own cache). Python also keeps its bytecode cache next to the scripts. A few steps use the system's temporary folder for files they remove when done: the version checks of `doctor`, a WAV reference while it is measured, a FLAC recording while a bank is built from it, and pip's own work while it installs the wheel. Nothing is written anywhere else.
- **What it sends**: nothing. The only network access is the setup (once, and again when you add banks or set up anew), which downloads FluidSynth, FFmpeg and Surge XT from their publishers, the sound banks from this project's GitHub release (from their publishers if it cannot be reached), and the pedalboard wheel from PyPI's file host. The tools and banks come from GitHub, plus the University of Iowa's sample site when its banks are built from source; the setup fetches the pedalboard wheel itself, checks it against its pinned size and SHA-256, and pip then installs that file without going online. Those requests carry none of your data. NumPy comes through pip when you or your agent install it.
- **What it keeps**: nothing. There is no music-skill service to keep anything.

Where the scripts run depends on your agent: on your computer in Claude Code or Codex, or in the agent's own sandbox in a chat. What you send to the agent is covered by that agent's privacy policy.

Questions: open an issue at https://github.com/owoevan-dev/music-skill/issues.
