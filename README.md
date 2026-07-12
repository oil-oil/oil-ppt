# oil-slides

oil-slides is a Codex skill for creating 16:9 HTML presentations with a restrained oil visual style:

- white background with a subtle grid
- clear hierarchy and large presentation typography
- structured component and layout contracts
- real media planning and deck-level rhythm checks
- browser-validated, self-contained delivery HTML

New presentations follow two confirmation gates:

1. Create and confirm a human-readable `outline.md`.
2. Generate and confirm the real visual preview before building.

## Install

Install the skill into Codex:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo oil-oil/oil-slides \
  --path oil-slides
```

Restart Codex after installation.

## Use

Ask Codex to use `oil-slides`, for example:

```text
[$oil-slides] Create a presentation about this topic.
```

The skill first asks whether to develop the Markdown outline through conversation or generate a complete first draft directly.

## License

MIT
