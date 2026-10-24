#!/bin/sh
# Vercel's ignored build step (vercel.json `ignoreCommand`): exit 0 skips the build, anything else builds.
#
# Skips when nothing changed since the last deploy but files the app never serves. VERCEL_GIT_PREVIOUS_SHA is the
# last deployed commit, so commits pushed together count as one; without it, the parent. A commit missing from
# Vercel's shallow clone makes git fail with 128, which builds.
# Markdown anywhere is never served; the explorations' HTML under docs/ is. The container image and its chart are
# not part of the preview.
git diff --quiet "${VERCEL_GIT_PREVIOUS_SHA:-HEAD^}" HEAD -- . \
    ':!tests' ':!.github' ':(exclude,glob)**/*.md' ':!LICENSE' \
    ':!charts' ':!Dockerfile' ':!.dockerignore'
