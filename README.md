# VoiceBridge

Windows 11 / RTX 3050 Laptop 4 GB için Türkçe **VCClient kurulum ve başlatma yardımcısı**. Hedef kullanım: mikrofon sesini genç yetişkin kadın sesine dönüştüren bir modeli Valorant sesli sohbetinde kullanmak.

**Durum: geliştirme sürümü.** `DOGAL_SES_DENE.cmd`, OpenVoice V2 ve açık lisanslı kadın sesi referansıyla kendi ses kaydını **yerel WAV dosyasına** dönüştürür. `BASLAT.cmd`, ayrı çalışan [w-okada VCClient](https://github.com/w-okada/voice-changer) için kurulum yardımcısıdır. `MODEL_EGIT.cmd`, deneysel Seed-VC eğitimidir. Henüz Windows'ta canlı mikrofon, Valorant bağlantısı veya FPS ölçümü yapılmadı. Bu farklı motorların modelleri birbirinin yerine kullanılamaz.

## Doğal kadın sesi için ilk yerel deneme

1. Güncel ZIP'in tamamını çıkar. Python **3.12** kurulu olsun.
2. **DOGAL_SES_DENE.cmd** dosyasını aç.
3. Bilgisayarındaki kendi konuşma kaydını seç; yeni WAV dosyasının kaydedileceği yeri seç.
4. İlk kurulum için birkaç GB indirme gerekebilir. Model kendi ayrı Python ortamına kurulur. Sonuç hazır olunca varsayılan ses oynatıcın açılır. Kayıtlar internete yüklenmez.

Seçilen başlangıç tınısı, kamu malı **LJ Speech LJ001-0001** kaydından alınan nötr yetişkin kadın sesi adayıdır. Referans İngilizcedir; girişteki Türkçe konuşma doğrudan ses olarak dönüştürülür. Metin okuma/TTS kullanılmaz. Kaynak ve lisans bilgileri [referans notunda](assets/voices/NOTICE.md) bulunur. Belirli bir yaşta algılanma, doğallık ve tüm Türkçe seslerin hatasız korunması dinleme testi olmadan garanti edilemez.

OpenVoice V2 tonu dönüştürür. Kaynak çok pesse, akustik perde ölçümüne göre en fazla +6 yarım seslik yükseltme denenir; mevcut perdeyi düşürmez. Fark küçükse perdeye müdahale edilmez. Uzun kayıtlar 6 saniyelik örtüşen bloklarla işlenir; kaynak tını özeti her blokta yeniden hesaplanır. Her sonucun yanında `.json` teknik raporu oluşur. Otomatik perde uyumu seste artefakt oluşturursa CLI'da `--pitch none` ile karşılaştırılabilir.

```console
python -m voicebridge.natural convert --source "kendi-kaydim.wav" --output "yeni-sonuc.wav" --engine "/seed-vc/kaynagi" --pitch auto
```

Bu akış **dosya üzerinden ses denemesidir**; canlı oyun mikrofonu bağlamaz. Önce kendi sesinle örneği dinleyerek tınıyı değerlendirmek içindir. Windows CUDA kurulumu ve aygıt bağlantısı hâlâ o bilgisayarda doğrulanmalıdır.

### Mevcut doğrulama ve sınırı

Bulutta 57 saniyelik kullanıcı kaydıyla Seed-VC için **100 gerçek optimizasyon adımı** tamamlandı ve checkpoint oluştu. Ancak 6 saniyelik Türkçe dönüşümde otomatik konuşma tanıma ciddi içerik uyuşmazlığı gösterdi; bu checkpoint kullanıma hazır olarak işaretlenmedi ve özel çalışma alanında tutuldu. Aynı kısa örnekte OpenVoice tabanlı dönüşüm kaynak cümleyi daha iyi koruduğu için yerel deneme yoluna seçildi.

Bu karşılaştırma yalnızca tek kısa örneğin Whisper-small transkriptleri arasındadır; insan tarafından doğrulanmış metin, doğallık puanı veya genellenebilir başarı oranı değildir. Orijinal konuşmanın tanınmasında da hatalar vardır. Bir checkpoint oluşması, modelin Türkçe için yeterli olduğu anlamına gelmez. Kullanıcı kayıtları ve eğitilmiş özel checkpoint'ler bu depoda paylaşılmaz.

## Deneysel Seed-VC model hazırlığı ve eğitimi

**Bu rota mevcut Türkçe anlaşılırlık ekranından geçmedi; araştırma amaçlıdır.** Aday profil **DogalKadinTR / Seed-VC Whisper-small + BigVGAN** kullanır. Başlangıç ses tonu seçilen referans kaydından gelir; profil tek başına belirli bir yaş ya da tını üretmez. Hazırlanmış referansla eğitimsiz (zero-shot) dönüşüm de mümkündür; kişiye özel ince ayar ayrı bir işlemdir. Kısa veriyle ince ayar yapılabilmesi kaliteli sonucu garanti etmez.

Windows'ta eğitim denemesi için:

1. Güncel ZIP'in tamamını çıkar. Python **3.12** kurulu olsun.
2. Kullanım hakkın olan, tek kadın konuşmacıya ait temiz kayıtları ayrı bir klasöre koy. `C:\Axtenix\SesVerisi` kullanılabilir; klasörü bilgisayarında sen seçersin. Müzik ve başka konuşmacıları önceden ayır.
3. **MODEL_EGIT.cmd** dosyasını açıp kayıt klasörünü seç.
4. Ayrı Python ortamı ve sabit sürümlü Seed-VC kaynağı indirilir; birkaç GB alan/internet gerekebilir. Kaynak ZIP'i tam commit'e ve SHA-256'ya sabitlenmiştir. Ana uygulamanın Python ortamı değiştirilmez.
5. 22.050 Hz mono, 1–6 saniyelik veri parçaları ve 15 saniyeye kadar referans WAV hazırlanır. Orijinal kayıtlar korunur. Bu işlem müzik ayırma, konuşmacı ayırma, otomatik kalite değerlendirmesi veya gürültü temizleme yapmaz. Parça sınırları cümle sınırlarıyla örtüşmeyebilir.
6. 100 adımlık, batch-size 1 ince ayar **denemesi** başlar. 4 GB GPU belleğine sığması henüz test edilmedi; diğer GPU uygulamalarını kapat. CUDA/bellek hatası olursa eğitim tamamlanmış sayılmaz. Yalnızca adımlar tamamlanıp checkpoint oluştuğunda durum raporu eğitildi olarak işaretlenir.

Veriler ve çıktılar `%LOCALAPPDATA%\VoiceBridge\training\DogalKadinTR-…` içinde kalır; GitHub'a yüklenmez. `status.json`, tamamlanan gerçek optimizasyon adımlarını, son kaybı ve varsa hatayı kaydeder. Başarılı çıktı `runs/DogalKadinTR/ft_model.pth` ve `seed-quality.yml` dosyalarıdır. Eğitim sonrası her zaman referans WAV da gerekir. **Bu Seed-VC checkpoint'i RVC modeli olarak VCClient'a yüklenemez.**

Çıktıyı Seed-VC kaynak klasöründe kendi Python ortamıyla denemek için (yer tutucuları kendi dosya yollarınla değiştir):

```console
python inference.py --source "kaynak.wav" --target "referans.wav" --output "sonuc" --checkpoint "ft_model.pth" --config "seed-quality.yml" --diffusion-steps 50 --inference-cfg-rate 0.7 --length-adjust 1.0 --f0-condition False --fp16 True
```

`50` difüzyon adımı kalite denemesi içindir; Türkçe anlaşılırlık ve doğallık dinleme testinde doğrulanmalıdır. Konuşmayı metne çevirip yeniden okutmaz; Türkçe seslerin korunması yine de ölçülmeden garanti edilemez. Üretici ince ayarın bazı durumlarda kelime hatalarını artırabileceğini belirtiyor. Önce orijinal hazır model ve aynı referansla karşılaştır; ince ayar daha iyi çıkmazsa hazır modeli kullan.

VoiceBridge içinden dosya dönüştürme kontrolü de bulunur. Ayrı model Python ortamıyla, depo klasöründen:

```console
python -m voicebridge.conversion --engine "/seed-vc/kaynagi" --checkpoint "/calisma/runs/DogalKadinTR/ft_model.pth" --config "/calisma/seed-quality.yml" --source "/kaynak.wav" --reference "/referans.wav" --output "/sonuc.wav"
```

Bu yardımcı 50 adımlık kalite profilini uygular, CPU'da Whisper'ı float32 yükler, çıktının boş/sessiz olmadığını ve süresinin kaynakla uyumunu kontrol eder. Bu sinyal kontrolleri doğal ses veya doğru telaffuz kanıtı değildir. Canlı mikrofon bağlantısı kurmaz.

Motorun ayrı `real-time-gui.py` arayüzü de özel checkpoint/config alabilir; canlı mikrofon, modelin 4 GB GPU'ya sığması ve VB-CABLE yönlendirmesi bu yeni akışta henüz doğrulanmadı. Eğitim paketi hazır olması Valorant ses yolunun hazır olduğu anlamına gelmez. Seed-VC kodu/modeli GPL-3.0 koşullarına tabidir; indirilen kaynak kendi lisansını içerir.

Bulutta doğrudan veri hazırlamak/eğitim girişimini izlemek için:

```console
python -m voicebridge.training prepare --source "/kaynak/kayit.wav" --work "/yeni/calisma"
python -m voicebridge.training run --source "/kaynak/kayit.wav" --work "/baska/yeni/calisma" --engine "/seed-vc/kaynagi" --device cpu --steps 1
```

CPU komutu yalnızca açıkça seçilen deneme yoludur; eğitim hızı veya kaliteli sonuç vaadi değildir. CUDA otomatik olarak var kabul edilmez. Kaynaklar ve model ağırlıkları internetten indirilemiyorsa optimizasyon başlamaz; `completed_steps: 0` olarak raporlanır. Windows başlatıcısı ve gerçek model çıktısı doğrulanmadan bu akış hazır kabul edilmemelidir.

## En kısa kurulum

1. Depo klasörünü Windows bilgisayarına indirip çıkar.
2. [Python'ın Windows sürümünü](https://www.python.org/downloads/windows/) kur (3.10 veya üzeri; öneri 3.12). Kurulumda **Tcl/Tk** ve **Python launcher** açık kalsın. VoiceBridge için `pip install` gerekmez.
3. ZIP'e sağ tıkla → **Tümünü Ayıkla** → **Ayıkla**. Açılan normal klasördeki **`BASLAT.cmd`** dosyasına çift tıkla. ZIP'in içinden çalıştırma; `main.py` dosyası ve `voicebridge` klasörü başlatıcının yanında bulunmalı.
4. **Resmî CUDA sürümlerini getir** → uygun sürümü seç → **Seçili sürümü indir ve doğrula**. Dosya adı ve indirme boyutu listede görünür. Kurulum çalıştırılabilir dosyaları kendiliğinden açmaz.
5. **Ses motorunu başlat**. İlk açılışta VCClient kendi yardımcı model dosyalarını indirebilir. Arayüz açılıp model yüklendiğinde, kulaklığında dönüşümü dinleyerek çalıştığını doğrula.
6. Motor içinde kullanım koşulları uygun bir kadın sesi modeli seç/yükle. Başlangıçta motorun örnek modellerini dinleyebilirsin; örneklerin sesini, dilini ve kullanım koşullarını değerlendir. Bu sürüm belirli bir Türkçe kadın sesini otomatik seçmez.
7. **Valorant'a bağla** sekmesindeki VB-CABLE yönlendirmesini uygula.

Katalog veya otomatik kurulum çalışmazsa [resmî indirme sayfasından](https://huggingface.co/wok000/vcclient000/tree/main) **Windows CUDA** paketini indirip ayrı bir klasöre çıkar; **Mevcut motoru seç** ile `start_http.bat` veya `vcclient.exe` seç. Elle seçilen dosya VoiceBridge tarafından doğrulanmış sayılmaz. Başka başlatıcı adı olan paketler bu sürümde desteklenmez. Otomatik kurucu yalnızca SHA-256 metadatası bulunan ZIP paketlerini destekler; `.7z` gibi paketler elle çıkarılmalıdır.

Güncel VCClient sürümlerinde `std` edisyonu Beatrice destekler; RVC için **CUDA** veya uygun ONNX edisyonu gerekir. Bu yardımcı NVIDIA kartın için CUDA ZIP'lerini listeler. RTX 5090'a özel veya adında `experimental` geçen paketleri listeden çıkarır. Diğer sürümler için uygunluğu motorun sürüm notlarından kontrol et.

## Valorant ses bağlantısı

[VB-CABLE](https://vb-audio.com/Cable/) sanal ses sürücüsünü resmî yönergesiyle Windows'ta kur. VoiceBridge bu sürücüyü yüklemez.

| Aşama | Seçilecek aygıt |
| --- | --- |
| VCClient giriş | Fiziksel mikrofonun |
| VCClient çıkış | **CABLE Input** |
| Valorant → Ses → Sesli Sohbet → Giriş Aygıtı | **CABLE Output** |
| Valorant çıkış | Kulaklığın |

Önce motor çıkışını kulaklığa verip dönüşümü dinle, sonra CABLE Input'a geçir. Passthrough kapalı olsun. Oyundaki geri döngü testiyle tekrar kontrol et. Motorun çalıştığını yalnızca açık bir pencere veya çalışan işlem üzerinden varsayma. Bu uygulama oyun dosyalarına, oyun belleğine veya Vanguard'a müdahale etmez; standart Windows ses aygıtlarını kullanır.

## RTX 3050 Laptop için başlangıç ayarı

Bu değerler **denenecek başlangıç önerileridir**; otomatik uygulanmaz ve bu cihazda ölçülmedi. Arayüz adları/ölçü birimleri VCClient sürümüne göre değişebilir.

| Ayar | Başlangıç önerisi |
| --- | --- |
| GPU | Motor listesinden NVIDIA RTX 3050 |
| Ses örnekleme | Mikrofon ve sanal kabloda 48 kHz |
| Aygıt modu | Destekleniyorsa Server |
| RVC F0 | Destekleniyorsa RMVPE; yük fazlaysa DIO ile karşılaştır |
| TUNE | +8 yarım sesle başla; +6…+12 arasında aynı cümleyi dinle |
| INDEX | `.index` yoksa 0; varsa 0.3 ile karşılaştır |
| CHUNK | Arayüzde gösterilen tampon süresi 80–120 ms civarında başla |
| EXTRA | Motor varsayılanıyla başla; kararlı çalışınca kademeli azalt |

Sesin genç yetişkin kadın sesi gibi algılanması modele, sesine ve konuşma biçimine bağlıdır; bir yaş düğmesiyle ayarlanmaz. Sadece perdeyi yükseltmek doğal kadın sesi sağlamaz. Türkçe kelimelerdeki s/ş/ç/t seslerini karşılaştır. Model kalitesini iyileştirmek için aynı cümleyi farklı ayarlarda kaydet.

Valorant ile aynı 4 GB VRAM paylaşılır. Oyunun FPS'ini sınırlamak GPU'da boşluk bırakabilir. Kesilme varsa CHUNK'ı büyüt, INDEX'i azalt, gerekirse daha hafif model/motor kullan. Motorun `res` süresi `buf` süresini sürekli aşıyorsa işleme yetişmiyor olabilir. Motorun gecikme göstergesi Windows sürücüsü, sanal kablo ve oyundaki tüm gecikmeyi ölçmez. Belirli bir FPS, gecikme veya ses kalitesi garantisi verilmez.

## Dosyalar ve indirme doğrulaması

### Pencere açılıp kapanıyorsa

`can't open file ... Temp ... zip ... main.py` hatası, başlatıcının ZIP içinden çalıştırıldığını gösterir. ZIP'e sağ tıklayıp **Tümünü Ayıkla** seç; çıkarılan klasörden başlat. Python'ı yeniden kurman gerekmez. Eksik dosyalar yeni başlatıcıda doğrudan açıklanır. Python uygulaması başka bir nedenle çökerse hata raporu `%TEMP%\VoiceBridge-startup.log` dosyasına yazılır ve Not Defteri'nde açılır.

VoiceBridge ayarları ve motorlar `%LOCALAPPDATA%\VoiceBridge` altında tutulur. Depo içine model veya çok GB'lık motor dosyaları yazılmaz. Önceki kurulum yeni bir indirme başarısız olduğunda korunur. İndirme iptal edildiğinde geçici dosyalar temizlenir; bu sürümde kaldığı yerden devam etme yoktur.

Katalog resmî `wok000/vcclient000` Hugging Face deposundan TLS doğrulamasıyla okunur. İndirme URL'si katalogdaki tam commit'e sabitlenir. Boyut ve yayıncının LFS SHA-256 değeri uyuşmadan dosyalar açılmaz. ZIP yolları ve disk alanı kontrol edilir; doğrulanmış dosyalar yeni bir dizine kurulur. Bu, yayıncının dosyasıyla bütünlük eşleşmesidir; bağımsız bir kod imzası değildir.

VoiceBridge mikrofon kaydı almaz ve sesi bir sunucuya göndermez. Gerçek ses işleme VCClient'tadır; yerel giriş/çıkış modunu kullan. Model ve motor lisansları kendi yayıncılarına aittir; bu depo bunları yeniden dağıtmaz. Modelin kullanım koşullarını ayrıca kontrol et.

## Geliştirme ve test

```console
python -m unittest discover -s tests -v
python main.py --diagnose
python main.py --catalog
python main.py
```

Python 3.10+ ve GUI için Tk gerekir. Linux bulut ortamı Windows ses motorunu, fiziksel mikrofonu, sanal kabloyu ve Valorant'ı çalıştırmaz. Ekransız ortamda GUI testi atlanır; Windows batch testi yalnızca Windows'ta çalışır. Kurucu testleri gerçek yerel HTTP istekleriyle küçük test ZIP'leri indirir; gerçek motor veya ses modeli indirmez. Ekran varsa GUI testi pencereyi açar ve ayar seçimi/kaydetmeyi doğrular. Bunlar ses dönüşüm kalitesini doğrulamaz.

GitHub Actions yapılandırması Linux ve Windows testleri ile PyInstaller üzerinden Windows EXE paketi üretimini içerir. İş akışı henüz bu depoda çalıştırılmadı. Push sonrası başarılı Windows işinin **Artifacts → VoiceBridge-Windows** bölümünden EXE alınabilir; önceden üretilmiş EXE bu depoda bulunmaz.

Elle EXE üretmek için Windows'ta:

```console
python -m pip install pyinstaller==6.12.0
python -m PyInstaller --noconfirm --clean --onefile --windowed --name VoiceBridge main.py
```

### Windows'ta tamamlanacak kabul kontrolü

- Resmî kataloğu getir; CUDA ZIP'ini indirip doğrulamanın tamamlandığını gör.
- Motorun modelini yükle; NVIDIA kullanımını `nvidia-smi` veya Görev Yöneticisi ile kontrol et.
- Kulaklıkta 10 saniyelik dönüştürülmüş Türkçe konuşma dinle; ham ses/passthrough olmadığını doğrula.
- VB-CABLE üzerinden Valorant geri döngü testini çalıştır.
- Oyundayken 5 dakika dene; kesilme, GPU belleği, FPS ve motorun tampon/işleme sürelerini not et.

Bu kontroller geçmeden uygulama uçtan uca hazır kabul edilmemeli. Bulut ortamında Hugging Face erişimi ağ politikasıyla engellenirse gerçek katalog/indirme testi tamamlanamaz. Windows'taki normal internet bağlantısı aynı bulut politikasına bağlı değildir.
