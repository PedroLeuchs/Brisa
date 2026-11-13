import json
import pytest
from coletar_esquema import collect, decode_model, property_definitions, scrub, ReadOnlyCloud, PATHS


def test_full_schema_keeps_unmapped_properties_units_scales_and_access():
    model={'model':json.dumps({'modelId':'functional-model-only','services':[{'code':'main','properties':[
        {'abilityId':1024,'code':'unknown_power','name':'Power','accessMode':'ro','typeSpec':{'type':'value','unit':'W','scale':1,'min':0,'max':50000}},
        {'abilityId':3,'code':'temp_current','accessMode':'ro','typeSpec':{'type':'value','unit':'C','scale':0}}
    ]}]})}
    decoded=decode_model(model)
    rows=property_definitions('things_model',decoded)
    assert len(rows)==2
    assert rows[0]['dp_id']==1024 and rows[0]['code']=='unknown_power'
    assert rows[0]['unit']=='W' and rows[0]['scale']==1 and rows[0]['access']=='ro'
    assert rows[1]['code']=='temp_current'


def test_standard_specification_does_not_invent_ids_or_read_access():
    rows=property_definitions('standard',{'functions':[{'code':'custom','type':'Integer','values':'{"unit":"V","scale":1}'}]})
    assert rows[0]['dp_id'] is None and rows[0]['access'] is None
    assert rows[0]['access_inferred']=='w'
    assert rows[0]['unit']=='V'


def test_collection_queries_all_sources_even_when_first_has_data_and_strips_secrets():
    class Cloud:
        paths=[]
        def get(self,path):
            self.paths.append(path)
            if path==PATHS['device_details']:
                return {'success':True,'result':{'name':'Air Conditioner','model':'MODEL-TEST','local_key':'SECRET','uid':'PRIVATE'}}
            if path==PATHS['things_model']:
                return {'success':True,'result':{'model':'{"services": [{"properties": [{"code":"energy","abilityId":99,"accessMode":"ro","typeSpec":{"unit":"kWh","scale":2}}]}]}','access_token':'SECRET'}}
            return {'success':False,'code':1106,'msg':'SECRET'}
    class Local:
        def status(self):return {'timestamp':123,'dps':{'1':False},'available':[],'state':{}}
        def command(self,*args):pytest.fail('Read-only collection wrote to device')
    cloud=Cloud();report=collect(cloud,Local());encoded=json.dumps(report)
    assert len(cloud.paths)==5
    assert report['metadata']=={'name':'Air Conditioner','model':'MODEL-TEST'}
    assert report['properties'][0]['code']=='energy'
    assert 'SECRET' not in encoded and 'PRIVATE' not in encoded
    assert report['lan']['dps']=={'1':False}


def test_sensitive_property_values_are_not_saved():
    result=scrub({'properties':[{'code':'password','value':'SECRET','typeSpec':{'typeDefaultValue':'SECRET'}}]})
    assert 'SECRET' not in json.dumps(result)


def test_cloud_only_accepts_fixed_read_paths_and_does_not_send_secret_header(monkeypatch):
    cloud=ReadOnlyCloud('test-id','test-secret')
    with pytest.raises(ValueError):cloud.get('/v1.0/something-else')
    captured=[]
    class Reply:
        status_code=200
        def json(self):return {'success':True,'result':{'access_token':'test-token'}}
    def get(url,**kwargs):captured.append((url,kwargs));return Reply()
    monkeypatch.setattr(cloud.session,'get',get)
    cloud.authenticate()
    assert cloud.token=='test-token'
    assert 'secret' not in captured[0][1]['headers']
    assert captured[0][1]['timeout']==(5,15)
    assert captured[0][1]['allow_redirects'] is False
    cloud.close()
    assert cloud.secret==cloud.token==''
