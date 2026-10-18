# Handy motorunun JARVIS'e entegrasyonu — 2026-10-18

Kullanıcı ayrı uygulama istemediğini, hazır çözümün JARVIS'e taşınmasını istediğini
açıkladı. Windows üretim ses yolu artık Handy'nin kullandığı **transcribe.cpp 0.2.4**
motorunu resmî Rust bağlayıcısıyla doğrudan Native Core içinde çalıştırır. Handy uygulaması,
panosu, Python ASR süreci veya HTTP/API sunucusu çağrılmaz. Önceki bağımsız deneme tarihseldir.

## Akış ve varsayılanlar

Qt -> JarvisCoreClient -> Named Pipe -> speech tool validation/policy -> Rust AudioService
-> mevcut CPAL/WASAPI yakalama + Silero GGML VAD -> transcribe-cpp -> son transkript -> normal
Brain oturumu. Hold-to-talk, Auto turn/preroll/silence, iptal/lease sınırları ve SAPI bitişini
bekleyen rearm davranışı korunur. Ham PCM Rust belleğindedir; JSON'a/diske yazılmaz. Ayrı Handy
denemesine verilen yerel WAV izni üretime aktarılmadı. Üretime ONNX runtime eklenmedi.

Bu 8 GB host için varsayılan: `JARVIS_SPEECH_ENGINE=transcribe-cpp`,
`JARVIS_WHISPER_PROFILE=large-v3-turbo-q5_0`, `JARVIS_SPEECH_DEVICE=gpu`.
Vulkan cihazları native olarak bulunur; DeviceType::Gpu olan en büyük dedicated GPU seçilir,
iGPU seçilmez. Bu hostta RTX 4070. Model 574041195 bayt, SHA256
`394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2`.
Genel katalog yazım bağlamı yalnız initial prompt olarak kalır; kelime değiştirme yapılmaz.
En/tr/auto seçenekleri, çeviri kapalı oluşu ve 2000 karakter çıktı sınırı korunur.
Explicit dil seçildiğinde motor otomatik dil etiketi döndürmese de UI seçilen dili görür.

Her çağrıda yeni model/session açılır ve sonuçtan sonra GPU ağırlıkları bırakılır. Yalnız
checksum/size doğrulanmış okuma tanıtıcısı cache'lenir; Windows share_mode=READ ile bu süre
boyunca dosya değiştirme/silme engellenir. Böylece dosyadan native yükleme doğrulamayla yarışmaz.
İlk çağrı hash/model/shader hazırlığı nedeniyle uzundur. Sonrakilerde yeniden yükleme maliyeti,
ana modelle VRAM paylaşabilmek için kabul edildi. Bu erken uygulama ısınma optimizasyonu değildir.
GPU bulunamaması veya bildirilen boş belleğin model+384MiB sınırından düşük olması hatadır;
sessiz CPU/model değişimi yoktur. Boş bellek değeri sürücü anlık görüntüsüdür, OOM garantisi değildir.

Explicit CPU: `JARVIS_SPEECH_DEVICE=cpu`. Tarihsel karşılaştırma:
`JARVIS_SPEECH_ENGINE=whisper-cpp`, `JARVIS_WHISPER_PROFILE=small`.
Eski `JARVIS_WHISPER_DECODER` yalnız whisper-cpp provider'ına aittir; yeni motorun kendi
decoder varsayılanları ve bounded Whisper extension kullanılır. Tanıyıcı etiketi hem status
hem finish sonucunda gerçek motor/model/seçilen cihazı gösterir.

## Hazırlama / derleme

Windows x64 MSVC C++ araçları, mevcut desktop CMake/libclang paketleri gerekir. Proje kökünde:

```powershell
python scripts/models/provision_speech.py --profile large-v3-turbo-q5_0
./scripts/models/provision_transcribe.ps1
./scripts/shell/build-voice.ps1
jarvis -Desktop
```

`provision_transcribe.ps1` eldeki `.cache/handy-trial/app` dosyalarını kullanır; yoksa yalnız
açık kurulum sırasında sabit Handy 0.9.8 Windows paketini indirip taşınabilir olarak çıkarır.
Installer checksum'u, transcribe.dll yayıncı imzası ve **bütün** alınan DLL'lerin repository'deki
`transcribe-runtime-pins.json` SHA256 değerleri doğrulanır. transcribe/ggml/VC runtime dosyaları
alınır; Handy exe, ONNX DLL/modeli veya ses arşivi üretim paketine alınmaz.
MSVC dumpbin/lib, DLL'nin C ABI export'larından import library üretir. Cargo'nun resmî
`TRANSCRIBE_DIR` prebuilt-prefix sözleşmesi için link manifesti oluşturulur.
`.cargo/config.toml` bu prefix'i `models/transcribe-runtime` altında gösterir; Cargo native
DLL'leri Core ve test exe'lerinin yanına stage eder. Derleme için Vulkan SDK indirmek gerekmez.
Motor/binding sürümleri 0.2.4'e pinlidir; çalışma sırasında indirme yapılmaz.
Kaynaklar: [Handy 0.9.8](https://github.com/cjpais/Handy/tree/v0.9.8),
[transcribe.cpp 0.2.4](https://github.com/handy-computer/transcribe.cpp/tree/v0.2.4).

## Doğrulama ve sınırlar

- Rust ordinary: **97 geçti /7 opt-in atlandı**. Yeni testler checksum/size bozulmasını,
  doğrulanmış dosyanın yazmaya kapalı kalmasını, uzun girdi/geçersiz dil/çıktı kontrol
  karakterlerinin reddini kapsar. Mevcut policy/IPC/ses testleri geçti.
- Qt sözleşme/arayüz: **22 geçti /4 opt-in atlandı**, 2,43s. Kişisel mikrofon açılmadı.
- Gerçek native provider, ortak VAD dahil: Türkçe tablo isteği, İngilizce spreadsheet isteği
  ve Auto Türkçe selamlaşma **3/3** doğru, 37,30s (ilk tur 34,81s; diğerleri 1,17/1,32s).
  İlk tur süreleri farklı süreçlerde 14–35s aralığında değişti; sıcak tur garantisi değildir.
- Aynı 16 temiz/gürültülü sentetik örneğin yeni Q5 GPU yolunda ilk ölçümü: **4 kritik hata**,
  **9/102 kelime hatası (%8,8)**; 30,57s. İlk tur 14,46s, sonraki turlar yaklaşık 1,01–1,17s.
  Steam adının Türkçe sentetik telaffuzu ve gürültülü olumsuzluk başarısız kalır. Bu test
  bilerek başarısızdır; kişisel ses doğruluğu veya genel asistan kabulü ilan edilmez.
  İlk ölçümün eski test rapor etiketi yanlış small/beam varsayıyordu; rapor artık gerçek
  recognizer etiketini okur. Bu yalnız tanısal metadata düzeltmesidir.
  Son seri tekrar doğru Q5/transcribe-cpp/RTX4070 etiketini doğruladı: yine 4 kritik hata,
  9/102 kelime hatası; 28,41s toplam (13,96s ilk tur; diğerleri 0,90–1,02s).
- Gerçek Auto rolling VAD -> TurnDetector/preroll/endpoint -> yeni ASR yolu: 6 sentetik
  denemenin 2 selamlaşması geçti, 4 uygulama adı/olumsuzluk örneği başarısız kaldı (33,16s).
  Süreler 2200/2900–3000/4100ms; bu örneklerde yanlışlar tam PCM ile de aynıdır. Auto kalite
  kabulü başarısızdır; test gizlenmedi veya gevşetilmedi.
- Gürültü/sessizlik + genel sözlük: **1 geçti /0,07s**. Kayıt/agent eylemi yoktur.
- Gerçek 9B modelin mevcut **32 GPU katmanı** ayarı değiştirilmedi. Önce token üretildi,
  model yüklü tutulurken üç native ASR örneği geçti, sonra tekrar token üretildi.
  GPU kullanımı önce 7527MiB, izlenen tepe 7594MiB, ASR sonrasında 7399MiB;
  ASR süreleri 14,44 /1,21 /1,16s, toplam 16,81s. Bu sıralı half-duplex kaynak paylaşımıdır;
  aynı anda ASR+LLM inference veya her masaüstü yükünde sığma garantisi değildir.
- Rust fmt/Clippy tüm hedeflerde `-D warnings` geçti. Derleme mevcut sandbox dışı libclang
  erişimi gerektirdi; ACL veya sistem ayarı değiştirilmedi. OneDrive bir test exe'sinde
  geçici LNK1104 verdi; seri tekrar kullanıldı. Ayrı Handy süreci ve eski proje Core'u kapatıldı.
- Genel Brain dosya/bağlam kabulünün önceki başarısızlıkları bu entegrasyonla çözülmüş sayılmaz.

Yeni Core gizli PID28784 olarak başlatıldı. Gerçek Named Pipe `speech_status`, doğrulanmış
Q5 modelin mevcut olduğunu, transcribe-cpp/RTX4070 Vulkan etiketini ve `recording=false`
durumunu döndürdü. Native süreçte transcribe/ggml DLL'leri görüldü, ONNX DLL'i yüklenmedi.
Varsayılan giriş Windows'un Microphone Array (AMD Audio Device) rotasıdır; aygıt tercihi
kullanıcı tarafından UI'da seçilebilir. Kişisel mikrofon açılmadı.

Kişisel mikrofon doğruluğunu kullanıcı doğal konuşmasıyla yeniden sınamalıdır. Hız ölçümleri
CV'ye özel üretim kuralı, fine-tuning veya LLM transkript onarımı içermez.

## Yeniden çalıştırma

```powershell
$env:JARVIS_ASR_EVAL="$pwd/target/voice-quality-fixtures"
$env:JARVIS_ASR_EVAL_HINTS='1'
cargo test --test audio_pipeline real_handy_provider_transcribes_bilingual_and_auto_language -- --ignored --nocapture
cargo test --test audio_pipeline real_whisper_quality_comparison -- --ignored --nocapture
cargo test --test audio_pipeline real_whisper_spelling_context_does_not_create_words_from_noise -- --ignored --nocapture
cargo test --lib real_auto_turn_retains_short_utterances -- --ignored --nocapture
cargo test -p jarvis-core -j 2
cargo clippy --all-targets -j 2 -- -D warnings
cargo fmt --all --check
```

Build ortamı için `scripts/shell/build-voice.ps1` veya ASR_QUALITY.md'deki CMAKE/LIBCLANG_PATH
değerleri kullanılır. Yerel sonuçlar: `target/asr-native-handy-quality.log`,
`target/asr-native-handy-auto.log`, `target/handy-llm-memory.json`; fixtures önceki
ASR_QUALITY.md'deki sentetik üretimdir.
İndirilen native/model dosyaları Git dışında kalır. Commit/push yapılmadı.
