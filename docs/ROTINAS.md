# Rotinas com vários horários — 24/10/2026

## Uso

Abra Automações (ou Timer no Modo controle). Informe o nome da rotina, escolha o aparelho e os dias uma vez. Em cada entrada, informe horário, ação e valor. Use **Adicionar horário** para incluir a próxima ação e **Remover** para retirar uma entrada. O botão ativo/pausado vale para a rotina inteira. Nada é salvo ou executado apenas por abrir o editor.

É possível, por exemplo, ligar/desligar várias vezes ao dia dentro de uma rotina. Esses exemplos não foram cadastrados no aparelho. O editor suporta de 1 a 16 entradas, com as ações e valores realmente disponíveis na configuração local. Ao salvar, organiza a sequência por horário; ações diferentes no mesmo minuto mantêm a ordem informada.

No mobile, Automações é uma tela inteira com cabeçalho/voltar, área de conteúdo rolável, safe areas e campos adequados ao teclado. No desktop, permanece um painel sobre a página. Foco fica dentro da tela e é devolvido ao botão de origem ao fechar.

## Validação de conflitos

- Repetir a mesma ação no mesmo horário dentro de uma rotina é rejeitado, tanto com valor igual (duplicação) como diferente (conflito).
- Ações diferentes no mesmo minuto são permitidas e seguem a ordem mostrada.
- Uma ação/horário que colide com outra rotina ativa para o mesmo aparelho nos mesmos dias é rejeitada ao criar, editar ou reativar. O servidor não pausa, remove ou muda valores automaticamente.
- Dias, nome, intervalo de temperatura, enums, tipos e IDs de entrada são validados no backend. O cliente não pode injetar histórico nem resultados de execução.

## Compatibilidade e preservação

A leitura de uma rotina antiga de um horário migra para schema_version 2. Antes da primeira gravação da migração, preserva a versão anterior em `data/automations.v1-backup.json`. ID da rotina, criação, enabled e último resultado são mantidos. A entrada legada recebe ID estável e o registro de execução anterior é copiado para seu histórico.

As respostas ainda incluem code/value/time da primeira entrada para clientes antigos. Um update legado edita a primeira entrada sem apagar as demais ou renomear a rotina. O editor atual sempre usa entries e conserva seus IDs.

Cada entrada mantém last_run, last_result e history. Retirar uma entrada arquiva-a em retired_entries na mesma rotina, preservando histórico e identidade; recolocá-la com o mesmo ID conserva esse histórico. Excluir uma rotina inteira continua exigindo confirmação do usuário.

## Execução

O processo doméstico segue com um worker/agendador e fuso America/Sao_Paulo. A deduplicação usa rotina + ID da entrada + ocorrência no minuto/dia. A reserva e o registro incerto são persistidos antes do envio. Resultado offline/incerto não é repetido. Edições e disparos continuam serializados pelo lock da transação completa.

Não há compensação de minutos anteriores após suspensão ou salto de relógio, nem execução de rotinas antigas ao reiniciar. Recuperação de falha de arquivo preserva a referência temporal para não executar horários perdidos.

## Evidências desta entrega

- 132 testes Python integrados aprovados, incluindo os 27 testes de agenda/modelo de rotina.
- 54 testes frontend aprovados e TypeScript/build concluídos, preservando Consumo, temas, Ambiente e login.
- Artefatos de QA com dados fictícios pausados gerados em work/routines-mobile-qa.html e work/routines-desktop-qa.html. O navegador de automação bloqueou file://; não foi contornado. A conferência visual final no Android permanece pendente; testes de DOM/foco e estrutura mobile passaram.
- Nenhuma agenda real criada ou comando físico enviado. Não existiam rotinas ativas antes do único reinício desta entrega.
- HTTPS 192.168.1.5:8443 e certificado existentes preservados. Painel/bundle responderam 200 após reinício, API de rotinas exige autenticação (401 sem sessão).
- Sem publicação, instalação de VPN ou alteração de firewall/roteador. Acesso externo/Tailscale segue como pendência separada.
