from pathlib import Path
import subprocess,json,time,re,os,traceback,signal
HOME=Path('/workspace/rvc-restart');ROOT=HOME/'source';EXP=ROOT/'logs/DogalKadinTR-v3';PYTHON='/workspace/voicebridge-rvc-env/bin/python';NAME='DogalKadinTR-v3';active=None

def update(**kw):
 p=HOME/'status.json';s=json.loads(p.read_text());s.update(kw);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(s,indent=2));tmp.replace(p)

def command(args,logname):
 with (HOME/logname).open('ab') as log:subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)

try:
 update(supervisor_pid=os.getpid(),target_epochs=50,status='waiting_pitch')
 # Preparation is currently running in the foreground tool session. Verify outputs, not a PID.
 while True:
  missing=[]
  for wav in (EXP/'0_gt_wavs').glob('*.wav'):
   if wav.name=='0_226.wav':continue
   if not (EXP/'2a_f0'/f'{wav.stem}.wav.npy').is_file() or not (EXP/'2b-f0nsf'/f'{wav.stem}.wav.npy').is_file():missing.append(wav.name)
  if not missing:break
  update(pitch_clips_remaining=len(missing))
  time.sleep(5)
 command([PYTHON,str(HOME/'prepare.py')],'prepare-final.log')
 import sys;sys.path.insert(0,str(ROOT))
 from train.data_utils import TextAudioLoaderMultiNSFsid,DistributedBucketSampler
 from train.utils import HParams
 c=json.loads((EXP/'config.json').read_text());dataset=TextAudioLoaderMultiNSFsid(str(EXP/'filelist.txt'),HParams(**c['data']));sampler=DistributedBucketSampler(dataset,2,[100,200,300,400,500,600,700,800,900],num_replicas=1,rank=0,shuffle=True);per=len(sampler);assert per>0
 update(steps_per_epoch=per,target_steps=per*50,status='prepared')
 command([PYTHON,str(HOME/'publish.py'),'--progress','0','--steps','0'],'publish.log')
 env=os.environ.copy();env.update(RVC_CPU_PRECISION='fp32',RVC_PUBLISH_EPOCHS='1')
 args=[PYTHON,str(HOME/'cpu_train.py'),'-e',NAME,'-sr','32k','-f0','1','-bs','2','-g','0','-te','50','-se','10','-pg','assets/pretrained_v2/f0G32k.pth','-pd','assets/pretrained_v2/f0D32k.pth','-l','1','-c','1','-sw','1','-v','v2']
 with (HOME/'train.log').open('wb') as log:
  active=subprocess.Popen(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  update(status='training',training_pid=active.pid)
  while True:
   text=(HOME/'train.log').read_text(errors='replace');epochs=[int(x) for x in re.findall(r'====> Epoch: (\d+)',text)];steps=[int(x) for x in re.findall(r'INFO:DogalKadinTR-v3:\[(\d+), ',text)];current=re.findall(r'Training epoch: (\d+)',text)
   if re.search(r'loss_\w+=\s*(?:nan|inf)',text,re.I):raise RuntimeError('Nonfinite training loss')
   update(completed_epochs=max(epochs,default=0),current_epoch=int(current[-1]) if current else 1,completed_steps=len(steps))
   code=active.poll()
   if code is not None:break
   time.sleep(5)
 assert code==0,code
 active=None
 text=(HOME/'train.log').read_text(errors='replace');epochs=[int(x) for x in re.findall(r'====> Epoch: (\d+)',text)];steps=[int(x) for x in re.findall(r'INFO:DogalKadinTR-v3:\[(\d+), ',text)];assert max(epochs)==50 and steps==list(range(per*50))
 update(status='validating',completed_epochs=50,completed_steps=per*50)
 command([PYTHON,str(HOME/'publish.py'),'--epoch','50','--steps',str(per*50)],'publish.log')
 backup=json.loads((HOME/'backup-state.json').read_text());assert backup['model_epoch']==50
 update(status='trained_compatible_quality_unverified',completed_epochs=50,completed_steps=per*50,download_url=backup['download_url'],archive_sha256=backup['archive_sha256'],ready_for_vcclient_import=True,ready_for_use=False)
except BaseException as e:
 if active and active.poll() is None:
  try:os.killpg(active.pid,signal.SIGTERM)
  except ProcessLookupError:pass
 update(status='failed',error=str(e),traceback=traceback.format_exc());raise
