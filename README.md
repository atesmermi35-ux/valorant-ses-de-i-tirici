# VoiceBridge

Windows 11 / RTX 3050 Laptop 4 GB için Türkçe **VCClient kurulum ve başlatma yardımcısı**. Hedef kullanım: mikrofon sesini genç yetişkin kadın sesine dönüştüren bir modeli Valorant sesli sohbetinde kullanmak.

**Durum: ilk sürüm.** Bu depo yeni bir ses dönüşüm ağı veya eğitilmiş kadın sesi modeli içermez. Ses dönüşümünü ayrı çalışan [w-okada VCClient](https://github.com/w-okada/voice-changer) yapar. VoiceBridge resmî Windows CUDA ZIP'ini bulur, doğrular ve kurar; motoru açar, NVIDIA bilgisini gösterir ve oyun bağlantısı/ayar adımlarını sunar. Model seçimi, mikrofon seçimi ve dönüşümü başlatma motorun kendi arayüzünde yapılır. Henüz Windows cihazında uçtan uca ses veya FPS ölçümü yapılmadı.

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
