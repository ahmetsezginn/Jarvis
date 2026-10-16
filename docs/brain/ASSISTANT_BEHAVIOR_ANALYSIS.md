# JARVIS asistan davranışı: teşhis ve kabul ölçütleri

2026-10-14. Bu belge bir düzeltme veya genel başarı beyanı değil; kullanıcı kaydı, kod incelemesi
ve mevcut modelle kontrollü deneylerin sonucudur. Üretim Brain/Core davranışı bu analizde değiştirilmedi.

## Sonuç

Doğrulanmış sorunlarımız görev/diyalog tasarımı, bilgi kaybettiren sözleşmeler ve yetersiz test
ölçütleridir. Mevcut Qwen3-4B Q4 çalıştırması da bağlam ve yönerge takibinde kırılgan davranıyor.
Ancak model boyutunun veya kuantizasyonun katkısını bu çalışmadan sayısal olarak ayıramayız:
başka bir model/kuantizasyonla aynı koşullarda karşılaştırma yapılmadı. Yalnızca modeli büyütmek,
şemada bulunmayan konum/arama kapsamını veya engellenen açıklama sorusunu geri getirmez.

Bugünkü sistemin temel akışı bir niyet sınıflandırıcısı, tek eylem planı ve dosya seçimi durumudur.
Hedefi koruyup sonuçtan öğrenen bir asistanın gerekli diyalog ve görev durumu henüz yeterli değildir.
Rust sınırının korunması bununla çelişmez; sorunları çözmek için Python'a shell veya doğrudan OS
erişimi vermek gerekmiyor.

## Önceki test sonucundaki ölçüt hatası

Önceki 289 birim testi ve gerçek model testleri gerçekten geçti. Bunlar arayüz, güvenlik,
seçilmiş cümleler ve belirli dosya eşleşmeleri için kanıttır; genel asistan kalitesinin kanıtı değildir.

`test_everyday_file_goals_across_domains`, aranan dosyanın sonuçlarda bulunmasını denetliyor;
yanlış sonuç sayısını, konumu, zamanı ve aramanın ne kadar daraltıldığını denetlemiyor. Küçük örnek
arşivde her isteğe `query="*"` döndürmek bütün hedef dosyaları sonuçlara katıyor.

Çalıştırılmış karşı örnek: kullanıcı girdisini yorumlamayan, her seferinde aynı `*` sorgusunu veren
FakeIntentModel, bu test fonksiyonundaki **16 isteğin tamamını geçti**. Test değiştirilmedi.
Bu, bütün testlerin geçersiz olduğunu söylemez; önceki “16/16 doğal isteği anlıyor” yorumunu geçersiz
kılar. İlgili test: [test_natural_file_goals.py](../../services/brain/tests/integration/test_natural_file_goals.py:140).
Tekrar üretim: `scripts/evaluation/audit_file_goal_assertions.py`.

Ayrıca olumlu örnekler çoğunlukla yeni Brain örneğiyle, olumsuzluk/sohbet örnekleri de temiz durumla
deneniyor. Dört mesajlık ardışık testin bütün mesajları yine olumlu arama istekleri. Bul → reddet →
isim bilinmiyor → kapsamı düzelt → neden diye sor → sohbete geç zinciri ölçülmemişti.
Başlangıçta ayrılan diğer örnekler de geliştirmede incelendiği için bağımsız kör değerlendirme sayılmaz.

## Yeniden üretim

Yerel, sabit Qwen3-4B-Instruct-2507 Q4_K_M / llama-cpp-python 0.3.35 kullanıldı. Sentetik katalog
gerçek ad/uzantı/klasör eşleştirmesi yapıyor. Bütün açmalar yalnızca kayda geçiyor; gerçek Core/IPC
bağlantısı, uygulama açılması, kişisel belge okuması veya eğitim yok. Seçim süresi deneyde sabitlenerek
120 saniyelik zaman aşımı ayrı bir değişken olarak dışarıda tutuldu.

- 8 mesaj × 3 bağlam koşulu = 24 yönlendirme gözlemi.
- 14 mesajlık kesintisiz senaryo, model aşamaları ve araç argümanlarıyla kaydedildi.
- Daha zengin, çalıştırılmayan bir anlam şemasıyla 8 gözlem yapıldı.
- 5 gerçek senaryo bağlamında 3 sunum biçimiyle 15 ek yönlendirme gözlemi yapıldı.
- 5 anlam örneğinde 3 sunum biçimiyle 15 ek gözlem yapıldı.

Bunlar 76 teşhis gözlemidir; birbirinden bağımsız 76 başarılı test veya bir model kıyaslama puanı
değildir. Ham sentetik kayıtlar ignored `target/assistant-analysis/` altında: diagnostic.json,
rendering.json, test-oracle.json. Kayıttaki her davranış birebir tekrarlanmadı.

| Kullanıcı amacı | Sentetik ardışık denemedeki gerçek karar | Teşhis |
|---|---|---|
| Masaüstündeki notu aç | Yönlendirme perform_action / 1.0; plan unsupported / 1.0; araç yok | Rust reddetmiyor; Brain planı desteklenen hedefi çözemiyor. |
| Önceki ret sonrası “neden?” | locate_file / 1.0; query=turnuva; eski dosya yeniden aranıyor | Güncel açıklama isteği eski görevle karışıyor. |
| Masaüstünde adı bilinmeyen not | query=not; konum yok; AnnotationManager ve üretim-notu dönüyor | Belge türü/amacı, dosya adı zannediliyor; konum kısıtı kayboluyor. |
| “Bunlar değil”, “ismini hatırlamıyorum” | locate_file doğru; zorunlu arama planı 0.7; genel açıklatma metni | Kullanıcı ipucu anlaşılmış olsa da uygun sonraki soru üretilemiyor. |
| Masaüstünde neler var? | list_folder(query="*"); tüm köklerde klasör araması | Araç çağrılması var; kullanıcının istediği kapsam yok. |
| “Alt klasörler değil, normal masaüstü” | select_file, action=open; masaüstü klasörü açılıyor | Listeleme düzeltmesi açma eylemine dönüşebiliyor. |
| “Alt klasör araması yapma” | Global list_folder(query="*") | Kapsam düzeltmesini ifade eden ve uygulayan bir sözleşme yok. |

Kullanıcı kaydındaki “hava güzel, mutluyum” mesajının dosya aratması sentetik ardışık denemede
tekrarlanmadı: sohbet yolu seçildi, araç çağrılmadı. Buna karşın cevap İngilizce çıktı. Bu nedenle
bu örneğe “hatası kesin çözüldü” veya “sebebi kesin şudur” demiyoruz. Bağlam/gerçek katalog/
oturum süresi gibi farklarla inceleme gerektiren bir kullanıcı kaydı olarak tutuluyor.

## Kodda doğrulanan nedenler

### 1. Arama şeması gerektiğinde soru soramıyor

`locating_file=True` halinde provider doğrudan FILE_SEARCH_SCHEMA üretmeye zorlanıyor.
Bu şemada soru, yanıt, isim bilinmiyor veya sonuçları reddetme alanı yok; zorunlu query ve filtreler
var. Model “hangi tür not?”, “doğrudan masaüstüne mi kaydettin?” gibi bir sonraki konuşma adımını
bu yoldan üretemez. 0.7 gibi düşük bir skor ise hedefli soru yerine sabit “daha açık ifade et” oluyor.
Ek olarak locate_file için runtime yalnızca search_files/clarify kabul ediyor; salt okunur klasör
listeleyerek aramayı daraltmak bile bu amaç altında mümkün değil.

Kaynaklar: [provider](../../services/brain/src/jarvis_brain/intelligence/models/qwen_gguf.py:192),
[arama şeması](../../services/brain/src/jarvis_brain/intelligence/prompts.py:356),
[amaç koruması](../../services/brain/src/jarvis_brain/intelligence/runtime.py:150).

### 2. Hedef ve kısıtlar diyalog boyunca temsil edilmiyor

Python model sözleşmesi query/sort/extension/kind taşıyor. Arama için masaüstü gibi anlamsal konum,
alt klasörlere girme tercihi, ismin bilinmemesi, reddedilen adaylar ve ipuçları ayrı alanlar değil.
FileSession sadece belirli göreli ifadelerde önceden edinilmiş folder_id uyguluyor; açıkça yeni bir
“masaüstünde” kısıtı tek başına bu mekanizmaya bağlanmıyor. Scope ve görüntülenen sayfa, devam eden
kullanıcı hedefinin yerine geçiyor.

Rust search_files aslında folder_id ve modified_after/modified_before destekliyor. Bunlar Brain'ın
model sözleşmesine bağlı değil. search_files bir klasörün altını özyinelemeli arıyor; list_directory
ise doğrudan çocukları listeleyebiliyor. Dolayısıyla “Rust bu işi yapamıyor” sonucu yanlış.
“Bugün indirdim” ayrıca değiştirilme zamanı ile aynı şey değildir; indirme zamanı anlamı tanımlanmadan
modified_after eklemek de doğru çözüm olmaz.

Kaynaklar: [FileSession](../../services/brain/src/jarvis_brain/intelligence/file_session.py:302),
[Rust arama alanları](../../core/native/src/files/catalog.rs:44),
[doğrudan çocuk listeleme](../../core/native/src/files/catalog.rs:283).

### 3. Model sonuçtan sonra değerlendirme yapmıyor

Mevcut akış araç sonucunu çoğunlukla doğrudan sabit metne çeviriyor. Modelin eşleşme sayısını,
yanlış kapsamı, kısmi taramayı, kullanıcı reddini ve sonraki anlamlı adımı birlikte değerlendirdiği
bir geri besleme döngüsü yok. “Not” sorgusunun ilgisiz teknik dosyalar getirmesini fark edip
strateji değiştirecek planlayıcı çalışmıyor. Literal alt dize araması kendi tanımına göre doğru
çalışırken kullanıcı hedefi hâlâ karşılanmamış oluyor.

Kaynak: [araç sonucu ve metin üretimi](../../services/brain/src/jarvis_brain/intelligence/file_session.py:380).

### 4. Bağlamın anlamı, modelin pencere sınırından önce kaybediliyor

Görüntülenen aday varken planlama geçmişi iki kullanıcı mesajına indiriliyor ve bütün asistan
mesajları çıkarılıyor. Unsupported cevapları da ayrı planlama belleğinde boşaltılıyor. Yanlış
asistan yetenek iddialarına güvenmemek doğru; fakat doğrulanmış sonuç, başarısızlık ve neden bilgisi
ayrı bir yapı olarak korunmadığı için “neden?” gibi bir mesaj açıklanacak olayı kaybedebiliyor.

Ayrıca tek kullanıcı JSON'u içinde **güncel mesaj önce, geçmiş ve adaylar sonra** geliyor. Modelin
en son gördüğü bilgi güncel mesaj olmayabiliyor. Aynı model/aynı yönlendirme prompt'u/aynı grammar
ile sadece JSON alan sırası değiştirildiğinde, kesintisiz senaryodaki “neden?” locate_file / 1.0
yerine recall / 0.95 oldu. Böylece bu hata için sunum biçiminin katkısı deneyle gösterildi.

Ancak geçmişi ayrı chat mesajlarına çevirmek bütün örnekleri düzeltmedi, bazılarında amaç kararını
bozdu. Daha zengin alanlar da tek başına çözmedi; şema içi çelişkili kararlar devam etti. Bu yüzden
tek bir sıra değişikliğini “sistem düzeldi” diye yayına almak doğru olmaz.

Kaynaklar: [geçmişin kesilmesi](../../services/brain/src/jarvis_brain/intelligence/runtime.py:247),
[bellek ayrımı](../../services/brain/src/jarvis_brain/intelligence/conversation.py:37),
[JSON alan sırası](../../services/brain/src/jarvis_brain/intelligence/prompts.py:150).

### 5. Güven skoru doğruluk olasılığı değil

Yanlış “neden?” araması için model 1.0 üretti; ad bilinmiyor açıklamasında 0.7 üretti. Bunlar
modelin oluşturduğu sayılar. Sayının biçimini ve aralığını doğrulamak, doğruluğa göre kalibre
edildiğini göstermiyor. Eşiği düşürmek yanlış işlemleri; yükseltmek de yararlı açıklamaları
engelleyebilir. Amaç/işlem/kapsam tutarlılığı ayrıca doğrulanmalı.

## Model kapasitesi hakkında söylenebilenler

- Mevcut 4B Q4 çalıştırması Türkçe diyalog ve birbiriyle ilişkili alanlarda tutarlı karar vermekte
  zorlanıyor. Aynı nesneyi/aynı hedefi konuşma boyunca koruma kalitesi şu haliyle yeterli değil.
- Bunun bir bölümünün sunum ve sözleşme tasarımına bağlı olduğu gösterildi. Başka bir bölümünü
  yalnızca parametre sayısına veya Q4'e atfetmek için karşılaştırmalı deney eksik.
- Uygulama 2048 giriş/128 çıkış token'ıyla sınırlı; GGUF backing context 2304. Kesintisiz denemede
  en büyük giriş 1704, en büyük çıkış 40 token oldu. Bu hatalar context-overflow veya çıktı
  kesilmesiyle açıklanmıyor; bilgi kaybı ve karışma daha önce oluyor.
- Resmî [Qwen model kartı](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), 262144 doğal bağlam
  uzunluğu ve non-thinking model olduğunu belirtiyor. Bu, 8 GB GPU'da o pencerenin çalışacağı veya
  yerel Q4 sürümün yeterli olacağı anlamına gelmez. `/think` eklemek bu modelde ayrı bir düşünme
  modunu açmaz. Daha fazla bağlam/çıktı bütçesi ancak bellek, gecikme ve kaliteyle birlikte ölçülmeli.
- Daha büyük modelin, eksik konum/özyineleme alanlarını bugünkü sözleşmeden iletmesi yine mümkün
  olmaz. Eğitim veya model değişimi, mevcut test ölçütüyle değerlendirilirse yanlış başarı raporu
  üretmeye devam edebilir.

## Önerilen mühendislik sırası

1. **Önce kabul ölçütü:** yalnızca doğru dosyanın bir yerde bulunması değil; gereksiz işlem,
   yanlış kapsam, gereksiz soru, tekrar edilen reddedilmiş sonuç ve dil tutarlılığı ölçülsün.
   Her şeye `*` döndüren, önceki sorguyu tekrar eden ve konumu yok sayan kontrol modelleri
   senaryo testlerinden geçememeli. Geliştirmede görülmeyen konuşmalar ayrı tutulmalı.
2. **Diyalog ve görev durumu:** amaç, bilinen/bilinmeyen ad, konum, kapsam, reddedilen adaylar,
   son doğrulanmış sonuç ve sorulan açıklatma sorusu ayrı tutulsun. Sohbet, açıklama, düzeltme,
   iptal ve devam etme farklı konuşma hareketleri olarak anlaşılsın. Serbest asistan iddiası ile
   doğrulanmış yürütme sonucu aynı güven düzeyinde olmasın.
3. **Kabiliyet ve plan sözleşmesi:** konum ve kapsam anlamsal alanlar olsun. Model hedefli soru
   sorabilsin; ad bilinmiyorsa salt okunur listeleme/arama adımlarını seçebilsin. Sonuçtan sonra
   kısıtlı sayıda yeniden değerlendirme yapılabilsin. Bulma isteği açma izni sayılmasın. Bütün
   makine işlemleri mevcut JarvisCoreClient → pipe → registry → validation → policy → executor
   yolunda kalsın; model yine path/ID/executable üretmesin.
4. **Sonra model karşılaştırması:** aynı kör konuşmalar, aynı araçlar ve aynı donanım ölçümüyle
   mevcut 4B çalıştırması ile alternatif model/kuantizasyon karşılaştırılsın. Sözleşme, model ve
   context bütçesi aynı anda değiştirilmesin. Karar, hedef tamamlama ve yanlış işlem oranlarıyla
   gecikme/VRAM birlikte değerlendirilerek verilsin.

Örnek kabul zinciri: adı rastgele masaüstü notu → ilgili konum ve biçim ipucuyla daraltma → yanlış
adayları reddetme → alt klasörleri dışlama → doğrudan masaüstü içeriği → “neden?” açıklaması →
gündelik sohbet. Sohbet/açıklama adımlarında araç çağrısı olmamalı; doğrudan masaüstü isteğinde
Belgeler/İndirilenler veya alt proje dizinleri sonuçlara karışmamalı. Adında “not” bulunmayan gerçek
hedef de erişilebilir olmalı; bu sırada belge içeriği okunmuş gibi davranılmamalı.

## Tekrar üretim

Depo kökünden, mevcut yerel Python/venv ile:

```powershell
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = ((Get-Location).Path, (Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
& $taskPython -m scripts.evaluation.audit_file_goal_assertions --output target/assistant-analysis/test-oracle.json
& $taskPython -m scripts.evaluation.analyze_file_assistance --run-local-model --output target/assistant-analysis/diagnostic.json
& $taskPython -m scripts.evaluation.probe_context_rendering --run-local-model --input target/assistant-analysis/diagnostic.json --output target/assistant-analysis/rendering.json
& $taskPython -m ruff check scripts/evaluation/analyze_file_assistance.py scripts/evaluation/audit_file_goal_assertions.py scripts/evaluation/probe_context_rendering.py
& $taskPython -m ruff format --check scripts/evaluation/analyze_file_assistance.py scripts/evaluation/audit_file_goal_assertions.py scripts/evaluation/probe_context_rendering.py
```

Bu turdaki dosyalar: üç teşhis aracı, bu rapor ve handoff/önceki kabul beyanına açıklama. Üretim
akışına yeni davranış, model indirme/eğitim, Core yeniden başlatma, commit veya push eklenmedi.

Bu bölüm 14 Ekim teşhisinin tarihsel kaydıdır. Kullanıcının ardından onayladığı geliştirme,
güçlendirilmiş kabul kontrolleri ve ayrı Q8 karşılaştırması
[ASSISTANT_DIALOGUE.md](ASSISTANT_DIALOGUE.md) belgesinde izlenir; güncel durum için o belgeye bak.
