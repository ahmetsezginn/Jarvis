# Normal yanıt sesi ve bilinmeyen dosya adı — 2026-10-18

Ses kuyruğu düzeltildi ve gerçek normal QML/ajan yanıtında doğrulandı. Dosya keşfi ve genel
asistan kabulü **başarısız**: kullanıcının aynı Türkçe not isteği son üretim ayarında hâlâ
masaüstü kapsamını atlıyor. Ara sürümdeki 6/6 sonucu nihai kodun kabulü değildir.

Kullanıcı test sesini duyduğu halde normal yanıtların okunmadığını ve “Masa üstünde bir tane
not vardı. Onu bulabilir misin?” isteğinde yalnızca `not` adlı dosya aranıp durulduğunu bildirdi.
Önceki kısa ses testleri normal ajan/otomatik dönüş zincirini kapsamıyordu.

## Ses

Audit kaydında normal `speech_speak` başarılı, yaklaşık 0,6 saniye sonra `speech_start`
görülüyordu. Mikrofon açılışı yarım çift yönlü akışta çıktıyı durdurur. Native kod yalnızca
`RunningState == 2` değerini konuşma sayıyor; bekleyen async sentez/çıkışı bitiş gibi
yorumlayabiliyordu. Microsoft'un [durum tanımında](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720498(v=vs.85))
0 bekleyen konuşmayı belirtir. Bitiş artık [WaitUntilDone(0)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723616(v=vs.85))
ile bütün kuyruğun tamamlanmasına bağlıdır. Sabit bir konuşma süresi tahmini eklenmedi.

`speech_poll.speaking`, eski istemciler için kuyruk beklerken de true kalır. Yeni `output_phase`
queued/speaking/idle ayrımını taşır. Qt queued fazını processing olarak gösterir, otomatik
dönüşü yalnızca tamamlanmadan sonra yapar. Stop/epoch/iptal ve cihaz hatası denetimleri korunur.
Yeni canlı test gerçek QML Send → ayrı gerçek Qwen worker → normal yanıt → Named Pipe → Rust
SAPI → tamamlanma → otomatik dönüş çağrısını kapsar. Test son dönüş çağrısını gözlemleyerek
mikrofonu açmaz; fiziksel mikrofon kaydı yapılmaz. Önceki sahte worker testiyle karıştırılmaz.

## Keşif

İlk gerçek model denemesi kullanıcının erken vazgeçme yanıtını yeniden üretti. Genel “yeniden
dene” yönergesi yetmedi. Son sözleşmede `find_files.name_is_constraint`, kullanıcının zorunlu
kaydedilmiş adıyla modelin konu/türden türettiği tahmini ayırır. Alanı model seçer; Türkçe
cümle veya belge adına özel üretim dallanması yoktur.

- true: ad filtresi korunur; ad bulunamazsa farklı adlı alternatifler getirilmez.
- false (varsayılan): ad sorgusu sıfır eşleşme döndürürse, yalnızca doğrulanmış klasörde en fazla bir ek metadata
  araması yapılabilir. `query=*`, aynı tür/uzantı, recursive, sort ve ret filtreleriyle, mevcut
  20 sonuç/120s sınırında çalışır. Tüm bilgisayara genişleme veya açma yoktur.
- Orijinal sorgu/sıfır ad eşleşmesi ve `same_scope_alternatives_not_name_matches` ayrı bildirilir.
  Alternatifler ad eşleşmesi, içerik veya sahiplik kanıtı değildir. Bir adayı model seçer.
- Klasör yazımı bulunamazsa kayıtlı `file_catalog_status` üzerinden doğrulanmış kök adları
  döner. Model yalnızca eşdeğer yerelleştirilmiş/yazımı düzeltilmiş etiketi deneyebilir.
  `find_files` search_files ve file_catalog_status araçlarını gerektirir; list_folder da aynı
  kök bilgisine ihtiyaç duyduğunu açıkça bildirir.
- Sunum denetimi, bilinen dosya adlarının virgül/noktalı virgülle yan yana sıralanmasını da
  liste sayar. Düzyazı karşılaştırması korunur; toplu liste için açık show_results isteği gerekir.

Uzun serbest yanıtı constrained grammar'a katma denemesi native grammar sınırına takıldı;
diğer iç değerlendirme denemeleri de not vakasını güvenilir çözmedi. Bu denemeler teslim edilen
koddan kaldırıldı. Nihai uygulama mevcut tek AgentModel sunum adımını korur. Yeni classifier,
belgeye özel kural, model eğitimi, cloud, ONNX veya doğrudan Python OS erişimi yoktur.

## Doğrulama

- 18 Ekim: **516 Brain/Qt ordinary geçti /175 opt-in atlandı**, 3,60s.
- 18 Ekim: **90 Rust ordinary geçti /3 opt-in atlandı**, fmt ve debug build geçti.
  Ruff check/format geçti (117 dosya). Native kaynak değişmedi; Clippy 16 Ekim'de geçti.
- Altı yeni gerçek 9B vaka Türkçe/İngilizce not, bilinmeyen fotoğraf, Türkçe hesap tablosu,
  zorunlu tam-ad negatif kontrolü ve boş klasörü kapsar. TXT/JPG/XLSX ve başka kökte yanıltıcı
  dosyalar kullanılır. Tümü sentetik metadata; gerçek kullanıcı dosyası açılmaz, içerik okunmaz.
  18 Ekim nihai tekrar: **5 geçti /1 başarısız**, 90,11s. Tek başarısızlık kullanıcının aynı
  Türkçe not isteğidir. Ara sürümün 6/6 geçişi teslim kabulü sayılmaz.
- 16 Ekim normal gerçek QML/ajan/ses/otomatik dönüş: **1 geçti**, 25,52s. Native fazlar speaking → idle;
  dönüş yalnızca kuyruk tamamlandıktan sonra görüldü. Bu test son aşamada mikrofon açmaz.
  **18 Ekim son tekrar da geçti**, 25,78s: gerçek QML Send, ayrı gerçek 9B worker ve Native
  SAPI speaking → idle görüldü; otomatik dönüş yalnızca bitişten sonra çağrıldı.
- İngilizce/Türkçe SAPI: **2 geçti**, 18,12s. Kullanıcı önceki iki kısa sesi duyduğunu
  doğrulamıştı. Bu takipte kullanıcının normal uygulama yanıtını tekrar dinlemesi henüz kabul
  edilmiş değildir.
- Genel İngilizce 56 vaka: **51 geçti /5 başarısız**, 419,83s. Başarısızlar: fazla dar kira
  sorgusu, sunum kategorisini kind alanına yazma, DOCX/XLSX için talep edilmemiş Word/Excel,
  yeni salt-okunur kök metadata çağrısını kabul etmeyen eski test beklentisi. Son beklenti
  düzeltildi; global dosya araması hâlâ yasaklanır. Tam suite yeniden geçmedi.
- Ara düzeltme 23 vaka: **20 geçti /3 başarısız**, 255,59s. Sonraki 29 vaka: **24 geçti /5
  başarısız**, 214,41s. Yetki kontrolü payload sırası denemesi how-to ve kurulum devamını
  bozdu; geri alındı. Bu sonuçları birleştirip genel geçiş oranı üretmeyin.
- 18 Ekim üretim ayarıyla 16 odaklı vaka: **12 geçti /4 başarısız**, 168,55s. Kalan gerçek
  sorunlar aşağıda. Dördüncü başarısızlık testin tam adın tek bir araç yazımıyla gösterilmesini
  istemesiydi: `query=missing-report` + `extension=pdf` de aynı zorunlu adı korur. Test bu eşdeğer
  gösterimi kabul edecek şekilde düzeltildi; wildcard/global arama/başka dosya önerisi kabul edilmez.

## Açık sorunlar ve model karşılaştırması

- Aynı Türkçe not isteğinde model `query=not, category=text` gönderip location alanını atlıyor.
  Sonraki yanıt yanlış biçimde daha fazla ipucu istiyor; bazen İngilizce yanıt yönergesini de
  izlemiyor. Kapsam hiç belirtilmeyince güvenli aynı-klasör alternatifi devreye giremez.
- İngilizce karşılık, fotoğraf ve Türkçe hesap tablosu son odaklı koşuda doğru tek adayı önerdi.
  Bu, genel Türkçe yeteneğinin veya tüm dosya senaryolarının geçtiği anlamına gelmez.
- Varsayılan XLSX açılışında model hâlâ Excel seçebiliyor. Ayrı current-action değerlendirmesi
  de bazen kullanıcının istemediği WriterPro parametresini onaylıyor. Desteklenmeyen override
  mevcut sınırlarda Core'a ulaşmadan reddediliyor; bu anlamsal değerlendirme hatası açıktır.
- Üretim Qwen3.5 sağlayıcısı düşünmeyi kapatır, 6144 bağlam/384 çıktı tokenı ve beş adım kullanır.
  [Resmî model kartı](https://huggingface.co/Qwen/Qwen3.5-9B) düşünme modunu ve yeterli çıktı
  bütçesini ayrı ayarlar olarak tanımlar. Bu ayar tek başına model kapasitesi yetersizliğini kanıtlamaz.
- Aynı ağırlıklarla salt sentetik tanısal karşılaştırma: düşünme kapalı Türkçe 7,16s başarısız,
  İngilizce 16,27s başarılı. Düşünme açık (2048 çıktı tokenı) Türkçe ilk adımda Desktop kapsamını
  korudu, ikinci adımda kapanmamış düşünme/araç çıktısı yüzünden güvenli biçimde durduruldu
  (11,55s); İngilizce başarılı (17,56s). Araç çağrısı düşünme içinden yürütülmedi. Bu iki vaka
  geçerli bir genel kalite karşılaştırması değildir; üretim modu değiştirilmedi. Ham düşünme
  kaydedilmedi; yalnızca biçim sayaçları, süreler, son yanıt ve sentetik araç sonuçları tutuldu.

Rust dosya erişimi ile modelin kullanıcı kapsamını doğru çıkarması ayrı problemlerdir. Yeni
sözleşme yanlış ad varsayımından güvenli dönüş sağlar; modelin hiç göndermediği bir konumu
üretemez. Sonraki kalite çalışması bu scope/parametre ve yetki hatalarını birlikte ölçmelidir.

Core 18 Ekim'de derlenip gizli serve olarak yeniden başlatıldı (yolu doğrulanmış PID25816).
Desktop yeniden açılmalı.
Commit/push yok; önceki kaydedilmemiş çalışma korundu. GPU testleri sırayla, kullanıcı JARVIS'i
kapattığını doğruladıktan sonra çalıştırıldı. Kullanıcının Python/GUI süreci öldürülmedi;
yalnızca bize ait CPU testi ve yolu doğrulanmış proje Core'u test/güncelleme için durduruldu.

## Komutlar

```powershell
$python='C:/Users/szgnm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH="$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages;$pwd/services/desktop/.venv/Lib/site-packages"
$env:CMAKE="$pwd/services/desktop/.venv/Lib/site-packages/cmake/data/bin/cmake.exe"
$env:LIBCLANG_PATH="$pwd/services/desktop/.venv/Lib/site-packages/clang/native"
$env:CXXFLAGS='/O2'
cargo fmt --manifest-path core/native/Cargo.toml --check
cargo test --manifest-path core/native/Cargo.toml -j1
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
& $python -m ruff check services/brain scripts services/desktop
& $python -m ruff format --check services/brain scripts services/desktop
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_BACKEND='software'
$testTemp=Join-Path $pwd ('target/reply-voice-check-'+[guid]::NewGuid().ToString())
& $python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider --basetemp $testTemp -q
$env:JARVIS_RUN_UNKNOWN_NAME_TESTS='1'
& $python -m pytest services/brain/tests/integration/test_unknown_filename_discovery.py -o addopts= -p no:cacheprovider -q -s
# Core serve açıkken; mikrofon açılmaz:
$env:JARVIS_RUN_DESKTOP_VOICE_LIVE='1'
& $python -m pytest scripts/tests/test_desktop_qt.py -k normal_qml_agent_reply -o addopts= -p no:cacheprovider -q -s
$env:JARVIS_RUN_VOICE_DEVICE_LIVE='1'
& $python -m pytest scripts/tests/test_desktop_qt.py -k actual_qt_reply -o addopts= -p no:cacheprovider -q -s
$env:JARVIS_RUN_ENGLISH_AGENT_TESTS='1'
& $python -m pytest services/brain/tests/integration/test_english_agent_acceptance.py -o addopts= -p no:cacheprovider -q -s
# 18 Ekim 16 vakalık odaklı tekrar; iki opt-in değişkeni de 1:
& $python -m pytest services/brain/tests/integration/test_english_agent_acceptance.py services/brain/tests/integration/test_unknown_filename_discovery.py -k '(discovery_precision and (garden or landlord)) or (default_open and (budget or lease)) or new_installation or (current_action_assessment and (How or inferred)) or item_description or exact_name or empty_folder' -o addopts= -p no:cacheprovider -q -s
git diff --check
```

Genel İngilizce suite iki yeni parametre-yetki negatif/pozitif kontrolüyle artık 58 vakadır;
51/56 tarihsel tam koşusuna bu iki yeni test dahil değildir. 16-vaka odaklı koşu yukarıdaki
tam-ad assertion düzeltmesinden önceydi. Altı vakalık son tekrar düzeltmeden sonradır.

Yerel çıktılar Git dışı `target/reply-voice-current-{unit,rust,build,focus}.log`,
`target/reply-voice-current-normal-live.log`, `target/unknown-name-current.log`,
`target/discovery-thinking-{comparison,structure}.log` ve
`target/reply-voice-{clippy,normal-live,native,regression,targeted,final-focus}.log` içindedir.
`target/unknown-name-final.log` ara sürümün tarihsel sonucudur.
