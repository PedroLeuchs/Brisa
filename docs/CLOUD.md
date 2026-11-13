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

## Configuração pronta para Render

O `render.yaml` cria uma única instância Starter com 1 GB de disco em `/app/data`.
O custo de referência é US$ 7/mês pelo serviço e US$ 0,25/mês pelo disco, antes de
impostos e excedentes. Consulte https://render.com/pricing antes de confirmar.
Nenhum recurso foi contratado ou criado no Render. O plano Free não preserva o
disco e suspende o processo, interrompendo coleta e agenda.

Após autorizar a contratação, conecte o repositório em
https://dashboard.render.com/select-repo?type=blueprint e revise os recursos.
O formulário solicita os quatro valores secretos declarados com `sync: false`.
Cole o novo Access Secret somente nesse formulário, nunca no GitHub ou no chat.
Para criar a senha do painel, rode `python -m backend.tools.generate_password_hash`
em um terminal privado e cole a linha gerada em `APP_PASSWORD_HASH`. A senha em
si não é exibida nem gravada. Também é possível usar o hash doméstico existente.

O Render fornece HTTPS e `RENDER_EXTERNAL_HOSTNAME`; o container usa esse hostname
como `ALLOWED_HOSTS`. Para um domínio próprio, configure `ALLOWED_HOSTS` explicitamente.
O container confia nos cabeçalhos do proxy da hospedagem e deve ser exposto apenas
por esse proxy. Publicações automáticas estão desativadas no Blueprint.

Após o deploy, entre no Android e marque "Lembrar deste dispositivo". A sessão
fica no SQLite persistente e dura até 30 dias. A validação de produção deve incluir
fechar e reabrir o navegador, testar um comando combinado com o proprietário,
e ler o estado com o PC doméstico desligado usando a internet móvel.
