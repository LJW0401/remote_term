#!/usr/bin/env python3
"""Web SSH Server - browser-based SSH client with custom mobile UI"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time

import asyncssh
from aiohttp import web, WSMsgType

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
HOSTS_FILE = os.path.join(DATA_DIR, 'hosts.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
DEFAULT_PASSWORD = '000000'

# Active session tokens
valid_tokens = set()


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {'password_hash': hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_hosts():
    if not os.path.exists(HOSTS_FILE):
        return []
    with open(HOSTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_hosts(hosts):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HOSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(hosts, f, ensure_ascii=False, indent=2)


async def api_hosts_list(request):
    return web.json_response(load_hosts())


async def api_hosts_create(request):
    data = await request.json()
    host = data.get('host', '').strip()
    username = data.get('username', '').strip()
    if not host or not username:
        return web.json_response({'error': 'Host and Username are required'}, status=400)
    hosts = load_hosts()
    entry = {
        'id': f"{int(time.time() * 1000):x}{os.urandom(2).hex()}",
        'label': data.get('label', '').strip() or host,
        'host': host,
        'port': int(data.get('port', 22)),
        'username': username,
        'password': data.get('password', ''),
    }
    hosts.append(entry)
    save_hosts(hosts)
    return web.json_response(entry, status=201)


async def api_hosts_update(request):
    host_id = request.match_info['id']
    data = await request.json()
    hosts = load_hosts()
    for h in hosts:
        if h['id'] == host_id:
            h['label'] = data.get('label', h.get('label', ''))
            h['host'] = data.get('host', h['host'])
            h['port'] = int(data.get('port', h.get('port', 22)))
            h['username'] = data.get('username', h['username'])
            h['password'] = data.get('password', h.get('password', ''))
            save_hosts(hosts)
            return web.json_response(h)
    return web.json_response({'error': 'Not found'}, status=404)


async def api_hosts_delete(request):
    host_id = request.match_info['id']
    hosts = load_hosts()
    new_hosts = [h for h in hosts if h['id'] != host_id]
    if len(new_hosts) == len(hosts):
        return web.json_response({'error': 'Not found'}, status=404)
    save_hosts(new_hosts)
    return web.json_response({'ok': True})


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


async def api_browse_dir(request):
    """List subdirectories and files of a given path for the file browser."""
    path = request.query.get('path', '~')
    path = os.path.realpath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return web.json_response({'error': 'Not a directory'}, status=400)
    dirs = []
    files = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: e.name.lower()):
            if entry.is_dir(follow_symlinks=False):
                dirs.append(entry.name)
            elif entry.is_file(follow_symlinks=False):
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                files.append({'name': entry.name, 'size': size})
    except PermissionError:
        return web.json_response({'error': 'Permission denied'}, status=403)
    return web.json_response({'path': path, 'dirs': dirs, 'files': files})


async def api_upload(request):
    """Upload a file to the specified directory."""
    reader = await request.multipart()
    dest_dir = None
    filename = None
    filepath = None

    async for part in reader:
        if part.name == 'path':
            dest_dir = (await part.text()).strip()
            dest_dir = os.path.realpath(os.path.expanduser(dest_dir))
        elif part.name == 'file':
            filename = part.filename
            if not dest_dir or not os.path.isdir(dest_dir):
                return web.json_response({'error': 'Invalid destination'}, status=400)
            filepath = os.path.join(dest_dir, filename)
            with open(filepath, 'wb') as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)

    if not filepath:
        return web.json_response({'error': 'No file provided'}, status=400)
    size = os.path.getsize(filepath)
    log.info(f'File uploaded: {filepath} ({size} bytes)')
    return web.json_response({'ok': True, 'path': filepath, 'size': size})


async def api_download(request):
    """Download a file."""
    path = request.query.get('path', '')
    path = os.path.realpath(os.path.expanduser(path))
    if not os.path.isfile(path):
        return web.json_response({'error': 'File not found'}, status=404)
    return web.FileResponse(path, headers={
        'Content-Disposition': f'attachment; filename="{os.path.basename(path)}"'
    })


async def check_host(host, port, timeout=3):
    """Check if a host's SSH port is reachable via TCP connect."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def api_hosts_status(request):
    """Return online/offline status for all saved hosts."""
    hosts = load_hosts()
    if not hosts:
        return web.json_response({})

    async def probe(h):
        online = await check_host(h['host'], h.get('port', 22))
        return h['id'], online

    results = await asyncio.gather(*(probe(h) for h in hosts))
    return web.json_response({hid: online for hid, online in results})


async def api_login(request):
    """Verify password and return a session token."""
    data = await request.json()
    password = data.get('password', '')
    config = load_config()
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != config.get('password_hash'):
        return web.json_response({'error': 'Wrong password'}, status=401)
    token = secrets.token_hex(16)
    valid_tokens.add(token)
    resp = web.json_response({'ok': True, 'token': token})
    resp.set_cookie('auth_token', token, httponly=True, samesite='Strict')
    return resp


async def api_change_password(request):
    """Change the login password."""
    data = await request.json()
    old_pw = data.get('old_password', '')
    new_pw = data.get('new_password', '')
    if not new_pw:
        return web.json_response({'error': 'New password is required'}, status=400)
    config = load_config()
    if hashlib.sha256(old_pw.encode()).hexdigest() != config.get('password_hash'):
        return web.json_response({'error': 'Wrong old password'}, status=401)
    config['password_hash'] = hashlib.sha256(new_pw.encode()).hexdigest()
    save_config(config)
    valid_tokens.clear()
    return web.json_response({'ok': True})


def check_auth(request):
    """Check if request has a valid auth token."""
    token = request.cookies.get('auth_token', '')
    if not token:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
    return token in valid_tokens


@web.middleware
async def auth_middleware(request, handler):
    # Allow login endpoint and static assets without auth
    path = request.path
    if path == '/api/login' or path == '/':
        return await handler(request)
    # Static assets (css, js, fonts, images)
    if '.' in path.split('/')[-1] and not path.startswith('/api/'):
        return await handler(request)
    # All API and WebSocket requests require auth
    if not check_auth(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    return await handler(request)


async def handle_index(request):
    return web.FileResponse(os.path.join(STATIC_DIR, 'index.html'))


def create_app():
    app = web.Application(middlewares=[auth_middleware])
    app.router.add_post('/api/login', api_login)
    app.router.add_post('/api/change-password', api_change_password)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/api/browse', api_browse_dir)
    app.router.add_post('/api/upload', api_upload)
    app.router.add_get('/api/download', api_download)
    app.router.add_get('/api/hosts', api_hosts_list)
    app.router.add_get('/api/hosts/status', api_hosts_status)
    app.router.add_post('/api/hosts', api_hosts_create)
    app.router.add_put('/api/hosts/{id}', api_hosts_update)
    app.router.add_delete('/api/hosts/{id}', api_hosts_delete)
    app.router.add_get('/', handle_index)
    app.router.add_static('/', STATIC_DIR)
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
