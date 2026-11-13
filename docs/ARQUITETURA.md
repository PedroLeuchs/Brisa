# Direção de arquitetura

## Implementação isolada do transporte remoto

A pasta `remote/` agora contém um protótipo executável de relay/agente em Python/FastAPI, reaproveitando a stack existente para validar o transporte antes de introduzir outro servidor. Ele tem fila, autenticação de máquinas, isolamento por casa/aparelho, expiração, deduplicação durável e reconexão. A composição opcional reutiliza o DeviceService doméstico, sem segundo controlador/agendador. Testes e ensaio HTTP usam apenas aparelhos simulados. Nada foi ativado no painel atual.

O servidor/BFF público e a autenticação de usuários continuam pendentes; Node/TypeScript permanece uma opção para essa camada. O relay atual não publica o frontend nem aceita a senha doméstica como login público. As descrições abaixo sobre serviços públicos futuros continuam válidas e não devem ser confundidas com uma implantação já feita. Consulte `remote/README.md`.

## Estado atual e decisão de compatibilidade

O controle LAN real foi validado com Python e TinyTuya 1.20.0, protocolo Tuya 3.4. A camada HTTP atual é FastAPI e a interface principal foi migrada para React/TypeScript com Vite. O briefing prefere também Node/TypeScript no servidor, mas admite adaptação por compatibilidade LAN. O servidor público Node e o canal remoto ainda não foram implementados.

Preservar o adaptador TinyTuya validado durante a migração. React/TypeScript pode substituir a interface consumindo a mesma API. Node/TypeScript pode servir a aplicação pública e as regras de usuários/dispositivos; não precisa substituir a comunicação LAN ao mesmo tempo.

## Fronteiras previstas

- **frontend/**: React/TypeScript, componentes de climatização e PWA. Só conhece a API de aplicação; nunca recebe Local Key ou credenciais Tuya.
- **backend/**: servidor público Node/TypeScript, contas, casas, aparelhos, permissões e registro das operações. Localmente, o servidor atual permanece operacional até concluir a migração.
- **agent/**: serviço doméstico Python com adaptador TinyTuya; mantém as chaves locais e serializa o acesso ao aparelho. Conecta ao servidor público por uma conexão autenticada de saída.
- **docs/**: decisões, operação e evidências de validação.

Já implementados: frontend React/TypeScript, serviço de registro de aparelhos em backend/services, contrato DeviceAdapter e adaptador TinyTuya em backend/adapters. controller.py preserva a implementação LAN existente; app.py continua sendo o ponto de entrada. O contrato novo não inclui IDs Tuya, IP ou DPS no frontend. Agente em processo separado, transporte remoto e servidor público permanecem como próximas etapas, não como funcionalidades disponíveis.

## Caminho local e caminho remoto

No uso local, navegador → API doméstica → adaptador → ar. Na futura publicação, navegador → servidor público HTTPS → canal autenticado de saída do agente doméstico → adaptador → ar. Nenhum IP privado do aparelho será usado pelo navegador remoto.

Publicar o painel não elimina a necessidade do agente ligado em casa. A Local Key permanece no agente. Credenciais da Tuya Cloud servem apenas ao provisionamento e não fazem parte do caminho de execução do controle.

VPN privada ou túnel autenticado podem antecipar o acesso pessoal, conforme o briefing. Não substituem o desenho de contas/casas/agentes caso o produto público passe a atender vários usuários.

## Contrato de comandos para a expansão

Cada comando remoto deve incluir identificador único, casa, aparelho, função, valor e prazo de validade. O servidor verifica a permissão; o agente valida novamente função, tipo, faixa e destino. Comandos expirados são descartados, nunca executados depois de um longo período offline.

Estados de um comando: recebido, enviado ao dispositivo, confirmado por leitura, falhou ou resultado incerto. Sucesso no transporte não significa atuação física. Um envio sem resposta não deve ser repetido automaticamente. Identificadores já processados precisam ser deduplicados no agente, inclusive após reinício, com armazenamento durável e retenção definida.

Telemetria deve trazer horário da leitura e disponibilidade. A interface deve identificar valores antigos após queda da conexão. Sessão do usuário e conectividade do aparelho são estados independentes.

## Segurança e operação

Produção exige HTTPS, cookies seguros, autenticação de usuário, autorização por casa/aparelho, proteção contra tentativas e autenticação individual dos agentes, com revogação/rotação. Endpoints LAN de diagnóstico não devem ser publicados como API pública. Segredos nunca entram em frontend, mensagens de erro, histórico de comandos ou repositório.

Não abrir portas Tuya no roteador. A conexão do agente deve sair da casa. Implantação pública, domínio, hospedagem e custos precisam ser definidos antes da publicação; nenhum serviço pago foi contratado.

Começar com um servidor e um banco, sem exigir microserviços. Só escalar processos e filas quando houver necessidade medida. Antes de múltiplos workers locais, mover a exclusão mútua do dispositivo para um agente único: o lock Python atual protege apenas um processo.

## Sequência de evolução

1. Consolidar estabilidade e confirmar comandos físicos LAN.
2. Validar celular e HTTPS/PWA na rede doméstica.
3. Extrair uma interface de adaptador e migrar a interface para React/TypeScript, preservando o controle existente.
4. Criar servidor público e agente com contrato de comandos, autenticação e confirmação de estado.
5. Adicionar contas/casas/aparelhos e testes de isolamento entre usuários.
6. Implantar e validar reconexão, expiração, deduplicação e operação remota antes de automações.

Não simular consumo energético nem exibir sensores que não tenham medição real confirmada.
