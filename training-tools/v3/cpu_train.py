"""CPU RVC trainer: single-process training and optional native BF16 autocast."""
from pathlib import Path
import sys,os,contextlib
ROOT=Path('/workspace/rvc-restart/source');sys.path.insert(0,str(ROOT));os.chdir(ROOT)
import torch
import train.train as trainer
mode=os.environ.get('RVC_CPU_PRECISION','fp32')
if mode=='bf16':
 depth=0
 @contextlib.contextmanager
 def cpu_autocast(enabled=True):
  global depth
  use_bf16=depth==0
  depth+=1
  try:
   with torch.autocast('cpu',dtype=torch.bfloat16,enabled=use_bf16):yield
  finally:depth-=1
 trainer.autocast=cpu_autocast
 original_mel=trainer.spec_to_mel_torch
 def mel_float32(*args,**kwargs):
  with torch.autocast('cpu',enabled=False):return original_mel(*args,**kwargs)
 trainer.spec_to_mel_torch=mel_float32
original_loader=trainer.DataLoader
def cpu_loader(*args,**kwargs):
 kwargs.update(num_workers=0,persistent_workers=False,prefetch_factor=None,pin_memory=False)
 return original_loader(*args,**kwargs)
trainer.DataLoader=cpu_loader
assert not torch.cuda.is_available(),'This entrypoint is CPU only.'
torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS','4')))
logger=trainer.utils.get_logger(trainer.hps.model_dir)
logger.info('CPU mode: %s; single process, no DDP; FP32 mel/loss/master weights',mode)
if os.environ.get('RVC_PUBLISH_EPOCHS')=='1':
 original_epoch=trainer.train_and_evaluate
 def epoch_with_backup(*args,**kwargs):
  epoch=args[1];args[2].save_every_epoch=1 if epoch==1 else 10
  original_epoch(*args,**kwargs)
  import subprocess
  if epoch==1 or epoch%10==0:
   subprocess.run([sys.executable,'/workspace/rvc-restart/publish.py','--epoch',str(epoch),'--steps',str(trainer.global_step)],check=True)
  else:
   subprocess.run([sys.executable,'/workspace/rvc-restart/publish.py','--progress',str(epoch),'--steps',str(trainer.global_step)],check=True)
 trainer.train_and_evaluate=epoch_with_backup
if os.environ.get('RVC_RESUME_COMPLETED'):
 completed=int(os.environ['RVC_RESUME_COMPLETED'])
 original_load=trainer.utils.load_checkpoint
 def resume_load(*args,**kwargs):
  try:
   result=original_load(*args,**kwargs)
   assert result[3]==completed,(result[3],completed)
   logger.info('Verified full checkpoint completed epoch %s; next epoch %s',completed,completed+1)
   return (*result[:3],completed+1)
  except BaseException:
   logger.exception('Full checkpoint resume failed; refusing pretrained fallback')
   os._exit(2)
 trainer.utils.load_checkpoint=resume_load
trainer.run(0,1,trainer.hps,logger,False)
