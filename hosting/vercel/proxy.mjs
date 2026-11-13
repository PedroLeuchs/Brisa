const READ = /^(session|status|devices|devices\/home-ac\/status|automations(?:\/health)?|consumption\/home-ac)$/;
const WRITE = /^(login|logout|command|devices\/home-ac\/command|automations(?:\/[a-zA-Z0-9_-]{1,64}(?:\/delete)?)?|consumption\/home-ac\/settings)$/;
const MAX_AGE = 30 * 86400;

function reply(status, detail) {
  return new Response(JSON.stringify({detail}), {status, headers: {
    'Content-Type': 'application/json', 'Cache-Control': 'private, no-store',
    'Vercel-CDN-Cache-Control': 'no-store', 'CDN-Cache-Control': 'no-store'
  }});
}

function sessionCookie(raw) {
  return raw?.match(/(?:^|;\s*)ar_session=([A-Za-z0-9_-]{1,128})(?:;|$)/)?.[1];
}

function outputCookie(raw) {
  if (!raw || !/^ar_session=/.test(raw)) return null;
  const matched = raw.match(/^ar_session=(""|[A-Za-z0-9_-]{0,128});/);
  const value = matched ? (matched[1] === '""' ? '' : matched[1]) : undefined;
  const age = raw.match(/(?:^|;\s*)Max-Age=(\d+)(?:;|$)/i)?.[1];
  if (value === undefined || age === undefined) return null;
  return `ar_session=${value}; Path=/; Max-Age=${Math.min(Number(age), MAX_AGE)}; HttpOnly; Secure; SameSite=Strict`;
}

export async function proxyRequest(request, env, fetcher = fetch) {
  let backend, publicOrigin;
  try {
    backend = new URL(env.BRISA_BACKEND_URL);
    publicOrigin = new URL(env.BRISA_PUBLIC_ORIGIN);
    if (backend.protocol !== 'https:' || !backend.hostname.endsWith('.ts.net') ||
        backend.port || backend.pathname !== '/' || backend.search || backend.hash || backend.username || backend.password ||
        publicOrigin.protocol !== 'https:' || publicOrigin.port || publicOrigin.pathname !== '/' ||
        publicOrigin.search || publicOrigin.hash || publicOrigin.username || publicOrigin.password ||
        typeof env.BRISA_PROXY_TOKEN !== 'string' || env.BRISA_PROXY_TOKEN.length < 32) throw new Error();
  } catch { return reply(503, 'Configure a conexão com o PC no servidor da hospedagem.'); }
  const url = new URL(request.url);
  if (url.origin !== publicOrigin.origin) return reply(403, 'Endereço do painel não autorizado.');
  const route = url.pathname.slice('/api/'.length);
  if (!url.pathname.startsWith('/api/')) return reply(404, 'Rota não encontrada.');
  if (!['GET', 'POST'].includes(request.method)) return reply(405, 'Método inválido.');
  if (!(request.method === 'GET' ? READ : WRITE).test(route)) return reply(404, 'Rota não encontrada.');
  const consumption = request.method === 'GET' && route === 'consumption/home-ac';
  if ([...url.searchParams.keys()].some(key => !consumption || !['start', 'end'].includes(key)) ||
      [...url.searchParams.keys()].some(key => url.searchParams.getAll(key).length !== 1)) return reply(400, 'Consulta inválida.');
  let body;
  if (request.method === 'POST') {
    if (request.headers.get('origin') !== publicOrigin.origin || request.headers.get('x-ar-request') !== '1') return reply(403, 'Origem inválida.');
    if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type') || '')) return reply(415, 'Envie um pedido JSON.');
    body = await request.text();
    if (Buffer.byteLength(body) > 4096) return reply(413, 'Pedido grande demais.');
    try { JSON.parse(body); } catch { return reply(400, 'Pedido inválido.'); }
  }
  const headers = {'X-Brisa-Proxy-Token': env.BRISA_PROXY_TOKEN, 'Accept': 'application/json'};
  const token = sessionCookie(request.headers.get('cookie'));
  if (token) headers.Cookie = 'ar_session=' + token;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    headers['X-Ar-Request'] = '1';
  }
  const target = new URL('/api/' + route, backend);
  target.search = url.search;
  try {
    // A physical command is sent at most once. Never follow redirects or retry.
    const upstream = await fetcher(target, {method: request.method, headers, body,
      redirect: 'manual', cache: 'no-store', signal: AbortSignal.timeout(18000)});
    if (upstream.status < 200 || upstream.status >= 300 && upstream.status < 400 ||
        !upstream.headers.get('content-type')?.includes('application/json')) {
      return reply(503, 'O PC não respondeu pela conexão configurada.');
    }
    const data = await upstream.text();
    try { JSON.parse(data); } catch { return reply(502, 'Resposta inválida do PC.'); }
    const response = new Response(data, {status: upstream.status, headers: {
      'Content-Type': 'application/json', 'Cache-Control': 'private, no-store',
      'Vercel-CDN-Cache-Control': 'no-store', 'CDN-Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'
    }});
    if (['login', 'logout'].includes(route)) {
      const cookie = outputCookie(upstream.headers.get('set-cookie'));
      if (cookie) response.headers.set('Set-Cookie', cookie);
      else if (upstream.ok) return reply(502, 'Não foi possível confirmar a sessão.');
    }
    return response;
  } catch {
    return reply(503, request.method === 'POST' && route !== 'login' && route !== 'logout'
      ? 'Envio sem confirmação. Consulte o estado antes de tentar novamente.'
      : 'PC sem conexão. Confira se está ligado e se o Brisa iniciou.');
  }
}
