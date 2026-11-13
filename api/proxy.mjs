import {proxyRequest} from '../hosting/vercel/proxy.mjs';

// One function for all existing Brisa API routes. No Tuya credentials here.
export default async function handler(req, res) {
  let response;
  try {
    const rawRoute = req.query?.route;
    if (typeof rawRoute !== 'string') throw new Error('invalid_route');
    const route = rawRoute.replace(/^\/+/, '');
    const input = new URL(req.url, 'https://' + req.headers.host);
    const target = new URL('/api/' + route, 'https://' + req.headers.host);
    for (const [key, value] of input.searchParams) {
      if (key !== 'route') target.searchParams.append(key, value);
    }
    const headers = new Headers();
    for (const key of ['origin', 'content-type', 'x-ar-request', 'cookie']) {
      if (typeof req.headers[key] === 'string') headers.set(key, req.headers[key]);
    }
    let body;
    if (!['GET', 'HEAD'].includes(req.method)) {
      if (Buffer.isBuffer(req.body)) body = req.body;
      else if (typeof req.body === 'string') body = req.body;
      else if (req.body !== undefined) body = JSON.stringify(req.body);
      else {
        const chunks = [];
        let length = 0;
        for await (const chunk of req) {
          length += Buffer.byteLength(chunk);
          if (length > 4096) throw new Error('body_limit');
          chunks.push(chunk);
        }
        body = Buffer.concat(chunks);
      }
    }
    response = await proxyRequest(new Request(target, {method: req.method, headers, body}), process.env);
  } catch {
    response = new Response(JSON.stringify({detail: 'Pedido inválido.'}), {
      status: 400, headers: {'Content-Type': 'application/json', 'Cache-Control': 'private, no-store'}
    });
  }
  res.statusCode = response.status;
  for (const [key, value] of response.headers) res.setHeader(key, value);
  res.end(Buffer.from(await response.arrayBuffer()));
}
