# Relay remoto e agente doméstico — fatia executável isolada

Este código prepara o controle externo sem publicar o painel e sem supor que a nuvem tenha acesso à LAN. O painel em execução, suas sessões, suas rotinas e seu processo não são alterados por importar estes módulos.

## Implementado

- Relay HTTP independente com fila SQLite persistente, IDs lógicos e autorização por casa/aparelho.
- Credenciais de máquina distintas para agente e operador/BFF, armazenadas como hashes no relay e revogáveis. Cookies/senha do painel local não dão acesso ao relay.
- Agente que faz polling autenticado **de saída**; não escuta portas domésticas.
- Prazo curto de validade (1–120 segundos), validação também no agente e verificação no ponto de envio físico pelo executor compartilhado.
- Idempotência de criação no relay e diário durável de deduplicação no agente, incluindo reinício.
- Reserva gravada antes de tentar enviar. Se houver queda entre reserva e resultado, a tentativa fica **incerta**, sem repetição automática.
- Caixa de saída de resultados: se a conexão cair após uma tentativa, o resultado é reenviado, não o comando físico.
- Confirmação por leitura, estados confirmado/incerto/expirado/rejeitado, reconexão com espera crescente e descarte de pedidos vencidos.
- Integração opcional `attach_agent(app, devices, config)` com o **mesmo DeviceService/controlador/lock** já usado pelo painel e pelas rotinas. Não cria outro scheduler. Lock de processo impede duas instâncias usando o mesmo diário.
- HTTPS obrigatório no cliente, com validação de certificado. HTTP só é aceito quando explicitamente habilitado para hostname/IP de loopback em ensaio local.

## O que NÃO foi ativado

Nenhum agente está conectado ao ar ou a um servidor público. `app.py` não foi modificado para registrar o agente. Nenhum token real de pareamento foi criado. Nenhuma porta do painel/roteador foi aberta. Não há nova conta, hospedagem ou cobrança.

O relay é por enquanto uma API de máquinas; **não é uma aplicação pública com login de usuários pronta para publicação**. A autenticação do navegador precisa de uma camada BFF com OIDC/MFA e autorização por casa. O token de operador é para testes/BFF, não para localStorage, frontend público ou URLs. Ainda faltam UI remota, pareamento/rotação operacionais, domínio/HTTPS público, proteção de borda, backups e validação 4G/5G.

## Ensaio completo sem ar-condicionado

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test_remote.py
.\.venv\Scripts\python.exe -m remote.simulate
```

O segundo comando cria um relay HTTP em uma **porta efêmera de 127.0.0.1**, um agente de saída e um aparelho simulado. Envia um pedido só ao simulador, confirma por leitura, encerra o serviço e remove apenas seus arquivos temporários. Não importa o app doméstico nem solicita Local Key. Não ocupa 8080/8443 e não inicia rotinas reais.

## Preparar um relay de desenvolvimento, quando necessário

```powershell
.\.venv\Scripts\python.exe -m remote.provision
.\.venv\Scripts\python.exe -m remote.server
```

O provisionamento é um passo administrativo local, não uma rota pública. Gera `remote/runtime/agent.env`, `operator.env` e `relay.sqlite3`; não imprime tokens nem sobrescreve arquivos existentes. A pasta está ignorada no Git. No Windows, restrinja o diretório ao usuário responsável (chmod não substitui ACL NTFS). O servidor de ensaio usa somente 127.0.0.1:8090 e um worker. Não registra o agente no painel atual.

Somente `agent.env` deve acompanhar a instalação doméstica; o relay nunca recebe o `.env` do controlador ou a Local Key. Configure permissões reais disponíveis no provisionamento antes de ativar: o agente volta a validar o mapeamento local. Para revogar, o administrador usa `RelayStore.revoke(token)` no ambiente administrativo; um fluxo de rotação com UI ainda não foi entregue.

## Integração futura sem segundo executor

Depois de definir hospedagem/HTTPS e parear as identidades, na composição do backend doméstico, **antes de iniciar o único worker**:

```python
from remote.inprocess import AgentConfig, attach_agent

# Ler token de um arquivo local protegido/secret manager, nunca do frontend.
# Reutilizar app e devices já existentes, sem importar/iniciar outro app.
attach_agent(app, devices, AgentConfig(
    relay_url=relay_url_https,
    token=agent_token_local,
    home_id=home_id,
    agent_id=agent_id,
    devices=('home-ac',),
    journal_path=agent_journal_local,
))
```

Essa chamada não foi acrescentada ao servidor atual. O executor prepara a conexão TinyTuya e testa novamente o prazo antes de `socket.sendall`, sob o lock do controlador existente. Não execute um processo LAN separado contra o mesmo aparelho. Múltiplos workers domésticos continuam fora do escopo suportado.

## Implantação proposta, ainda sem execução

Uma pequena VPS com disco persistente pode hospedar o relay e um BFF autenticado, atrás de HTTPS com domínio. A casa só faz conexões de saída. `remote/Dockerfile` prepara uma imagem que copia apenas `remote/`; `.dockerignore` exclui dados, relatórios, ambientes e runtime. O banco deve ficar em volume persistente. Não executar a imagem publicamente antes de configurar autenticação do navegador, host permitido, HTTPS, limites de corpo/conexões, rate limit de borda e backups.

O primeiro passo de implantação depende de escolher servidor/domínio e autenticação de usuários. Não é necessário comprar nada para executar os testes locais.

## Limites e operação

- Não há promessa de “exatamente uma vez”: falhas no instante da escrita produzem resultado incerto. O desenho evita repetir uma tentativa potencialmente executada.
- Preserve o diário do agente entre reinícios, não clone uma identidade/diário em agentes concorrentes e não remova registros para forçar repetição.
- Relógios com divergência superior a cinco segundos fazem o agente rejeitar execução. Sincronização de relógio deve ser mantida.
- Só controles conhecidos são transmitidos. Respostas brutas, DPS, exceções, Local Key e credenciais nunca são resultados do relay.
- Sem conexão externa, o controle e as rotinas locais continuam independentes. Pedidos remotos vencidos não são compensados depois.
- Este ciclo valida o caminho com simuladores. Integração com o aparelho real e acesso móvel externo precisam de etapa posterior autorizada.
