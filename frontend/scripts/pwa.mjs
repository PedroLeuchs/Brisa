import {readFile, writeFile, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import sharp from 'sharp';

const dist = new URL('../dist/', import.meta.url);
for (const size of [192, 512]) await sharp(new URL('icon.svg', dist).pathname.replace(/^\/([A-Za-z]:)/, '$1')).resize(size,size).png().toFile(new URL(`icon-${size}.png`, dist).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const files = (await readdir(dist, {recursive:true})).filter(name => /\.(js|css|svg|png|webmanifest)$/.test(name) && !name.endsWith('sw.js'));
const shell = ['/', ...files.map(name => '/ui/' + name.replaceAll('\\','/'))];
const version = createHash('sha256').update(await readFile(new URL('index.html', dist))).digest('hex').slice(0,12);
await writeFile(new URL('sw.js', dist), `
const CACHE='brisa-react-${version}';
const SHELL=${JSON.stringify(shell)};
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)));self.skipWaiting();});
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('brisa-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
 if(SHELL.includes(url.pathname))event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)));
});
`);
console.log('PWA: ícones PNG e cache da interface gerados; API e comandos nunca são armazenados.');
