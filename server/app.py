"""Server for the Brandeis tracker, with shared saving and Authentik sign-in.

Serves index.html and the drawings, and stores the tracker data in DATA_DIR
so every user sees the same saved copy. The page was written for a Claude
artifact; server/shim.js provides the same window.claude calls (save, who is
signed in, downloads) on top of this server.

Users are identified by the headers the Authentik proxy outpost adds
(X-authentik-uid, -name, -username, -email, -groups). The server must only be
reachable through that proxy, or anyone could send those headers themselves.

Usage:
  python3 app.py                serve (settings come from environment variables)
  python3 app.py seed [--force] copy the data embedded in index.html into DATA_DIR
"""
import datetime
import json
import os
import pathlib
import re
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

HERE = pathlib.Path(__file__).resolve().parent
SITE_DIR = pathlib.Path(os.environ.get('SITE_DIR', HERE.parent)).resolve()
DATA_DIR = pathlib.Path(os.environ.get('DATA_DIR', HERE.parent / 'data')).resolve()
PORT = int(os.environ.get('PORT', '8080'))
# 'authentik' (default): require the Authentik headers. 'none': no sign-in,
# everyone is an owner. Only for trying the tracker on your own computer.
AUTH_MODE = os.environ.get('AUTH_MODE', 'authentik').strip().lower()


def _groups(name, default):
    return {g.strip() for g in os.environ.get(name, default).split(',') if g.strip()}


EDITOR_GROUPS = _groups('EDITOR_GROUPS', 'tracker-editors')
OWNER_GROUPS = _groups('OWNER_GROUPS', 'tracker-owners,authentik Admins')
KEEP_BACKUPS = int(os.environ.get('KEEP_BACKUPS', '200'))
MAX_BODY = 32 * 1024 * 1024

STATE_RE = re.compile(r'(<script id="state" type="application/json">)(.*?)(</script>)', re.S)
STATE_FILE = DATA_DIR / 'state.json'
META_FILE = DATA_DIR / 'meta.json'
USERS_FILE = DATA_DIR / 'users.json'
BACKUP_DIR = DATA_DIR / 'backups'
STATIC_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}

lock = threading.Lock()


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(tmp, path)


def template():
    return (SITE_DIR / 'index.html').read_text(encoding='utf-8')


def seed(force=False):
    """Copy the data embedded in index.html into DATA_DIR (first start, or --force)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)
    if STATE_FILE.exists() and not force:
        return False
    if STATE_FILE.exists():
        backup(read_json(STATE_FILE, None), 'before-seed')
    state = json.loads(STATE_RE.search(template()).group(2))
    write_json(STATE_FILE, state)
    meta = read_json(META_FILE, {'version': 0})
    meta.update(version=meta.get('version', 0) + 1, savedAt=now(), savedBy='seed')
    write_json(META_FILE, meta)
    return True


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def backup(state, tag):
    if state is None:
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_json(BACKUP_DIR / f'state-{stamp}-{tag}.json', state)
    old = sorted(BACKUP_DIR.glob('state-*.json'))[:-KEEP_BACKUPS or None]
    for p in old:
        p.unlink(missing_ok=True)


def user_from(headers):
    if AUTH_MODE == 'none':
        return {'id': 'local', 'name': 'Local user', 'email': '', 'groups': [], 'canEdit': True, 'isOwner': True}
    uid = headers.get('X-authentik-uid', '').strip()
    if not uid:
        return None
    groups = [g for g in headers.get('X-authentik-groups', '').split('|') if g]
    name = (headers.get('X-authentik-name') or headers.get('X-authentik-username') or headers.get('X-authentik-email') or '').strip()
    owner = bool(OWNER_GROUPS.intersection(groups))
    return {
        'id': uid,
        'name': name or 'Unnamed user',
        'email': headers.get('X-authentik-email', '').strip(),
        'groups': groups,
        'isOwner': owner,
        'canEdit': owner or bool(EDITOR_GROUPS.intersection(groups)),
    }


def remember(user):
    """Keep id -> name so the Change history tab can show who made each change."""
    with lock:
        users = read_json(USERS_FILE, {})
        if users.get(user['id'], {}).get('name') != user['name']:
            users[user['id']] = {'name': user['name'], 'email': user['email'], 'seen': now()}
            write_json(USERS_FILE, users)


def page(user):
    with lock:
        state = read_json(STATE_FILE, None)
        version = read_json(META_FILE, {}).get('version', 0)
    doc = template()
    if state is not None:
        text = json.dumps(state, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        doc = STATE_RE.sub(lambda m: m.group(1) + text + m.group(3), doc, count=1)
    boot = {'version': version, 'user': {k: user[k] for k in ('id', 'name', 'isOwner', 'canEdit')}}
    inject = ('<script>window.__TRK=' + json.dumps(boot).replace('<', '\\u003c') + '</script>'
              '<script src="_trk/shim.js"></script>')
    # The first </head> is the page's own; later ones are inside the app's code.
    return doc.replace('</head>', inject + '</head>', 1)


class Handler(BaseHTTPRequestHandler):
    server_version = 'BrandeisTracker'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        headers = getattr(self, 'headers', None)
        sys.stderr.write('%s %s\n' % ((headers and headers.get('X-authentik-username')) or '-', fmt % args))

    def send(self, status, body=b'', ctype='text/plain; charset=utf-8', cache='no-store', extra=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def json(self, status, value):
        self.send(status, json.dumps(value, ensure_ascii=False), 'application/json; charset=utf-8')

    def auth(self):
        user = user_from(self.headers)
        if user is None:
            self.send(HTTPStatus.UNAUTHORIZED, '<!doctype html><title>Sign-in required</title>'
                      '<p>Open the tracker through its Authentik sign-in address.</p>', 'text/html; charset=utf-8')
            return None
        remember(user)
        return user

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/healthz':
            return self.send(HTTPStatus.OK, 'ok')
        user = self.auth()
        if not user:
            return
        if path in ('/', '/index.html'):
            return self.send(HTTPStatus.OK, page(user), 'text/html; charset=utf-8')
        if path == '/_trk/shim.js':
            return self.send(HTTPStatus.OK, (HERE / 'shim.js').read_bytes(), 'text/javascript; charset=utf-8', 'no-cache')
        if path == '/api/me':
            return self.json(HTTPStatus.OK, user)
        if path == '/api/profiles':
            ids = parse_qs(urlsplit(self.path).query).get('id', [])
            users = read_json(USERS_FILE, {})
            return self.json(HTTPStatus.OK, {i: {'name': users[i]['name']} for i in ids if i in users})
        # Drawings: plain files that sit next to index.html, no sub-folders.
        name = path.lstrip('/')
        f = (SITE_DIR / name).resolve()
        if '/' not in name and f.parent == SITE_DIR and f.suffix.lower() in STATIC_TYPES and f.is_file():
            return self.send(HTTPStatus.OK, f.read_bytes(), STATIC_TYPES[f.suffix.lower()], 'private, max-age=86400')
        self.send(HTTPStatus.NOT_FOUND, 'Not found')

    def do_POST(self):
        path = urlsplit(self.path).path
        user = self.auth()
        if not user:
            return
        if path != '/api/publish':
            return self.send(HTTPStatus.NOT_FOUND, 'Not found')
        if not user['canEdit']:
            return self.json(HTTPStatus.FORBIDDEN, {'code': 'not_writer'})
        # Same-origin check: a page on another site can't save on someone's behalf.
        origin = self.headers.get('Origin')
        host = self.headers.get('X-Forwarded-Host') or self.headers.get('Host')
        if origin and urlsplit(origin).netloc != host:
            return self.json(HTTPStatus.FORBIDDEN, {'code': 'bad_origin'})
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_BODY:
            return self.json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {'code': 'too_large'})
        body = self.rfile.read(length).decode('utf-8')
        m = STATE_RE.search(body)
        try:
            state = json.loads(m.group(2)) if m else None
        except ValueError:
            state = None
        if not isinstance(state, dict) or not isinstance(state.get('panels'), list):
            return self.json(HTTPStatus.BAD_REQUEST, {'code': 'bad_document'})
        try:
            base = int(self.headers.get('X-Tracker-Version', ''))
        except ValueError:
            return self.json(HTTPStatus.BAD_REQUEST, {'code': 'no_version'})
        with lock:
            meta = read_json(META_FILE, {'version': 0})
            if base != meta.get('version', 0):
                return self.json(HTTPStatus.CONFLICT, {'code': 'conflict', 'version': meta.get('version', 0)})
            backup(read_json(STATE_FILE, None), 'before-save')
            write_json(STATE_FILE, state)
            meta = {'version': base + 1, 'savedAt': now(), 'savedBy': user['id']}
            write_json(META_FILE, meta)
        self.json(HTTPStatus.OK, {'version': meta['version']})


def main(argv):
    if argv[:1] == ['seed']:
        done = seed(force='--force' in argv)
        print('Seeded data from index.html' if done else 'Data already exists; use --force to replace it (a backup is kept).')
        return
    if AUTH_MODE not in ('authentik', 'none'):
        sys.exit(f'AUTH_MODE must be "authentik" or "none", not {AUTH_MODE!r}')
    seed()
    if AUTH_MODE == 'none':
        print('WARNING: AUTH_MODE=none - no sign-in, everyone can edit. Use only on your own computer.', file=sys.stderr)
    print(f'Serving {SITE_DIR} on port {PORT}, data in {DATA_DIR}', file=sys.stderr)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main(sys.argv[1:])
