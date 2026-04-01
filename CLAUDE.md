# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Remote Term — a browser-based SSH client for controlling remote servers from iPhone Safari, with no app installation required. Self-hosted Python backend with custom mobile-optimized xterm.js frontend, optional **frp** for internet access via NAT traversal.

Architecture: `iPhone Safari → (frp tunnel via VPS) → Web SSH Server (Python) → SSH → target server`

## Code Structure

- `server/server.py` — Python backend (aiohttp + asyncssh). Serves static files, handles WebSocket bridging to SSH.
- `server/requirements.txt` — Python dependencies: `aiohttp`, `asyncssh`
- `web/index.html` — Single-page frontend with xterm.js terminal, SSH login form, custom mobile keyboard, Tokyo Night theme.

## Running

```bash
pip install -r server/requirements.txt
python server/server.py -p 8080
```

## WebSocket Protocol

Follows ttyd-compatible binary protocol over WebSocket (subprotocol `tty`):
- Initial message: JSON with `{host, port, username, password, columns, rows}`
- Client → Server: `'0'` + input bytes, `'1'` + resize JSON
- Server → Client: `'0'` + output bytes, `'1'` + title, `'2'` + status/prefs JSON

## Key Decisions

- frp is the primary tunneling method for internet access; Cloudflare Tunnel is noted as an alternative
- HTTPS required for internet-facing deployments (SSH passwords transmitted via WebSocket)
- Target user accesses via iPhone Safari — all solutions must work without installing native apps
- `known_hosts=None` in SSH connections (no host key verification) for simplicity

## Language

Project documentation is written in Chinese (Simplified). Continue using Chinese for user-facing docs unless directed otherwise.
