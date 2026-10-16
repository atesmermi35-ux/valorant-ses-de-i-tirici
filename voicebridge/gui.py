"""Turkish desktop companion; no microphone recording or inference in this process."""

from __future__ import annotations

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from . import __version__
from . import core


ROUTING = """1  Sanal mikrofonu hazırla

VB-Audio'nun resmî sitesinden VB-CABLE'ı indir. Windows sürücüsünü kendi
kurulum yönergesiyle yükle; istenirse bilgisayarı yeniden başlat.
VoiceBridge sürücü yüklemez veya Windows güvenlik ayarlarını değiştirmez.

2  VCClient içinde sesi seç

Bir kadın sesi modeli yükle veya motorun kendi örneklerini dinle.
Hedefimiz 18–20 yaşlarında algılanan yetişkin kadın sesi. Yaş bir model
ayar düğmesi değildir; tını, konuşma şekli ve eğitim verisine bağlıdır.
Türkçe konuşmayı iyi koruyan, kullanım koşulları uygun bir model seç.
Bu uygulama belirli bir kadın sesi modeliyle birlikte gelmez.

3  Ses yolunu kur

VCClient INPUT  →  Kendi fiziksel mikrofonun
VCClient OUTPUT →  CABLE Input (VB-Audio Virtual Cable)
Valorant giriş  →  CABLE Output (VB-Audio Virtual Cable)
Valorant çıkış  →  Kendi kulaklığın

CABLE adları ters gibi görünür: motor kablonun Input'una yazar,
Valorant kablonun Output'undan okur. Windows varsayılan mikrofonunu
değiştirmek zorunda değilsin; Valorant içinden açıkça seç.

4  Önce kulaklıkla dene

İlk denemede OUTPUT'u kulaklığın yapıp dönüştürülmüş sesi dinle.
Ardından OUTPUT'u CABLE Input'a al. Passthrough'u kapat; aksi halde
ham sesin iletilir. Dönüşümün gerçekten etkin olduğunu kontrol et.
Motorun REC özelliğiyle kısa bir deneme alıp dinleyebilirsin.

5  Valorant'ta doğrula

Ayarlar → Ses → Sesli Sohbet → Giriş Aygıtı: CABLE Output.
Geri döngü testiyle sesi kontrol et, sonra geri döngüyü kapat.
İlk denemeyi antrenman veya lobide yap. Oyunun dosyalarına, belleğine
ve Vanguard'a müdahale edilmez; bağlantı standart ses aygıtı üzerinden.
"""

PROFILES = {
    "Dengeli · ilk deneme": """RTX 3050 Laptop 4 GB · başlangıç önerisi

Bu değerler ölçülmüş sonuç veya otomatik uygulanmış ayarlar değildir.
VCClient sürümünde karşılıkları varsa motor arayüzünden uygula.

Motor: Windows CUDA sürümü; GPU listesinden RTX 3050'yi seç.
Örnekleme: mikrofon ve sanal kabloda 48.000 Hz.
Ses aygıt modu: Server mevcutsa önce dene.
RVC perde algılama: RMVPE mevcutsa dene.
TUNE: önce +8 yarım ses; kendi sesinle +6…+12 arasında karşılaştır.
INDEX: .index yoksa 0; varsa önce 0.3 dene.
CHUNK: arayüzün gösterdiği 80–120 ms civarı tamponla başla.
EXTRA: önce motor varsayılanı; kesintisiz çalışınca küçük adımlarla azalt.

Doğal sesi TUNE tek başına üretmez. Öncelik uygun model, temiz ve
patlamayan mikrofon kaydı, sonra perde ve gecikme ayarıdır.
""",
    "Oyun öncelikli · yükü azalt": """Valorant ile birlikte kullanım

Önce Dengeli profili kur. Bunlar motor içinde elle denenir:
• Oyunun FPS'ini sabitleyerek GPU'da boşluk bırak.
• INDEX'i 0'a indir; modelin karakteri değişebilir, tekrar dinle.
• RMVPE pahalı geliyorsa motorun desteklediği DIO'yu karşılaştır.
• CHUNK tamponunu bir kademe artır; gecikme yükselir, kesilme azalabilir.
• Birden fazla ses modeli/motor örneği açık tutma.
• Dizüstünü prize tak; ısınma ve güç modunu kontrol et.

4 GB VRAM hem oyun hem motor tarafından paylaşılır. FPS veya gecikme
garantisi verilemez. GPU belleği yetmezse modeli küçültmek, daha hafif
bir motor seçmek veya dönüşümü ayrı bilgisayara almak gerekebilir.
""",
    "Doğallık · karşılaştırmalı dinle": """Ses kalitesi ayarı

• Türkçe cümlelerle, özellikle s/ş/ç/t sesleriyle 10 saniyelik kayıt al.
• Aynı cümleyi TUNE +6, +8, +10 ile karşılaştır.
• Uygun .index varsa 0, 0.3 ve 0.5'i karşılaştır; yükü de izle.
• Metalik ses varsa CHUNK/EXTRA'yı fazla küçültmüş olabilirsin.
• Mikrofonda sert gürültü bastırmayı azalt; sessiz ortam ve kulaklık kullan.
• Bir seferde yalnızca bir ayarı değiştir.

Motorun res (işleme) süresi buf (tampon) süresinden sürekli büyükse
gerçek zamanlı işleme yetişmiyor olabilir. Tamponu artır veya yükü azalt.
buf + res, motor içi bir gecikme göstergesidir; ses sürücüsü, sanal kablo
ve oyun sohbeti de ek gecikme getirir. Uçtan uca ölçüm yerine geçmez.

Bir örnek ses seçtikten sonra kendi sesinle yapılan kayıtla ayarları
iyileştirebiliriz. Bu sürümde hazır Türkçe kadın sesi doğrulanmış değildir.
""",
}


class App:
    def __init__(self, root: tk.Tk, home: Path | None = None):
        self.root = root
        self.home = home or core.app_home()
        self.config = core.read_config(self.home)
        self.events: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.releases: list[core.Release] = []
        self.process = None
        self.preview_process = None
        self.closed = False
        root.title(f"VoiceBridge {__version__} · Valorant ses kurulumu")
        root.geometry("960x760")
        root.minsize(780, 650)
        root.configure(bg="#10131c")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#10131c")
        style.configure("TLabel", background="#10131c", foreground="#e9ecf5", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 27, "bold"))
        style.configure("Sub.TLabel", foreground="#a5afc9")
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 9))
        style.configure("TNotebook", background="#10131c", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(15, 10), font=("Segoe UI", 10))
        body = ttk.Frame(root, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="VOICEBRIDGE", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="Gerçek zamanlı ses dönüşümü için kurulum ve başlatma yardımcısı", style="Sub.TLabel").pack(anchor="w", pady=(2, 6))
        ttk.Label(body, text="Windows 11  ·  RTX 3050 Laptop / 4 GB  ·  Doğal kadın sesi denemesi", style="Sub.TLabel").pack(anchor="w", pady=(0, 18))
        tabs = ttk.Notebook(body)
        tabs.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, text="GPL-3.0 · Garanti verilmez.", style="Sub.TLabel").pack(side="left")
        ttk.Button(footer, text="Kaynak ve lisans ↗", command=lambda: webbrowser.open("https://github.com/atesmermi35-ux/valorant-ses-de-i-tirici/blob/main/LICENSE")).pack(side="right")
        setup = ttk.Frame(tabs, padding=18)
        route = ttk.Frame(tabs, padding=12)
        settings = ttk.Frame(tabs, padding=18)
        tabs.add(setup, text="01  Kur ve başlat")
        tabs.add(route, text="02  Valorant'a bağla")
        tabs.add(settings, text="03  Performansı ayarla")
        ttk.Label(setup, text="Ses motoru · w-okada VCClient", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(setup, text="Dönüşümü ayrı VCClient uygulaması yapar. İlk kurulum birkaç GB indirebilir.", wraplength=780).pack(anchor="w", pady=(6, 14))
        self.catalog_button = ttk.Button(setup, text="Resmî CUDA sürümlerini getir", command=self.load_catalog)
        self.catalog_button.pack(anchor="w")
        self.release_box = ttk.Combobox(setup, state="readonly", width=85)
        self.release_box.pack(fill="x", pady=10)
        self.release_box.bind("<<ComboboxSelected>>", lambda _: self.refresh_buttons())
        self.install_button = ttk.Button(setup, text="Seçili sürümü indir ve doğrula", command=self.install_release)
        self.install_button.pack(anchor="w")
        self.progress = ttk.Progressbar(setup, maximum=100)
        self.progress.pack(fill="x", pady=(15, 6))
        self.status = tk.StringVar(value="Henüz bir ses motoru başlatılmadı.")
        ttk.Label(setup, textvariable=self.status, wraplength=780).pack(anchor="w")
        self.cancel_button = ttk.Button(setup, text="İşlemi iptal et", command=self.cancel.set)
        self.cancel_button.pack(anchor="w", pady=(8, 15))
        self.path_text = tk.StringVar()
        ttk.Label(setup, textvariable=self.path_text, wraplength=780, style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(setup)
        buttons.pack(fill="x")
        self.select_button = ttk.Button(buttons, text="Mevcut motoru seç", command=self.select_engine)
        self.select_button.pack(side="left")
        self.launch_button = ttk.Button(buttons, text="Ses motorunu başlat ↗", command=self.start_engine)
        self.launch_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Doğal ses kaydı denemesi ↗", command=self.natural_preview).pack(side="left")
        self.download_button = ttk.Button(setup, text="Resmî indirme sayfası ↗", command=lambda: webbrowser.open(core.OFFICIAL_DOWNLOADS))
        self.download_button.pack(anchor="w", pady=(14, 0))
        ttk.Label(setup, text="Kayıt denemesinde kendi ses dosyanı seçip dönüştürülmüş WAV'ı dinleyebilirsin. İlk CPU kurulumu yüzlerce MB indirebilir. Bu deneme canlı oyun mikrofonu bağlamaz.", wraplength=780, style="Sub.TLabel").pack(anchor="w", pady=(10, 0))
        route_buttons = ttk.Frame(route)
        route_buttons.pack(fill="x", pady=(0, 8))
        ttk.Button(route_buttons, text="VB-CABLE resmî sitesi ↗", command=lambda: webbrowser.open(core.VIRTUAL_CABLE)).pack(side="left")
        ttk.Button(route_buttons, text="VCClient kaynak ve belgeler ↗", command=lambda: webbrowser.open(core.UPSTREAM)).pack(side="left", padx=8)
        self.text_panel(route, ROUTING)
        self.profile_box = ttk.Combobox(settings, values=list(PROFILES), state="readonly")
        self.profile_box.pack(fill="x", pady=(0, 12))
        self.profile_box.current(0)
        self.profile_text = self.text_panel(settings, PROFILES[self.profile_box.get()])
        self.profile_box.bind("<<ComboboxSelected>>", lambda _: self.set_text(self.profile_text, PROFILES[self.profile_box.get()]))
        self.gpu_status = tk.StringVar(value="NVIDIA bilgisi henüz okunmadı.")
        ttk.Label(settings, textvariable=self.gpu_status, wraplength=780, style="Sub.TLabel").pack(anchor="w", pady=12)
        self.gpu_button = ttk.Button(settings, text="NVIDIA kartını ve sürücüyü kontrol et", command=self.check_gpu)
        self.gpu_button.pack(anchor="w")
        self.update_path()
        self.refresh_buttons()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def text_panel(self, parent, text):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        widget = tk.Text(frame, wrap="word", bg="#191e2c", fg="#e2e7f3", insertbackground="white", font=("Segoe UI", 10), relief="flat", padx=16, pady=16, height=12)
        scroll = ttk.Scrollbar(frame, command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        widget.pack(fill="both", expand=True)
        self.set_text(widget, text)
        return widget

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def update_path(self):
        self.path_text.set("Seçili motor: " + self.config.get("launcher", "henüz seçilmedi"))

    def refresh_buttons(self):
        for button in (self.catalog_button, self.select_button, self.gpu_button):
            button.configure(state="disabled" if self.busy else "normal")
        self.install_button.configure(state="normal" if self.releases and self.release_box.current() >= 0 and not self.busy else "disabled")
        self.launch_button.configure(state="normal" if self.config.get("launcher") and not self.busy else "disabled")
        self.cancel_button.configure(state="normal" if self.busy else "disabled")
        self.release_box.configure(state="disabled" if self.busy else "readonly")

    def work(self, operation, finished):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.progress["value"] = 0
        self.refresh_buttons()

        def run():
            try:
                result = operation()
                self.events.put(("success", (finished, result)))
            except Exception as exc:
                self.events.put(("error", exc))

        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        # Worker threads never touch Tk. Keep draining bounded so UI stays usable.
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                message, amount = value
                self.status.set(message)
                self.progress["value"] = amount
            else:
                self.busy = False
                try:
                    if kind == "error":
                        self.status.set(str(value))
                        if not isinstance(value, core.Cancelled):
                            messagebox.showerror("İşlem tamamlanamadı", str(value), parent=self.root)
                    else:
                        finished, result = value
                        finished(result)
                except Exception as exc:
                    self.status.set(str(exc))
                    messagebox.showerror("Ayar kaydedilemedi", str(exc), parent=self.root)
                self.refresh_buttons()
        self.root.after(100, self.poll)

    def load_catalog(self):
        self.status.set("Hugging Face üzerindeki resmî katalog okunuyor…")

        def finished(releases):
            self.releases = releases
            self.release_box["values"] = [r.label for r in releases]
            self.release_box.current(0)
            self.status.set("CUDA sürümünü seç. Arşiv ve açılmış dosyalar için yeterli disk alanı ayır.")

        self.work(core.fetch_catalog, finished)

    def install_release(self):
        index = self.release_box.current()
        if index < 0 or self.busy:
            return
        release = self.releases[index]
        if not messagebox.askyesno("Resmî motoru indir", f"{release.label}\n\nDosya resmî w-okada deposundan indirilecek, SHA-256 ile doğrulanacak ve açılacak. Motor ayrıca kendi model dosyalarını ilk açılışta indirebilir. Devam edilsin mi?", parent=self.root):
            return

        def finished(path):
            self.store_launcher(path)
            self.status.set("Motor kuruldu; şimdi başlat ve 'Valorant’a bağla' adımlarını uygula.")

        self.work(lambda: core.install(release, self.home, lambda text, value: self.events.put(("progress", (text, value))), self.cancel), finished)

    def store_launcher(self, path):
        new_config = {**self.config, "launcher": str(path)}
        core.save_config(self.home, new_config)
        self.config = new_config
        self.update_path()
        self.refresh_buttons()

    def select_engine(self):
        filename = filedialog.askopenfilename(title="Resmî paketten start_http.bat veya vcclient.exe seç", filetypes=[("VCClient başlatıcısı", "*.bat *.exe")], parent=self.root)
        if not filename:
            return
        if Path(filename).name.lower() not in core.LAUNCHERS:
            messagebox.showerror("Başlatıcı tanınmadı", "start_http.bat veya vcclient.exe seç.", parent=self.root)
            return
        try:
            self.store_launcher(Path(filename).resolve())
            self.status.set("Mevcut motor seçildi. Bu dosya VoiceBridge tarafından indirilip doğrulanmadı.")
        except OSError as exc:
            messagebox.showerror("Ayar kaydedilemedi", str(exc), parent=self.root)

    def start_engine(self):
        if self.process is not None and self.process.poll() is None:
            messagebox.showinfo("Motor açık", "Başlattığımız motor hâlâ açık. Kendi motor penceresini kullan.", parent=self.root)
            return
        try:
            self.process = core.launch(Path(self.config["launcher"]))
            self.status.set("Başlatma komutu gönderildi. Hazır olduğunu motorun arayüzünden ve kulaklık testiyle doğrula.")
        except (OSError, core.SetupError) as exc:
            messagebox.showerror("Motor başlatılamadı", str(exc), parent=self.root)

    def check_gpu(self):
        self.gpu_status.set("NVIDIA bilgisi okunuyor…")
        self.work(core.gpu_report, self.gpu_status.set)

    def natural_preview(self):
        if os.name != "nt":
            messagebox.showinfo("Windows denemesi", "Yerel ses denemesini Windows bilgisayarında çalıştır.", parent=self.root)
            return
        if getattr(sys, "frozen", False):
            messagebox.showinfo("Kaynak paketi gerekiyor", "Bu deneme için güncel kaynak ZIP'ini çıkarıp DOGAL_SES_DENE.cmd dosyasını aç. Python 3.12 gerekir.", parent=self.root)
            return
        if self.preview_process is not None and self.preview_process.poll() is None:
            messagebox.showinfo("Deneme açık", "Ses denemesi penceresi zaten açık.", parent=self.root)
            return
        code = "from voicebridge.natural import main\ntry:\n main()\nfinally:\n input('Pencereyi kapatmak icin Enter...')\n"
        try:
            self.preview_process = subprocess.Popen([sys.executable, "-c", code, "local"], cwd=Path(__file__).resolve().parent.parent, creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError as exc:
            messagebox.showerror("Deneme açılamadı", str(exc), parent=self.root)

    def close(self):
        if self.busy:
            messagebox.showinfo("İşlem sürüyor", "Önce işlemi iptal et ve tamamlanmasını bekle. Ağ yanıtı için kısa bir bekleme gerekebilir.", parent=self.root)
            return
        self.closed = True
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
