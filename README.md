# Smart Vision QC - Endüstriyel Kalite Kontrol & Sürekli Öğrenme Sistemi

PC sunucusundan veya harici kameralardan veri çeken, fotoğraf yükleyerek **altın referans "OK" modellerine** göre failure/anomali tespiti yapan, operatör arayüzüne sahip ve operatörün verdiği kararlardan anında öğrenen (**Human-in-the-Loop / Active Learning**) akıllı endüstriyel kalite kontrol sistemi.

Sistem hem **Kapı Kolu (Door Handle)** hem de **Elektronik Kart (PCB)** parçalarını destekler.

---

## 🚀 Mimari ve Özellikler

1. **Girdi Esnekliği (Kamera veya Fotoğraf Yükleme):**
   - Diskten tek tek veya toplu kapı kolu fotoğrafları yükleyip muayene edebilirsiniz (`📂 Resim Yükle & Muayene Et`).
   - Yüklediğiniz hatasız bir fotoğrafı tek tıkla altın şablon yapabilirsiniz (`⭐ Bu Resmi Referans Olarak Öğret`).
   - Harici Ethernet IP kameralar (RTSP / HTTP / GigE) ve konveyör simülasyonu desteklenir.

2. **Aşama 1: Parça Konumlama ve Açı Düzeltme (`core/door_handle_locator.py` & `core/locator.py`):**
   - PCA (Principal Component Analysis) ve kontur momentleri ile dönme açısını alt-derece hassasiyetle hesaplar.
   - Parçayı standart referans koordinat düzlemine (Kapı kolu: 600x300 piksel, PCB: 500x350 piksel) taşır ve rozet/uç yönelimini kanonik doğrultuya oturtur.

3. **Aşama 2: "OK" Referans Tabanlı Failure & Anomali Tespiti (`core/golden_reference.py`):**
   - Yalnızca onaylanmış "OK" referans parçalarını temel alır; morfolojik tolerans bandı ile mikro-titreşim ve ışık parlamalarını tolere eder.
   - Çizik, çatlak, gözenek, kaplama lekesi veya darbe izlerini kusur ısı haritası (**Heatmap**) ve sınır kutucukları (**Defect BBoxes**) olarak çıkarır.

4. **Aşama 3: Kural Tabanlı Alt Muayene Kontrolleri (`core/door_handle_inspector.py`):**
   - **Montaj Vida Delikleri (Üst & Alt):** Rozet üzerindeki vida deliklerinin varlığı, açık/kapalı durumu ve çapak tıkanıklığı.
   - **Kare Mil Yuvası (Spindle Hole):** Kilit mekanizması mil yuvasının varlığı ve ölçüsel uygunluğu.
   - **Kol Düzgünlüğü (Curvature / Bending):** Kol gövdesinin eğiklik, bükülme veya pres deformasyonlarının tespiti.

5. **Aşama 4: Operatör Kararından Öğrenme (`core/active_learner.py`):**
   - **Hatalı Ret Düzeltmesi (Model NOK dedi, Operatör OK dedi):** Sistem bu görüntüyü onaylı OK hafıza havuzuna ekler, benzer yüzey varyasyonlarını bir daha reddetmez.
   - **Hatalı Kabul Düzeltmesi (Model OK dedi, Operatör NOK dedi):** Modelin anomali hassasiyet eşiğini sıkılaştırır ve hatayı zor örnekler havuzuna kaydeder.
   - Tüm öğrenme adımları ve istatistikler SQLite veritabanında saklanır.

---

## 🛠 Kurulum ve Testler

### 1. Testleri Çalıştırma
```bash
# Kapı Kolu Entegrasyon Testi
./.venv/bin/python test_door_handle.py

# Veritabanı ve PCB Testleri
./.venv/bin/python test_pipeline.py
./.venv/bin/python test_db.py
./.venv/bin/python test_server.py
```

### 2. Masaüstü Arayüzünü Başlatma
```bash
./run_client.sh
# veya
./.venv/bin/python client/app.py
```

### 3. PC Sunucusunu Başlatma (İsteğe Bağlı)
```bash
./run_server.sh
# veya
./.venv/bin/python server/server.py
```
*Sunucu varsayılan olarak `http://localhost:8000` adresinde çalışır ve API dökümantasyonu `http://localhost:8000/docs` adresindedir.*

---

## 🖥 Arayüz Kılavuzu

- **Mod Seçici:** Üst bardan **"🚪 Kapı Kolu Muayenesi"** veya **"🔲 Elektronik Kart (PCB)"** modları arasında geçiş yapabilirsiniz.
- **📂 Resim Yükle & Muayene Et:** Bilgisayarınızdaki herhangi bir kapı kolu fotoğrafını seçerek anında muayene edin.
- **⭐ Bu Resmi Referans Olarak Öğret:** Ekranda incelediğiniz veya diskten seçeceğiniz hatasız kapı kolunu altın referans modeli olarak kaydedin.
- **Görüntü Modları:** Ham kamera görüntüsü, hizalanmış parça (ROI), veya kusur ısı haritası (Heatmap Composite) arasında geçiş yapın.
- **Kararı Düzelt:** Model bir parçada yanıldığında tek tuşla müdahale edin; sistem geri bildiriminizden derhal öğrenir.
