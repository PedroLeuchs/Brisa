# Backend doméstico / base do agente local

`app.py` continua sendo o ponto de entrada (`uvicorn app:app`). A API passa por `DeviceService`, que conhece adaptadores pelo identificador lógico do aparelho, sem aceitar IPs ou credenciais enviados pelo navegador.

`adapters/tuya_local.py` encapsula o controlador TinyTuya existente. O contrato `DeviceAdapter` exige `capabilities`, `status` e `command`, permitindo no futuro outro transporte. O componente público/agente remoto ainda não foi implementado ou publicado.

Rotas autenticadas consumidas por React:

- `GET /api/session`: sessão do usuário, independente da disponibilidade do ar.
- `GET /api/devices`: aparelhos e capacidades configuradas.
- `GET /api/devices/{id}/status`: estado, funções disponíveis e horário da leitura; sem DPS ou Local Key.
- `POST /api/devices/{id}/command`: `{code, value}`; só destinos registrados, funções mapeadas e valores válidos.

Rotas antigas permanecem por compatibilidade. Um único worker doméstico deve acessar o aparelho; o lock atual não atravessa processos. Autorização multiusuário, pareamento de agentes, expiração/deduplicação de comandos e transporte remoto são trabalho posterior. Não expor esta API diretamente à internet.
