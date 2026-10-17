"""Persist validated RVC exports and progress through the authorized Git remote."""
from pathlib import Path
import argparse,subprocess,json,zipfile,hashlib,urllib.request,sys,fcntl,time
HOME=Path('/workspace/rvc-restart');ROOT=HOME/'source';REPO=Path('/workspace/valorant-ses-de-i-tirici');NAME='DogalKadinTR-v3';EXP=ROOT/'logs'/NAME
p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True);group.add_argument('--epoch',type=int);group.add_argument('--progress',type=int);p.add_argument('--steps',type=int);a=p.parse_args();epoch=a.epoch if a.epoch is not None else a.progress

def git(*args,data=None):return subprocess.check_output(['git',*args],cwd=REPO,input=data).decode().strip()
def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def validate(modelpath):
 import torch,numpy as np,faiss
 import torch.nn.functional as F
 sys.path.insert(0,str(HOME/'vcclient-source/server'))
 from voice_changer.RVC.inferencer.rvc_models.infer_pack.models import SynthesizerTrnMs768NSFsid
 c=torch.load(modelpath,map_location='cpu',weights_only=True)
 assert c['version']=='v2' and c['f0']==1 and len(c['config'])==18 and c['config'][-1]==32000 and c['info']==f'{epoch}epoch'
 assert all(torch.isfinite(v).all() for v in c['weight'].values())
 model=SynthesizerTrnMs768NSFsid(*c['config'],is_half=False).float().eval();loaded=model.load_state_dict(c['weight'],strict=False)
 assert not loaded.unexpected_keys and all(k.startswith('enc_q.') for k in loaded.missing_keys)
 index=faiss.read_index(str(HOME/'DogalKadinTR-v3.index'));assert index.d==768 and index.ntotal>0
 stem='0_0';phone=np.load(EXP/'3_feature768'/f'{stem}.npy',allow_pickle=False).astype(np.float32)
 _,ix=index.search(phone,1);assert (ix>=0).all();bank=index.reconstruct_n(0,index.ntotal);phone=.7*phone+.3*bank[ix[:,0]]
 phone=F.interpolate(torch.from_numpy(phone).unsqueeze(0).transpose(1,2),scale_factor=2).transpose(1,2)
 pitch=np.load(EXP/'2a_f0'/f'{stem}.wav.npy',allow_pickle=False);pitchf=np.load(EXP/'2b-f0nsf'/f'{stem}.wav.npy',allow_pickle=False)
 n=min(phone.shape[1],len(pitch),len(pitchf));torch.set_num_threads(4);torch.manual_seed(0)
 with torch.inference_mode():out=model.infer(phone[:,:n],torch.tensor([n]),torch.from_numpy(pitch[:n]).long().unsqueeze(0),torch.from_numpy(pitchf[:n]).float().unsqueeze(0),torch.tensor([0]))[0][0,0]
 assert torch.isfinite(out).all() and out.abs().max().item()>1e-5 and abs(len(out)/32000-n*.01)<.05
 return {'vcclient_synthesizer_load':'passed','finite_real_feature_audio':'passed','output_seconds':len(out)/32000,'peak':out.abs().max().item(),'index_vectors':index.ntotal,'limits':'CPU graph smoke check, target-speaker input. No listening, real male microphone or Windows/Valorant validation.'}

with (HOME/'publish.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 statepath=HOME/'backup-state.json';previous=json.loads(statepath.read_text()) if statepath.exists() else {}
 status=json.loads((HOME/'status.json').read_text());payloads={}
 if a.epoch is not None:
  model=ROOT/'assets/weights'/f'{NAME}.pth' if epoch==50 else next((ROOT/'assets/weights').glob(f'{NAME}_e{epoch}_s*.pth'))
  report=validate(model)
  archive=HOME/'DogalKadinTR-v3-latest.zip'
  info={'completed_epochs':epoch,'target_epochs':50,'completed_steps':a.steps,'source_seconds':757.6555,'source_sha256':status['source_sha256'],'validation':report,'quality_approved':False}
  readme=f'DogalKadinTR-v3 — {epoch}/50 epoch.\nYeni 12 dakika 38 saniyelik kayıtla eğitim. RVC v2, 32 kHz, F0 açık, konuşmacı 0.\nZIP dosyasının tamamını ayıkla. VCClient model yüklemesinde DogalKadinTR-v3.pth ve DogalKadinTR-v3.index seç.\nBu bir eğitim adayıdır; doğallık, Türkçe anlaşılırlık, gerçek erkek mikrofonu ve Windows/Valorant performansı insan dinlemesiyle doğrulanmadı.\n'
  members={'DogalKadinTR-v3.pth':model.read_bytes(),'DogalKadinTR-v3.index':(HOME/'DogalKadinTR-v3.index').read_bytes(),'model-info.json':json.dumps(info,indent=2).encode(),'OKU.txt':readme.encode()}
  members['SHA256SUMS.txt']=''.join(f'{hashlib.sha256(v).hexdigest()}  {k}\n' for k,v in members.items()).encode()
  with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
   for n,b in members.items():z.writestr(NAME+'/'+n,b)
  with zipfile.ZipFile(archive) as z:assert z.testzip() is None
  assert archive.stat().st_size<100*1024*1024,'GitHub file limit exceeded'
  sha=digest(archive);payloads[archive.name]=archive
  previous.update(model_epoch=epoch,archive_sha256=sha,archive_bytes=archive.stat().st_size)
 for path in [HOME/'cpu_train.py',HOME/'publish.py',HOME/'supervise.py',HOME/'download.py',HOME/'prepare.py',HOME/'requirements-tested.txt']:
  if path.is_file():payloads['training-tools/v3/'+path.name]=path
 progress={'completed_epochs':epoch,'target_epochs':50,'completed_steps':a.steps,'status':'trained_compatible_quality_unverified' if epoch==50 else ('training' if epoch else 'preparing'),'latest_model_epoch':previous.get('model_epoch'),'model_sha256':previous.get('archive_sha256'),'updated_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'quality_approved':False}
 config_file=EXP/'config.json'
 if config_file.is_file():payloads['training-tools/v3/config.json']=config_file
 provenance=ROOT/'model-provenance.json'
 if provenance.is_file():payloads['training-tools/v3/model-provenance.json']=provenance
 progresspath=HOME/'progress-public.json';progresspath.write_text(json.dumps(progress,indent=2));payloads['v3-progress.json']=progresspath
 from datetime import datetime
 from zoneinfo import ZoneInfo
 stamp=datetime.now(ZoneInfo('Europe/Istanbul')).strftime('%d.%m.%Y %H:%M')
 page=HOME/'progress-public.md'
 text=f'# Yeni kayıtla RVC modeli\n\n**Son kaydedilen ilerleme: {epoch}/50 epoch.**\n\nSon güncelleme: {stamp} (Türkiye saati).\n\n'
 if previous.get('model_epoch'):
  text+=f'**İndirilebilir son model: {previous["model_epoch"]} epoch.**\n\n[Model ZIP dosyasını indir](https://github.com/atesmermi35-ux/valorant-ses-de-i-tirici/raw/refs/heads/voice-model/DogalKadinTR-v3-latest.zip)\n\nZIP dosyasının tamamını ayıkla; VCClient model yüklemesinde .pth ve .index dosyalarını seç.\n\n'
 else:text+='Henüz yeni model ZIP dosyası oluşmadı.\n\n'
 text+='Hedef 50 epoch. Model yedekleri ilk epoch ve her 10 epoch sonrasında güncellenir. Bu sayfa son kaydedilen durumu gösterir; güncel kaydı görmek için sayfayı yenile. Doğallık ve gerçek mikrofon/Valorant kalitesi henüz dinleyerek doğrulanmadı.\n'
 page.write_text(text);payloads['V3-DURUM.md']=page
 git('fetch','origin','refs/heads/voice-model:refs/remotes/origin/voice-model')
 parent=git('rev-parse','refs/remotes/origin/voice-model')
 # Git trees are nested, so use a temporary alternate index to preserve all existing files.
 import tempfile,os
 fd,indexpath=tempfile.mkstemp(prefix='rvc-git-index-',dir=HOME);os.close(fd);os.unlink(indexpath)
 env=os.environ.copy();env['GIT_INDEX_FILE']=indexpath
 def indexed(*args,data=None):return subprocess.check_output(['git',*args],cwd=REPO,input=data,env=env).decode().strip()
 try:
  indexed('read-tree',parent)
  for name,path in payloads.items():
   blob=git('hash-object','-w',str(path));indexed('update-index','--add','--cacheinfo',f'100644,{blob},{name}')
  tree=indexed('write-tree')
 finally:Path(indexpath).unlink(missing_ok=True)
 commit=git('commit-tree',tree,'-p',parent,data=f'Persist RVC v3 epoch {epoch} progress and validated model backup\n'.encode())
 subprocess.run(['git','push','origin',commit+':refs/heads/voice-model'],cwd=REPO,check=True)
 if a.epoch is not None:
  url=f'https://github.com/atesmermi35-ux/valorant-ses-de-i-tirici/raw/{commit}/DogalKadinTR-v3-latest.zip';h=hashlib.sha256();size=0
  with urllib.request.urlopen(url,timeout=120) as response:
   assert response.status==200
   while block:=response.read(1024*1024):h.update(block);size+=len(block)
  assert h.hexdigest()==sha and size==archive.stat().st_size
  previous.update(model_commit=commit,download_url=url,model_epoch=epoch)
 previous.update(last_progress_commit=commit,completed_epochs=epoch)
 statepath.write_text(json.dumps(previous,indent=2));print(json.dumps(previous),flush=True)
