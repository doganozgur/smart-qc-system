# Smart Vision QC - Endüstriyel Kalite Kontrol & Sürekli Öğrenme Sistemi

PC sunucusundan veri çeken, çok aşamalı görüntü işleme hattıyla (parça konumlama + altın referans "OK" modellerine göre failure/anomali tespiti + alt bileşen kontrolleri) çalışan, operatör arayüzüne sahip ve operatörün verdiği kararlardan sürekli öğrenen (Active Learning) akıllı kalite kontrol sistemi.

## 🚀 Mimari ve Özellikler

1. **PC Sunucu & İstemci İletişimi (`server/` & `client/network_client.py`):**
   - FastAPI tabanlı sunucu, konveyör kamera akışını (`/api/stream/next`), referans modelleri ve karar telemetrilerini sunar.
   - İstemci sunucuya bağlıyken senkronize çalışır; sunucu çevrimdışıyken yerel test moduna kesintisiz geçer.

2. **Aşama 1: Parça Konumlama ve Açı Düzeltme (`core/locator.py`):**
   - Gelen ham kamera görüntüsünde parçayı arka plandan ayırır, yönlendirilmiş sınır kutusunu (Oriented Bounding Box - OBB) ve dönme açısını bulur.
   - Parçayı standart referans koordinat düzlemine (500x350 piksel) perspektif dönüşümüyle hizalar.

3. **Aşama 2: "OK" Referans Tabanlı Failure & Anomali Tespiti (`core/golden_reference.py`):**
   - Sistem yalnızca onaylanmış "OK" referans parçalarını temel alır.
   - Gelen parçayı referans modelle çok ölçekli yapısal ve gradyan düzeyinde karşılaştırır.
   - Çizik, çatlak, gözenek, leke veya eksik lehim gibi kusurları anomali ısı haritası (Heatmap) ve kusur kutucukları (Defect BBoxes) olarak çıkarır.

4. **Aşama 3: Kural Tabanlı Alt Kontroller (`core/pipeline.py`):**
   - 4 köşe montaj deliğinin sağlamlığı ve kontrastı.
   - Merkezi mikrodenetleyici entegresinin (IC) yerleşimi ve varlığı.

5. **Aşama 4: Operatör Kararından Öğrenme (`core/active_learner.py`):**
   - **Hatalı Ret Düzeltmesi (Model NOK dedi, Operatör OK dedi):** Sistem bu görüntüyü onaylı OK hafıza havuzuna ekler, benzer proses/ışık varyasyonlarını bir daha reddetmez.
   - **Hatalı Kabul Düzeltmesi (Model OK dedi, Operatör NOK dedi):** Modelin anomali hassasiyet eşiğini sıkılaştırır ve hatayı zor örnekler havuzuna kaydeder.
   - Tüm öğrenme adımları ve istatistikler SQLite veritabanında saklanır.

---

## 🛠 Kurulum ve Çalıştırma

### 1. Sanal Ortamı Aktifleştirme
```bash
cd /Users/doganozgur/.gemini/antigravity/scratch/smart_qc_system
source .venv/bin/activate
```

### 2. Sentetik Test Verilerini Oluşturma
```bash
python mock_data/generate_samples.py
```

### 3. PC Sunucusunu Başlatma (Terminal 1)
```bash
python server/server.py
```
*Sunucu varsayılan olarak `http://localhost:8000` adresinde çalışır ve API dökümantasyonu `http://localhost:8000/docs` adresindedir.*

### 4. Masaüstü Arayüzünü Başlatma (Terminal 2)
```bash
python client/app.py
```

---

## 🖥 Arayüz Kılavuzu
- **Görüntü Modları:** Ham kamera görüntüsü, hizalanmış parça (ROI), veya kusur ısı haritası (Heatmap Composite) arasında geçiş yapın.
- **Sonraki Parçayı Muayene Et:** Sunucudan sıradaki parçayı çeker ve milisaniyeler içinde OK / NOT OK kararını üretir.
- **Otomatik Akış:** Konveyör bandı simülasyonuyla parçaları aralıksız otomatik denetler.
- **Kararı Düzelt:** Model bir parçada yanıldığında tek tuşla müdahale edin; sistem geri bildiriminizden derhal öğrenir.
