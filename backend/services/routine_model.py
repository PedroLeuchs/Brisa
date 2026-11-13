"""Rotinas v2: identidade estável e histórico por entrada, sem apagar legado."""
import copy
import json
import re
import uuid

TIME_RE=re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d$')
ID_RE=re.compile(r'^[A-Za-z0-9_-]{1,80}$')
MAX_ENTRIES=16


def aliases(item):
    first=item['entries'][0]
    return {**item,'schema_version':2,'code':first['code'],'value':first['value'],'time':first['time']}


def signature(item):
    return (item['device_id'],tuple((e['time'],e['code'],json.dumps(e['value'],sort_keys=True)) for e in item['entries']),tuple(item['days']))


def upgrade_stored(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('id'),str) or type(raw.get('enabled')) is not bool:
        raise ValueError('invalid_stored_routine')
    item=copy.deepcopy(raw)
    if 'entries' not in item:
        entry={'id':uuid.uuid5(uuid.NAMESPACE_URL,'brisa:'+item['id']+':legacy-entry').hex,
               'code':item['code'],'value':item['value'],'time':item['time'],
               'last_run':item.get('last_run'),'last_result':copy.deepcopy(item.get('last_result')),'history':[]}
        if entry['last_run']:
            entry['history'].append({'occurrence':entry['last_run'],'code':entry['code'],'value':entry['value'],
                                     'time':entry['time'],'result':copy.deepcopy(entry['last_result'])})
        item['entries']=[entry]
    if not isinstance(item['entries'],list) or not item['entries']:
        raise ValueError('invalid_stored_entries')
    ids=[]
    for entry in item['entries']:
        if not isinstance(entry,dict) or not ID_RE.fullmatch(str(entry.get('id',''))) or not TIME_RE.fullmatch(str(entry.get('time',''))):
            raise ValueError('invalid_stored_entry')
        ids.append(entry['id'])
        entry.setdefault('last_run',None);entry.setdefault('last_result',None);entry.setdefault('history',[])
        if not isinstance(entry['history'],list):raise ValueError('invalid_stored_history')
    if len(set(ids))!=len(ids):raise ValueError('duplicate_stored_ids')
    item.setdefault('retired_entries',[])
    item.setdefault('name','Rotina de climatização')
    return aliases(item)


def preserve_entries(entries,current=None):
    current=current or {}
    old=current.get('entries',[]);retired=current.get('retired_entries',[])
    previous={entry['id']:entry for entry in [*retired,*old]}
    used=set();output=[]
    for entry in entries:
        identity=entry.get('id')
        if not identity and len(entries)==1 and old:identity=old[0]['id']
        identity=identity or uuid.uuid4().hex
        prior=previous.get(identity,{})
        output.append({**entry,'id':identity,'last_run':prior.get('last_run'),
                       'last_result':copy.deepcopy(prior.get('last_result')),
                       'history':copy.deepcopy(prior.get('history',[]))})
        used.add(identity)
    archived={entry['id']:copy.deepcopy(entry) for entry in [*retired,*old] if entry['id'] not in used}
    return output,list(archived.values())
