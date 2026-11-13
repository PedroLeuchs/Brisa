# Consumo — histórico local de uso

O botão **Consumo**, disponível no painel e no modo controle, abre um dashboard em modal. Há seleção de período (até 366 dias por consulta), tempo observado ligado/desligado, lacunas, cobertura diária e estimativas opcionais de energia/custo.

## Gráficos por período — direção confirmada em 24/10/2026

O usuário rejeitou o gráfico anterior de faixas. **Não retomar essa abordagem como visual principal. Hoje/diário é gráfico de linha em degraus**: horários no eixo horizontal, Ligado e Desligado no vertical. A linha sobe/desce nas mudanças observadas. Lacunas offline, anteriores à coleta e após a última leitura interrompem a linha; o gráfico termina no momento consultado, sem projetar estado futuro.

O gráfico usa os intervalos e as observações existentes, sem migração ou reconstrução do banco. A API retorna `timeline` nas consultas de um único dia: `start`, `end`, `date`, `ends_at_now`, resolução, segmentos `on/off/unknown` e `transitions`. Uma transição só é produzida por duas leituras válidas com estados diferentes, no mesmo ciclo de coleta, separadas por até 90 segundos. É desenhada pontilhada na leitura que detecta a mudança; o detalhe informa a janela entre as amostras, não um instante exato inventado. Dados brutos são retidos por 90 dias; em períodos mais antigos pode não haver transições detalhadas, mesmo com intervalos preservados.

**Semana/mês e outros períodos de vários dias usam gráficos de barras.** A altura representa horas observadas ligado, não kWh. Até 62 dias, há uma barra por dia; acima disso, grupos de até sete dias. Dias sem leitura recebem `?`, sem fingir zero uso. Dias parcialmente cobertos mostram sua cobertura e lacunas no detalhe. A tabela/resumo e configurações continuam disponíveis.

Toque/clique, foco e teclado ou os seletores acessíveis apresentam horário/data, estado, duração e cobertura. O gráfico diário é de estado do aparelho, não curva de potência nem tempo de compressor. Amostragem de 60 segundos e limites de inferência ficam explícitos.

No mobile, Consumo é uma tela inteira com cabeçalho fixo, voltar ao controle, safe areas e rolagem própria, sem overflow horizontal. O dialog nativo mantém foco e cancelamento e devolve o foco ao elemento que abriu a tela. No desktop permanece em painel modal.

O acabamento segue a direção indicada pelo usuário: [Dark Dashboard UI, Sanmi Ibitoye](https://dribbble.com/shots/25912286-Dark-Dashboard-UI) como referência principal e [Energy SaaS Dashboard UI, Isaac Sanchez](https://dribbble.com/shots/26185060-Energy-SaaS-Dashboard-UI) para hierarquia e organização. Os tokens `--theme-*` do Brisa alimentam fundos, contraste, texto, linha e barras; cold/hot/off continuam consistentes. Nenhuma métrica ilustrativa foi adicionada ao produto.

## Fonte verificada

O relatório completo `reports/esquema-completo-20261023T233350073923Z.json`, de 23/10/2026, contém consultas bem-sucedidas a things_model, specifications_v11, standard_specifications e shadow_properties. Os 20 campos do things_model e os demais códigos normalizados foram conferidos com tipos, unidades e escalas. Não há campo comprovado de energia, potência, corrente ou tensão. `icon-dp_power3`/`icon-dp_power2` são nomes de ícones, não medidores. `switch` é liga/desliga; `temp_current` é temperatura Celsius no DP 3, escala 0. `gen` e `gen_10` são enums, sem unidade elétrica. Modelo comercial e potência de entrada continuam desconhecidos.

Portanto o Brisa não mostra kWh ou custo **medidos**. Nenhum consumo antigo foi importado ou reconstruído do relatório.

## Coleta e lacunas

O coletor faz somente leituras de estado no servidor, a cada 60 segundos, mesmo com navegador fechado. Usa o mesmo controlador serializado da integração LAN. Login e comandos continuam independentes da disponibilidade do banco de consumo. O coletor inicia após o servidor carregar esta versão; a primeira leitura acontece no primeiro intervalo.

Um intervalo é contabilizado apenas se duas leituras consecutivas concordarem em ligado/desligado, com distância de até 90 segundos. Isso é uma aproximação por amostragem: pode haver mudanças entre leituras. Transições divergentes, falhas, intervalos longos e tempo antes da primeira leitura ficam **sem observação**. Reiniciar o servidor cria um novo ciclo, sem ligar leituras de ciclos diferentes. Falha de disco quebra a continuidade; recuperação não preenche a lacuna. Regressões do relógio não geram sobreposição. Nenhum intervalo após a última leitura é extrapolado.

O tempo ligado é o estado do aparelho; não é medição do compressor, cujo funcionamento e potência podem variar. A cobertura é a proporção de intervalos observados sobre o período selecionado até o momento atual, inclusive lacunas anteriores ao início da coleta.

## Estimativas e referências

Potência elétrica de referência começa **em branco**, sem valor inventado. Pode ser informada em W pela etiqueta/documentação de entrada elétrica; BTU/h não é potência elétrica. Informar uma referência habilita uma estimativa simples: `W / 1000 × horas observadas ligado`.

A tarifa inicial é **R$ 1,056961/kWh**, referência informada da conta Copel, Toledo/PR, modalidade convencional, set/26: energia 0,417569 + uso do sistema 0,614088 + bandeira amarela 0,025304. Não é tarifa atual garantida nem preço por horário. Créditos solares são ignorados e tributos não são adicionados novamente. Tarifa e potência são configuráveis e persistentes; limpar a potência desabilita estimativas.

As referências atuais recalculam todo o período consultado; esta versão não mantém vigências de tarifa/potência históricas. Custo = energia estimada × tarifa. Não inclui carga variável, standby, lacunas, consumo solar ou total real da fatura. Período sem intervalos observados mantém energia/custo indisponíveis mesmo se houver potência configurada. Um período observado desligado pode mostrar zero na estimativa de uso ligado, sem afirmar consumo real zero.

## Persistência, volume e operação

`data/consumption.sqlite3` contém migração inicial atômica `PRAGMA user_version=1`, metadados de início, referências por aparelho, leituras e intervalos. Há índices por aparelho/data e por data para retenção. Leituras detalhadas são mantidas por 90 dias; intervalos por 730 dias. Intervalos contínuos concordantes são compactados em uma linha, separados por ciclo/estado. A limpeza é automática nas novas coletas; não remove referências ou a data original de início. O banco reutiliza páginas livres, sem VACUUM automático durante controle do aparelho.

Um processo servidor e um worker são suportados, como na agenda. Não inicie vários coletores usando o mesmo aparelho. Use cópia de segurança consistente do SQLite com servidor parado ou ferramenta de backup SQLite; não copie arquivo durante escrita. Os dados não são servidos como arquivos públicos nem armazenados no navegador.

Rotas autenticadas:

- `GET /api/consumption/{device_id}?start=YYYY-MM-DD&end=YYYY-MM-DD`: dashboard, cobertura, referências e diagnóstico do coletor.
- `POST /api/consumption/{device_id}/settings`: `reference_watts` (número positivo ou null) e `tariff_per_kwh` (número não negativo); exige mesma origem e proteção CSRF existente.

Datas inclusivas são interpretadas em America/Sao_Paulo. Intervalos são divididos à meia-noite local. Erros de armazenamento retornam mensagens sem detalhes internos; o coletor registra falhas e tenta novamente no ciclo seguinte.

## Validação e ativação

Testes usam relógios, arquivos temporários e dispositivos simulados, incluindo reinício, offline, transições, meia-noite, regressão/salto do relógio, recuperação de disco, retenção, configurações, autenticação e fluxo do modal. Nenhum comando físico ou agenda real é criado pelos testes.

É necessário reinício **coordenado** do servidor para carregar o coletor e as rotas desta versão. Não houve reinício por este chat durante o trabalho paralelo de acesso pelo celular. O build atualizado já está gerado; até reiniciar, o botão pode informar histórico indisponível porque o servidor antigo ainda não possui as rotas.

Atualização de ativação: reinício coordenado autorizado e concluído em 23/10/2026 às 20:44, exclusivamente em 127.0.0.1:8080 e um worker. Painel e API de consumo retornaram HTTP 200; agenda e coletor saudáveis, sem falhas. Primeira leitura real persistida às 20:45:17 (desligado), confirmada no SQLite v1. A coleta passa a construir histórico desse momento em diante; nenhuma rotina ativa ou comando físico foi criado.
