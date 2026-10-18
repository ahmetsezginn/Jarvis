# Konuşma tanıma kalitesi — 2026-10-18

Son kullanıcı düzeltmesiyle ayrı Handy denemesi yerine motor JARVIS Rust ses katmanına
entegre edildi. Güncel varsayılanlar, testler ve kalan başarısızlıklar
[NATIVE_SPEECH_PROVIDER.md](NATIVE_SPEECH_PROVIDER.md) belgesindedir. Aşağıdaki CPU/small
varsayılanı ve karşılaştırmalar önceki aşamanın tarihsel sonuçlarıdır.

## Kullanıcı yeniden denemesi ve çevrimdışı alternatifler

Kullanıcı sonraki denemede tanımanın hâlâ yetersiz olduğunu bildirdi. Paylaştığı tanıyıcı
çıktıları aşağıdadır; bunlar söylenmek istenen cümlenin doğrulanmış metni değildir. Özgün
ses yoktur; bu çıktılardan WER veya hatanın mikrofon/model/endpointing kaynağı hesaplanamaz.

> BİLGESİ YARINDA, CV DOSYOSU VAR. Nerede olduğunu bilmiyorum bulabilir misin CV mi?
> (Türkü) Pardon ben yanlış söylemişim. Bu dosyadaymış başka hangi dosyalar var?
> Buna bilgisayarımla araştır bulmanı istiyorum.

Bu geri bildirim kişisel kullanımda ASR sorununun sürdüğünü gösterir. Aşağıdaki sentetik
sonuçlar kullanıcı kabulü değildir. Kullanıcı GitHub'daki hazır çözümlerden yararlanmayı,
harici API kullanılmamasını istedi. Bu takip yalnız araştırma/belgelemedir; yeni paket,
model, ses kaydı veya üretim ayarı değişikliği yapılmadı.

18 Ekim 2026 tarihinde resmî proje kaynaklarıyla incelenen adaylar:

| Proje | JARVIS için değerlendirme |
|---|---|
| [Handy](https://github.com/cjpais/Handy) | Windows dahil çevrimdışı dikte uygulaması; bağımsız mikrofon karşılaştırması ve ses akışı için referans. Tek başına daha yüksek doğruluk kanıtı değildir. |
| [transcribe-rs](https://github.com/cjpais/transcribe-rs) | Rust çoklu motor arayüzü; yerel whisper-cpp ve CUDA özellikleri ayrı seçilebilir. ONNX/uzak API özellikleri zorunlu değildir. Mevcut native sınırı koruyacak entegrasyon için referans; kütüphane değişimi aynı ağırlığın doğruluğunu garanti etmez. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper'ın CTranslate2 tabanlı yerel çalıştırıcısı; GPU ve nicemleme seçenekleri vardır. Farklı bir tanıma modeli değildir. Python sarmalayıcısı mevcut Rust ses sınırına doğrudan takılamaz. |
| [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) | Türkçe/İngilizce destekleyen 0.6B/1.7B ayrı ASR model ailesi; yerel Transformers çalıştırması vardır. JARVIS'in 9B planlayıcısından farklıdır. Türkçede bu kullanıcı için daha iyi olduğu henüz ölçülmedi; native entegrasyon ayrıca tasarlanmalıdır. |
| [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) | VAD, konuşma sonlandırma ve canlı tanıma akışı için referans Python kütüphanesi. Aynı Whisper ağırlığıyla doğruluk artışı varsayılmaz; mikrofonu Python'a taşıma veya ONNX'i geri getirme kararı değildir. |

Önerilen sonraki değerlendirme: mevcut small CPU tabanını, tam Whisper large-v3 CUDA ve
bağımsız Qwen3-ASR adaylarıyla aynı gerçek konuşma girdisinde karşılaştırmak. Önceki CPU
large-v3-turbo denemesi tam large-v3 GPU ölçümü değildir. Bu bir öneridir, mevcut CPU/GPU
politikası değiştirilmedi. 8 GB VRAM'de 9B planlayıcıyla eşzamanlı bellek/latans ölçülmeden
GPU'da birlikte çalışma sözü verilmez. Model dosyaları önceden hazırlanarak harici API'siz
çalışma hedeflenir; çalışma anında indirme yapılmaz.

Karşılaştırma konuşma başlangıcı/sonu korunumu, Türkçe/İngilizce karışımı, farklı konular,
olumsuzluk, özel ad, sessizlik ve oda gürültüsünü kapsamalı; ham transkript LLM düzeltmesinden
önce değerlendirilmelidir. Aynı PCM'in native bellekte tekrar kullanımı, yalnız metin/süre
sonuçları ve eylemsiz tanı modu tercih edilir. Mikrofon kaydını diske yazma, PCM'i JSON ile
taşıma veya belirli CV cümlelerine üretim kuralı ekleme yetkisi çıkarılmaz.

Kullanıcı normal yanıtların seslendirildiğini doğruladı. Açık sorun artık giriş tanıması:
“Steam'i açar mısın?” → “kaçağı”, “Merhaba Jarvis, nasılsın?” → “Merhaba Javi, nasılsın”.
Örneklerin ses kaydı alınmadı; verilen metinler sabit sentetik değerlendirme girdisi yapıldı.
Bu rapor önceki dosya keşfi ve genel asistan kabulünün başarısızlığını değiştirmez.

## Uygulama

- Native Whisper profil seçimi checksum/size pinleriyle kapalıdır: small, large-v3-turbo,
  large-v3-turbo-q5_0. Yalnız açık kurulum indirir; çalışma sırasında indirme veya sessiz başka
  modele geçiş yoktur. Çıktı GPU'su Qwen'e kalır; ASR CPU'da en fazla altı thread kullanır.
- Greedy best_of=1 yerine beam_size=5 karşılaştırılır. Eski greedy açık developer ayarıyla
  yeniden üretilebilir. Her kayıtta yeni decoder state; başka konuşmadan metin taşınmaz.
- speech_finish, validation/policy sonrasında Native Core uygulama kataloğunun görünen adlarını
  kısa bir **yazım sözlüğüne** dönüştürür. JARVIS ürün adı ve güncel katalog adları kullanılır;
  Steam veya belirli bir cümle için üretim koşulu yoktur. En fazla 64 ad/512 karakter;
  yollar, kontrol karakterleri, şablon işaretleri ve kimlikler aktarılmaz. Kısa adlar önce gelir.
  İstemci/model speech_finish'e kendi vocabulary/prompt alanını gönderemez.
- Bu sözlük Whisper initial_prompt bağlamıdır; transkript sonradan düzeltilmez, uygulama
  kimliği veya eylem yetkisi oluşturmaz. Metin normal Brain/Native Core sınırından geçer.
- Native giriş adı, örnekleme hızı, kanal sayısı ve RMS/peak/clipping bilgisi döner. UI gerçek
  giriş aygıtını ve düşük/taşan seviyeyi gösterir. Bunlar tanıma güven skoru değildir.
  Mikrofon PCM'i JSON'a veya diske yazılmaz. TTS kuyruğu/bitiş düzeltmesi korunur.
- Son ek kontrol, salt gürültüde yüksekliğe dayalı kapının yetmediğini gösterdi: 0,01 genlikli
  beyaz gürültüden “Hüseyin” üretildi. Tamamlanmış bütün kayıtlar artık mevcut yerel Silero
  VAD'dan da geçer; bu kontrol manual ve Auto için ortaktır. En az beş 32ms karede konuşma
  olasılığı >=0,5 gerekir. Kontrol bütün PCM'i olduğu gibi bırakır, kelime/sessizlik kırpmaz.
  Son tekrar sessizlik ve üç gürültü genliğini reddetti (1 test geçti /0,10s); cihaz açılmaz.

Bu bilgisayarın varsayılanı **small + beam + katalog sözlüğü** kaldı. Büyük ağırlıklar açık
karşılaştırma için indirildi; otomatik olarak seçilmez. Genel sözlük destekli Q5 aynı kritik
hata sayısında daha yüksek CPU gecikmesi verdiği için varsayılan yapılmadı.

## Ölçüm sınırları

Sekiz sabit Tolga/Zira cümlesi; temiz ve deterministik düşük seviye/gürültü varyantlarıyla 16
decode. Beş Türkçe, üç İngilizce cümle; özel ad, açma/açmama, farklı konuda dosya arama ve
alternatif reddi içerir. Karşılaştırılan bütün profiller aynı WAV'ları kullanır. Gürültülü
varyant: ses ×0,12 + deterministik beyaz gürültü ±0,003. Bu gerçek oda/mikrofon simülasyonu
değildir; kullanıcı aksanı veya gerçek mikrofon başarısı iddia edilmez. Sentetik Türkçe sesin
İngilizce uygulama adını telaffuzu da hata kaynağı olabilir.

WER, küçük harf/noktalama/Türkçe I normalizasyonundan sonra kelime edit mesafesidir. Anahtar
kelime kaybı ayrıca sayılır; WER'deki düşüş olumsuzluğun korunduğu anlamına gelmez. Tanısal
test eksik kritik kelime varsa başarısız kalır; testler ajana veya makine eylemine bağlanmaz.
Kullanıcı daha sonra bu hataların **Auto conversation** modunda olduğunu doğruladı.

| Ayar | Kritik kayıp /16 | Kelime hatası | Süre |
|---|---:|---:|---:|
| small / greedy / sözlüksüz | 5 | 12/102 (%11,8) | 82,06s |
| large-v3-turbo F16 / beam / sözlüksüz | 4 | 9/102 (%8,8) | 439,35s |
| small / beam / genel sözlük | 2 | 5/102 (%4,9) | 89,12s |
| large-v3-turbo Q5 / beam / genel sözlük | 2 | 5/102 (%4,9) | 385,67s |
| son small / beam / sözlük + ortak VAD | 2 | 5/102 (%4,9) | 89,73s |

Kısa üç Türkçe örneğin Auto dil koşusu: 6 decode /2 kritik kayıp, 5/28 kelime hatası,
70,33s (ilk yükleme dahil). Olumlu kullanıcı örnekleri temiz/gürültülü dört koşuda doğru;
iki başarısızlık yine olumsuz komuttadır. Auto küçük modelde yaklaşık 9s sıcak decode,
açık Türkçe yaklaşık 5s verdi. Listen dilini Türkçe seçmek ürünün İngilizce yanıt metnini
veya Voice telaffuz ayarını değiştirmez.
Ortak VAD eklendikten sonraki Auto dil tekrarı da 6 decode /2 kritik kayıp, 5/28 kelime hatası
verdi (65,16s); konuşma örnekleri yeni kapıdan geçerken kaybolmadı.

Auto giriş sınırları ayrıca **gerçek rolling Silero -> TurnDetector -> preroll/silence ->
ASR Auto** yolunda sınandı: iki olumlu cümle temiz/gürültülü dört koşuda doğru (Steam isteği
2200ms, selamlaşma 2900–3000ms tamamlanmış tur). Olumsuz cümlenin iki varyantı tam PCM ile
aynı hataları verdi; test 61,86s'de başarısız kaldı. Bu örneklerde sorun endpointing ile
açıklanmıyor; gerçek mikrofonun farklı seviyede tetiklenmesi ayrıca değerlendirilmelidir.
Kamuya açık gerçek insan sesi (Whisper JFK WAV) ortak VAD ve small/beam ile geçti: 1 test,
17,56s (ilk yükleme dahil). Kullanıcı mikrofonu açılmadı, kişisel ses kaydı saklanmadı.

İlk model yükleme/hash doğrulaması toplamlara dahildir. İlk iki koşudaki doğal cümlelerin
benzer yanlışları üretmesi tanıyıcı/çözümleme problemini destekler, kullanıcının “kaçağı”
çıktısını bire bir yeniden ürettiğimiz anlamına gelmez. Small+beam+sözlük iki olumlu kullanıcı
örneğini temiz/gürültülü seslerde doğru çözdü; gürültülü olumsuz komut hâlâ başarısızdı.
Büyük model tek başına güvenilir çözüm veya bu CPU'da iyi gecikme sağlamadı.
Q5 temiz olumsuz cümlede doğru ad/olumsuzluğu korudu, gürültülü olumlu cümlede ise adı
kaybetti ve gürültülü olumsuz cümlede ilk isteği tamamen düşürdü. Sıradan dosya arama,
alternatif reddi ve İngilizce örnekler bu koşularda korundu. Bütün tanısal karşılaştırma
testleri en az bir kritik kelime hatası nedeniyle **başarısızdır**; 16/16 geçti iddiası yoktur.
İlk yükleme hariç small yaklaşık 4,7–5,1s, Q5 yaklaşık 21–29s/decode verdi. Derleme/statik
kontroller bazı karşılaştırmalarla eşzamanlıydı; bunlar kontrollü performans benchmarkı değildir.
Gecikme farkı kesin bir donanım hız katsayısı olarak genellenmemelidir.

## Son kod doğrulaması

- Brain/Qt ordinary: **517 geçti /175 opt-in atlandı**, 2,96s.
- Rust ordinary: **95 geçti /6 opt-in atlandı**. Ruff check/format (117 dosya), Rust fmt ve
  tüm hedeflerde Clippy `-D warnings` geçti. Yeni opt-in ses testlerinin yukarıdaki bilinen
  başarısızlıkları bu ordinary geçişe dahil değildir.
- Son native binary hash'i doğrulanarak launcher'ın target/debug yoluna kopyalandı. Proje
  Core'u gizli PID34456 olarak çalışıyor. Named Pipe speech_status: Whisper small CPU,
  model_available=true, default_input=Microphone Array (AMD Audio Device), recording=false.
- Kullanıcı desktop'ı yeniden açmalı. Bu takipte commit/push yapılmadı; çalışma sırasında
  gözlenen HEAD f0e05ed (jarvis voice fixed), önceki ses düzeltmesinin kayıtlı tabanıdır.

## Artefaktlar

Kaynak [ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp/tree/5359861c739e955e79d9a303bcbc70fb988958b1),
revision `5359861c739e955e79d9a303bcbc70fb988958b1`:

| Profil | Bayt | SHA256 |
|---|---:|---|
| small | 487601967 | `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b` |
| large-v3-turbo | 1624555275 | `1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69` |
| large-v3-turbo-q5_0 | 574041195 | `394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2` |

Resmî [Whisper açıklaması](https://github.com/openai/whisper#available-models-and-languages)
model/hız/doğruluk dengesini açıklar; oradaki GPU hızları bu CPU'nun ölçümü değildir.
[whisper.cpp CLI](https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/cli.cpp)
beam search ve initial prompt seçeneklerini ayrı çözümleme ayarları olarak sunar.

## Tekrarlama

Proje kökünde; kişisel mikrofon açılmaz:

```powershell
$python='C:/Users/szgnm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH="$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages;$pwd/services/desktop/.venv/Lib/site-packages"
$env:CMAKE="$pwd/services/desktop/.venv/Lib/site-packages/cmake/data/bin/cmake.exe"
$env:LIBCLANG_PATH="$pwd/services/desktop/.venv/Lib/site-packages/clang/native"
$env:CXXFLAGS='/O2'
& $python scripts/models/provision_speech.py --profile large-v3-turbo
& $python scripts/models/provision_speech.py --profile large-v3-turbo-q5_0
./scripts/evaluation/make_voice_fixtures.ps1 -RecognitionQuality
$env:JARVIS_ASR_EVAL="$pwd/target/voice-quality-fixtures"
$env:JARVIS_WHISPER_PROFILE='small' # aynı komutu large-v3-turbo / large-v3-turbo-q5_0 ile de çalıştır
$env:JARVIS_WHISPER_DECODER='beam' # eski baseline: greedy
$env:JARVIS_ASR_EVAL_HINTS='1' # eski baseline: bu değişkeni kaldır
cargo test --manifest-path core/native/Cargo.toml --target-dir target/asr-verify --test audio_pipeline real_whisper_quality_comparison -j1 -- --ignored --nocapture
# Sözlük varken sessizlik/gürültü kontrolü:
cargo test --manifest-path core/native/Cargo.toml --target-dir target/asr-verify --test audio_pipeline real_whisper_spelling_context_does_not_create_words_from_noise -j1 -- --ignored --nocapture
# Auto kayıt sınırları ve gerçek insan sesi:
cargo test --manifest-path core/native/Cargo.toml --target-dir target/asr-verify --lib real_auto_turn_retains_short_utterances -j1 -- --ignored --nocapture
$env:JARVIS_SPEECH_FIXTURE="$pwd/target/voice-public-jfk.wav"
cargo test --manifest-path core/native/Cargo.toml --target-dir target/asr-verify --test audio_pipeline real_whisper_transcribes_public_fixture_without_device_access -j1 -- --ignored --nocapture
# Auto dil seçimini sadece kısa isim/olumsuzluk örneklerinde ölçmek için:
$env:JARVIS_ASR_EVAL_LANGUAGE='auto'
$env:JARVIS_ASR_EVAL_FILES='0.wav,1.wav,2.wav'
# Yukarıdaki test komutunu tekrar çalıştır; sonra bu iki değişkeni kaldır.
cargo test --manifest-path core/native/Cargo.toml --target-dir target/asr-verify -j1
cargo clippy --manifest-path core/native/Cargo.toml --target-dir target/asr-verify --all-targets -- -D warnings
cargo fmt --manifest-path core/native/Cargo.toml --check
& $python -m ruff check services/brain scripts services/desktop
& $python -m ruff format --check services/brain scripts services/desktop
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_BACKEND='software'
$testTemp=Join-Path $pwd ('target/asr-check-'+[guid]::NewGuid().ToString())
& $python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider --basetemp $testTemp -q
git diff --check
```

Eski OneDrive test exe'leri linker tarafından açılamadı; izin/ACL değiştirmek yerine yeni
`target/asr-verify` çıktı dizini kullanıldı. Projeye ait Core dışında süreç kapatılmadı.
Loglar ve yalnız sentetik WAV'lar Git dışı target/asr-*, target/voice-quality-fixtures içindedir.
