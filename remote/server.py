"""Entrada para ensaio isolado: sempre 127.0.0.1:8090, nunca o painel atual."""
if __name__=='__main__':
    import uvicorn
    uvicorn.run('remote.broker:create_app',factory=True,host='127.0.0.1',port=8090,
                workers=1,access_log=False,proxy_headers=False)
