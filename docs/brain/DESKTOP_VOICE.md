# Qt masaüstü ve yerel ses — 2026-10-16

Son normal yanıt/otomatik dönüş düzeltmesi ve gerçek QML/ajan testi:
[VOICE_AND_DISCOVERY_FOLLOWUP.md](VOICE_AND_DISCOVERY_FOLLOWUP.md). Aşağıdaki ilk iki kısa
sesin duyulması, normal ajan yanıtının otomatik modda kesilmediğini tek başına doğrulamıyordu.

## Güncel takip: dil seçimi ve duyulmayan yanıt

Kullanıcı metin yanıtının göründüğünü fakat hata olmadan ses çıkmadığını ve sesinin yanlış
çözüldüğünü bildirdi. İncelemede QML açılışının tanıyıcıyı İngilizceye zorladığı bulundu.
Bu satır kaldırıldı; Listen seçicisi artık gerçek Auto durumuna bağlıdır. Kısa Türkçe/İngilizce
ifadelerde açık dil seçimi kullanılabilir. `speech_finish`, Whisper'ın tespit ettiği dili de
döndürür ve Qt bunu gösterir. Whisper small ağırlıkları/Greedy decoder değiştirilmedi; kişisel
mikrofon örneği olmadan model kapasitesinin yetersiz olduğu veya tüm tanıma sorununun çözüldüğü
sonucuna varılmadı.

Önceki SAPI kodu yalnızca İngilizce sesi arıyordu. Bu bilgisayarda standart SAPI listesinde Zira,
OneCore kategorisinde ise Türkçe Tolga bulundu. Rust `audio/sapi.rs` iki kurulu kategoriyi
salt okunur keşfeder, LCID değerlerini baştaki sıfırları ve farklı ülke kodlarını koruyarak
çözümler. Registry kopyalama/yazma, yeni ses paketi veya ONNX eklenmedi. `speech_speak` artık
`language: en|tr` (varsayılan en) ve isteğe bağlı `output_device_index: 0..31` kabul eder;
token kimlikleri Rust'ta kalır. Dil/aygıt yoksa açık hata verir. SAPI nesnesinin kendi ses
seviyesi 100'dür; Windows genel/uygulama mikseri değiştirilmez. Çağrılar aynı validation,
policy, executor ve Named Pipe yolunu kullanır.

Qt'de **Listen** tanıma dilini, **Voice** telaffuz sesini, **Output** ses çıkışını seçer.
**Test voice** seçilen dilde sabit bir cümle okur; ajan görevi çalıştırmaz ve mikrofon açmaz.
Gerçek ses ve çıkış adı arayüzde görünür. Voice seçimi mevcut İngilizce ajan metnini çevirmez.
Bu hostta varsayılan SAPI çıkışı `Speaker (Realtek(R) Audio)`; `Hoparlör (OMEN Cam & Voice)`
ayrıca seçilebilir. Kullanıcı canlı İngilizce ve Türkçe denemelerin **ikisini de duyduğunu**
sonradan doğruladı. Böylece test edilen Qt → Core → Realtek yolunda fiziksel duyulma da
doğrulandı. Bu kanıt kişisel mikrofon tanıma doğruluğunu veya önceki sessizliğin kesin kök
nedenini belirlemez; yalnızca konuşmanın kuyruğa alınmasına dayanılarak duyulma iddia edilmedi.

### Bu takipte ölçülenler

- Brain + Qt ordinary: **511 geçti /166 opt-in atlandı**, 2,44s.
- Rust ordinary: **89 geçti /3 opt-in atlandı**; argüman/policy sınırları ve gerçek dile/aygıta
  iletim testi dahil. Ruff check/format ve Rust fmt/Clippy geçti.
- Gerçek Qt yanıtı → Named Pipe → Rust → SAPI: **2 geçti /17,73s**. İngilizce Zira ve Türkçe
  Tolga seçildi, Realtek'e yönlendi, speaking başlangıcı ve gerçek bitişi gözlendi.
- Altı farklı sentetik SAPI konuşması, açık dil ve Auto ile **12 decode /76,30s** geçti.
  Doğal soru, kayıp sunum, alternatif isteme ve iki dilde olumsuz açma ifadeleri korundu.
  Bu testler kişisel mikrofon, oda gürültüsü veya kullanıcının aksanını kapsamıyor. Mikrofon
  sesi kaydedilmedi; yalnızca sabit test cümleleri `target/voice-bilingual-fixtures` altında
  developer WAV çıktısı olarak üretildi ve hiçbir transkript ajana gönderilmedi.

Core yeniden derlenip gizli olarak başlatıldı (PID 26152); açık eski desktop kapatılıp
`jarvis -Desktop` ile yeniden açılmalı. İngilizce/Türkçe test düğmesi ve doğru Output seçimiyle
fiziksel duyulma ayrıca kullanıcı tarafından sınanabilir. Commit/push yapılmadı.

Kesin komutlar (proje kökü, mevcut yerel ortam):

```powershell
$python='C:/Users/szgnm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH="$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages;$pwd/services/desktop/.venv/Lib/site-packages"
$env:CMAKE="$pwd/services/desktop/.venv/Lib/site-packages/cmake/data/bin/cmake.exe"
$env:LIBCLANG_PATH="$pwd/services/desktop/.venv/Lib/site-packages/clang/native"
$env:CXXFLAGS='/O2'
# Sadece yolu doğrulanmış proje Core'u durdurulmuşken:
cargo test --manifest-path core/native/Cargo.toml -j1
cargo test --manifest-path core/native/Cargo.toml --test audio_pipeline -j1
cargo fmt --manifest-path core/native/Cargo.toml --check
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
./scripts/evaluation/make_voice_fixtures.ps1
$env:JARVIS_SPEECH_ROUNDTRIP="$pwd/target/voice-bilingual-fixtures"
cargo test --manifest-path core/native/Cargo.toml --test audio_pipeline real_whisper_bilingual -- --ignored --nocapture
& $python -m ruff check services/brain scripts services/desktop
& $python -m ruff format --check services/brain scripts services/desktop
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_BACKEND='software'
$testTemp=Join-Path $pwd ('target/voice-bilingual-check-'+[guid]::NewGuid().ToString())
& $python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider --basetemp $testTemp -q
# Güncel Core serve açıkken; yalnızca hoparlör:
$env:JARVIS_RUN_VOICE_DEVICE_LIVE='1'
& $python -m pytest scripts/tests/test_desktop_qt.py -k actual_qt_reply -o addopts= -p no:cacheprovider -q -s
git diff --check
```

Loglar: `target/voice-bilingual-{rust,contract,python,asr,qt-live,clippy}.log`.
İlk Rust denemesi çalışan Core exe kilidi nedeniyle durdu; yalnızca yolu doğrulanmış proje
süreci durdurularak tekrar geçirildi. Qt testi açılıştaki İngilizce zorlamasını yakaladı ve
satır kaldırıldıktan sonra geçti. Önceki sonuçlar aşağıda tarihsel olarak korunur.
Son dar sözleşme testi de ilk linker dosya kilidi sonrası tekrarında geçti; ACL veya güvenlik
ayarları değiştirilmedi.

## Güncel takip: bas-konuş düzeltmesi ve otomatik konuşma

Kullanıcının bildirdiği `A buffer underrun or overrun occurred` hatası CPAL `ErrorKind::Xrun`
bildirimidir. Önceki kod her stream bildirimini fatal saklayıp `speech_finish` sırasında tüm
kaydı reddediyordu. Geçici Xrun, otomatik rota değişimi ve zamanlama uyarıları artık kalıcı
cihaz hatalarından ayrılır. Ses callback'i mutex beklemez; sınırlı, bloklamayan kuyrukla native
worker'a mono ses iletir. Tekil Xrun kaydı düşürmez; sekiz Xrun veya iç kuyruk kaybı olduğunda
kayıt reddedilir ve ajana metin gönderilmez. Cihazın kopması/izin hatası fatal kalır.

**Auto conversation** isteğe bağlıdır ve başlangıçta kapalıdır. Yerel Silero v6.2.0 GGML VAD,
mevcut whisper.cpp üzerinde iki CPU thread ile çalışır; ONNX eklenmedi. 960ms kayan model
penceresi, 800ms ses ön tamponu, 200ms konuşma başlangıcı ve 900ms sessizlik bitişi kullanılır.
Bekleme sesi sınırlı bellekte tutulur; uzun sessizlik belleği büyütmez. Tamamlanmış son metin
aynı JarvisBrain oturumuna gider. Yeni bir komut yönlendiricisi/uygulama yeteneği yoktur.

Üç sürekli görünür animasyon gerçek duruma bağlıdır: beklemede yörünge/nabız, dinlerken giriş
seviyesine bağlı yeşil çubuklar, yanıt okurken mor/camgöbeği akış. ASR/model bekleme ayrı bir
processing durumudur. Yeni kayıt açılırken henüz dinliyormuş gibi gösterilmez.
`speech_poll(recording_id?)`, mevcut validation/policy/executor yolundan geçen Low-risk bir
araçtır; UUID doğrulaması, faz/seviye/Xrun bilgisi ve SAPI'nin gerçek konuşma durumunu döndürür.
PCM JSON kanalına girmez. Arayüz ses kontrollerini tek kuyrukta işler; eski kayıt/çıktı cevapları
iptalden sonra durumu yeniden açamaz. Kontrolcü/cihaz testleri bu yarışları sınar.

Konuşma bittiğinde mikrofon kapanır; ASR, ajan ve sesli yanıt sırasında kapalı kalır. SAPI'nin
gerçek bitişi görüldükten sonra 300ms yankı kuyruğu payıyla tekrar bekler. Yanıtlar sessizse
metin yanıtından sonra döner. **End conversation** veya Escape otomatik modu kapatır. Altı
saniye heartbeat gelmezse aktif kayıt ve bekleyen tamamlanmış PCM bırakılır. Süre sınırına
ulaşan cümle kesilip çalıştırılmaz; manual UI deadline iptal eder, native üst sınır da reddeder.
ASR başladıktan sonra CPU decode tamamlanabilir; iptal sonucu düşürür, herhangi bir görev başlatmaz.

Silero artefaktı: [resmî ggml-org modeli](https://huggingface.co/ggml-org/whisper-vad/blob/c5c26827b67dfd053856f92e824e14fdcc123daf/ggml-silero-v6.2.0.bin),
revision `c5c26827b67dfd053856f92e824e14fdcc123daf`, 885.098 bayt, SHA256
`2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987`.
`scripts/models/provision_speech.py` artık Whisper ve VAD'ı açık kurulumda sağlar; başlangıçta
indirme yoktur. Modeller Git dışındadır. Rust model yüklemede hash doğrular.

### Bu takipte doğrulananlar

| Kontrol | Sonuç |
|---|---|
| Rust ordinary | 88 geçti / 2 opt-in atlandı |
| Gerçek VAD + Whisper, kamuya açık ses | 1 geçti / 19,21s; sessizlik ve üç gürültü seviyesi reddedildi |
| Qt + Brain ordinary | 474 geçti / 158 atlandı (=458 Brain + 16 Qt) |
| Gerçek Qwen worker dahil Qt | 17 geçti / 14,37s |
| Gerçek mikrofon / SAPI | 4 geçti / 49,88s |
| Ruff check/format, Rust fmt/Clippy -D warnings, build | geçti |

Gerçek mikrofon kaydı 12.050ms sürdü ve bir Xrun bildirimiyle başarıyla tamamlandı. Transkript
metni yazdırılmadı, diske kaydedilmedi veya ajana gönderilmedi; yalnızca uzunluğu kontrol edildi.
Otomatik cihaz testinde waiting/listening/complete fazları gözlendi; ses iptal edilerek atıldı.
Yedi saniye heartbeat kesintisi, tamamlanmış sesin de silinmesini doğruladı. SAPI testi gerçek
speaking=true ve sonra false gördü; hoparlörün akustik kalitesi ölçülmedi.

Kamuya açık JFK kaydının ilk doğal duraklaması 3.200ms'lik tur oluşturdu; bunun transkripsiyonu
bilinen örnek sözcüğüyle doğrulandı. Test, tüm konuşmanın tek tur olmasını beklemez. Gerçek VAD
testi sentetik sessizlik ve beyaz gürültüyü de kullanır; gerçek odadaki tüm gürültüleri veya tüm
konuşmacıları kapsadığı iddia edilmez. Qt testleri gerçek düğmeye mouse press/release, hızlı
bırakma, açılırken/transkripsiyonda iptal, eski çıktı cevabı, süre sınırı ve sesin gerçek bitişine
bağlı yeniden başlatmayı kapsar. Üç fazın ekran görüntüsü `target/voice-*.png` ile incelendi.

İlk toplu pytest denemesinde eski sistem geçici dizinine erişim hataları oluştu; yeni proje içi
`--basetemp` ve kapalı pytest cache ile 474 test geçti. ACL veya güvenlik ayarı değiştirilmedi.
Gerçek cihaz testi önce, erken tamamlanmış sesin lease dışına çıkabildiğini buldu; tamamlanan
PCM'nin de süre aşımında silinmesi uygulanıp dört cihaz testi yeniden geçirildi.

### Tekrarlanan komutlar

Proje kökünde, bu bilgisayardaki mevcut yorumlayıcı ve paket hedefleriyle:

```powershell
$python = 'C:/Users/szgnm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH="$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages;$pwd/services/desktop/.venv/Lib/site-packages"
$env:CMAKE="$pwd/services/desktop/.venv/Lib/site-packages/cmake/data/bin/cmake.exe"
$env:LIBCLANG_PATH="$pwd/services/desktop/.venv/Lib/site-packages/clang/native"
$env:CXXFLAGS='/O2'
cargo fmt --manifest-path core/native/Cargo.toml --check
cargo test --manifest-path core/native/Cargo.toml -j1
$env:JARVIS_SPEECH_FIXTURE="$pwd/target/voice-public-jfk.wav"
cargo test --manifest-path core/native/Cargo.toml --lib real_vad -- --ignored --nocapture
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
# Projenin çalışan Core süreci durdurulmuşken:
cargo build --manifest-path core/native/Cargo.toml -j1
& $python -m ruff check services/brain scripts services/desktop
& $python -m ruff format --check services/brain scripts services/desktop
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_BACKEND='software'
$testTemp=Join-Path $pwd ('target/voice-check-'+[guid]::NewGuid().ToString())
& $python -m pytest scripts/tests/test_desktop_qt.py services/brain/tests -o addopts= -p no:cacheprovider --basetemp $testTemp -q
# Güncel Core serve açıkken, gerçek ayrı agent worker:
$env:JARVIS_RUN_DESKTOP_LIVE='1'
& $python -m pytest scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider -q -s
$env:JARVIS_RUN_VOICE_DEVICE_LIVE='1'
& $python -m pytest scripts/tests/test_voice_device_live.py -o addopts= -p no:cacheprovider -q -s
```

Sonuçlar `target/voice-auto-{rust-tests,vad,clippy,build,python-tests,qt,device}.log` içindedir.
Core yeniden derlendi/serve olarak başlatıldı. Açık eski arayüz yeniden açılmalıdır. Commit/push
yapılmadı; ilk desktop teslimindeki kaydedilmemiş değişiklikler korundu. Etkileşimli açılıştan
önce offscreen render ortam değişkenlerini kaldırın veya yeni terminal kullanın.

Bu sürüm sıralı dinleme/konuşmadır. Wake word, sesle araya girme, akustik yankı giderme ve
Kokoro yoktur. Bilgisayar becerilerinin model kabulü hâlâ önceki 53/56 sonucudur; bu ses testleri
ajanın üç bilinen anlamsal sorununu düzeltmiş sayılmaz.

## Tarihsel: ilk Qt ve bas-konuş teslimi

Kullanıcı mevcut yeteneklerin yeterli olduğunu belirterek Qt arayüzü ve kendi bilgisayarına
uygun ilk yerel ses sürümünü onayladı. Bu teslim yeni dosya/uygulama yeteneği eklemez ve
önceki gerçek-model kabulündeki üç anlamsal hatayı çözülmüş saymaz.

## Teslim

- `jarvis -Desktop`: Qt Quick/QML + PySide6 6.10.3. `jarvis` terminal davranışını korur.
- Ayrı sabit Python worker sürecinde aynı JarvisBrain oturumu. Model GUI döngüsünü kilitlemez.
- Sohbet, dosya/uygulama kartları, gerçek kapsam/kısmi tarama bilgisi, mikrofon ve dil seçimi.
- Basılı tutarak kayıt, bırakınca yalnızca tamamlanmış metni gönderme. İngilizce varsayılan;
  Türkçe ve otomatik tanıma da seçilebilir. En fazla 30 saniye; iptal edilen ses çözülmez.
- Rust CPAL/WASAPI mikrofon ve Windows SAPI seslendirme. Çıktı kayıt başlamadan durdurulur.
- whisper-rs 0.16.0 / whisper.cpp ile CPU üzerinde multilingual Whisper small, en fazla altı
  thread. Bu ses katmanı native inference kullanır; görev aklı Python'da kalır.
- Ses kayıtları diske yazılmaz. PCM Rust belleğinde kalır ve JSON pipe'a konmaz. Ayrı bulk
  ses protokolüne bu sürümde ihtiyaç yoktur. Modele ses araçları sunulmaz.
- UI dosya yollarını kartlarda gösterebilir; model ve TTS tam yol listesi almaz. Yeni keşifte
  ses kısa sayfa özeti verir. Kartlar yeni sayfa belirteci ve özel 120 saniyelik bağlara bağlıdır.
- `speech_status/start/finish/cancel/speak/stop` kayıtlı Rust araçlarıdır. Her biri argüman
  doğrulama -> policy -> executor -> servis -> Windows adaptörü yolunu izler. Status read-only,
  diğerleri low-risk. SAPI yalnızca düz metin okur; XML/dosya çalıştırma bayrakları kullanılmaz.

İlk TTS motoru Windows'un kurulu İngilizce sesi, bulunamazsa OS varsayılanıdır. Kokoro/PyTorch
kurulmadı ve Brain ortamına eklenmedi. Konuşma sonu bas-konuş bırakmayla belirlenir; enerji ve
Whisper no-speech filtresi sessizliği eler. Silero VAD, wake word, gerçek full-duplex kesme ve
akustik yankı giderme bu sürümün tamamlanmış özellikleri değildir. Mikrofon kendiliğinden
arka planda açılmaz. İlk tanıma model yükleme/hash doğrulaması nedeniyle gecikebilir.

## Yerel artefakt ve kurulum

| Alan | Değer |
|---|---|
| Model | `ggerganov/whisper.cpp`, `ggml-small.bin` |
| Revision | `5359861c739e955e79d9a303bcbc70fb988958b1` |
| Boyut | 487.601.967 bayt |
| SHA256 | `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b` |
| Yerel dosya | `models/whisper-small/ggml-small.bin` |
| Sağlama | `scripts/models/provision_speech.py`, yalnızca açık geliştirme işlemi |

Sağlama ve ilk native yükleme boyut/SHA256 doğrular; Unicode Windows yolu için model doğrulanmış
bellek tamponundan yüklenir. Başlangıçta indirme veya model fallback yoktur. Qt paketleri ayrı
`services/desktop/.venv/Lib/site-packages` hedefindedir; bu dizin ayrı paket hedefidir, yeni
bir Python yorumlayıcısı oluşturulduğu anlamına gelmez. Mevcut Brain paketleri korunur.
Qt Essentials ve Addons birlikte kurulur. CMake 4.2.3 ve libclang 18.1.1 yalnızca geliştirme
derlemesi içindir. Rust bağımlılıkları Cargo.lock'a kaydedildi. Tüm ağırlıklar ve paketler Git dışı.

Kurulum/başlatma komutları [masaüstü README](../../services/desktop/README.md) içindedir.
Kısıtlı ajan terminali ilk ağ/yerel DLL erişimlerini engelledi; izinli ortamda kurulum ve
testler tamamlandı. Güvenlik/ExecutionPolicy veya dosya ACL ayarı değiştirilmedi. Native
paketin Linux için hazır bağları Windows'ta boyut hatası verdi; Windows bağları libclang ile
üretildi. Üçüncü taraf kaynak dosyası yamalanmadı.

Whisper debug decoder loglarının kelime yazabildiği testte görüldü; provider logging hooks
etkinleştirilerek bu loglar kapatıldı. Hatalar hâlâ typed Result/Core audit olarak görünür.
Son örnek test logunda yalnızca testin açıkça yazdığı kamuya açık örnek metni bulunur; decoder
token dökümü yoktur. Gerçek kişisel ses içeriğiyle transkripsiyon testi yapılmadı.

## Son doğrulama

| Kontrol | Sonuç |
|---|---|
| Brain ordinary regresyonları | 458 geçti / 157 opt-in atlandı |
| Yeni desktop oturum testleri | 6 geçti, Brain toplamının içinde |
| Rust ordinary testleri | 83 geçti / 1 opt-in atlandı |
| Gerçek CPU Whisper örneği | 1 geçti; ilk model yükleme dahil 14,58 saniye |
| Qt offscreen + gerçek Qwen worker | 6 geçti / 8,70 saniye |
| Ruff check/format, Rust fmt/Clippy | geçti |
| Native debug build | geçti |
| PowerShell başlatıcı/build betiği parser kontrolü | geçti |

Qt testleri hızlı bırakma, mikrofon açılırken iptal, transkripsiyon sırasında iptal sonrası
geç metni atmama, sessizlikte ajan çağırmama, QML kart çizimi ve gerçek ayrı Qwen sürecini
sınar. Son QML ekran görüntüsü `target/desktop-preview.png` üzerinden gözle incelendi:
Unicode fontlar, koyu tema, kapsam/eksik tarama bilgisi ve kartlar okunur. Görsel yüzey
offscreen'dir; kullanıcının diğer uygulamalarına UI otomasyonu yapılmadı.

Gerçek Named Pipe cihaz testi üç mikrofon gördü (USB BSX, AMD, OMEN). Varsayılan mikrofon
yarım saniye açılıp iptal edildi; ardından `recording=false` doğrulandı. Bu kaydın içeriği
çözülmedi veya dosyaya yazılmadı. SAPI test cümlesini kuyruğa aldı ve stop başarılı oldu;
fiziksel hoparlör sesinin duyulduğuna ilişkin akustik ölçüm yapılmadı.
Core `system_status` yaklaşık 32 GB RAM bildirdi; mevcut 8 GB GPU profilinde Qwen korundu.

Whisper testi resmî v1.7.6 örneği `samples/jfk.wav` kullanır: 352.078 bayt, SHA256
`59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e`.
Yalnızca bu kamuya açık 11 saniyelik örneğin doğru çıktığı ölçüldü. Bu sonuç gerçek kullanıcının
aksanı, gürültüsü, karışık dilli dosya adları veya bütün olası sesli komutlar için kabul değildir.
Mevcut ajan genel kabulü de önceki rapordaki 53/56 seviyesindedir; burada yeniden ölçülmedi.

Derleme sırasında çalışan Core exe kilidi ve bazı geçici LNK1104 test dosyası kilitleri görüldü.
Yolu/PID'si doğrulanmış proje Core'u güncellendi; son sıralı test/build başarılı oldu. Proje
Core'u önceki çalışma durumunu korumak için arka planda yeniden başlatıldı. Diğer süreçlere
dokunulmadı. Başlangıç çalışma ağacı `main...origin/main` temizdi; bu teslim commit/push yapmadı.

## Kullanılan denetim komutları

Bu makinede mevcut taban Python ve venv paketleri:

```powershell
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages;$pwd/services/desktop/.venv/Lib/site-packages"
& $taskPython -m ruff check services/brain scripts services/desktop
& $taskPython -m ruff format --check services/brain scripts services/desktop
& $taskPython -m pytest services/brain/tests -o 'addopts=' -q
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_QUICK_BACKEND = 'software'
$env:JARVIS_RUN_DESKTOP_LIVE = '1'
& $taskPython -m pytest scripts/tests/test_desktop_qt.py -o 'addopts=' -q -s
$env:CMAKE = "$pwd/services/desktop/.venv/Lib/site-packages/cmake/data/bin/cmake.exe"
$env:LIBCLANG_PATH = "$pwd/services/desktop/.venv/Lib/site-packages/clang/native"
$env:CXXFLAGS = '/O2'
cargo fmt --manifest-path core/native/Cargo.toml --check
cargo test --manifest-path core/native/Cargo.toml -j 1
$env:JARVIS_SPEECH_FIXTURE = "$pwd/target/voice-public-jfk.wav"
cargo test --manifest-path core/native/Cargo.toml --test audio_pipeline real_whisper -- --ignored --nocapture
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
cargo build --manifest-path core/native/Cargo.toml -j 1
git diff --check
```

Örnek WAV indirilecekse yalnızca resmî
[sabit sürüm dosyası](https://raw.githubusercontent.com/ggml-org/whisper.cpp/v1.7.6/samples/jfk.wav)
kullanılır; normal testler bu dosyayı indirmez. Loglar `target/voice-*.log` ve
`target/desktop-qt-live.log` altındadır. Mikrofon ve hoparlör canlı denemeleri bu oturumda
explicit Core araç istekleriyle yapıldı, normal pytest çalışmasında cihaz açılmaz.
