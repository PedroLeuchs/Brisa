# Brisa com Tuya Cloud

**Alternativa opcional.** O caminho atual escolhido permite manter o PC ligado
e publica a interface gratuitamente na Vercel, sem Tuya Cloud. Consulte
[VERCEL.md](VERCEL.md). As notas abaixo registram a alternativa investigada.

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

## Requisito atualizado: custo zero

A hospedagem deve ser gratuita. A configuração de contratação do Render foi
retirada; nenhum serviço foi contratado. O container continua disponível para
infraestrutura compatível já existente.

Para dispensar a Tuya Cloud, o agente em `remote/` precisa rodar na rede do ar.
Com o PC desligado e sem outro aparelho disponível, a alternativa a investigar
é o próprio roteador. É necessário identificar modelo e revisão de hardware
antes de determinar se o firmware permite executar o agente ou uma ponte.
Um servidor na internet não acessa diretamente o IP privado do ar; publicar
somente a interface não resolve a comunicação.

Cloudflare Workers e D1 oferecem planos gratuitos, mas exigem adaptar o backend,
armazenamento e agenda. Isso resolve a hospedagem, não substitui a ponte doméstica
necessária ao controle local. Ainda não há implantação desse transporte.

Após uma implantação funcional, a validação deve incluir fechar e reabrir o
navegador no Android, testar um comando combinado com o proprietário e ler o
estado com o PC doméstico desligado usando a internet móvel.
