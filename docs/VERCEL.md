# Brisa na Vercel + PC doméstico

Opção para custo zero: Vercel Hobby hospeda a interface e um proxy Node,
Tailscale Personal/Funnel fornece HTTPS até o PC, e FastAPI/TinyTuya continua
controlando o ar na rede doméstica. Não depende de Access ID/Secret Tuya.
O PC precisa ficar ligado, conectado e sem suspender. Os serviços gratuitos
têm limites; indisponibilidade do PC ou do túnel interrompe o acesso remoto.

O navegador usa somente o domínio Vercel. O proxy encaminha apenas rotas
conhecidas, sem redirects ou repetição de comandos. Seu segredo não chega ao
frontend. O backend exige tanto o token do proxy quanto o login do usuário.
Cookies Secure/HttpOnly/SameSite=Strict pertencem ao domínio Vercel.
"Lembrar deste dispositivo" mantém sessão por até 30 dias. Rotinas, histórico
e sessões continuam nos arquivos originais em `data/` no PC.

## Preparar o Windows

Integrar esta revisão à cópia ativa `C:\projects\ar`, preservando `.env`,
`data/`, certificados e arquivos privados. Não clonar por cima da pasta existente
nem iniciar outra cópia contra o mesmo ar. A `.venv` e o Tailscale devem estar
instalados; a senha do painel e a Local Key continuam somente no `.env` do PC.

No PowerShell do usuário que mantém o computador ligado, na pasta do projeto:

```powershell
.\instalar-inicio-brisa.ps1
```

O instalador gera `data/vercel-proxy.token`, protegido por ACL e sem exibi-lo,
e registra a tarefa **BrisaHome** com privilégio limitado. Não encerra o serviço
atual nem altera o ar. Recusa outra tarefa identificada para o mesmo projeto.

**A tarefa inicia ao entrar nesse usuário do Windows, não antes do login.**
Depois de reiniciar, entre uma vez. Bloquear a tela mantém o processo; sair da
conta, suspender ou desligar pode interrompê-lo. Não exige terminal aberto.
Não há limite de duração; após falha, tenta reiniciar até três vezes.

Coordenar a parada do processo anterior, conferindo que não há rotinas em
execução, e iniciar a tarefa sem manter outro backend:

```powershell
Start-ScheduledTask -TaskName BrisaHome
```

O iniciador recusa outra instância e portas 8080/8443 ocupadas. Usa loopback,
um worker, transporte local, cookies seguros e hosts exatos. Nesse modo, as
APIs exigem o token do proxy e o painel doméstico acessado diretamente deixa
de autenticar pela API. Use o painel Vercel. Para voltar ao uso anterior,
pare a tarefa e use o iniciador antigo sem token no ambiente.

## Ativar o túnel uma vez

Em PowerShell como Administrador, na mesma pasta:

```powershell
.\publicar-tunel.ps1
```

O script exige que o backend recuse pedidos sem token e continue exigindo login
com token correto. Confere Serve, guarda uma cópia local da configuração e ativa
Funnel em segundo plano somente para `http://127.0.0.1:8080`. Não abre portas
do roteador. Se houver autorização no navegador Tailscale, conclua pela própria
conta. Não contrate plano pago. A configuração `--bg` é mantida pelo serviço
Tailscale. O script imprime o endereço do túnel, sem imprimir o token.

## Importar na Vercel

Importar `https://github.com/PedroLeuchs/Brisa` em https://vercel.com/new,
no plano pessoal **Hobby**, com raiz `.`. Não selecionar FastAPI como framework
nem usar `frontend` como raiz. O `vercel.json` define instalação, build, saída
estática e proxy; o Node é 22.x e o build usa o lockfile pnpm existente.

Em **Settings > Environment Variables**, somente **Production**:

| Nome | Valor a configurar diretamente no gerenciador |
|---|---|
| `BRISA_BACKEND_URL` | Origem HTTPS do Funnel, sem caminho nem query |
| `BRISA_PUBLIC_ORIGIN` | Origem HTTPS exata do painel, como `https://seu-brisa.vercel.app` |
| `BRISA_PROXY_TOKEN` | Mesmo token privado do PC, armazenado como segredo |

Para copiar o token sem exibi-lo no terminal:

```powershell
.\copiar-token-vercel.ps1
```

Cole diretamente na variável secreta da Vercel e limpe a área de transferência.
Não envie ao chat nem coloque em código, URL ou variável `VITE_*`. Não envie o
`.env` doméstico: Tuya Local Key e hash da senha ficam no PC.

Se o endereço Vercel só for conhecido após o primeiro deploy, configure
`BRISA_PUBLIC_ORIGIN` e faça um novo deploy. Sem a configuração completa, a
API falha fechada. Hosts de preview não acessam o backend de produção.
Trocar domínio ou segredo exige atualizar as configurações e republicar.

## Validar antes de considerar entregue

Conferir um único backend no PC. A API direta do túnel deve responder 403 sem
token; pelo domínio Vercel, sem login, a sessão deve responder 401. Com PC
desconectado, o painel deve informar perda de conexão e não repetir comandos.

No Android, em 4G/5G e sem Tailscale ativo: abrir Vercel, entrar com a senha
existente e marcar "Lembrar deste dispositivo". Fechar/reabrir navegador,
conferir estado e histórico, testar um comando autorizado e depois conferir
persistência da sessão após reiniciar a tarefa. Esta validação real e a
instalação Windows ainda não foram feitas pelo ambiente cloud.

## Desfazer

```powershell
.\instalar-inicio-brisa.ps1 -Remove
# Em PowerShell administrativo, retirar somente a exposição pública em 443:
& "$env:ProgramFiles\Tailscale\tailscale.exe" funnel --https=443 off
```

O arquivo `data/tailscale-before-funnel.json` permite conferir a configuração
Serve anterior. Não fazer reset global do Tailscale nem apagar bancos para
desfazer. Para revogar o token, trocar no PC e no gerenciador da Vercel.

Referências: [Vercel Hobby](https://vercel.com/docs/plans/hobby),
[Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel),
[Tailscale Personal](https://tailscale.com/pricing).
