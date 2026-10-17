from pathlib import Path
import json,numpy as np,faiss,soundfile as sf,argparse
HOME=Path('/workspace/rvc-restart');EXP=HOME/'source/logs/DogalKadinTR-v3'
p=argparse.ArgumentParser();p.add_argument('--index-only',action='store_true');a=p.parse_args()
status=json.loads((HOME/'status.json').read_text());rows=[];arrays=[];excluded=[]
for wav in sorted((EXP/'0_gt_wavs').glob('*.wav')):
 if sf.info(wav).duration<1:
  excluded.append({'name':wav.name,'seconds':sf.info(wav).duration,'reason':'Less than one second; short/unvoiced tail excluded, original retained.'});continue
 f=EXP/'3_feature768'/f'{wav.stem}.npy';assert f.is_file();features=np.load(f,allow_pickle=False);assert features.ndim==2 and features.shape[1]==768 and np.isfinite(features).all()
 paths=[wav,f,EXP/'2a_f0'/f'{wav.stem}.wav.npy',EXP/'2b-f0nsf'/f'{wav.stem}.wav.npy']
 if not a.index_only:
  assert all(v.is_file() for v in paths),paths
  for v in paths[2:]:assert np.isfinite(np.load(v,allow_pickle=False)).all()
 rows.append('|'.join(str(v) for v in paths)+'|0');arrays.append(features.astype(np.float32))
assert len(rows)==216,len(rows)
(EXP/'filelist.txt').write_text('\n'.join(rows)+'\n')
if not (HOME/'DogalKadinTR-v3.index').exists():
 faiss.omp_set_num_threads(2);bank=np.concatenate(arrays);full=len(bank)
 if len(bank)>12000:bank=bank[np.sort(np.random.default_rng(20261018).choice(len(bank),12000,replace=False))]
 bank=np.ascontiguousarray(bank);index=faiss.index_factory(768,'IVF128,Flat');index.nprobe=8;index.train(bank);index.add(bank);_,ids=index.search(bank[::120],8);assert (ids>=0).all();faiss.write_index(index,str(HOME/'DogalKadinTR-v3.index'))
 status.update(index_vectors=len(bank),original_feature_vectors=full,index_clusters=128,index_nprobe=8)
status.update(training_clips=len(rows),excluded_clips=excluded,status='index_ready_waiting_pitch' if a.index_only else 'prepared',target_epochs=50)
(HOME/'status.json').write_text(json.dumps(status,indent=2));print(json.dumps(status),flush=True)
