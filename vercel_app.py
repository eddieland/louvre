"""Vercel's entrypoint: `[tool.vercel] entrypoint` in pyproject.toml names this file's `app`."""

from louvre.web.app import create

app = create()
