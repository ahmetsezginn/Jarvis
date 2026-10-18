# Güncelleme öncesi dosyalama ve hata incelemesi — 18 Ekim 2026

Kullanıcı sesin biraz iyileştiğini, daha fazla gelişmesi gerektiğini belirtti; sonraki
özelliğe geçmeden dosyalama/hata incelemesi ve Git push istedi. İnceleme hem depo düzenini
hem mevcut dosya/klasör işlevlerini kapsar. Yeni yetenek, model eğitimi veya dosya içeriklerini
okuma eklenmedi. Başlangıç HEAD `f0e05ed`; fetch sonrasında yerel `main` ve `origin/main`
arasında 0/0 commit farkı vardı. Ses değişiklikleri çalışma ağacındaydı, commit varsayılmadı.

## Düzen ve teslim kapsamı

- `core/native`: mikrofon, yerel ASR/SAPI, dosya/uygulama katalogları, validation/policy/executor.
- `services/brain`: model/ajan, mevcut sonuç kimliklerinin özel bağlamda tutulması; OS bypass yok.
- `services/desktop`: Qt sunum ve Core istemcisi. `scripts/evaluation` yalnız tanısal araçlardır.
- `agent/`: kurallar ve durum indeksi; `docs/brain`: ayrıntılı raporlar. Ayrı Handy denemesi
  tarihsel tanıdır; güncel ürün Rust içindeki motordur.
- `models/`, `.cache/`, `target/`, venv, yerel tercihler ve ses kayıtları Git dışındadır.
  257 sürümlü/adayı dosyada model, DLL, EXE veya WAV artefaktı bulunmadı. Özellikle yeni
  transcribe runtime, GGUF/GGML, deneme kayıtları ve loglar için ignore kontrolü geçti.
- Windows `jarvis` komutunun bu checkout'un `bin/jarvis.cmd` dosyasını kullandığı doğrulandı.
- README'nin eski “UI/ses gelecekte eklenecek” durumu ve yalnız `cargo build` önerisi
  düzeltildi. Native provider hazırlama adımı ve güncel model dizinleri belgelendi.
  Tarihsel CPU-small/Greedy raporları güncel Turbo Q5 GPU profilinden açıkça ayrıldı.

## Bulunan ve düzeltilen bağlam kaybı

Üretim capability yolunun kullandığı `FileSession.select_displayed`, desteklenmeyen bir
uygulama tercihini doğrulamadan mevcut sayfa bağını tüketiyordu. İki sonuçlu sentetik
örnekte Google Docs reddi: **2 sonuç -> 0 sonuç**, **0 Core çağrısı**, açma yok.
Ardından varsayılan uygulamayla aynı dosyayı açma isteği artık hedefini bulamıyordu.

Uygulama tercihi, saf bir ön doğrulamayla bağ tüketiminden önce kontrol edilir. Desteklenmeyen
tercih mevcut kimliği ve özgün 120 saniye TTL'yi korur; yeni açma yetkisi veya uzayan süre
oluşmaz. Geçerli işlem hâlâ ilk Core çağrısından önce bağı tüketir; başarısız IPC tekrar
yürütülmez. Doğrudan/eski açma yolları da aynı tercih doğrulamasını kullanır.

Üç regresyon testi düzeltmeden önce başarısız, sonra başarılı: iki farklı desteklenmeyen
uygulama sonrası **aynı ikinci sonucun** varsayılan açılışı ve ret sonrası TTL'nin uzamaması.
İlgili dosya/ajan/öneri kümesi 143/143 geçti. Cümle veya belge adına özel üretim kuralı yoktur.

## Dosya katmanı incelemesi

- Rust varsayılan açma ile açık uygulama seçimini ayrı tutar. Desteklenen belge/medya
  varsayılan Windows ilişkilendirmesiyle açılır; açık uygulama adaptörü yerel PDF için
  Chrome/Edge ile sınırlıdır. Program/script/kısayol bu dosya yolu üzerinden yürütülmez.
- ID'ler Core kataloğundan gelir. Sayfa, kapsam, ret ve süre sonu sınırları; junction/linked
  hedefler; değişmiş hedef; izin reddi ve IPC validation testleri geçti. Model yol/ID üretemez.
- Ad/konu, dosya türü ve klasör kapsamı farklı filtrelerdir. Kesin ad zorunluluğu başarısızsa
  wildcard alternatife dönülmez. Tahmini ad için ancak aynı doğrulanmış klasörde sınırlı
  metadata alternatifi alınır; farklı köke genişleme yoktur.
- Gerçek `file_catalog_status` salt metadata kontrolü: Desktop/Documents/Downloads kökleri,
  `indexed=false`, `contents_read=false`, `configured_roots_only`. Yeni Core'un sıfır sayaçları
  boş bilgisayar anlamına gelmez; ilk arama katalog hazırlığını tetikler. Kişisel dosya adları
  veya içerikleri rapora alınmadı.
- Katalog tasarım gereği tüm bilgisayar değildir: 20.000 öğe, 16 derinlik, 2 saniye tarama
  bütçesi; dışlanan/erişilemeyen/bulut-only öğeler ve `partial` bayrağı vardır. Arama sonucu
  yokluğu, bu sınırların dışındaki dosyanın bulunmadığını kanıtlamaz.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Brain/Qt normal testler (düzeltme sonrası) | **520 geçti /175 opt-in atlandı**, 4,40s |
| Rust normal testler | **97 geçti /7 opt-in atlandı** |
| Rust fmt ve bütün hedeflerde Clippy `-D warnings` | Geçti |
| Ruff check/format | Geçti, 118 dosya |
| Model/DLL/WAV/log ignore kontrolleri | Geçti |
| Gerçek model dosya/klasör incelemesi | **61 geçti /3 başarısız**, 64 senaryo, 686,54s |

Gerçek model koşusu eski dosya yorumlama hatalarını yeniden ölçmek için sentetik katalog
ve fake Core kullanır. Makine dosyası açma, içerik okuma, mikrofon kaydı veya bulut çağrısı
yapmaz. Bu koşu bağ tüketimi düzeltmesinden önce yüklenen kodla başlatılmıştır; aşağıdaki
semantik kabul ile yeni saf ön doğrulamanın regresyon sonuçları birbirine karıştırılmamalıdır.

## Kalan sınırlar

Yeni koşu aynı üç model sorununu doğruladı; genel dosya/asistan kabulü **başarısızdır**:

1. Türkçe masaüstü not isteğinde model Desktop kapsamını göndermeyip `query=not/category=text`
   aradı; sonuç bulunamayınca erken ipucu istedi. İngilizce ve farklı tür kontrolleri geçti.
2. Varsayılan XLSX açılışında kullanıcı uygulama belirtmediği halde Excel seçildi; modelin ayrı
   current-action kontrolü de bunu onayladı. Desteklenmeyen override açılmadı, istek başarısızdı.
3. Yalıtılmış yetki testinde kullanıcı yalnız dosyayı açmayı isterken önerilen WriterPro parametresi
   onaylandı. Bu kontrolün karşı örneği (WriterPro açıkça istendiğinde) geçti. Rust kimlik/policy
   doğrulaması, kullanıcı tercihinin semantik olarak doğru çıkarıldığını tek başına kanıtlamaz.

Bu tur model yönergelerini/ana ağırlıkları değiştirerek bu üç sonuca özel kurallar eklemez.
Bağ tüketimi düzeltmesi model kararını doğrulamaz; geçersiz tercihin dosya kimliğini
kaybettirmesini önler. Ayrıntılı eski örnekler ve yeni başarısız testler korunur.

Ses için önceki tanısal 16 örnekte 4 kritik hata, gerçek Auto zincirinde 4/6 hata korunur.
Kullanıcının “biraz daha iyi” geri bildirimi kaydedildi; genel ASR veya asistan kabulü değildir.
[Native provider raporu](NATIVE_SPEECH_PROVIDER.md) ve
[önceki dosya keşfi raporu](VOICE_AND_DISCOVERY_FOLLOWUP.md) ayrıntıları korur.

## Komutlar / kayıtlar

Proje kökünde mevcut yerel Python/Qt paket yolu ve CMAKE/LIBCLANG_PATH ile:

```powershell
cargo test -p jarvis-core -j 2
cargo fmt --all --check
cargo clippy --all-targets -j 2 -- -D warnings
python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider -q
ruff check services/brain scripts services/desktop
ruff format --check services/brain scripts services/desktop
$env:JARVIS_RUN_UNKNOWN_NAME_TESTS='1'
$env:JARVIS_RUN_ENGLISH_AGENT_TESTS='1'
python -m pytest services/brain/tests/integration/test_unknown_filename_discovery.py services/brain/tests/integration/test_english_agent_acceptance.py -o addopts= -p no:cacheprovider -q
git diff --check
```

Yerel loglar: `target/prepush-rust-tests.log`, `target/prepush-file-model-review.log`.
Git teslimi mevcut `origin/main` üzerinde normal commit/push olarak yapılır; zorla push yoktur.
Kaynaklar, belgeler ve kurulum pinleri dahildir; modeller ve yerel çıktılar dahil değildir.
