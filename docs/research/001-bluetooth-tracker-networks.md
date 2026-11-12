# Araştırma Notu 001 — Bluetooth Takip Ağları (Samsung SmartTag vb.)

**Durum:** Fikir / sonraki çalışma için not. Henüz deney yapılmadı.
**Tarih:** 2026-11-12

## Fikir

Samsung SmartTag, dünyanın neredeyse her yerinden konumunu bildirebiliyor. Aynı yapıyı:

1. **Kimlik** olarak kullanmak (bir cihazı/kişiyi tanımlayan küçük bir Bluetooth işareti),
2. Sonrasında **yalnızca konum (veya çok küçük veri) üzerinden iletişim** kurmak

mümkün olabilir mi?

## SmartTag aslında nasıl çalışıyor?

SmartTag'in kendi interneti veya GPS'i yok. Çalışma zinciri kabaca şöyle:

```
SmartTag ──(BLE yayını)──▶ Yakından geçen herhangi bir Galaxy telefon
                              │ (kendi GPS konumunu ekler, şifreler)
                              ▼
                     Samsung sunucuları (SmartThings Find)
                              │
                              ▼
                     Etiketin sahibi konumu sorgular
```

- Etiket sürekli kısa Bluetooth Low Energy (BLE) yayınları yapar; kimliği gizlilik için periyodik olarak değişir.
- "Offline Finding"e izin vermiş, yakından geçen bir Galaxy cihaz bu yayını duyar, kendi konumunu ekleyip şifreli olarak Samsung'a yükler.
- Sahip, Samsung hesabıyla bu raporları çeker.

**Önemli düzeltmeler:**

- **"Anında" değil:** Konum, ancak yakından bir Galaxy cihaz geçtiğinde güncellenir. Kalabalık şehirde dakikalar, ıssız yerde saatler/günler sürebilir veya hiç gelmeyebilir.
- **Aracısız değil:** Zincir tamamen Samsung'un sunucularına, Samsung hesabına, başkalarının telefonlarına ve internete bağlı. Bu, QC'nin "sıfır aracı" ilkesinin tam tersi.

Apple AirTag (Find My), Google Find My Device ağı ve Tile de aynı "kalabalık kaynaklı (crowd-sourced) aktarım" modelini kullanır.

## Bu ağlar iletişim için kullanılabilir mi? — Bilinen çalışmalar

Evet, sınırlı ölçüde gösterildi (kaynaklar ayrıca doğrulanmalı):

- **"Send My" (Positive Security, 2021):** Apple Find My ağı üzerinden, yayınlanan açık anahtarların içine veri gizleyerek internete bağlı olmayan bir cihazdan küçük veri sızdırmanın mümkün olduğu gösterildi. Bant genişliği çok düşük (saniyede birkaç bayt mertebesinde), gecikme yüksek.
- **OpenHaystack (TU Darmstadt SEEMOO):** Apple Find My ağına kendi BLE cihazlarını dahil etmeye yarayan açık kaynak çerçeve.
- **SEEMOO'nun Samsung Offline Finding analizi:** Samsung'un sisteminin güvenlik/gizlilik incelemesi; protokolün nasıl çalıştığına dair en iyi başlangıç kaynağı olabilir.

**Sınırlar ve riskler:**

- Çok düşük bant genişliği → yalnızca kimlik, "buradayım", kısa durum kodları gibi minik mesajlar.
- Üretici ağını bu amaçla kullanmak kullanım şartlarını ihlal edebilir; üretici protokolü her an değiştirebilir veya engelleyebilir.
- Takip karşıtı korumalar (bilinmeyen etiket uyarıları, IETF DULT standardı) bu tür kullanımları tespit edip kullanıcıları uyarabilir.
- Konum verisi en hassas kişisel verilerden biri; tasarımda kötüye kullanım (izinsiz takip) baştan engellenmeli.

## QC için asıl çıkarım

SmartTag'in değerli olan tarafı Samsung'un sunucuları değil, **modelin kendisi**:

> Küçük, şifreli bir işaret yayınla → yakından geçen herhangi bir düğüm onu taşısın → alıcıya ulaşsın.

Bu, QC yol haritasındaki **store-and-forward (sakla ve ilet)** maddesiyle aynı fikir. QC bunu kendi düğümleriyle, üretici sunucusu olmadan yapabilir:

1. **BLE kimlik işareti:** Her QC düğümü, kendi anahtarından türetilen ve periyodik olarak değişen bir BLE yayını yapar (izlenemez ama arkadaşları tarafından tanınabilir).
2. **Yakınlık keşfi:** Kişi listesindeki biri yakına gelince internetsiz fark edilir.
3. **Taşıyıcı düğümler:** Yakından geçen QC düğümleri şifreli zarfları (envelope) okuyamadan taşır ve hedefe yaklaştıkça bırakır — internetsiz, gecikmeye dayanıklı bir ağ (DTN).
4. **Konum mesajı:** "Konumum / güvendeyim" gibi kısa durum mesajları, mevcut zarf formatıyla şifreli şekilde gönderilir.

Kısıt: Bu ağ, ancak yeterince QC düğümü olduğunda kapsama sağlar. Samsung'un avantajı yüz milyonlarca telefon; QC bunu ancak kullanıcı sayısıyla yakalayabilir. Ara çözüm olarak üretici ağları yalnızca **deney** amaçlı incelenebilir.

## Sonraki adımlar (önerilen)

- [ ] SEEMOO'nun Samsung Offline Finding makalesini ve "Send My" yazısını okuyup notları doğrulamak
- [ ] Bluetooth'lu bir cihazda (laptop / Raspberry Pi) BLE yayını + tarama prototipi (`bleak` kütüphanesi)
- [ ] QC anahtarından dönen (rotating) BLE kimliği türetme şeması tasarlamak
- [ ] `qc/transports/ble.py`: çok küçük zarflar için BLE transport denemesi
- [ ] Store-and-forward tasarımı: kim neyi ne kadar süre taşır, spam/doldurma saldırısına karşı sınırlar
