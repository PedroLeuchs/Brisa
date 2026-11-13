"""Provisionamento administrativo local; nenhum endpoint público de cadastro."""
import argparse
from pathlib import Path
import re

from remote.protocol import RULES
from remote.storage import RelayStore


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',default='remote/runtime')
    parser.add_argument('--home',default='home')
    parser.add_argument('--agent',default='bridge-1')
    parser.add_argument('--device',default='home-ac')
    parser.add_argument('--controls',default='switch,temp_set,mode,fan_speed_enum,sleep,cleaning,switch_vertical,switch_horizontal')
    args=parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value) for value in [args.home,args.agent,args.device]):
        raise SystemExit('Identificadores devem conter somente letras, números, hífen ou sublinhado.')
    controls=args.controls.split(',')
    if not controls or not set(controls).issubset(RULES):
        raise SystemExit('Lista de controles inválida.')
    directory=Path(args.directory).resolve()
    agent_file,operator_file=directory/'agent.env',directory/'operator.env'
    if agent_file.exists() or operator_file.exists():
        raise SystemExit('Configuração já existe; nada foi sobrescrito.')
    directory.mkdir(parents=True,exist_ok=True)
    store=RelayStore(directory/'relay.sqlite3')
    agent=store.provision_agent(args.home,args.agent,{args.device:controls})
    operator=store.provision_operator(args.home,'owner',[args.device])
    # Arquivos separados: só agent.env pertence ao equipamento doméstico.
    for path,text in [
        (agent_file,f'BRISA_AGENT_TOKEN={agent}\nBRISA_HOME_ID={args.home}\nBRISA_AGENT_ID={args.agent}\n'),
        (operator_file,f'BRISA_OPERATOR_TOKEN={operator}\n')]:
        with path.open('x',encoding='utf-8') as file:
            file.write(text)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    print('Credenciais criadas em arquivos locais separados. Nenhum token foi exibido.')
    print('Este provisionamento não habilita comandos no ar nem publica um serviço.')


if __name__=='__main__':
    main()
