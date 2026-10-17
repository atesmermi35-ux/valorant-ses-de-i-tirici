from pathlib import Path
from huggingface_hub import hf_hub_download
from concurrent.futures import ThreadPoolExecutor
import hashlib,json
root=Path('/workspace/rvc-restart/source/assets');rev='e6d0c1a17da07c33557852f9dfa2bd44cc75737d'
checks={'hubert_base/pytorch_model.bin':'cc8c20f4b90a520757260197a3ff2505705a7adbd20ad9eeaa4e1a9b38442ef5','pretrained_v2/f0G32k.pth':'2332611297b8d88c7436de8f17ef5f07a2119353e962cd93cda5806d59a1133d','pretrained_v2/f0D32k.pth':'bd7134e7793674c85474d5145d2d982e3c5d8124fc7bb6c20f710ed65808fa8a','rmvpe.pt':'6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193'}
def fetch(name):
 dest=root/'rmvpe' if name=='rmvpe.pt' else root
 p=Path(hf_hub_download('lj1995/VoiceConversionWebUI',name,revision=rev,local_dir=dest))
 if name in checks:assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==checks[name],name
 print('VERIFIED',name,p.stat().st_size,flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,['hubert_base/config.json','hubert_base/preprocessor_config.json',*checks]))
(root.parent/'model-provenance.json').write_text(json.dumps({'repository':'lj1995/VoiceConversionWebUI','revision':rev,'sha256':checks},indent=2))
