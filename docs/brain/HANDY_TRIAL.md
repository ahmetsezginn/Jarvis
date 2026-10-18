# Handy bağımsız denemesi — 2026-10-18

Kullanıcı ilk seçeneği (Handy/Rust motoru) denemeyi istedi; kayıt davranışı açıklanınca
“Hazır uygulamada yerel kayıtla dene; ses buluta gitmesin.” yanıtını verdi. Bu izin yalnız
bu bağımsız denemenin yerel WAV kayıtları içindir. JARVIS'in üretim ses sınırı, model
varsayılanı ve kayıt saklamama kuralı değişmedi. Kişisel mikrofon testi ajan tarafından
başlatılmadı; doğruluk için kullanıcı denemesi bekleniyor.

## Kurulum ve ayarlar

- Resmî [Handy v0.9.8](https://github.com/cjpais/Handy/releases/tag/v0.9.8) Windows x64 paketi
  `.cache/handy-trial/app` altına `/S /PORTABLE /D=<absolute-app-dir>` ile çıkarıldı. Taşınabilir
  şablon kayıt defteri/kısayol/uninstaller eklemiyor. `portable` işareti ve `Data/` doğrulandı.
- Installer SHA256: `4212edb5658ec2867855fc2ee83ac16ec5bbad09db3c2da8d3d9d5f8bd5eeccc`;
  GitHub release digest eşleşti. Installer ve exe Authenticode durumu Valid (YNYNG LLC).
  Exe SHA256: `9a1d2246b64322cb334960a5b3830b0d125070735c355648c498076ec7c0a0ff`.
- Aynı sürümün kaynakları incelendi. Whisper yolu artık `transcribe-cpp 0.2.4` kullanıyor;
  önceki genel transcribe-rs önerisi bu sürümün Whisper yolu için güncel değildi.
  [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp/tree/v0.2.4) Rust bağlayıcısı
  sunar. Windows paketi CUDA değil **Vulkan** hızlandırmasıyla geliyor.
- Mevcut checksum-pinned `ggml-large-v3-turbo.bin` (1624555275 bayt,
  `1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69`) aynı NTFS diskte hardlink
  ile `Data/models` altına bağlandı; büyük model tekrar indirilmedi. Hardlink üzerindeki
  dosyanın içeriği değiştirilmemeli. JARVIS'in profili hâlâ small CPU.
- Dil `tr`, model `turbo`, GPU açık; cihazın backend tarafından bildirilen PCI kimliğiyle
  RTX 4070 seçildi. AMD iGPU'ya otomatik seçim bırakılmadı.
- Dinleme toggle: **Ctrl+Alt+Space** başlatır, aynı kombinasyon bitirir. Always-on ve autostart
  kapalı. Sonuç yalnız panoya kopyalanır; otomatik yapıştırma ve gönderme kapalıdır.
- Bulut post-processing kapalı; API anahtarı eklenmedi; post-process kısayolu boş bırakıldı.
  Güncelleme kontrolü kapalı ve launcher `HANDY_DISABLE_UPDATER=1` geçiriyor. Çalışma sırasında
  model indirmesi yok. Bu ayarlar harici API'siz yerel tanıma içindir; ağ paketi yakalama testi
  yapılmadı. Kurulum dosyaları GitHub'dan indirildi.
- ONNX ASR seçilmedi; VAD için saf Rust **Earshot** seçildi. Paket ONNX alternatifleri ve
  DLL'ini de içeriyor. Son süreç modülü kontrolünde `onnxruntime.dll` yüklüydü; dolayısıyla
  hazır paketin hiç ONNX runtime yüklemediği söylenemez. Seçili tanıyıcı transcribe-cpp Whisper,
  VAD Earshot; JARVIS'in ONNX üretim yolu açılmadı.
- **WAV ve transkript geçmişi yerel Data altında saklanır.** `history_limit=1`, retention
  `preserve_limit`; bu anlık sıfır kayıt garantisi değildir. Kaynakta retention `never`
  seçeneği kayıt saklamayı kapatmaz, eski kayıtların silinmesini durdurur. Bu yüzden kullanıcıya
  ayrıca soruldu. İlk hazırlık sonunda recordings dizini boştu.

Uygulama açıldı, Computer Use listesinde Handy penceresi döndü. Ayrıntılı UI yakalama için
Computer Use app approval zaman aşımına uğradı; ekran/ayar ekranı görüntüsü doğrulanmadı.
Dosyadan okunan ayarlar ve gerçek uygulamanın headless tanıma yolu doğrulandı.
Son başlatılan deneme PID22204; PID gelecekte geçerli varsayılmamalı.

## İlk performans ve doğruluk ölçümü

Kişisel olmayan aynı sekiz Tolga/Zira WAV, temiz ve düşük seviye/gürültülü varyantlarıyla
16 decode. Resmî 0.2.4 Python bağlayıcısı, paketin kendi imzalı DLL'ini yükledi; başka
ASR paketi kurulmadı. Bu yalnız değerlendirme aracıdır, Python mikrofon yolu/üretim sağlayıcısı
değildir. Ses 16 kHz mono; 30 saniye sınırı, her cümlede yeni decoder session, altı CPU thread.
GPU Vulkan1 RTX 4070. Dil her fixture'dan tr/en alınır; UI denemesi tr seçilidir.
Initial prompt, katalog ipucu, kelime değiştirme, LLM düzeltmesi ve VAD bu motor testinde yoktur.
Gürültü üretimi native testteki aynı LCG ve genlik formülünü kullanır; Python float ara
işlemlerinin Rust f32 ile bit düzeyinde eşitliği iddia edilmez.

| Ölçüm | Sonuç |
|---|---:|
| Model yükleme | 2,79s |
| İlk decode | 12,89s |
| Sonraki 15 decode medyanı | 0,282s |
| Sonraki decode aralığı | 0,264–0,344s |
| Test seslerinin uzunluğu | 2,055–4,535s |
| Toplam decode süresi (yükleme hariç) | 17,28s |
| Kritik kelime kaybı | **4/16** |
| Kelime edit hatası | **9/102 (%8,8)** |

Steam adının Türkçe sentetik telaffuzu iki olumlu ve iki olumsuz örnekte korunmadı;
gürültülü olumsuz örnekte “açma” da kayboldu. Diğer 12 örneğin transkripti referansla
kelime düzeyinde eşleşti. Bu sonuç **ASR kabulü değildir**. Önceki katalog ipuçlu small
profiline karşı daha doğru olduğu söylenemez; model, decoder, ipuçları ve cihaz birlikte
değişiyor. Sentetik özel ad telaffuzu ayrıca hata kaynağı olabilir. Mikrofon ve VAD akışı
bu hız ölçümünde yok; kullanıcı konuşmasında aynı süre/doğruluk garantisi verilmez.

Hazır uygulamanın kendi headless yolu da ayrıca çalıştırıldı:
3,565s Türkçe tablo arama fixture'ı, `turbo`, `--device-index 1`, üç tekrar.
Model yükleme 2577ms; decode süreleri **12978 /276 /270ms**, bağlı backend Vulkan1,
metin doğru: “Toplantı için hazırladığım tabloyu bulabilir misin?”
İlk açılış/yükleme/ilk çözümleme gecikmesini sıcak tekrar süresinden ayrı değerlendirin.

Son kontroller: Ruff check/format, PowerShell launcher sözdizimi, kelime edit mesafesi ve
fixture/gürültü kontrolleri geçti; `git diff --check` temiz. İlk ek metrik kontrolü büyük İ'nin
küçük harfe dönüşümündeki birleşen nokta sorununu buldu; yalnız değerlendirme normalizasyonu
düzeltildi ve tekrarlandı. Bu cümle kümesinin referans/transkriptleri büyük İ içermediğinden
yukarıdaki ölçüm sayıları etkilenmedi. Son açık süreçte pencere başlığı Handy ve ayarlar doğrulandı.

## Kullanıcı denemesi

1. Handy açıkken Ctrl+Alt+Space'e bas, normal konuş, tekrar basıp bitir. İlk tur daha uzun sürebilir.
2. Panodaki sonucu Ctrl+V ile bir metin alanında gör; otomatik gönderilmez.
3. Farklı konularda doğal cümleler dene; doğru söylediğin cümleyle yazılanı birlikte paylaş.
   Özellikle cümle başı/sonu ve olumsuzluk kaybını belirt. Kayıtlar yerel kalır.
4. Yeniden açmak için proje kökünde `./scripts/evaluation/start_handy_trial.ps1` çalıştır.

## Tekrarlama ve artefaktlar

```powershell
$python='C:/Users/szgnm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python scripts/evaluation/benchmark_handy.py
& .cache/handy-trial/app/handy.exe --list-devices
& .cache/handy-trial/app/handy.exe --transcribe-file target/voice-quality-fixtures/3.wav --model turbo --device-index 1 --repeat 3 --json
& services/brain/.venv/Scripts/ruff.exe check scripts/evaluation/benchmark_handy.py
& services/brain/.venv/Scripts/ruff.exe format --check scripts/evaluation/benchmark_handy.py
git diff --check
```

Yerel, Git dışı: installer, kaynak arşivleri, model bağlantısı, ayarlar ve
`.cache/handy-trial/benchmark-nvidia.json` (bütün sentetik ham transkriptler/süreler).
Kaynak bağlayıcılar resmî `v0.2.4/bindings/python/src/transcribe_cpp` dosyalarıdır;
model fixture üretimi ASR_QUALITY.md'de. Bu takipte JARVIS Rust/Brain/Qt üretim kodu,
bağımlılıkları veya ana model değiştirilmedi; geniş üretim testleri yeniden çalıştırılmadı.
