# Bağımsız Windows uyandırma bileşeni — önerilen plan

Durum: **yalnızca plan; henüz geliştirilmedi veya kurulmadı.** Kullanıcının 2026-10-19 düzeltmesi
önceki Core/Qt içine gömülü uyandırma yaklaşımının yerini alır. O entegrasyon kaldırıldı.

## Hedef ve mimari karar

JARVIS kapalıyken arayüz, Python, büyük dil modeli ve tam konuşma tanıyıcısı bellekte durmamalı.
Windows kullanıcı oturumunda ayrı ve küçük bir `jarvis-wake.exe` çalışmalı. Yalnızca seslenme
ifadesini algılamalı; ardından JARVIS'i sıfırdan başlatmalı. Asistan kapanınca küçük dinleyici
beklemeye dönmeli. Bellek kazancını arayüzü gizlemek değil, ağır süreçleri sonlandırmak sağlar.

**Ayrı Rust executable / ayrı crate öneriyorum; mevcut Core'a bağlanmamalı.** Aynı depoda
geliştirilebilir. `jarvis-core` kütüphanesine doğrudan bağımlılık, Whisper/transcribe GPU DLL'leri
ve diğer ağır bağımlılıkları dinleyiciye taşıyabilir. Gerekirse yalnızca küçük IPC tipleri ve
kurulum doğrulama kodu bağımsız, hafif bir ortak crate'e ayrılır.

| Parça | JARVIS kapalıyken | Sorumluluk |
|---|---|---|
| `jarvis-wake.exe` | Çalışır | Mikrofon, küçük keyword detector, tek örnek kontrolü, sabit başlatma |
| Sabit native launcher | Yalnız başlatırken | Doğrulanmış yerel kurulumu açar, süreç sahipliğini kaydeder |
| Rust Core | Gerekmedikçe kapalı | Makine araçları, registry, validation, policy, executor |
| Qt + Python Brain | Kapalı | Arayüz, konuşma ASR/TTS akışı ve planlama |
| GGUF dil modeli / normal ASR | Yüklü değil | Asistan açıldığında ihtiyaç üzerine yüklenir |

Başka bir istemcinin kullandığı paylaşılan Core zorla kapatılmaz. Süreç sahipliğinin launcher
tarafında açıkça tutulması gerekir; yalnızca kendi başlattığı süreçleri durdurabilir.

## Windows ile bütünleşme

İlk tercih, kullanıcı oturum açınca başlayan **arka plan uygulaması**. Klasik SCM hizmeti
Session 0'da çalışır ve kullanıcı arayüzünü doğrudan açamaz; ek oturum aracısı gerektirir.
Bu ihtiyaç için başlangıçta iki servis/süreç katmanı kurmak gereksiz karmaşıklık olur.
[Microsoft: Interactive Services](https://learn.microsoft.com/en-us/windows/desktop/services/interactive-services).

Kurulum aşamasında kullanıcıya ait başlangıç girdisi eklenebilir; yönetici/LocalSystem
yetkisi gerekmez. Başlangıçta yalnız küçük dinleyici açılır.
[Microsoft: Run keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys).
Bu düzeltme sırasında başlangıç girdisi eklenmedi. İlk prototip elle başlatılmalı; oturum açılışı
entegrasyonu, ölçümler geçtikten sonraki kurulum adımı olmalı.

Küçük native tepsi simgesi dinleyicinin durumunu ve Durdur/Devam/Çıkış seçeneklerini gösterebilir.
Bu simge Qt'yi veya asistan modelini bellekte tutmaz. Kilitli oturum/uyku/mikrofon kaybı için
duraklama ve güvenli yeniden açma davranışları ayrıca tanımlanır.

## Çalışma akışı

```text
Kullanıcı oturum açar
    -> küçük Rust dinleyici
    -> seslenme algılanır
    -> mikrofon bırakılır + tekrar algılama kilitlenir
    -> sabit native launcher
    -> Core + Qt/Brain başlar, model ihtiyaç üzerine yüklenir
    -> hazır bildirimi; normal ses girişinin sahibi asistan olur
    -> kullanıcı JARVIS'i kapatır
    -> Qt/Brain/model çıkar; yalnız sahip olunan Core kapatılır
    -> dinleyici tekrar mikrofonu alır
```

Başlatılıyor/Çalışıyor/Kapanıyor durumlarında tekrar seslenme ikinci bir 9B süreç açmamalı.
Hazır bildirimi gelmezse zaman aşımı/hata gösterilmeli; sınırsız yeniden başlatma yapılmamalı.
UI zaten açıksa tek örnek/aktivasyon protokolü kullanılmalı. Kapanma/çökme sonrası mikrofon
sahipliği PID ve oturum doğrulamasıyla geri alınmalı; aynı anda iki süreç kayıt yapmamalı.

## Ses motoru kararı ve bellek bütçesi

Sürekli tam konuşmayı yazıya çeviren Whisper-small bu hedefin başlangıç çözümü olmamalı.
İlk ölçüm adayı **PocketSphinx'in native keyword spotting modu**: `keyphrase`, eşik ve algılama
gecikmesi ayarları var; projenin native Windows mikrofon örneği de mevcut.
[Kaynak ayarları](https://github.com/cmusphinx/pocketsphinx/blob/main/src/config_macro.h),
[Windows örneği](https://github.com/cmusphinx/pocketsphinx/blob/main/examples/live_win32.c).
Rust tarafı C ABI üzerinden küçük ve sınırlandırılmış bir adapter kullanabilir.

Bu bir motor seçimi garantisi değil: İngilizce seslenmenin Türkçe aksanda başarısı, gürültüde
yanlış tetikleme ve gerçek bellek/CPU ölçülmeden varsayılan yapılmamalı. Sürüm/lisans/model
dosyaları ve checksum kurulumdan önce doğrulanmalı. Başarısızsa başka native/offline küçük
detector ölçülmeli; mevcut ONNX yasağı kendiliğinden kaldırılmamalı. Bulut/API gerekmemeli.

İlk kabul hedefleri — henüz ölçülmüş sonuç değildir:

- Qt/Python/LLM/tam ASR yüklemeden çalışmak; **ek GPU/VRAM kullanımı sıfır**.
- Yalnız dinleyici için başlangıç hedefi **100 MB altında private bytes**, 10 dakika sessizlikte
  makine toplamına normalize ortalama CPU hedefi **%1 altında**; çalışma kümesi ayrıca raporlanır.
- Seslenme bitiminden algılamaya başlangıç hedefi **1 saniyenin altında**. Uygulama/modelin soğuk
  açılış süresi ayrı ölçülür; bunu detector gecikmesiyle karıştırmayız.
- Farklı mesafeler, Türkçe aksan ve İngilizce örneklerde kaçırma oranı; benzer isimler, TV,
  müzik, sıradan konuşma ve uzun sessizlikte yanlış tetikleme/saat raporlanır. İlk uzun test hedefi
  8 saatte en fazla bir yanlış açılmadır; sentetik sesler gerçek kullanıcı doğruluğunu kanıtlamaz.

## Güven sınırı

Dinleyici yalnızca önceden izin verilen **JARVIS'i başlat** olayını üretebilir. Tanınan metin,
shell komutu, executable yolu, uygulama kimliği veya model talimatı taşıyamaz. Native launcher
kurulumda belirlenen sabit hedefi doğrular; PATH'ten rastgele program aramaz, shell çağırmaz.
Bu, bugün sabit launcher'ın Core/Qt'yi açmasına benzer güvenilir bir başlangıç işlemidir;
asistan açıldıktan sonraki model eylemleri yine JarvisCoreClient -> Named Pipe -> Rust registry
-> validation -> policy -> executor yolundan geçer.

Dinleyici/launcher kontrolü için gerekirse SID ile sınırlandırılmış küçük, sürümlü Named Pipe
protokolü kullanılır: durum, hazır, duraklat, devam, çıkış. Ham PCM ve arka plan konuşması bu
kanala veya Brain'e gitmez. Ses kaydı/konuşma günlüğü tutulmaz. Yapılandırma ve pinned küçük
model `%LOCALAPPDATA%\JARVIS\wake` altında; çalışma verisi kaynak klasörünün içinde değil.

## Geliştirme sırası

1. **Şimdi:** yanlış entegrasyonu kaldır, sohbetten gerçek kapatmayı doğrula. Yeni daemon yazma.
2. **Küçük detector prototipi:** tek Rust executable; yalnız algılama/durum, uygulama açmadan
   RAM/CPU/gecikme/yanlış tetikleme ölçümü. Karar kapısı bu sonuçlar.
3. **Sabit başlatıcı ve tek örnek:** Core/UI/Brain kapalıyken soğuk açılış, açılış hatası,
   tekrarlanan seslenme, sahip olunan süreçlerin kapanması.
4. **Mikrofon devri ve native kontrol:** asistanla çakışmasız geçiş; çökme, uyku/uyanma,
   cihaz çıkarma/değiştirme testleri.
5. **Windows başlangıç kurulumu ve son bellek testi:** oturum açma kaydı + açık kapatma,
   20 aç/kapat döngüsü sonrası worker/GPU/bellek sızıntısı kontrolü, uzun negatif ses denemesi.

Bu planın uygulanması sonraki geliştirme işidir; şu an çalışan bir bağımsız dinleyici yoktur.
