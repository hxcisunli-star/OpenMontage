import concurrent.futures,json,sys,time
from pathlib import Path
sys.path.insert(0,'/home/MyProject/OpenMontage/tools/video')
from remote_cpu_render import RemoteRenderClient
client=RemoteRenderClient(identity='/root/.ssh/openmontage_render_local',known_hosts='/root/.ssh/openmontage_render_known_hosts')
if len(sys.argv) != 3: raise SystemExit('Usage: poll_every_3s.py JOB_ID OUTPUT.jsonl')
job=sys.argv[1]
path=Path(sys.argv[2])
start=time.monotonic()
def sample(seq):
 tick=time.monotonic()
 row={'seq':seq,'scheduled':seq*3,'request_started':tick-start,'errors':[]}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pair:
  futures=[pair.submit(client.request,c,timeout=20,attempts=1) for c in (f'status {job}',f'logs {job} 0')]
  results=[]
  for future in futures:
   try: results.append(future.result())
   except Exception as e:row['errors'].append(str(e));results.append({})
 row['seconds']=time.monotonic()-tick
 row['state']=results[0].get('state');row['active_jobs']=results[0].get('active_jobs')
 row['log_bytes']=len(results[1].get('log',''))
 return row
with path.open('x') as f,concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 pending=[]
 terminal=False
 for i in range(200):
  time.sleep(max(0,start+i*3-time.monotonic()))
  pending.append(pool.submit(sample,i))
  finished=[p for p in pending if p.done()]
  for p in finished:
   row=p.result();f.write(json.dumps(row)+'\n');f.flush();pending.remove(p)
   if row['seq']%20==0:print(json.dumps(row),flush=True)
   if row['state'] in ('completed','failed','canceled'):terminal=True
  if terminal:break
 for p in pending:
  row=p.result();f.write(json.dumps(row)+'\n');f.flush()
print('saved',path,flush=True)
