# Asistan davranışının yeniden değerlendirilmesi — 2026-10-16

Durum: **genel asistan kabulü başarısız**. ONNX kapatıldı; sohbet yanıtına metadata aktarımı
ve konuşurken görev bağlamının korunması düzeltildi. Bunlar mevcut planlayıcının tamamının
düzeldiği anlamına gelmiyor. Aşağıdaki başarısızlıklar saklanmadan kaydedildi.

## Kullanıcının kaydının gösterdiği sorun

Başlangıç çıktısı `QwenGgufIntentModel` gösteriyor. Bu oturumda ONNX çıkarım yapmıyordu.
Doğru yazılan sertifika isteği bir sonuç buluyor; ardından tek sonuca gönderme yapan açma
isteği gereksiz açıklatma istiyor. Yazım hatalı istekten sonraki klasör ve biçim cevapları
aranan konunun yerini alıyor. Öneri istendiğinde asistan olmayan bir yetki yasağı uyduruyor.

Bu hataların çoğu Core çağrısından önce oluşuyor. Rust'ın dosya açma gücü, bu karar hatalarını
açıklamıyor. Bir uygulamayla özel haberleşme de varsayılan uygulamada dosya açmak için gerekli değil;
Core zaten Windows dosya ilişkisini kullanıyor. Rastgele uygulama otomasyonu ayrı bir yetenektir.

## Kodda bulunan nedenler

1. Planlama tek bir tutarlı görev değerlendirmesi değil; birbirini daraltan amaç, hareket,
   işlem, hedef, konum, uygulama ve ek hedef eşleştirme kararlarına bölünmüş. Bazıları yalnızca
   son mesajı görüyor. Yerel olarak makul bir karar, bütün görevi bozabiliyor.
2. `qwen_gguf.plan_turn` yeni sorguyu son mesajın normalleştirilmiş alt dizisi olmaya zorluyor.
   Bu bir anlamsal doğrulama değil: yazım düzeltmesi veya eş anlamlı arama terimini silebilir.
   İnsan sorgusunu doğrulamakla güvenilir yol/kimlik üretimine izin vermek farklı meselelerdir.
   Bu kural bu turda kaldırılmadı; değiştirilmeden önce görev/işlem doğrulamasıyla birlikte
   yeniden tasarlanması gerekiyor.
3. Hedef eşleştirme geçişi, önceki seçici doğru sonucu bulsa da boş ad döndürebiliyor.
   Sonuç, tek satırlık listede bile gereksiz açıklatma. Sadece üretilen sayıyı doğrulamak da
   geçmişte yanlış satır açmayı engellememişti; iki yaklaşım da genel kabul sağlamadı.
4. Sohbet dalı mevcut adayları aktarmıyor, sohbet şablonu da son mesajı kurarken adayları
   düşürüyordu. Sonra sayfa ve görev siliniyordu. Öneri konuşması için gereken gözlem yoktu.
5. Ad araması başarısız olunca geniş tür araması ham bir liste döndürüyor. Dosya türünü bulmak,
   kullanıcının aradığı belgeyi anlamakla aynı şey değil. Sonuç değerlendirme ve sorgu düzeltme
   döngüsü eksik.

## Bu turdaki değişiklikler

- Factory varsayılanı GGUF. Açık `onnx` seçimi hata veriyor; otomatik geri dönüş yok.
- Launcher sadece `-Model gguf` kabul ediyor. ONNX Runtime GenAI zorunlu bağımlılık değil;
  ONNX sınıfı modellerin genel dışa aktarımından kaldırıldı. Eski kaynak ve arşiv testleri
  silinmedi, kurulu paket/model dosyaları kaldırılmadı.
- Sohbet modeline mevcut, süre sınırı geçmemiş adayların yalnızca ad/tür/sıra bilgisi
  aktarılıyor. Son şablon payload'ı bunu koruyor; geçmiş iki kez eklenmiyor.
- Salt konuşma görev/sayfayı tüketmiyor veya ömrünü uzatmıyor. İptal, reset ve süre sonu
  geçerliliğini koruyor. Metin yanıtı hiçbir Core çağrısını veya açma iznini üretmiyor.
- Yanıt sözleşmesi metadata üzerinden öneriye izin verildiğini, adın içerik/sahiplik kanıtı
  olmadığını anlatıyor. Öneri için belge içeriği açılmıyor.
- Cümleye veya belge adına özel üretim kuralı eklenmedi. Yeni bir planlayıcı canlıya alınmadı.

Python → JarvisCoreClient → Named Pipe → Rust registry → validation → policy → executor sınırı
korundu. Bu turda kişisel dosyalar okunmadı/açılmadı, Core yeniden başlatılmadı, model eğitilmedi
veya değiştirilmedi, yeni paket/model indirilmedi. Commit/push yapılmadı.

## Model mi, mimari mi?

İkisinin de etkisi gözlendi; tek bir suçlu ilan etmek için kanıt yok.

`compare_planner_contracts.py`, aynı 4B Q4 modele aynı sekiz sentetik durumu iki sözleşmeyle
veriyor: serbest kısa yanıt ve küçük düz JSON kararı. Hiçbir Core bağlantısı yok.

| Gözlem | Sonuç |
| --- | --- |
| Düz JSON'da klasör cevabı | Konu `garanti` kaldı, konum `indirilenler` oldu |
| Düz JSON'da biçim cevabı | Konu `garanti` kaldı, uzantı `pdf` oldu |
| Tek aday ve açma isteği | Düz JSON doğru sıra 1 ve `open` seçti |
| Adlardan öneri | Düz JSON doğru adayı önerdi |
| Yazım hatası | İki sözleşmede de gereksiz açıklatma |
| Olumsuz istek | Serbest yanıt açmayı teklif etti; JSON yanlış açıklatma seçti |

Düz JSON'da yalnızca eylem etiketi **6/8** doğru. Bu bir arama başarısı puanı değildir:
örneğin fatura sorgusunda gereksiz sözler ve çekimler var; gerçek dosya eşleşmesi ayrıca
doğrulanmalıdır. Örnekler görünür, tekrar sayısı bir; kör genelleme testi değildir.

Tam TurnPlan şemasını kullanan iki geçici tek-geçiş denemesi de gereksiz sorulara düştü ve
üretime alınmadı. Dolayısıyla sadece aşamaları birleştirmek de kanıtlanmış çözüm değil.

Önceki aynı-checkpoint Q4/Q8 tanısında iki model de 14 görünür bileşen sorusunun iki tekrarında
22/28 aldı. Daha yüksek kuantizasyon bu hataları çözmedi. Daha büyük parametreli model
karşılaştırılmadı; “4B kesin yetersiz”, “eğitim gerekli” veya “büyük model kesin çözer” sonucu
çıkarılamaz. [Önceki karşılaştırma](ASSISTANT_DIALOGUE.md) tarihsel ayrıntıları içeriyor.

## Güncel doğrulama

| Kontrol | Sonuç ve sınır |
| --- | --- |
| Olağan Brain testleri | **391 geçti, 51 isteğe bağlı test atlandı** |
| Gerçek GGUF öneri bileşeni | **4 geçti**; garanti, servis faturası, ders programı ve metadata yokluğu |
| Yeni gerçek GGUF uçtan uca regresyonları | **4 geçti, 3 başarısız**, 76.84 saniye |
| Factory temiz süreç kontrolü | Varsayılan GGUF, unloaded; ONNX adapter/runtime import edilmedi; açık ONNX reddedildi |
| Launcher | PowerShell sözdizimi doğrulandı; ONNX parametresi başlangıçtan önce reddediliyor |
| Statik kontroller | Ruff check, 79 dosyada format kontrolü ve git diff --check geçti |

Yeni regresyonlar CV kullanmıyor. Garanti, servis faturası, uçak bileti ve doğru yazılan
sertifika isteği tam olarak beklenen dosyayı buldu; açma çağrısı yapmadı. Kırk alakasız PDF
vardı; yalnızca hedefin listede bulunması veya bir search çağrısı yeterli sayılmadı.

Kalan üç başarısızlık:

- Yazım hatalı sertifika isteği Core aramasına ulaşmadı.
- Tek bulunan belgeye “onu açmanı istiyorum” cevabı açmak yerine açıklatma istedi.
- Bulunan garanti belgesi hakkında fikir sorusu sohbet yerine `query=dosya` ile yeni arama yaptı.

Bu son test, öneri bileşenindeki düzeltmenin yeterli olmadığını açıkça gösteriyor: planlayıcı
yanıt dalını seçmediğinde doğru metadata yanıtı üretilmiyor. Başarısız testler `xfail` yapılmadı
ve beklentileri gevşetilmedi. Önceki gerçek-model süitinin tamamı da yeşil değildi; özellikle
adla seçilen Edge açma regresyonunun başarılı olduğu varsayılmamalı.

Yerel kanıtlar `target/assistant-analysis/` altında (git tarafından hariç):
`ordinary-oct16.xml`, `metadata-reply.xml`, `metadata-reply.log`, `reported-dialogues.xml`,
`reported-dialogues.log`, `contract-ablation.json`. Geçici tek-geçiş denemesi
`unified-probe.json` ve `probe_unified.py` içinde; ürün kodu değil.

## Sonraki mimari kabul ölçütü

Bir sonraki planlayıcı; amaç, yeni kullanıcı bilgisi, bekleyen soru ve gerçek araç gözlemlerini
aynı görev bağlamında değerlendirmeli. Metadata üzerinden öneri, yeni arama ve açma ayrı
çıktılar olmalı. Araç tanımları gerekli/isteğe bağlı parametreleri anlatmalı; modelden belirli
kelimeleri kullanması beklenmemeli. Her araç sonucu yeni gözlem olmalı; sonuç yoksa model
sorguyu düzeltebilmeli veya gerekli tek soruyu sorabilmeli. Açma yetkisi ve güvenilir kimlik
bağlama bu anlamsal esnekliğe rağmen ayrı doğrulanmalı.

Yeni varsayılan seçmeden önce mevcut çok aşamalı planlayıcı, küçük araç-karar döngüsü ve
gerekirse daha güçlü yerel referans aynı gizli değerlendirme kümesinde karşılaştırılmalı.
Küme yalnızca belge adlarını değiştirmekle oluşmamalı: sohbet, olumsuzluk, yazım hatası,
sıralama, yanlış aday reddi, konum/biçim cevabı, zamir, belirsizlik, konu değişimi ve süre sonu
dahil konuşmalar içermeli. Tam doğru hedef/kapsam/işlem, yanlış açma, gereksiz soru, toparlanma
ve gecikme ayrı ölçülmeli. Mevcut görünür testler regresyon içindir; gizli kabul kümesi değildir.

## Tekrarlama

Depodaki mevcut paketler kullanıldı; kurulum gerekmedi:

```powershell
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = ((Get-Location).Path, (Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
& $taskPython -m pytest services/brain/tests -o addopts='' -q --tb=short
& $taskPython -m ruff check services/brain scripts/evaluation
& $taskPython -m ruff format --check services/brain scripts/evaluation
& $taskPython scripts/evaluation/compare_planner_contracts.py --output target/assistant-analysis/contract-ablation.json
$env:JARVIS_RUN_GGUF_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_metadata_reply.py -o addopts='' -q -s --junitxml=target/assistant-analysis/metadata-reply.xml
$env:JARVIS_RUN_ASSISTANT_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_reported_file_assistance.py -o addopts='' -q --junitxml=target/assistant-analysis/reported-dialogues.xml
git diff --check
```

Son komutlu model regresyonunun üç hata vermesi bu sürüm için beklenen **açık hata** durumudur;
başarılı kabul değildir. Windows PowerShell'in CUDA stderr yönlendirmesi log başına
`NativeCommandError` başlığı ekleyebiliyor; test sonucu için JUnit XML ve pytest özetine bakıldı.
