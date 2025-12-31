# Email OAuth Bağlantı Rehberi

Bu rehber, MindOps Entegrasyon sistemine email hesabınızı OAuth ile bağlamanız için adım adım talimatlar içerir.

---

## 🔷 Microsoft / Outlook / Office 365 Bağlantısı

Microsoft email hesabınızı bağlamak için Azure'da uygulama kaydı oluşturmanız gerekmektedir.

### Adım 1: Azure Portal'a Giriş

1. **[Azure Portal](https://portal.azure.com)** adresine gidin
2. Microsoft hesabınızla giriş yapın
3. Ücretsiz hesap yoksa oluşturabilirsiniz

### Adım 2: Azure Active Directory'ye Git

1. Sol menüden **"Microsoft Entra ID"** (eski adı Azure Active Directory) seçin
2. **"App registrations"** → **"New registration"** tıklayın

### Adım 3: Uygulama Kaydını Oluştur

Aşağıdaki bilgileri girin:

| Alan | Değer |
|------|-------|
| **Name** | `MindOps Entegrasyon` (veya istediğiniz isim) |
| **Supported account types** | `Accounts in any organizational directory and personal Microsoft accounts` |
| **Redirect URI** | Platform: `Web`, URL: `https://entegrasyon.mindops.net/api/oauth/microsoft/callback` |

**"Register"** butonuna tıklayın.

### Adım 4: Credentials'ları Kopyala

Uygulama oluşturulduktan sonra:

1. **Overview** sayfasında **Application (client) ID**'yi kopyalayın
2. Bu ID'yi not edin (Settings sayfasına gireceksiniz)

### Adım 5: Client Secret Oluştur

1. Sol menüden **"Certificates & secrets"** seçin
2. **"Client secrets"** sekmesinde **"New client secret"** tıklayın
3. Description: `MindOps` (veya istediğiniz)
4. Expires: `24 months` (önerilen)
5. **"Add"** tıklayın
6. ⚠️ **ÖNEMLİ:** Oluşan **Value** değerini hemen kopyalayın! Bu değer sayfadan çıkınca bir daha görünmez.

### Adım 6: API İzinlerini Ekle

1. Sol menüden **"API permissions"** seçin
2. **"Add a permission"** → **"Microsoft Graph"** → **"Delegated permissions"**
3. Aşağıdaki izinleri ekleyin:
   - ✅ `openid`
   - ✅ `email`
   - ✅ `profile`
   - ✅ `offline_access`
   - ✅ `IMAP.AccessAsUser.All`
   - ✅ `SMTP.Send` (opsiyonel, email göndermek için)

4. **"Add permissions"** tıklayın
5. Kurumsal hesaplar için: **"Grant admin consent"** tıklayın

### Adım 7: MindOps Settings'te Yapılandırma

1. **[https://entegrasyon.mindops.net/settings](https://entegrasyon.mindops.net/settings)** adresine gidin
2. Booking Email veya Stop Sale Email bölümünde **"Microsoft"** butonuna tıklayın
3. **"Configure Azure Credentials"** butonuna tıklayın
4. Bilgileri girin:
   - **Application (Client) ID:** Azure'dan kopyaladığınız ID
   - **Client Secret:** Azure'dan kopyaladığınız secret değeri
   - **Tenant ID:** "Common" bırakın (tüm hesap türleri için)
5. **"Save"** butonuna tıklayın
6. **"Connect with Microsoft"** butonuna tıklayın
7. Microsoft giriş ekranında hesabınızla giriş yapın ve izinleri onaylayın

✅ Bağlantı başarılı olduğunda email adresiniz görünecektir.

---

## 🔴 Google / Gmail Bağlantısı

Gmail hesabınızı bağlamak için Google Cloud Console'da OAuth ayarları yapmanız gerekmektedir.

### Adım 1: Google Cloud Console'a Giriş

1. **[Google Cloud Console](https://console.cloud.google.com)** adresine gidin
2. Google hesabınızla giriş yapın

### Adım 2: Proje Oluştur veya Seç

1. Üst menüdeki proje seçiciden **"New Project"** tıklayın
2. Project name: `MindOps Mail` (veya istediğiniz)
3. **"Create"** tıklayın

### Adım 3: OAuth Consent Screen Yapılandır

1. Sol menüden **"APIs & Services"** → **"OAuth consent screen"** seçin
2. **User Type:** `External` seçin (kendi hesabınız için de bu gerekli)
3. **"Create"** tıklayın
4. Bilgileri doldurun:
   - **App name:** `MindOps Entegrasyon`
   - **User support email:** Kendi email adresiniz
   - **Developer contact:** Kendi email adresiniz
5. **"Save and Continue"** tıklayın
6. **Scopes** sayfasında **"Add or Remove Scopes"** tıklayın:
   - ✅ `.../auth/gmail.readonly`
   - ✅ `.../auth/gmail.modify`
   - ✅ `openid`
   - ✅ `email`
   - ✅ `profile`
7. **"Save and Continue"** tıklayın
8. **Test users** sayfasında **"Add users"** tıklayın ve kendi email adresinizi ekleyin
9. **"Save and Continue"** tıklayın

### Adım 4: OAuth Credentials Oluştur

1. Sol menüden **"APIs & Services"** → **"Credentials"** seçin
2. **"Create Credentials"** → **"OAuth client ID"** tıklayın
3. **Application type:** `Web application`
4. **Name:** `MindOps Web Client`
5. **Authorized redirect URIs:**
   - `https://entegrasyon.mindops.net/api/oauth/google/callback`
6. **"Create"** tıklayın
7. **Client ID** ve **Client Secret** değerlerini kopyalayın

### Adım 5: Gmail API'yi Aktif Et

1. Sol menüden **"APIs & Services"** → **"Library"** seçin
2. **"Gmail API"** arayın ve tıklayın
3. **"Enable"** butonuna tıklayın

### Adım 6: MindOps Settings'te Bağlan

1. **[https://entegrasyon.mindops.net/settings](https://entegrasyon.mindops.net/settings)** adresine gidin
2. Booking Email veya Stop Sale Email bölümünde **"Google"** butonuna tıklayın
3. **"Connect with Google"** butonuna tıklayın
4. Google giriş ekranında hesabınızla giriş yapın
5. İzinleri onaylayın

⚠️ **Not:** Google OAuth ayarları "test mode"'da olduğu sürece sadece Test Users'a eklediğiniz hesaplar bağlanabilir. Production'a geçmek için Google'ın doğrulama sürecinden geçmeniz gerekir.

✅ Bağlantı başarılı olduğunda email adresiniz görünecektir.

---

## 🔐 Güvenlik Notları

1. **Client Secret'ları güvenli tutun** - Bu değerler şifrelenmiş olarak saklanır
2. **Token süresi dolar** - Refresh token ile otomatik yenilenir
3. **İstediğiniz zaman bağlantıyı kesebilirsiniz** - "Disconnect" butonu ile
4. **Şifre kaydetmenize gerek yok** - OAuth ile şifreniz bizimle paylaşılmaz

---

## 🆘 Sorun Giderme

### Microsoft OAuth Hataları

| Hata | Çözüm |
|------|-------|
| `AADSTS50011: Reply URL mismatch` | Redirect URI'yi kontrol edin: `https://entegrasyon.mindops.net/api/oauth/microsoft/callback` |
| `AADSTS65001: Consent required` | Admin consent gerekli, IT yöneticinize başvurun |
| `Invalid client secret` | Secret'ın süresi dolmuş olabilir, yeni secret oluşturun |

### Google OAuth Hataları

| Hata | Çözüm |
|------|-------|
| `Error 403: access_denied` | Hesabınız Test Users'a eklenmemiş olabilir |
| `redirect_uri_mismatch` | Redirect URI'yi kontrol edin: `https://entegrasyon.mindops.net/api/oauth/google/callback` |
| `Gmail API not enabled` | Gmail API'yi Library'den aktif edin |

---

## 📞 Destek

Sorun yaşarsanız bizimle iletişime geçin:

- Email: <support@mindops.net>
- Sistem yöneticinize başvurun

---

*Bu döküman tüm tenantlar için geçerlidir. Her tenant kendi OAuth credentials'larını oluşturmalıdır.*
