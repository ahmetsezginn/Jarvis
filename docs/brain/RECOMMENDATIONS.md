# Tek aday önerisi ve ret diyaloğu — 2026-10-16

Kullanıcı seçeneklerin ilk yanıtta topluca okunmasını istemiyor. Dosya/klasör veya uygulama
adayları arasından model bağlama göre en uygun olanı kendisi önerir. Kullanıcı reddederse,
önceki aday elenir ve diğer adaylardan biri sunulur. Bu davranış CLI ve Qt/ses için ortaktır.

## Davranış

- Bulma isteği → arama → modelin metadata üzerinden seçtiği tek aday → “Could X be the one
  you're looking for?” İlk sıranın otomatik seçilmesi veya belge adına özel sıralama yoktur.
- “Hayır, bu değil” → yalnızca o özel kimliği reddet → kalanlardan yeni öneri. Tüm sayfa
  elenmez. Model, öneriyi sessizce değiştirip önceki reddi unutamaz.
- “Evet, bu” → `confirm_suggestion`: kimlik onayı. Dosya açılmaz. Ayrı bir açma isteği veya
  karta tıklama, mevcut yetki ve Rust yürütme zincirinden geçer. Kullanıcı zaten bir uygulamanın
  açılmasını istemişse, doğru uygulamayı onaylama o bekleyen isteği normal denetimle tamamlayabilir;
  bu yeni bir açma izni üretmez.
- “Diğerlerinin hepsini göster” → `show_results`, mevcut kullanıcı isteğinin ayrı denetimi
  sonrası kalan sayfa. Reddedilmiş kimlikler yeniden sıralamaya alınmaz.
- Sonuçlar ve retler mevcut 120 saniye sınırına bağlıdır. Sohbet, öneri veya kimlik onayı süreyi
  uzatmaz. Reset/iptal temizler. Sonuç yoksa model bir ipucu isteyebilir veya mevcut arama
  yetenekleriyle sorguyu değiştirebilir; içerik okuma/gerçek sahiplik doğrulaması eklenmedi.

## Uygulama

`services/brain/src/jarvis_brain/intelligence/agent/recommendations.py`, özel öneri bağını, görünür kartları ve en çok 100 reddedilmiş
katalog kimliğini tutar. Modele yalnızca özgün sıra, ad, tür ve sınırlı ret adları verilir.
Aynı ada sahip iki dosya özel kimlikleriyle ayrılır. Modelin isim bütçesi sınırlıdır; açık tam
liste isteğinde UI bütün özel sayfayı gösterebilir ve son kart da güvenli biçimde seçilebilir. Yeni sorgular reddedilmiş kimlikleri
Rust `exclude_ids` alanına otomatik taşır; model kimlik üretemez. Orijinal sıra numaraları
korunur. Masaüstü, yalnızca görünür kart numarasını ve geçerli sayfa belirtecini kabul eder.

Üç sunum adımı (`suggest_result`, `reject_suggestion`, `confirm_suggestion`) yalnızca özel
bellek durumunu değiştirir; OS işlemi yapmaz. Öneri bir tahmin sorusudur: emin olunmayan ama
geçerli bir aday için de sorulabilir. Bu saf bellek yeteneğine ayrı advisory güven eşiği tanımlıdır;
registry, Core bağımlılığı veya yan etkisi olan yetenekte bu istisnayı reddeder. Açma için mevcut
güven eşiği ve bağımsız yetki değerlendirmesi aynen kalır. `show_results`, yalnızca açık liste isteğinde
kullanılmak üzere mevcut eylem değerlendirmesine tabidir; bu da yeni bir makine izni vermez.
Uygulama belirsizliğinde seçenekler aynı 120s süresince korunur ve açmadan önce Core yeniden
çözümler. Dosya içeriği veya modelin uydurduğu yürütülebilir hedefler bu akışa katılmaz.

`CapabilityRegistry.register_response_check` genel bir sunum sözleşmesi kancasıdır. Keşiften
sonra model tam listeyi düzyazıyla vermeye kalkarsa taslak kullanıcıya/sese çıkmaz. Aynı
AgentModel, registry'den türetilen dar sunum şemasıyla kararını tamamlar. Model yine hangi
adayın uygun olduğuna kendisi karar verir. Geçerli bir düzyazı cevabı, sonradan birden çok
bilinen adayı listeleyerek kart durumunu sessizce değiştiremez; sunum sözleşmesi bu durumda da
uygulanır. Dosya adlarını içeren sıradan bir karşılaştırma cümlesi liste sayılmaz. Bu bir cümle eşleştirme/intent sınıflandırma
zinciri veya eski planlayıcıya dönüş değildir. Her araçtan sonra bağlam güncellenir.

Saf, başarısız bellek geçişi `Observation.retryable` ile düzeltildikten sonra tekrar edilebilir.
Bu bayrak Core bağımlılığı olan, yan etkili, terminal veya performed bir gözlemde reddedilir.
Makine işlemlerinde tekrar engeli ve toplam beş model adımı sınırı korunur.

Masaüstü worker'ı artık otomatik olarak tüm özel sayfayı kartlara dönüştürmez; yalnızca seçilmiş
öneriyi veya açıkça istenen listeyi verir. `speech_text` aynı öneridir. Qt'de tek öneri için
SUGGESTION başlığı ve kapsam/kısmi tarama bilgisi görünür. CLI de kısmi tarama/kapsam uyarısını
korur. Açık tam listede ses, modelin yeniden numaraladığı bir metin yerine doğrulanmış özgün
numara/adları okur; konumlar ayrı kalır. Uzun listede 1024 karakterlik ses sınırı aşılırsa kısa
sayım ve kartlara yönlendirme kullanılır. Model belleğine konumlar kopyalanmaz.

## Doğrulama

Birim senaryoları; farklı belge türleri, ilk sıra dışındaki seçim, tek kimliğin reddi, yeniden
aramada retlerin korunması, benzer adlar, kalanları listeleme, kimlik onayı/açma ayrımı,
süre aşımı/reset, gizli/eski kart engeli, şema onarımı ve makine işlemini tekrar ettirmeme
sınırlarını kapsar. Qt testi worker → kontrolcü → tek kart/ses bağını çizerek doğrular.

Gerçek 9B testleri yalnızca sentetik ad/metadata kullanır; Core bağlantısı veya gerçek dosya
açma yoktur. Bütçe XLSX, sunum PPTX ve tarif TXT senaryolarında bul → reddet → onayla → hepsini
iste akışı; sertifika PDF'de 2026 final tercihine göre seçim → kimlik onayı → varsayılan açma
sınanır. İlk mesajda açık tam liste isteği ve uygulama belirsizliğinde öner → reddet → diğerini
onayla → daha önce istenen açılışı tamamla da eklenmiştir. Son altı senaryo 179,76 saniyede geçti.
İlk denemeler yalnızca yönergenin yetmediğini, atlanan ret adımını ve uygulama önerisindeki
öznel belirsizliğin yürütme güveniyle karıştığını gösterdi; bu sınırlar sözleşmelerle ayrıldı.
508 ordinary test geçti / 164 opt-in atlandı (491 Brain +17 Qt, 3,56 saniye). Son genel İngilizce
kabul taraması 55/56 geçti (489,40 saniye). Kalan vakada kullanıcı yanlış öneriyi reddedip
dosyanın alakasız bir adı olduğunu söylediğinde model eski sonuç sayfasının tükenmesini
genişletilmiş arama sonucu sanıyordu. Boş kalan öneri gözlemine arama yapılmadığı ve mevcut
yeni ipuçlarıyla aramanın genişletilebileceği bilgisi eklendi. Aynı vaka ayrı gerçek model
tekrarında 35,33 saniyede geçti: kapsam Desktop kaldı, eski kimlik dışlandı ve yeni TXT bulundu.
Bu düzeltmeden sonra 56 vakanın tamamı tekrar çalıştırılmadı; ölçülmüş bir tam tarama 56/56
başarısı iddia edilmiyor. Altı öneri vakası da bütün asistan yeteneklerinin kabulü sayılmaz.

Ara regresyonda fotoğraf/sunum için kind/category karışıklığı, uzun yetenek cevabı ve kurulum
sonrası yeniden denemenin reddi yakalandı. Enum alanlarının açıklamaları ve bekleyen eylem/kimlik
sorusunun kapsamı netleştirildi; kısa özet yönergesi eklendi. Geçersiz araç çıktısı veya 2048
karakter sert sınırı onarılarak çalıştırılmaz; mevcut fail-closed davranışı korunur.

Yerel komutlar (proje kökü, mevcut yorumlayıcı):

```powershell
$python='C:/Users/szgnm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH="$pwd;$pwd/services/brain/src;$pwd/services/brain/.venv/Lib/site-packages;$pwd/services/desktop/.venv/Lib/site-packages"
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_BACKEND='software'
$testTemp=Join-Path $pwd ('target/recommendation-check-'+[guid]::NewGuid().ToString())
& $python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider --basetemp $testTemp -q
& $python -m ruff check services/brain scripts services/desktop
& $python -m ruff format --check services/brain scripts services/desktop
$env:JARVIS_RUN_RECOMMENDATION_TESTS='1'
& $python -m pytest services/brain/tests/integration/test_recommendation_dialogue.py -o addopts= -p no:cacheprovider -q -s
$env:JARVIS_RUN_ENGLISH_AGENT_TESTS='1'
& $python -m pytest services/brain/tests/integration/test_english_agent_acceptance.py -o addopts= -p no:cacheprovider -q -s
& $python -m pytest services/brain/tests/integration/test_english_agent_acceptance.py -k rejected_results -o addopts= -p no:cacheprovider -q -s
git diff --check
```

Test çıktı dosyaları `target/recommendation-{unit-qt,live-final,regression-final,exhaustion-live}.log`, Qt görseli
`target/recommendation-preview.png` içindedir. Bunlar yerel çıktılardır ve Git dışındadır.
Rust kodu bu takipte değişmedi; ses altyapısı ve Core yürütme sınırı korunur. Commit/push yoktur.
