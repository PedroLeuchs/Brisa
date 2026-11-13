# Painel React / TypeScript

## Construir

```powershell
cd C:\projects\ar\frontend
pnpm install --frozen-lockfile
pnpm test
pnpm build
```

O backend serve `dist/index.html` em `/` e os recursos em `/ui`. O build gera ícones PNG, manifest e service worker com cache exclusivo da interface. A API, sessões e comandos nunca são armazenados offline.

O painel usa cookies HttpOnly existentes. Senhas são apagadas do campo ao enviar, não vão para localStorage/sessionStorage. O estado exibido vem de uma leitura do dispositivo, inclusive após um envio sem confirmação. Cliques não simulam sucesso nem enfileiram comandos para reconexão.

O controlador de interface e a API HTTP são módulos separados. São testados com rede simulada, sem enviar comandos ao ar.

## Ajuste de temperatura

O seletor usa o intervalo real de 16 a 31 °C, com passo de 1 °C. Durante o gesto mostra o valor escolhido e só envia ao soltar; uma seleção cancelada não envia comandos. O teclado confirma ao soltar a tecla, e os botões +/− continuam disponíveis. O valor solicitado permanece identificado até terminar a consulta de confirmação. Leituras periódicas não interrompem o gesto.

No celular a composição assume formato de controle remoto. No desktop, o botão “Modo controle” abre a mesma árvore de componentes e estilos; “Voltar ao painel” restaura a disposição ampla. Não há um painel mobile duplicado com lógica divergente.

A revisão usa anel circular interativo e barra Modo/Velocidade/Funções/Timer com painéis secundários; Timer reutiliza automações. Ambiente permanece indisponível até validar ID, unidade e escala do sensor pelo esquema completo. Não é meteorologia nem a temperatura configurada.

## Desenvolvimento

Com a API em `http://127.0.0.1:8080`, execute `pnpm dev` para usar o servidor de desenvolvimento apenas no computador. O proxy mantém a origem do navegador, portanto as verificações CSRF continuam habilitadas.

## PWA e celular

O acesso em localhost permite testar o service worker neste computador. O botão de instalar aparece quando o navegador disponibiliza a instalação. Instalação no celular depende de uma origem HTTPS confiável e acesso de rede configurado; não foi habilitada publicação ou abertura de firewall por esta migração.

O painel antigo em `static/` é mantido como fallback se o build não existir e para compatibilidade durante a migração. O CSS compartilhado é incorporado pelo Vite no build novo. Não é necessário executar o JavaScript antigo para usar React.
