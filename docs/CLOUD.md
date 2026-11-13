# Brisa com Tuya Cloud

O transporte cloud usa o mesmo contrato de aparelho do backend doméstico. A API,
interface, rotinas e cálculo de consumo continuam no FastAPI. A leitura de estado
e a lista de funções foram validadas na região Western America em 13/11/2026:
autenticação OK, 18 estados e 16 funções. Não foi enviado um comando físico;
a permissão de escrita e a atuação do ar ainda exigem teste controlado.

Configure no **gerenciador de segredos da hospedagem**, nunca no frontend ou
repositório, `TUYA_ACCESS_ID`, `TUYA_ACCESS_SECRET`, `TUYA_DEVICE_ID` e
`APP_PASSWORD_HASH`. Configure também `TUYA_TRANSPORT=cloud`,
`TUYA_CLOUD_REGION=us`, `COOKIE_SECURE=true` e `ALLOWED_HOSTS` com o hostname
exato do domínio HTTPS. A senha do painel pode continuar usando o hash scrypt
existente. A opção "Lembrar deste dispositivo" emite sessão de até 30 dias.

O container requer um serviço Python que permaneça ligado, HTTPS no proxy da
hospedagem e um **volume persistente em `/app/data`**. Execute exatamente um
worker Uvicorn/uma instância: as rotinas usam um worker de processo e o histórico
é coletado a cada minuto. O volume deve ser incluído no backup. A cópia limpa
não contém as bases domésticas, então a migração dos dados existentes requer
exportação separada e privada de `data/automations.json`,
`data/consumption.sqlite3` e `data/sessions.sqlite3` (ou novo login).

O Site reservado em ChatGPT Sites permanece sem publicação: Sites executa
Cloudflare Worker, não o FastAPI Python nem seus workers contínuos/SQLite.
Um link funcional depende de uma hospedagem com Python, volume persistente e
execução contínua. Não há serviço pago contratado.

Como o Access Secret anterior apareceu em uma conversa, gere um novo no Tuya
Developer Platform e substitua-o diretamente no gerenciador de segredos da
hospedagem antes de publicar. A rotação invalida a chave antiga.
