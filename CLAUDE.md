# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Remote Term — a solution for controlling a computer terminal remotely from an iPhone Safari browser, with no app installation required. Uses **ttyd** (web-based terminal over WebSocket/xterm.js) with optional **frp** for internet access via NAT traversal.

Architecture: `iPhone Safari → (frp tunnel via VPS) → ttyd on target machine → shell`

## Repository State

This project is in the planning/research phase. There is no application code yet — only documentation (README.md, PLAN.md) and a research PDF/LaTeX document in `research/` (git-ignored).

## Key Decisions from README

- **ttyd** is the chosen web terminal solution (over alternatives like Tailscale which require app installation)
- frp is the primary tunneling method for internet access; Cloudflare Tunnel is noted as an alternative
- Security requirements: password auth (`-c`), HTTPS for internet-facing deployments, never expose ttyd directly to public internet
- Target user accesses via iPhone Safari — all solutions must work without installing native apps

## Language

Project documentation is written in Chinese (Simplified). Continue using Chinese for user-facing docs unless directed otherwise.
