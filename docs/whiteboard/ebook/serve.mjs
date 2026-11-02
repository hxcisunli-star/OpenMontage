#!/usr/bin/env node
/* Static, read-only HTTPS server for the ebook platform (Node 18, no dependencies).
 *   node serve.mjs init  --config <serve.json> --root <site dir> --host <bind address> --port <port> --san-ip <ip> [--san-ip <ip> ...]
 *        makes a self-signed certificate and a random password, writes the config (scrypt hash, never the password) and prints the password ONCE.
 *   node serve.mjs run   --config <serve.json>
 * Safety rules (this server may be reachable from outside; it only has to hand out the files of one folder):
 *   - serves only the folder `root` (symlinks may not leave it), no directory listing, no dotfiles, GET and HEAD only;
 *   - HTTP Basic auth over TLS, password checked in constant time (scrypt), 5 wrong tries lock the source address for 15 minutes, per-address request limit;
 *   - header size, connection and timeout limits; Range requests (video seeking); security headers; the access log never records credentials.
 * The address, the port and the password live only in the local config (outside git) and in the conversation with the owner. */
import crypto from 'node:crypto';
import fs from 'node:fs';
import https from 'node:https';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm', '.zip': 'application/zip', '.mjs': 'text/javascript; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.mp4': 'video/mp4', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.py': 'text/plain; charset=utf-8', '.srt': 'text/plain; charset=utf-8',
};
const SCRYPT = { N: 16384, r: 8, p: 1, keylen: 64 };

function args(argv) {
  const out = { _: [], 'san-ip': [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) { const k = argv[i].slice(2); const v = argv[++i]; if (k === 'san-ip') out[k].push(v); else out[k] = v; } else out._.push(argv[i]);
  }
  return out;
}

function hashPassword(pw, salt) { return crypto.scryptSync(pw, salt, SCRYPT.keylen, { N: SCRYPT.N, r: SCRYPT.r, p: SCRYPT.p }); }

function init(a) {
  for (const k of ['config', 'root', 'host', 'port']) if (!a[k]) throw new Error(`init needs --${k}`);
  const dir = path.dirname(path.resolve(a.config));
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  const key = path.join(dir, 'key.pem'), cert = path.join(dir, 'cert.pem');
  const san = ['DNS:localhost', 'IP:127.0.0.1', ...a['san-ip'].map((ip) => `IP:${ip}`)].join(',');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '365', '-keyout', key, '-out', cert, '-subj', '/CN=ebook', '-addext', `subjectAltName=${san}`], { stdio: 'ignore' });
  fs.chmodSync(key, 0o600); fs.chmodSync(cert, 0o600);
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';      // no look-alike characters
  let pw = ''; while (pw.length < 20) { const b = crypto.randomBytes(1)[0]; if (b < 256 - (256 % alphabet.length)) pw += alphabet[b % alphabet.length]; }
  const salt = crypto.randomBytes(16);
  const cfg = { host: a.host, port: Number(a.port), root: path.resolve(a.root), key, cert, user: 'reader', salt: salt.toString('hex'), hash: hashPassword(pw, salt).toString('hex'),
                maxFail: 5, lockSeconds: 900, perMinute: 900, maxConnections: 64, log: path.join(dir, 'access.log') };
  fs.writeFileSync(a.config, JSON.stringify(cfg, null, 1), { mode: 0o600 }); fs.chmodSync(a.config, 0o600);
  process.stdout.write(`user: ${cfg.user}\npassword: ${pw}\n`);
}

function run(a) {
  const cfg = JSON.parse(fs.readFileSync(a.config, 'utf8'));
  const root = fs.realpathSync(cfg.root);
  const salt = Buffer.from(cfg.salt, 'hex'), want = Buffer.from(cfg.hash, 'hex');
  const fails = new Map(), hits = new Map();
  const logFd = cfg.log ? fs.openSync(cfg.log, 'a', 0o600) : null;
  const log = (req, status, bytes) => {
    if (logFd === null) return;
    try { if (fs.fstatSync(logFd).size > 20e6) return; fs.writeSync(logFd, `${new Date().toISOString()} ${req.socket.remoteAddress} ${req.method} ${(req.url || '').split('?')[0].slice(0, 200)} ${status} ${bytes}\n`); } catch (e) { /* the log is optional */ }
  };
  const headers = (extra = {}) => ({
    'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Robots-Tag': 'noindex, nofollow', 'X-Frame-Options': 'DENY', 'Cross-Origin-Resource-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    ...extra,
  });
  const send = (req, res, status, body, extra = {}) => {
    const buf = Buffer.from(body); res.writeHead(status, headers({ 'Content-Type': 'text/plain; charset=utf-8', 'Content-Length': buf.length, 'Cache-Control': 'no-store', ...extra }));
    res.end(req.method === 'HEAD' ? undefined : buf); log(req, status, buf.length);
  };
  const okCache = new Map();         // sha256(Authorization header) -> expiry: a header that was verified lately is not run through scrypt again (a page has dozens of requests)
  const authOk = (req) => {
    const h = req.headers.authorization || '';
    if (!h.startsWith('Basic ')) return false;
    const ck = crypto.createHash('sha256').update(h).digest('hex'), hit = okCache.get(ck);
    if (hit && hit > Date.now()) return true;
    if (checkHeader(h)) { if (okCache.size > 200) okCache.clear(); okCache.set(ck, Date.now() + 600000); return true; }
    return false;
  };
  const checkHeader = (h) => {
    const [u, ...rest] = Buffer.from(h.slice(6), 'base64').toString('utf8').split(':');
    const pw = rest.join(':');
    const gotU = crypto.createHash('sha256').update(u).digest(), wantU = crypto.createHash('sha256').update(cfg.user).digest();
    const gotP = hashPassword(pw.slice(0, 256), salt);
    const a = crypto.timingSafeEqual(gotU, wantU), b = crypto.timingSafeEqual(gotP, want);
    return a && b;
  };
  const resolve = (pathname) => {
    let p; try { p = decodeURIComponent(pathname); } catch (e) { return { code: 400 }; }
    if (p.includes('\0') || p.includes('\\')) return { code: 400 };
    const segs = p.split('/').filter((s) => s !== '');
    if (segs.some((s) => s === '.' || s === '..' || s.startsWith('.'))) return { code: 404 };
    let file = path.join(root, ...segs);
    try {
      let st = fs.statSync(file);
      if (st.isDirectory()) { file = path.join(file, 'index.html'); st = fs.statSync(file); }
      const real = fs.realpathSync(file);
      if (real !== root && !real.startsWith(root + path.sep)) return { code: 404 };
      if (!st.isFile()) return { code: 404 };
      return { code: 200, file: real, st };
    } catch (e) { return { code: 404 }; }
  };
  const server = https.createServer({ key: fs.readFileSync(cfg.key), cert: fs.readFileSync(cfg.cert), minVersion: 'TLSv1.2', maxHeaderSize: 8192 }, (req, res) => {
    const ip = req.socket.remoteAddress, now = Date.now();
    // per-address request limit (a minute window) and the lock after wrong passwords
    const w = hits.get(ip) || { t: now, n: 0 }; if (now - w.t > 60000) { w.t = now; w.n = 0; } w.n++; hits.set(ip, w);
    if (w.n > cfg.perMinute) return send(req, res, 429, 'too many requests\n', { 'Retry-After': '60' });
    const f = fails.get(ip);
    if (f && f.until > now) return send(req, res, 429, 'locked for a while after too many wrong passwords\n', { 'Retry-After': String(Math.ceil((f.until - now) / 1000)) });
    if (!authOk(req)) {
      const g = fails.get(ip) || { n: 0, until: 0 }; if (req.headers.authorization) g.n++; if (g.n >= cfg.maxFail) { g.until = now + cfg.lockSeconds * 1000; g.n = 0; } fails.set(ip, g);
      return send(req, res, 401, 'authentication required\n', { 'WWW-Authenticate': 'Basic realm="ebook", charset="UTF-8"' });
    }
    fails.delete(ip);
    if (req.method !== 'GET' && req.method !== 'HEAD') return send(req, res, 405, 'method not allowed\n', { Allow: 'GET, HEAD' });
    const pathname = new URL(req.url, 'https:' + '//x').pathname;
    const r = resolve(pathname);
    if (r.code !== 200) return send(req, res, r.code, r.code === 400 ? 'bad request\n' : 'not found\n');
    const ext = path.extname(r.file).toLowerCase(), type = MIME[ext] || 'application/octet-stream', size = r.st.size;
    const etag = `W/"${size.toString(16)}-${Math.floor(r.st.mtimeMs).toString(16)}"`;
    const base = { 'Content-Type': type, 'Accept-Ranges': 'bytes', ETag: etag, 'Last-Modified': r.st.mtime.toUTCString(), 'Cache-Control': ext === '.html' ? 'no-cache' : ext === '.mp4' ? 'private, max-age=86400' : 'private, max-age=3600' };
    const assetPath = decodeURIComponent(pathname).replace(/\/+/g, '/');
    if (assetPath === '/assets/lab-config.json') base['Cache-Control'] = 'no-store';
    else if (assetPath.startsWith('/assets/vendor/')) base['Cache-Control'] = 'public, max-age=86400';
    if (ext === '.py') base['Content-Disposition'] = `attachment; filename="${path.basename(r.file)}"`;
    if (req.headers['if-none-match'] === etag) { res.writeHead(304, headers(base)); res.end(); return log(req, 304, 0); }
    let start = 0, end = size - 1, status = 200;
    const range = req.headers.range;
    if (range) {
      const m = /^bytes=(\d*)-(\d*)$/.exec(range.trim());
      if (!m || (m[1] === '' && m[2] === '')) return send(req, res, 416, 'bad range\n', { 'Content-Range': `bytes */${size}` });
      if (m[1] === '') { const n = Number(m[2]); start = Math.max(0, size - n); } else { start = Number(m[1]); end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1); }
      if (!(start <= end) || start >= size) return send(req, res, 416, 'range not satisfiable\n', { 'Content-Range': `bytes */${size}` });
      status = 206; base['Content-Range'] = `bytes ${start}-${end}/${size}`;
    }
    base['Content-Length'] = end - start + 1;
    res.writeHead(status, headers(base));
    if (req.method === 'HEAD') { res.end(); return log(req, status, 0); }
    const stream = fs.createReadStream(r.file, { start, end });
    stream.on('error', () => res.destroy());
    res.on('close', () => stream.destroy());
    stream.pipe(res); log(req, status, end - start + 1);
  });
  server.headersTimeout = 15000; server.requestTimeout = 30000; server.keepAliveTimeout = 5000; server.maxConnections = cfg.maxConnections;
  server.on('clientError', (err, socket) => { try { socket.end('HTTP/1.1 431 Request Header Fields Too Large\r\nConnection: close\r\n\r\n'); } catch (e) { socket.destroy(); } });
  server.listen(cfg.port, cfg.host, () => process.stdout.write(`listening ${cfg.host}:${cfg.port} root=${root}\n`));
  for (const s of ['SIGTERM', 'SIGINT']) process.on(s, () => server.close(() => process.exit(0)));
}

const a = args(process.argv.slice(2));
if (a._[0] === 'init') init(a); else if (a._[0] === 'run') run(a); else { process.stderr.write('usage: serve.mjs init|run --config <file> ...\n'); process.exit(2); }
