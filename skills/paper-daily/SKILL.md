---
name: paper-daily
description: Initialize, run, and maintain the Paper2Data pipeline with SQLite or MySQL and OpenClaw session delivery.
---

# Paper Daily

Use this skill when the user wants to install the paper pipeline, change database backends, update the OpenClaw session target, or run fetch and delivery tasks.

## Workflow

1. Before first run, execute `python -m cli.init` and ask for database type, storage path or MySQL connection, LLM config, and OpenClaw session settings.
2. Start the service with `python app.py` or `python -m cli.run`.
3. Manually fetch papers with `python -m cli.fetch`.
4. Manually deliver queued papers with `python -m cli.deliver`.

## Configuration Rules

- Default database is SQLite.
- Use `config.local.json` for machine-specific settings.
- Deliver papers directly to OpenClaw sessions.
