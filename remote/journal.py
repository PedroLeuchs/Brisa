"""Reserva antes do envio e caixa de saída durável do agente doméstico."""
import json

from remote.protocol import canonical, fingerprint
from remote.storage import Database


class Journal(Database):
    def __init__(self,path):
        super().__init__(path)
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS journal(id TEXT PRIMARY KEY,fingerprint TEXT,state TEXT,result TEXT,acked INTEGER NOT NULL DEFAULT 0)')

    def reserve(self,envelope):
        key=envelope['command_id']
        signature=fingerprint(envelope)
        with self.transaction() as db:
            row=db.execute('SELECT * FROM journal WHERE id=?',(key,)).fetchone()
            if row:
                if row['fingerprint']!=signature:
                    raise ValueError('command_identity_conflict')
                if row['state']=='started':
                    result={'status':'uncertain','reason':'restart_uncertain','observation':None}
                    db.execute("UPDATE journal SET state='done',result=? WHERE id=?",(canonical(result),key))
                    return False,result
                return False,json.loads(row['result'])
            db.execute("INSERT INTO journal(id,fingerprint,state) VALUES(?,?,'started')",(key,signature))
        return True,None

    def finish(self,key,result):
        with self.transaction() as db:
            db.execute("UPDATE journal SET state='done',result=? WHERE id=? AND state='started'",(canonical(result),key))

    def recover(self):
        # Não é possível provar se uma escrita aconteceu entre reserva e queda.
        result=canonical({'status':'uncertain','reason':'restart_uncertain','observation':None})
        with self.transaction() as db:
            db.execute("UPDATE journal SET state='done',result=? WHERE state='started'",(result,))

    def outbox(self):
        with self.transaction() as db:
            rows=db.execute("SELECT id,result FROM journal WHERE state='done' AND acked=0 ORDER BY rowid").fetchall()
        return [(row['id'],json.loads(row['result'])) for row in rows]

    def acknowledged(self,key):
        with self.transaction() as db:
            db.execute('UPDATE journal SET acked=1 WHERE id=?',(key,))
