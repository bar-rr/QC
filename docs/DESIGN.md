# QC Tasarım Notu — Enerji Odaklı Kriz Ağı

**Durum:** Tasarım taslağı. Henüz uygulanmadı ve ölçülmedi.

## 1. Hedef

Şebekenin, internetin ve elektriğin olmadığı, **tamamen çökmüş** bir ortamda insanların telefonları üzerinden birbirleriyle haberleşebilmesi.

- Amaç uyarı veya duyuru sistemi değil; kişiden kişiye iletişim.
- Uygulamayı (APK) yüklemiş herkes, menzil içindeyse aracısız doğrudan, menzil dışındaysa mesh üzerinden haberleşir.
- Her mesaj uçtan uca şifreli ve imzalıdır. Aradaki telefonlar içeriği okuyamaz.

## 2. Çözülecek asıl sorun: enerji

Krizde en kıt kaynak elektrik. Mevcut telefon mesh uygulamaları radyoyu **sürekli açık** tutarak çalışıyor:

- Bitchat (incelenen sürüm): Telefon 2 veya daha az bağlantıya sahipken ya da yakın zamanda trafik varken Bluetooth taraması kesintisiz çalışıyor. Yalnızken her 4 saniyede bir kendini duyuruyor. Aralıklı tarama (5 sn açık / 10 sn kapalı) yalnızca uygulama ön plandayken ve yeterli bağlantı varken devreye giriyor. Kaynak: `BLEScanDutyPolicy.swift`, `TransportConfig.swift`, `WHITEPAPER.md` §4.5.
- Sonuç: Telefon **yalnız kaldığında**, yani tam kriz senaryosunda, en çok enerjiyi harcıyor.
- Temel kısıt: Mesajın gitmesi için gönderen, aktaranlar ve alıcının **aynı anda** uyanık olması gerekiyor. Bunu "herkes sürekli açık" ile sağlamak krizde sürdürülemez.

## 3. QC'nin farkı: randevulu (senkronize) uyanma

Herkes sürekli açık kalmaz; **herkes önceden belirlenmiş aynı anlarda birlikte uyanır.**

```
Saat:   12:00   12:10   12:20   12:30
Radyo:  ██░░░░░░██░░░░░░██░░░░░░██░░░░░░
        ~30 sn açık, ~9,5 dk tamamen kapalı
```

### 3.1 Ortak saat (şebekesiz)
- Telefonun kendi saati şebeke olmadan çalışır; kayması günde birkaç saniye mertebesindedir.
- GPS, internet olmadan kesin saat verir (varsa kullanılır).
- Telefonlar karşılaştıklarında saatlerini birbirine göre düzeltir.
- Uyanma penceresi, saat kaymasını tolere edecek kadar geniş tutulur (örneğin ±5 sn tampon).

### 3.2 Mesaj gönderimi
- Kullanıcı mesaj yazdığında telefon hemen yayın yapmaz; mesaj **bir sonraki ortak uyanma anını** bekler.
- O anda çevredeki herkesin uyanık olduğu bilindiği için mesaj ve enerji boşa gitmez.
- İstisna: Kullanıcı isterse acil durumlarda anında yayın yapabilir ("Enkaz altındayım" gibi).

### 3.3 Pile göre iç içe takvim
Pil azaldıkça telefon daha seyrek uyanır, ama ağdan kopmaz:

| Pil | Uyanma sıklığı |
|---|---|
| Yüksek | Her 10 dakikada bir |
| Orta | Her 30 dakikada bir (:00 ve :30) |
| Düşük | Her saat başı (:00) |

Saat başı anları **tüm telefonlar için ortaktır.** Pili düşük bir telefon bile o anlarda herkesle buluşur; yalnızca daha yavaş haberleşir.

### 3.4 Taşıyıcı / çapa telefonlar (gönüllü)
- Uygulama kullanıcıya şunu sorar: **"Şarj imkânın var mı (powerbank, araç aküsü, güneş paneli)? Telefonunu taşıyıcı olarak kullanmaya izin veriyor musun?"**
- İzin verenlerin telefonları **sürekli açık posta kutusu** olur: başkalarının şifreli mesajlarını tutar ve aktarır.
- Telefon şarja takıldığında, kullanıcının izniyle otomatik olarak taşıyıcı moduna geçebilir; şarjdan çıkınca normal moda döner.
- Taşıyıcılar mesajları okuyamaz. Kişi ve toplam kotalarla kimse başkasının telefonunu dolduramaz.

### 3.5 Sakla ve ilet
- Alıcı ulaşılamıyorsa mesaj gönderende ve sınırlı sayıda taşıyıcıda şifreli olarak bekler.
- Alıcı herhangi bir uyanma anında bir taşıyıcıyla karşılaşınca mesaj teslim edilir. Alındı bilgisi kopyaları sildirir.
- Tutma süresi günler mertebesinde olur (öneri: 7 gün). Bitchat'teki 24 saat çökmüş sistem için kısa.

### 3.6 Hareket eden dinler, duran fısıldar (seyrek ağ çözümü)
- Her telefon çok düşük güçlü, bağlanılabilir bir Bluetooth işareti (beacon) yayınlar. Varsayılan maliyet ~3 mW; **ölçülmeli**.
- Telefon yürüyorsa (ivmeölçer hareket algılarsa) yürüdüğü sürece taramayı açık tutar ve yanından geçtiği her telefonla, o telefon uykudayken bile mesaj alışverişi yapar.
- Gerekçe: Yerinde duran insanlar arasındaki bağlantılar değişmez; onlara 10 dakikalık randevu yeter. Bağlantıları değiştiren şey hareket olduğu için keşfin enerji bedelini hareket eden telefon öder.
- Simülasyon (250 kişi, 30 m menzil): ortanca gecikme 15 saatten 7 saate iner, teslim oranı %53'ten %63'e çıkar. Radyo enerjisi sürekli açık moda göre yaklaşık 3,5 kat daha az kalır. Ayrıntı: `sim/README.md`.
- Denenip işe yaramayanlar: yalnız kalan telefonun penceresini uzatmak ve yürüyenleri daha sık uyandırmak. Diğerleri uykuda olduğu için tek taraflı uyanmak kimseyi bulmuyor.

## 4. Beklenen kazanç ve bedel

- **Kazanç:** Radyo zamanın yaklaşık %5'inde açık kalır; radyo enerjisi kabaca 20 kat azalır. Kesin rakam gerçek telefonlarda **ölçülmelidir**.
- **Bedel:** Mesaj anlık değildir; her aktarım adımı en fazla bir uyanma aralığı bekler. 3 adımlık bir yol yaklaşık 30 dakika sürebilir. Taşıyıcı telefonların olduğu bölgelerde gecikme azalır.

## 5. Platform gerçekleri

### Android (ilk hedef)
- Uygulama belirli saatlerde **kendi kendini uyandırabilir**: `AlarmManager.setAlarmClock` / `setExactAndAllowWhileIdle` ve exact alarm izni (`SCHEDULE_EXACT_ALARM` / `USE_EXACT_ALARM`).
- Taşıyıcı modu: Sürekli bildirimli ön plan servisi (foreground service).
- Risk: Bazı üreticilerin agresif pil tasarrufu (Xiaomi, Huawei vb.) alarmları geciktirebilir veya uygulamayı öldürebilir. Kullanıcıdan "pil optimizasyonundan muaf tut" izni istenmeli; cihaz bazında test şart.

### iOS (sonra)
- Uygulamanın belirli bir saatte güvenilir şekilde kendi kendini uyandırması **mümkün değil**. Arka plan görevlerinin zamanını sistem belirliyor.
- Olası yol: iOS, Bluetooth olayları ile uygulamayı arka planda uyandırabiliyor. Uyanma anında yayın yapan Android/taşıyıcı telefonlar, iPhone'ları bu yolla uyandırabilir. **Doğrulanması gerekiyor.**

## 6. Radyo

- Temel: **Bluetooth LE.** Az enerji harcar, her telefonda var, arka planda çalışabilir.
- Wi-Fi Aware / Wi-Fi Direct: İleride büyük veri (fotoğraf, ses) için isteğe bağlı ek. Fark radyodan değil çalışma mantığından gelir.
- 4G/5G hücresel radyo: Telefondan telefona kullanılamaz (modem kapalı, uygulamalara erişim yok, lisanslı frekans). Kapsam dışı.

## 7. Sonraki adımlar

1. **Simülasyon:** Binlerce sanal telefon, farklı pil seviyeleri ve hareket. Mesajın ulaşma oranı, gecikme ve enerji tüketimi; sürekli açık modelle karşılaştırma.
2. **Android prototip:** İki telefon arasında senkronize uyanma + Bluetooth mesaj alışverişi.
3. **Gerçek ölçüm:** Pil tüketimi, saat kayması, üretici pil tasarrufu davranışı.
4. Taşıyıcı modu ve sakla-ilet.
5. iOS'ta Bluetooth ile uyandırma araştırması.
