import {test} from 'node:test';
import assert from 'node:assert/strict';
import {proxyRequest} from './proxy.mjs';
import handler from '../../api/proxy.mjs';

const env = {BRISA_BACKEND_URL:'https://home.example.ts.net', BRISA_PUBLIC_ORIGIN:'https://brisa.example', BRISA_PROXY_TOKEN:'test-only-'.repeat(5)};
const request = (route, body, extra={}) => new Request(env.BRISA_PUBLIC_ORIGIN+'/api/'+route, {
  method: body === undefined ? 'GET' : 'POST',
  headers: {Origin:env.BRISA_PUBLIC_ORIGIN, 'Content-Type':'application/json', 'X-Ar-Request':'1', ...extra},
  body:body === undefined ? undefined : JSON.stringify(body)
});
const json = (data, status=200, headers={}) => new Response(JSON.stringify(data), {status,headers:{'Content-Type':'application/json',...headers}});

test('login and remembered cookie stay on the public origin; tokens stay server-side', async()=>{
  let calls=0;
  const response=await proxyRequest(request('login',{password:'test-only',remember:true}),env,async(url,options)=>{
    calls++;
    assert.equal(url.href,env.BRISA_BACKEND_URL+'/api/login');
    assert.equal(options.headers['X-Brisa-Proxy-Token'],env.BRISA_PROXY_TOKEN);
    assert.equal(options.headers['X-Ar-Request'],'1');
    assert.equal(options.redirect,'manual');
    assert.deepEqual(JSON.parse(options.body),{password:'test-only',remember:true});
    return json({ok:true},200,{'set-cookie':'ar_session=test_session; Max-Age=2592000; Path=/; Domain=home.example.ts.net; HttpOnly'});
  });
  assert.equal(calls,1);
  assert.equal(response.headers.get('set-cookie'),'ar_session=test_session; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Strict');
  assert.match(response.headers.get('cache-control'),/no-store/);
  assert.equal(response.headers.get('vercel-cdn-cache-control'),'no-store');
  assert.equal((await response.text()).includes(env.BRISA_PROXY_TOKEN),false);
});

test('session forwards only Brisa cookie, preserving backend authorization',async()=>{
  const response=await proxyRequest(request('session',undefined,{Cookie:'analytics=private; ar_session=abc_123; other=secret',Authorization:'Bearer not-forwarded'}),env,async(url,options)=>{
    assert.equal(options.headers.Cookie,'ar_session=abc_123');
    assert.equal(options.headers.Authorization,undefined);
    return json({detail:'Entre com a senha'},401);
  });
  assert.equal(response.status,401);
});

test('logout propagates cookie deletion including Starlette quoted empty value',async()=>{
  const response=await proxyRequest(request('logout',{}),env,async()=>json({ok:true},200,{'set-cookie':'ar_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=lax'}));
  assert.equal(response.status,200);
  assert.match(response.headers.get('set-cookie'),/^ar_session=; Path=\/; Max-Age=0;/);
});

test('blocks cross-site writes, preview origins, unknown routes and oversized bodies before forwarding',async()=>{
  const never=()=>assert.fail('blocked request reached backend');
  assert.equal((await proxyRequest(request('command',{}, {Origin:'https://evil.example'}),env,never)).status,403);
  assert.equal((await proxyRequest(new Request('https://preview.example/api/session'),env,never)).status,403);
  assert.equal((await proxyRequest(request('../.env'),env,never)).status,404);
  assert.equal((await proxyRequest(request('devices/other/status'),env,never)).status,404);
  assert.equal((await proxyRequest(request('login',{password:'x'.repeat(5000)}),env,never)).status,413);
  assert.equal((await proxyRequest(request('session?target=https://evil.example'),env,never)).status,400);
  assert.equal((await proxyRequest(request('session'),{...env,BRISA_PROXY_TOKEN:''},never)).status,503);
  assert.equal((await proxyRequest(request('session'),{...env,BRISA_BACKEND_URL:'http://127.0.0.1'},never)).status,503);
});

test('command failures and redirects are never retried; response explains uncertain result',async()=>{
  let calls=0;
  const result=await proxyRequest(request('devices/home-ac/command',{code:'switch',value:false}),env,async()=>{calls++;throw Error('secret network details');});
  assert.equal(calls,1);
  assert.equal(result.status,503);
  assert.match(await result.text(),/sem confirmação/);
  const redirected=await proxyRequest(request('session'),env,async()=>new Response(null,{status:302,headers:{location:'https://evil.example'}}));
  assert.equal(redirected.status,503);
});

test('consumption query and automation writes use the existing API contract',async()=>{
  const result=await proxyRequest(request('consumption/home-ac?start=2026-11-01&end=2026-11-13'),env,async(url)=>{
    assert.equal(url.search,'?start=2026-11-01&end=2026-11-13');
    return json({days:[]});
  });
  assert.equal(result.status,200);
  assert.equal((await proxyRequest(request('automations/abc123/delete',{}),env,async()=>json({ok:true}))).status,200);
});

test('Vercel Node adapter forwards rewritten route, body and consumption parameters',async()=>{
  const previous={...process.env};
  const oldFetch=globalThis.fetch;
  Object.assign(process.env,env);
  let destination;
  globalThis.fetch=async(url)=>{destination=String(url);return json({ok:true});};
  try {
    const req={method:'GET',url:'/api/consumption/home-ac?start=2026-11-01&end=2026-11-13',query:{route:'consumption/home-ac'},headers:{host:'brisa.example'}};
    const res={headers:{},setHeader(k,v){this.headers[k]=v;},end(data){this.body=data.toString();}};
    await handler(req,res);
    assert.equal(res.statusCode,200);
    assert.equal(destination,env.BRISA_BACKEND_URL+'/api/consumption/home-ac?start=2026-11-01&end=2026-11-13');
    globalThis.fetch=async(url,options)=>{
      assert.equal(String(url),env.BRISA_BACKEND_URL+'/api/login');
      assert.deepEqual(JSON.parse(options.body),{password:'test-only',remember:true});
      return json({ok:true},200,{'set-cookie':'ar_session=adapter_session; Max-Age=2592000; Path=/'});
    };
    Object.assign(req,{method:'POST',url:'/api/proxy?route=login',query:{route:'login'},
      headers:{host:'brisa.example',origin:env.BRISA_PUBLIC_ORIGIN,'content-type':'application/json','x-ar-request':'1'},
      body:{password:'test-only',remember:true}});
    await handler(req,res);
    assert.equal(res.statusCode,200);
    assert.match(res.headers['set-cookie'],/adapter_session; Path=\/; Max-Age=2592000; HttpOnly; Secure/);
    req.query.route=['session','login'];
    await handler(req,res);
    assert.equal(res.statusCode,400);
  } finally {
    globalThis.fetch=oldFetch;
    for(const key of Object.keys(env)) {
      if(previous[key]===undefined) delete process.env[key]; else process.env[key]=previous[key];
    }
  }
});
