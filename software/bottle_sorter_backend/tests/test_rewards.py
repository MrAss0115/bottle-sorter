"""真实 HTTP、SQLite 并发/事务失败测试；所有测试产物留在 E 盘。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reward_store import query_rewards, save_reward
from storage import initialize_database

CONTRACT = ROOT / 'tests/vendor/contract_test.py'
spec = importlib.util.spec_from_file_location('reward_contract', CONTRACT)
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class RewardsIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='rfid_test_', dir=ROOT/'outputs')
        cls.folder = Path(cls.temp.name)
        cls.database = cls.folder/'test.sqlite3'
        cls.device = 'contract-test-' + secrets.token_hex(4)
        cls.key, cls.viewer = secrets.token_hex(16), secrets.token_hex(32)
        credentials = cls.folder/'credentials.json'
        credentials.write_text(json.dumps(dict(devices={cls.device:cls.key,
            cls.device.upper():cls.key}, viewer_token=cls.viewer)), encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); cls.port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.log = (cls.folder/'server.log').open('w',encoding='utf-8')
        cls.process = subprocess.Popen([sys.executable,'-B','-m','uvicorn','app:app',
            '--host','127.0.0.1','--port',str(cls.port)], cwd=ROOT,
            env=dict(os.environ, BOTTLE_SORTER_DATABASE=str(cls.database),
                BOTTLE_SORTER_REWARD_CREDENTIALS=str(credentials),
                PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',TEMP=str(cls.folder),TMP=str(cls.folder)),
            stdout=cls.log,stderr=subprocess.STDOUT)
        cls.addClassCleanup(cls.cleanup)
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                if cls.request('GET','/api/health')[0]==200: return
            except OSError: pass
            if cls.process.poll() is not None: raise RuntimeError('Server exited')
            time.sleep(.1)
        raise RuntimeError('Server did not start')

    @classmethod
    def cleanup(cls):
        cls.process.terminate()
        try: cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill(); cls.process.wait(timeout=5)
        cls.log.close(); cls.temp.cleanup()

    @classmethod
    def request(cls, method, path, payload=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        req = urllib.request.Request(cls.base+path, data=data, method=method,
            headers={'Content-Type':'application/json', **(headers or {})})
        try: response = urllib.request.urlopen(req,timeout=12)
        except urllib.error.HTTPError as error: response=error
        with response: return response.status,response.read(),dict(response.headers)

    def event(self, batch, **kwargs):
        return dict(device=self.device,batch=batch,uid='00000001',earned=20,total=120,
            bottles=1,cans=1,rejected=0,**kwargs)

    def post(self,payload,**kwargs):
        return self.request('POST','/api/rewards',payload,{'X-API-Key':self.key},**kwargs)

    def test_01_supplied_contract_and_database(self):
        reports=[]
        errors=contract.run_contract(self.base+'/api/rewards',self.key,self.device,report=reports.append)
        self.assertEqual(errors,[],reports)
        data=query_rewards(self.database,device=self.device)
        self.assertEqual(sorted(r['batch'] for r in data['items']),[1,2,4,5])
        balance=query_rewards(self.database,device=self.device,uid='DEADBEEF',balances=True)['items'][0]
        self.assertEqual((balance['total'],balance['last_batch']),(130,5))
        for line in reports: print(line)

    def test_02_auth_and_strict_validation(self):
        sample=self.event(20)
        self.assertEqual(self.request('POST','/api/rewards',raw=b'{')[0],401)
        self.assertEqual(self.post(dict(sample,device='not-authorized'))[0],401)
        cases=[dict(earned=20.0),dict(batch=True),dict(batch=0),dict(batch=4294967296),
            dict(total=19),dict(earned=21),dict(bottles=0,cans=0,rejected=0),
            dict(bottles=0,cans=0,rejected=1),dict(uid='deadbeef'),dict(uid='DEADBEEF\n'),
            dict(device=self.device+'\n'),dict(earned=0),dict(bottles='1')]
        for change in cases:
            with self.subTest(change=change):self.assertEqual(self.post(dict(sample,**change))[0],400)
        self.assertEqual(self.post(None,raw=b'{"device":"a","device":"b"}')[0],400)
        self.assertEqual(self.post(None,raw=b' '*2049)[0],400)
        self.assertEqual(self.request('GET','/api/rewards')[0],401)
        self.assertEqual(self.request('GET','/api/rewards',headers={'Authorization':'Bearer '+self.key})[0],401)
        response=self.request('GET','/api/rewards?limit=1',headers={'Authorization':'Bearer '+self.viewer})
        self.assertEqual(response[0],200)
        self.assertEqual(len(json.loads(response[1])['items']),1)
        schema=json.loads(self.request('GET','/openapi.json')[1])
        operation=schema['paths']['/api/rewards']['post']
        self.assertEqual(operation['security'],[{'RewardDeviceKey':[]}])
        self.assertEqual(set(operation['requestBody']['content']['application/json']['example']),set(sample))

    def test_03_concurrent_retries_conflicts_and_out_of_order(self):
        sample=self.event(100)
        with ThreadPoolExecutor(max_workers=12) as pool:
            replies=list(pool.map(lambda _:self.post(sample),range(24)))
        self.assertTrue(all(r[0]==200 and r[1]==b'ACK 100\n' for r in replies))
        initial=query_rewards(self.database,device=self.device,uid='00000001')['items'][0]
        self.assertEqual(query_rewards(self.database,device=self.device,uid='00000001')['total'],1)
        with ThreadPoolExecutor(max_workers=8) as pool:
            replies=list(pool.map(lambda _:self.post(dict(sample,total=140)),range(8)))
        self.assertTrue(all(r[0]==409 for r in replies))
        self.assertEqual(query_rewards(self.database,device=self.device,uid='00000001')['items'][0],initial)
        with ThreadPoolExecutor(max_workers=8) as pool:
            replies=list(pool.map(lambda batch:self.post(dict(sample,batch=batch,total=batch*10)),[108,101,105,102,107,104,106,103]))
        self.assertTrue(all(r[0]==200 for r in replies))
        balance=query_rewards(self.database,device=self.device,uid='00000001',balances=True)['items'][0]
        self.assertEqual((balance['last_batch'],balance['total']),(108,1080))
        self.assertEqual(self.post(dict(sample,device=self.device.upper()))[0],200)
        self.assertEqual(query_rewards(self.database,device=self.device.upper())['total'],1)

    def test_04_real_transaction_abort_and_retry(self):
        sample=self.event(200)
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute('''CREATE TRIGGER fail_reward_write AFTER INSERT ON reward_events
                WHEN NEW.batch=200 BEGIN SELECT RAISE(ABORT,'test storage failure'); END''')
        reply=self.post(sample)
        self.assertEqual(reply[0],503)
        self.assertNotIn(b'ACK',reply[1])
        with closing(sqlite3.connect(self.database)) as conn, conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM reward_events WHERE batch=200').fetchone()[0],0)
            conn.execute('DROP TRIGGER fail_reward_write')
        self.assertEqual(self.post(sample)[:2],(200,b'ACK 200\n'))
        self.assertEqual(self.post(sample)[:2],(200,b'ACK 200\n'))
        with closing(sqlite3.connect(self.database)) as conn, conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM reward_events WHERE batch=200').fetchone()[0],1)

    def test_05_uint32_custom_rate_and_pagination(self):
        sample=dict(self.event(4294967295),earned=4294967295,total=4294967295,bottles=1,cans=0,uid='00000000000001')
        status,body,headers=self.post(sample)
        self.assertEqual((status,body),(200,b'ACK 4294967295\n'))
        self.assertEqual(headers['content-length'],'15')
        self.assertNotIn('transfer-encoding',headers)
        self.assertEqual(query_rewards(self.database,uid=sample['uid'])['items'][0]['uid'],sample['uid'])
        auth={'Authorization':'Bearer '+self.viewer}
        page=json.loads(self.request('GET',f'/api/reward-balances?uid={sample["uid"]}&limit=1&offset=1',headers=auth)[1])
        self.assertEqual(page['items'],[])
        self.assertEqual(page['total'],1)


class RealCommitFailureTest(unittest.TestCase):
    def test_deferred_constraint_fails_at_commit_and_rolls_back(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'outputs') as folder:
            database=Path(folder)/'commit.sqlite3'
            initialize_database(database)
            with closing(sqlite3.connect(database)) as conn, conn:
                conn.executescript('''CREATE TABLE parent(id INTEGER PRIMARY KEY);
                    CREATE TABLE child(id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED);
                    CREATE TRIGGER fail_commit AFTER INSERT ON reward_events
                    BEGIN INSERT INTO child VALUES(99); END;''')
            original=sqlite3.connect
            trace=[]
            def open_with_fk(*args,**kwargs):
                conn=original(*args,**kwargs)
                conn.execute('PRAGMA foreign_keys=ON')
                conn.set_trace_callback(trace.append)
                return conn
            payload=dict(device='commit-test',batch=1,uid='00000001',earned=10,total=100,bottles=1,cans=0,rejected=0)
            with patch('reward_store.sqlite3.connect',side_effect=open_with_fk):
                with self.assertRaises(sqlite3.IntegrityError):save_reward(database,payload)
            self.assertIn('COMMIT',trace)
            self.assertIn('ROLLBACK',trace)
            self.assertEqual(query_rewards(database)['total'],0)
            with closing(original(database)) as conn, conn:conn.execute('DROP TRIGGER fail_commit')
            save_reward(database,payload)
            save_reward(database,payload)
            self.assertEqual(query_rewards(database)['total'],1)


if __name__=='__main__':unittest.main(verbosity=2)

