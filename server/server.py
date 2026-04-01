#!/usr/bin/env python3
"""Web SSH Server - browser-based SSH client with custom mobile UI"""

import asyncio
import json
import logging
import os

import asyncssh
from aiohttp import web, WSMsgType

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web')


async def websocket_handler(request):
    ws = web.WebSocketResponse(protocols=['tty'])
    await ws.prepare(request)

    # Wait for initial JSON with SSH credentials and terminal size
    msg = await ws.receive()
    if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
        return ws

    data = msg.data if isinstance(msg.data, str) else msg.data.decode('utf-8')
    config = json.loads(data)

    host = config.get('host', 'localhost')
    port = int(config.get('port', 22))
    username = config.get('username', '')
    password = config.get('password', '')
    log.info(f'SSH connection request: {username}@{host}:{port}')
    cols = int(config.get('columns', 80))
    rows = int(config.get('rows', 24))

    conn = None
    process = None

    try:
        conn = await asyncio.wait_for(
            asyncssh.connect(
                host, port,
                username=username,
                password=password,
                known_hosts=None,
            ),
            timeout=10,
        )
        process = await conn.create_process(
            term_type='xterm-256color',
            term_size=(cols, rows, 0, 0),
            encoding=None,
        )
    except asyncio.TimeoutError:
        log.error(f'SSH connection timed out: {username}@{host}:{port}')
        err = '\r\n\x1b[31mConnection timed out\x1b[0m\r\n'
        await ws.send_bytes(b'\x30' + err.encode())
        await ws.close()
        return ws
    except Exception as e:
        log.error(f'SSH connection failed: {username}@{host}:{port} - {e}')
        err = f'\r\n\x1b[31mSSH error: {e}\x1b[0m\r\n'
        await ws.send_bytes(b'\x30' + err.encode())
        await ws.close()
        return ws

    log.info(f'SSH connected: {username}@{host}:{port}')

    # Send window title
    title = f'{username}@{host}'
    await ws.send_bytes(b'\x31' + title.encode())

    # Send connected signal (prefix '2' with status JSON)
    await ws.send_bytes(b'\x32' + json.dumps({'status': 'connected'}).encode())

    # Bridge SSH stdout/stderr -> WebSocket
    async def ssh_to_ws(stream):
        try:
            while True:
                data = await stream.read(4096)
                if not data:
                    break
                await ws.send_bytes(b'\x30' + data)
        except (asyncssh.DisconnectError, ConnectionError, asyncio.CancelledError):
            pass
        except Exception:
            pass

    stdout_task = asyncio.create_task(ssh_to_ws(process.stdout))
    stderr_task = asyncio.create_task(ssh_to_ws(process.stderr))

    async def monitor_ssh():
        """Close WebSocket when SSH process exits."""
        try:
            await process.wait()
        except Exception:
            pass
        if not ws.closed:
            await ws.close()

    monitor_task = asyncio.create_task(monitor_ssh())

    # Bridge WebSocket -> SSH stdin
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                cmd = msg.data[0:1]
                payload = msg.data[1:]
                if cmd == b'\x30':  # Input
                    process.stdin.write(payload)
                elif cmd == b'\x31':  # Resize
                    size = json.loads(payload.decode())
                    process.change_terminal_size(
                        size.get('columns', cols),
                        size.get('rows', rows),
                    )
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
    except (asyncssh.DisconnectError, ConnectionError):
        pass
    finally:
        stdout_task.cancel()
        stderr_task.cancel()
        monitor_task.cancel()
        if process:
            process.close()
        if conn:
            conn.close()
        if not ws.closed:
            await ws.close()

    return ws


async def handle_token(request):
    return web.json_response({'token': ''})


def create_app():
    app = web.Application()
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/token', handle_token)
    app.router.add_static('/', STATIC_DIR, show_index=True)
    return app


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Web SSH Server')
    parser.add_argument('-p', '--port', type=int, default=8080,
                        help='Listen port (default: 8080)')
    parser.add_argument('--host', default='0.0.0.0',
                        help='Listen address (default: 0.0.0.0)')
    args = parser.parse_args()

    app = create_app()
    print(f'Web SSH server starting on http://{args.host}:{args.port}')
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == '__main__':
    main()
