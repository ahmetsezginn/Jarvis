# Yetenek tabanlı ajan döngüsü — 2026-10-16

Bu çalışma, üretimdeki ardışık konuşma/görev, amaç, TurnPlan, işlem ve hedef sınıflandırma
zincirini kaldırır. `JarvisBrain.handle_text` yalnızca yeni `AgentRuntime` üzerinden çalışır.
Eski davranış `LegacyBrain` altında karşılaştırma içindir; hata durumunda ona dönüş yapılmaz.
Bir dosya adı veya Türkçe cümle için yeni yönlendirme dalı eklenmedi.

## İşleyiş

```text
Güncel istek + sınırlı konuşma + kayıtlı yetenekler + doğrulanmış metadata
  -> model: yanıt veya tek araç çağrısı
  -> şema / argüman / liste adresi doğrulaması
  -> yan etkide güncel istek ile önerilen hedef/uygulamanın ayrı denetimi
  -> yeteneğin özel katalog bağlaması
  -> JarvisCoreClient -> Named Pipe -> Rust registry -> validation -> policy -> executor
  -> güvenli araç gözlemi -> aynı model bir sonraki adımı seçer
```

Bir tur en fazla beş model adımı içerir. Aynı argümanlarla aynı araç tekrar çalıştırılmaz.
Başarılı açma işlemi turu bitirir; uygulama/pencere/süreç doğrulaması yapılmaz. Model hataları,
geçersiz sözleşmeler ve süresi dolmuş kimlikler işlem tekrarı veya eski planlayıcıya dönüş üretmez.

Model, GGUF dosyasındaki kendi `tokenizer.chat_template` şablonunu kullanır. Gerçek araç
çağrıları assistant/tool rolleriyle geri verilir. Üretimde eski sabit intent JSON'u veya
TurnPlan dilbilgisiyle yetenek seçimi yapılmaz. Sağlayıcıya özgü araç protokolü ayrıştırılır,
sonra aynı bağımsız registry doğrulamasından geçer. Doğal yanıt metni çalıştırılabilir komut değildir.
Güncel eylem değerlendirmesi de aynı yerel şablonu kullanır. Sınırlı bir istek-anlamı özeti
karardan önce üretilir; şemanın alan sırası korunur. Bu özet kullanıcıya gösterilen düşünce
zinciri veya çalıştırılabilir plan değildir; yalnızca doğrulanan izin değerlendirmesi kullanılır.

## Modüler sınır

`CapabilityRegistry`, yeteneğin adını, açıklamasını, tam parametre şemasını, işleyicisini,
etki/izin bilgisini ve gerekli Core araçlarını birlikte kaydeder. Modelin gördüğü tanım ile
çalıştırılan işleyici aynı kayıttan gelir. Core'da bulunmayan araçlara bağımlı yetenekler sunulmaz.
Yetenek paketi ayrıca güvenli bağlam görünümü, reset ve tur başlangıcı/bitişi kancaları kaydedebilir.
Yeni bir yeteneğin eklenmesi için döngüye `if intent == ...` dalı gerekmez; bunu sınayan bağımsız
test vardır. `AgentModel` sağlayıcı sözleşmesi modele bağlı değildir.

Bu, ileride beceri paketleri için bağlantı noktasıdır. Henüz internetten beceri indirme,
dinamik kod yükleme, imza/dağıtım sistemi veya yeni makine izinleri yoktur. Gelecekte yüklenen
bir beceri de Rust araç/policy sınırını aşamaz. Şimdiki registry yalnızca uygulama tarafından
güvenilen yerel kodu kabul eder; güvenilmeyen eklenti sandbox'ı olarak sunulmaz.

## Bağlam ve dosya davranışı

Kullanıcının son tercihiyle ürün etkileşim dili **İngilizce** oldu. Modelin sistem yönergesi,
aktif CLI, sonuç listeleri, hata ve onay mesajları İngilizcedir. Katkıda bulunan ajan bu
kullanıcıyla Türkçe iletişim kurar. Gerçek dosya/klasör adları değiştirilmez; Unicode korunur.
Windows Known Folder yolları aynı API ile çözülür, yalnızca görünen kök adları Desktop,
Documents ve Downloads olur. Özel TOML kök adları kullanıcıya aittir.
İngilizce soru, Türkçe isimli bütün dosyaların anlamsal çeviriyle bulunacağını garanti etmez:
katalog hâlâ isim/metadata arar; içerik veya çok dilli embedding araması eklenmedi.

Güncel kayıt şemaları parametre açıklamalarını ve doğrulanmış varsayılanları taşır.
Serbest metin açık `format="text"` ile tanımlanır; `message` gibi belirli bir alan adına
bağlı gizli doğrulama istisnası yoktur. Bağlanamayan klasör için bulunamadı/belirsiz ayrımı
gerçek katalog sonucundan üretilir. Başarısız kapsam çözümü genel aramaya düşmez.

Çapraz tur araç geçmişi, en fazla üç doğrulanmış gözlemi ait oldukları konuşma turunda
native assistant/tool-call ve tool-result rolleriyle taşır. Bunlar 120 saniyede sona erer;
sohbet süreyi yenilemez. Kullanıcıya gösterilen yollar bu geçmişe kopyalanmaz.
Etki değerlendirmesi, önce mevcut isteğin kısa sonuç tanımını, sonra önerilen işlemle
uyum kararını üretir. Bu tanım düşünce zinciri veya izin belirteci değildir; modelin
hatalı karar verebilmesi nedeniyle son yetki hâlâ Rust policy/validation katmanındadır.

- Konuşma yalnızca oturumda, en fazla altı çift/2400 karakter. Özel sonuç sayfası ve klasör
  bağlaması 120 saniye; `/reset` tüm kayıtlı yetenek bağlamlarını temizler.
- Model isim/tür/orijinal sıra numarası görür. Core kimlikleri ve gerçek yollar özel kalır;
  kullanıcıya gösterilen konumlu listeler model hafızasına kopyalanmaz.
- Arama yalnızca izinli köklerde isim metadatasını kullanır. Varsayılan tek çağrı bütün izinli
  köklerde arar; kullanıcının belirttiği klasör ayrıca bağlanır. Bulunamayan klasör sessizce
  genel aramaya dönüşmez. Dosya içerikleri okunmaz.
- Native isim araması ayraçlar arasındaki kelimeleri ve en az dört karakterli, sayısız
  kelimelerin ortak başlangıcını eşleştirir. Sayısal sürümler bu esneklikten yararlanmaz.
  Bu bir Türkçe kök bulucu, içerik araması veya anlamsal embedding indeksi değildir.
- Sonuç bulunamadığında model gerçek gözlem üzerinden sorgusunu değiştirebilir; Python
  belge türüne özel kurtarma sorgusu üretmez. Araç açıklaması AND kelime semantiğini bildirir.
- Dosya adı zorunlu değildir: bilinen konum veya tür ile adsız arama yapılabilir. İpucusuz
  genel joker arama reddedilir. Başarılı araç gözlemi ve geçerli sayfa bağlamı, gerçekte
  uygulanan kapsam/alt klasör/tür/sıralama filtrelerini de taşır; varsayılanlar belirsiz bırakılmaz.
- `open_result(number)` sadece mevcut sayfaya bağlanır. Uygulama belirtilmemişse Windows
  ilişkisi kullanılır; PDF'den tarayıcı tercihi çıkarılmaz. Belirtilmiş uygulamada mevcut
  Rust adaptörü kullanılır: şimdilik yerel PDF + Chrome/Edge. Diğer özel uygulama adaptörleri
  ayrıca geliştirilmeli; sıradan varsayılan açma bundan bağımsızdır.
- Yalın `Google` için somut Chrome sorusu bir hedefe bağlanır; `evet` sadece bu 120 saniyelik
  soruyu tamamlayabilir. Genel sohbet cevabı açma yetkisi yaratmaz.
- Bulunamayan uygulamadan sonraki kurulum bildirimi bir kez katalog yenileyip aynı insan
  sorgusunu yeniden çözer. Başka tur, reset veya süre aşımı bu bekleyen isteği temizler.

## Yerel model karşılaştırması

Yeni döngü, mevcut Qwen3-4B Q4 ve aynı modelin Q8 karşılaştırmasında da anlamsal hataları
tam çözmedi. Aynı dondurulmuş yedi vakalık karşılaştırmada ikisi de 1/7 verdi; yalnızca
kuantizasyonu büyütmek yeterli olmadı. Bu sonuç bütün 4B modellerin yetersiz olduğu iddiası değildir.
Farklı model ile döngü değişikliğinin katkısı ayrı değerlendirilmelidir.

Qwen3.5-9B Q4_K_M ayrıca yerel olarak sağlandı ve aynı yürütme sınırında denendi. Kaynak:
[Qwen model kartı](https://huggingface.co/Qwen/Qwen3.5-9B),
[sabitlenmiş GGUF deposu](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/99a1b2185534379e6e8b5ec869da25d3e7b3f73c).
Bu sağlayıcı Qwen3.5'in yerel araç protokolünü kullanır; thinking kapalıdır. Yeni bağımlılık,
sunucu, eğitim, bulut API'si veya çalışma sırasında indirme eklenmedi.
Üreticinin önerdiği non-thinking ayarlar da denendi: temperature 0,7, top_p 0,8,
top_k 20, min_p 0, presence_penalty 1,5, repeat_penalty 1 (model kartı Best Practices).
Bu aday koşu 56 testte 43 geçti / 13 başarısız verdi. Ardından doğrulanmış çapraz-tur
araç geçmişiyle greedy profil tekrar ölçüldü. Güncel yerel profil temperature 0,
presence_penalty 0, top_p 0,8, top_k 20, min_p 0, repeat_penalty 1, seed 0 kullanır.
İki koşu arasında bağlam aktarımı da düzeltildi; fark yalnızca sampling'e atfedilemez.

Launcher ve sağlayıcı fabrikasının varsayılanı `qwen35-9b` profilidir. Eski 4B ancak açıkça
`jarvis -Profile qwen3-4b` veya doğrudan Python'da `JARVIS_GGUF_PROFILE=qwen3-4b` ile seçilir.
Bu seçim eski sınıflandırma zincirine dönüş değildir; iki model de aynı yeni ajan sözleşmesini
kullanır. Bilinmeyen profil veya eksik model hata verir; otomatik fallback yoktur.

| Alan | Değer |
|---|---|
| Artefakt | `Qwen3.5-9B-Q4_K_M.gguf` |
| Dizin | `models/qwen35-9b-reference` (git dışında) |
| Revision | `99a1b2185534379e6e8b5ec869da25d3e7b3f73c` |
| Boyut | 5.680.522.464 bayt |
| SHA256 | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
| Runtime | mevcut `llama-cpp-python==0.3.35` |
| Bağlam / batch | 6144 / 64 |
| GPU yerleşimi | 32 blok GPU, çıkış izdüşümü CPU; CPU profili 0 |

Açık sağlama: `python scripts/models/provision_agent_reference.py`. Betik sabit LFS işaretçisi,
boyut ve SHA256 doğrular. Sağlayıcı dosyayı yüklerken tekrar doğrular. Başlangıç indirme yapmaz.
Tam GPU offload, geniş deneme sırasında 7.876 MiB kullanıma/73 MiB boş alana çıktı. Yaklaşık
20 dakika süren bu deneme durduruldu; tamamlanmış kabul sonucu olarak sayılmaz. GPU profilinde
32 blok GPU'da, çıkış izdüşümü CPU'da bırakıldı; batch 128'den 64'e indirildi. Aynı sabit
davranış testleri bu yerleşimle yeniden çalıştırılır. Tam CPU gecikmesi ayrıca ölçülmedi.

## Doğrulama kaydı

İlk geniş 35 vakalık gerçek 9B koşusu 26 geçti / 9 başarısız verdi (422,68 saniye).
Bu sonuç kabul edilmiş bir sürüm değildir. Farklı konuların bulunması ve varsayılan açılması
tek başına olumsuz komut, kapsam düzeltmesi, yazım hatası ve sonradan hedef seçimi kalitesini
kanıtlamadı. Başarısız ölçütler kaldırılmadı; sonraki kontrol gruplarına da eklendi.
Thinking modu için 1536 ve 2048 token sınırlarında yapılan iki izole değerlendirme denemesi
tamamlanamadı; token bütçesi hatası verdi. Bu seçenek üretime alınmadı.
256 token ile sınırlandırılmış düşünme deneyi de dört kontrolün üçünü yanlış değerlendirdi;
bu seçenek ve ayrı olumsuzluk-veto deneyi üretime alınmadı. Belge/cümleye özel çalışma
zamanı eşleştirmeleriyle bu hatalar gizlenmedi.

Son Türkçe greedy ölçümü: 56 testte 41 geçti / 15 başarısız (319,40 saniye;
`target/assistant-analysis/agent-acceptance-verified-history.xml`). Bu koşu sonraki İngilizce
arayüz ve parametre açıklamalarından öncedir; eski hatalar kabul edilmiş sayılmaz.

İlk İngilizce grup 49 testte 47 geçti / 2 başarısız verdi (275,20 saniye;
`agent-acceptance-english.xml`). Reddedilen sonucu yeniden katma ve bulunamayan klasör
sonrası başka kapsam deneme başarısızdı. Ek yedi farklı belge/konuşma vakası 6 geçti / 1
başarısız verdi (49,32 saniye; `agent-english-reported.xml`): model zamirle varsayılan PDF
açma isteğine kendiliğinden Adobe ekledi, adaptör açmayı reddetti. Core çağrısı olmadı.
Bu hatalar testlerden çıkarılmadı. Bulunamayan klasörün yanlışlıkla belirsiz diye
raporlanması düzeltildi; dışlama parametresinin açıklaması kendi şemasına eklendi.
İngilizce fixture envanteri de gerçek İngilizce kök etiketleriyle tutarlı hale getirildi.
Ardından 56 testin tamamı yeniden ölçüldü: **53 geçti / 3 başarısız, 302,48 saniye**
(`target/assistant-analysis/agent-english-final.xml` ve `.log`). Açık başarısızlıklar:

- Adsız masaüstü notu aramasında alt klasörleri kaldırınca model `note` isim filtresini
  gereksiz korudu. Doğrudan masaüstündeki `New Metin Belgesi.txt` bulunamadı; kapsam doğruydu.
- Kullanıcı önceki sonucu reddettiğinde dışlama parametresi kullanılmadı; reddedilen sonuç
  yeni listede yeniden göründü.
- Bulunan sertifikayı “I want you to open it” ile açarken model kendiliğinden Adobe seçti.
  Ayrı model değerlendirmesi de bu parametreyi yanlış onayladı. Desteklenmeyen adaptör
  çağrısı hiçbir Core açma isteğine dönüşmedi, fakat kullanıcı isteği tamamlanamadı.

Sekiz konu/formatta keşif, sekiz formatta varsayılan açma, ek beş farklı kayıp belge/yazım
hatası, sıra numarası, açık Edge tercihi, kimlik düzeltmesi/sohbet sonrası açma, eksik klasör,
kurulum sonrası aynı uygulamaya dönüş, uygulama seçimi, dokuz işlemsiz konuşma/olumsuz/
desteklenmeyen istek ve 17 güncel-etki değerlendirmesi geçti. Bu, genel kabulün geçtiği
anlamına gelmez: testlerin üçü hâlâ başarısız; model serbest cevaplarda yeteneklerini bazen
abartabiliyor. Başarısız koşullar gevşetilmedi veya xfail yapılmadı.

Bu koşular yalnızca dilin etkisini yalıtan bir
deney değildir; araç açıklamaları ve doğrulanmış bağlam aktarımı da geliştirilmiştir.

Geçmiş intent testleri `LegacyBrain` üzerinde tutulur; onların geçmesi yeni ajanın dil anlayışının
başarısı olarak sayılmaz. Yeni döngü testleri ile gerçek model davranış testleri ayrı raporlanır.
Sentetik metadata testlerinde gerçek kişisel dosya içeriği ve uygulama açma yoktur. Canlı test,
yalnızca `target/file-context-*` köklerini doğruladıktan sonra oluşturulan test dosyalarını açar.

Canlı yeni-ajan + gerçek Core/Named Pipe koşusu önce **1 geçti, 25,39 saniye** verdi.
PowerShell stderr sarmalayıcısından bağımsız gerçek süreç çıkışını doğrulayan tekrar
**1 geçti, 24,33 saniye; Python exit code 0** verdi. Son kayıt:
`target/assistant-analysis/live-agent-english.xml` / `.log`. `Toplantı-Sunum.txt` varsayılan
Windows ilişkisiyle, boş fixture `Ahmet-Sezgin-CV-TR.pdf` açık Google Chrome tercihiyle açıldı.
Audit kaydı her iki açmada `source=Brain`, `decision=Allow`, `status=Success` gösterdi
(`live-core-english.log`). İkinci işlem `resolve_app` -> `open_file_with_app` kullandı.
Sonrasında pencere/işlem kontrolü yapılmadı; kişisel belge açılmadı. Denetleyici kendi Core'unu
temizledi. Bu, iki somut açmanın uçtan uca geçtiğini kanıtlar; 56 vakalık gruptaki üç anlamsal
başarısızlığı ortadan kaldırmaz.

Son sağlayıcıdan bağımsız Brain koşusu **452 geçti / 157 isteğe bağlı atlandı**. Bunların
60'ı yeni ajan döngüsü testidir; arşivlenmiş intent testleri de toplamın içindedir. Ruff check
ve format (105 Python dosyası), `git diff --check`, PowerShell parser kontrolü, Rust fmt,
**79 Rust test girdisi**, Clippy `-D warnings` ve debug build geçti. Model-info yeni varsayılanı
`Qwen/Qwen3.5-9B`, 32 GPU blok, yerel artefakt mevcut olarak raporladı; bu komut model yüklemez.

## Tekrarlanabilir komutlar

Bu makinede venv yönlendiricisi yerine mevcut taban yorumlayıcı ve venv paketleri kullanıldı:

```powershell
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages"
& $taskPython -m ruff check services/brain scripts
& $taskPython -m ruff format --check services/brain scripts
& $taskPython -m pytest services/brain/tests -o 'addopts=' -q
$env:JARVIS_RUN_ENGLISH_AGENT_TESTS = '1'
$env:JARVIS_AGENT_TEST_PROFILE = 'qwen35'
& $taskPython -m pytest services/brain/tests/integration/test_english_agent_acceptance.py -o 'addopts=' -q -s --tb=short --junitxml=target/assistant-analysis/agent-english-final.xml
& $taskPython scripts/tests/run_agent_live.py
cargo fmt --manifest-path core/native/Cargo.toml --check
cargo test --manifest-path core/native/Cargo.toml -j 1
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
cargo build --manifest-path core/native/Cargo.toml
git diff --check
```

Gerçek model testlerini paralel GPU süreçlerinde çalıştırma. Ayrı `ask` süreçleri oturum
paylaşmaz; kullanıcı bağlam denemeleri için `jarvis` REPL kullanır. Source güncellemesinden
sonra Brain oturumunu kapatıp yeniden başlat; Native Core değişiklikleri için Core da yeniden
başlamalıdır. Canlı fixture denetleyicisi var olan Core'u kapatmaz ve yalnızca kendi
başlattığı süreci sonlandırır. PowerShell betiği bu ajan terminalinde ExecutionPolicy
tarafından engellendi; politika değiştirilmedi veya atlatılmadı. Aynı açık geliştirme
fixture'ı izinli Python denetleyicisiyle hazırlandı, ürünün OS yürütme sınırı değişmedi.

Rust yeniden derlemesinde iki paralel link denemesi geçici LNK1104 verdi; çalışan bir Core
süreci görülmedi. `cargo test -j 1` ardından Clippy ve build başarılı oldu; herhangi bir
kişisel süreç kapatılmadı. Gerçek model unload sırasında mevcut llama-cpp runtime'ı CUDA_Host
compute-buffer beklenti uyarısı basabiliyor; pytest sonuçları ayrıca kaydedilir. Uyarı
modelin anlamsal başarısızlıklarını başarılı saymak için kullanılmadı.
Son canlı tekrarın gerçek süreç çıkış kodu ayrıca loga yazıldı ve 0 olarak doğrulandı.

Modeller, fixture'lar ve ayrıntılı sentetik loglar Git dışında kalır. Kaynak/belge değişiklikleri
çalışma ağacındadır; commit/push yapılmadı. Başlangıçtaki `main...origin/main [ahead 1]`
durumu önceden vardı ve bu çalışmanın commit'i olarak yorumlanmamalıdır.
