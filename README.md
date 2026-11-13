# Brisa — controlador do ar-condicionado

A opção atual para publicação gratuita é **Vercel + PC doméstico + Tailscale
Funnel**. Consulte [o procedimento completo](docs/VERCEL.md). A interface fica na
Vercel; controle LAN, agenda, sessões e histórico permanecem no PC, que precisa
ficar ligado. O iniciador automático usa TinyTuya local, sem Tuya Cloud.

O transporte Tuya Cloud também está disponível como alternativa opcional;
consulte [implantação cloud](docs/CLOUD.md).

Projeto em `C:\projects\ar`. Backend Python/TinyTuya e painel React/TypeScript responsivo, com manifest e service worker para uso como PWA. No transporte local, nenhum comando usa a API cloud. O computador precisa permanecer ligado na rede do aparelho.

A prévia nova é servida em http://127.0.0.1:8080/ depois de `pnpm build` em frontend/. Consulte [instruções do frontend](frontend/README.md) e [contrato do backend](backend/README.md). O build já foi gerado neste computador. Em novas instalações, construa-o antes de iniciar; sem build, o painel anterior permanece disponível como fallback.

## Aparelho descoberto em 23/10/2026

- Device ID: `CONFIGURE_TUYA_DEVICE_ID`
- MAC do aparelho: omitido nesta cópia pública.
- IP anunciado pelo dispositivo: `192.168.1.3`
- Protocolo anunciado: `3.4`
- Computador: `192.168.1.5`, roteador: `192.168.1.1`

A descoberta confirmou o Device ID e a versão, e a leitura autenticada pela LAN já foi validada com a Local Key configurada localmente. Oito funções estão mapeadas. A confirmação física de cada comando, o acesso pelo celular e o teste sem WAN ainda precisam ser registrados. Reserve esses IPs no DHCP do roteador para evitar mudanças.

Consulte [situação e evidências](docs/STATUS.md) e [direção de arquitetura e expansão](docs/ARQUITETURA.md). O documento de requisitos recebido é a referência de prioridades; pontos históricos como IP e obtenção da chave já foram resolvidos neste computador.

## Configurar no computador

As dependências já estão instaladas em `.venv`. No PowerShell:

```powershell
cd C:\projects\ar
powershell -ExecutionPolicy Bypass -File .\configurar.ps1
```

Confirme IP e protocolo sugeridos. Digite a Local Key e crie uma senha do controlador com pelo menos 12 caracteres. Ambas as entradas ficam ocultas no terminal. A Local Key é salva somente em `.env`; a senha é salva como hash scrypt. Não envie a chave no chat, nem em capturas de tela. O script restringe o arquivo ao usuário atual e SYSTEM no Windows.

A Local Key não é descoberta pelo anúncio LAN. Se ainda não a possui, obtenha-a na consulta de detalhes do dispositivo no projeto Tuya já vinculado e copie-a diretamente para a configuração local. Esse provisionamento pode precisar da cloud uma vez; o serviço de controle não usa credenciais da cloud. Reparear o aparelho pode alterar a chave.

## Abrir o painel

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
```

Abra http://127.0.0.1:8080 e entre com a senha criada. A primeira leitura autenticada mostra os DPS em “Configuração das funções”. O aplicativo não envia comandos automaticamente.

## Consumo

O botão **Consumo** abre o dashboard de uso observado: período, tempo ligado/desligado, lacunas e cobertura. O histórico fica no servidor em SQLite e é coletado a cada minuto, mesmo com a interface fechada. Não há medição elétrica comprovada no esquema atual: kWh/custo ficam indisponíveis até informar potência elétrica de referência, quando passam a ser **estimativas**. A tarifa inicial configurável é R$ 1,056961/kWh da conta Copel de set/26, sem créditos solares. Veja [método, fontes, retenção e limitações](docs/CONSUMO.md). A primeira ativação desta funcionalidade exige reinício coordenado do servidor.

## Manter o acesso neste dispositivo

O login oferece **Lembrar deste dispositivo por 30 dias**, marcado inicialmente. Desmarque em computadores compartilhados para usar validade de 12 horas. O acesso sobrevive a recargas e reinícios normais do servidor, até vencer ou você clicar em **Sair**. Alterar a senha do controlador invalida as sessões anteriores. As sessões ficam em `data/sessions.sqlite3`, contendo hashes dos tokens, sem guardar a senha ou o cookie original. Abra sempre pelo mesmo endereço: `localhost` e `127.0.0.1` possuem cookies separados. Falhas de conexão não encerram uma sessão válida.

## Automações por horário

Depois de entrar no Brisa, abra **Automações** no cabeçalho. O modal permite escolher uma ação disponível no aparelho, valor, horário e dias da semana, além de editar, pausar, reativar e excluir rotinas.

As rotinas ficam no computador em `data/automations.json` e usam o fuso `America/Sao_Paulo`. Elas continuam funcionando com a interface fechada, mas dependem do servidor Brisa ligado. Se o aparelho estiver offline, a ocorrência é marcada como falha e não é reenviada automaticamente. Ao reiniciar, o Brisa começa a observar os próximos horários e não executa ocorrências passadas.

A agenda suporta **um processo servidor com um worker**, como no `iniciar.ps1`; não execute múltiplos workers nem dois servidores usando o mesmo arquivo. Dentro desse processo, criar/editar/pausar/excluir e disparar ocorrências usam a mesma transação protegida. Uma alteração já confirmada impede disparos posteriores; uma ocorrência que já começou termina antes da confirmação da alteração. A marcação é gravada antes de enviar: em caso de queda entre a reserva e a conclusão, ela aparece sem confirmação e não é repetida. Essa política privilegia não duplicar comandos e pode perder uma ocorrência em uma queda.

Falhas de armazenamento são registradas, mantêm a thread viva e são verificadas novamente a cada 15 segundos. Após recuperação, horários do intervalo indisponível são descartados. O modal informa falhas detectadas ao ser carregado; o diagnóstico completo autenticado está em `GET /api/automations/health` (estado, thread ativa, última verificação, última falha e contador). Não edite o JSON externamente enquanto o servidor estiver em execução.

## Mapear funções antes de comandar

Edite `mapping.json`, substituindo `null` pelo número inteiro de cada DP confirmado no esquema do seu aparelho. Não deduza IDs pela posição ou por exemplos de outro fabricante. Os nomes cloud não revelam os IDs locais. Consulte o esquema com IDs numéricos no projeto Tuya e compare com a leitura DPS local. O backend recarrega esse arquivo a cada consulta.

Os tipos previstos são: `switch`, `mode_eco`, `cleaning`, `sleep`, `switch_vertical` e `switch_horizontal` booleanos; `temp_set` inteiro de 16 a 31, em graus Celsius; `mode` enum auto/cold/hot/wet/wind; `fan_speed_enum` enum auto/high/middle/low. Confirme os tipos, a escala da temperatura e os valores do aparelho antes de preencher os IDs. Se algum tipo divergir, ajuste a integração antes de liberar essa função. Não há mapeamento pré-assumido.

Após mapear, faça primeiro uma leitura e confirme visualmente os valores. Depois teste uma função por vez. A UI só habilita funções mapeadas e presentes na leitura. Um comando enviado exige nova leitura para confirmar o estado; o painel não simula sucesso.

## Acesso pelo celular

O caminho preparado para a rede doméstica usa HTTPS direto no Brisa, autenticação existente e uma regra de firewall limitada ao IP/porta do serviço e à sub-rede local. Ele não abre portas no roteador e **não oferece acesso por 4G/5G ou fora de casa**.

O certificado atual foi preparado para `192.168.1.5`. Se o IP do computador mudar, reserve esse endereço no roteador ou gere novamente para o novo IP. Primeiro, instale **somente** `data/mobile-tls/brisa-ca.crt` como autoridade confiável no celular. Nunca copie `brisa-server.key`. No iPhone/iPad, instale o perfil e habilite a confiança total em Ajustes > Geral > Sobre > Ajustes de Confiança de Certificado. No Android, instale-o como certificado de CA nas configurações de segurança; os nomes dos menus variam por fabricante. Remova essa autoridade do celular se deixar de usar o Brisa.

Depois, em um PowerShell aberto como administrador, crie a regra restrita:

```powershell
powershell -ExecutionPolicy Bypass -File .\configurar-firewall-celular.ps1
```

Encerre o servidor local antigo antes da troca, para não criar um segundo executor de automações. Em seguida execute `celular.cmd` ou:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar-celular.ps1
```

No celular, conectado ao mesmo Wi-Fi, abra `https://192.168.1.5:8443`, entre e use a opção do navegador para instalar/adicionar o Brisa à tela inicial. Só considere a etapa concluída depois de confirmar que o navegador não mostra alerta de certificado, o login funciona, uma recarga mantém a sessão e a PWA pode ser instalada. Não encaminhe 8443 no roteador.

Para desfazer a exposição na rede, execute `configurar-firewall-celular.ps1 -Remove` como administrador e volte a iniciar normalmente por `iniciar.ps1`. O certificado e a chave locais ficam em `data/mobile-tls/`, que é ignorado pelo Git.

O service worker guarda apenas a interface. Ele nunca guarda respostas da API nem enfileira comandos offline. Sem rede ou sem o computador, o ar não pode ser controlado pelo painel.

## Diagnóstico e testes

```powershell
.\.venv\Scripts\python.exe discover.py
.\.venv\Scripts\python.exe validar.py
.\.venv\Scripts\python.exe -m pytest -q
node --test test_frontend.cjs
```

A descoberta grava somente IP, protocolo e ID do aparelho alvo em `discovery.json`. Para executá-la novamente, permita comunicação LAN ao Python se o Windows solicitar. Ela não requer a Local Key e não envia comandos de operação.

Se não houver leitura: confira IP, Local Key, protocolo, rede de convidados/isolamento Wi-Fi e acesso TCP 6668. Feche outras integrações locais que disputem a conexão. Não reemparelhe o aparelho como primeiro teste.

Testes usam dispositivos simulados e verificam autenticação, origem/CSRF, validação de comandos, bloqueio sem mapeamento, limite de tentativas e não exposição de segredos. Para reinstalar: crie `.venv` com Python 3.12+ e instale `requirements.txt`; para testes instale também `pytest` e `httpx`.

Fonte da integração: https://github.com/jasonacox/tinytuya
