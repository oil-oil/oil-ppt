# oil-slides

oil-slides is a personal Codex skill for making 16:9 technical slide decks in a fixed visual style:

- white background with a subtle grid
- black, white, grey, and warm yellow
- large, low-density presentation pages
- one strong visual per slide
- manga ink illustrations with a yellow Border Collie companion
- width-filled browser preview with no side black bars

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
[$oil-slides] Make this HTML into a slide deck.
```

## Optional Image Fallback

The skill prefers Codex built-in image generation. The bundled `scripts/gen_art.py` is only a fallback path and needs `ZENMUX_API_KEY` when used.

## License

MIT
