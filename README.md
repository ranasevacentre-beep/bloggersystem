# Blogger ऑटो-पोस्ट सिस्टम

रोज़ अपने आप: **ट्रेंडिंग टॉपिक खोजना → हिंदी पोस्ट लिखना → Blogger पर पब्लिश करना।**
चलाने का खर्च: GitHub Actions मुफ़्त है; सिर्फ़ Claude API का इस्तेमाल पैसे का है (एक पोस्ट पर कुछ सेंट)।

## यह कैसे काम करता है

1. Google Trends (भारत) से आज के सबसे ज़्यादा सर्च हो रहे टॉपिक आते हैं (रीच के हिसाब से)।
2. जो टॉपिक पहले लिखा जा चुका है, वह छोड़ दिया जाता है (`posted.json` में इतिहास रहता है)।
3. Claude वेब सर्च करके ताज़ा जानकारी लेता है और देवनागरी में 700-900 शब्द की पोस्ट लिखता है।
4. पोस्ट Blogger API से आपके ब्लॉग पर जाती है।
5. यह सब GitHub Actions पर रोज़ सुबह 8:00 बजे (IST) अपने आप चलता है। आपका कंप्यूटर चालू रखना ज़रूरी नहीं।

## शिक्षा ब्लॉग के लिए टॉपिक कैसे चुने जाते हैं

डिफ़ॉल्ट में सिस्टम **topics.txt** की सूची से ऊपर से नीचे एक-एक टॉपिक लेता है (कक्षा 8-12, हिंदी व्याकरण, सामान्य ज्ञान, परीक्षा तैयारी)। जो टॉपिक लिखा जा चुका है, उसे दोबारा नहीं लेता।

- **नए टॉपिक जोड़ने के लिए:** `topics.txt` में एक लाइन में एक टॉपिक लिख दें, जैसे `कक्षा 8 विज्ञान: ध्वनि`। जिस लाइन में "करेंट अफेयर्स" शब्द होगा, उस पर Claude लिखने से पहले वेब सर्च करेगा।
- **ट्रेंडिंग मोड चाहिए?** `daily.yml` में `TOPIC_SOURCE` को `"trends"` कर दें।
- हर पोस्ट में उदाहरण, अभ्यास प्रश्न और उत्तर होते हैं। फिर भी पहले हफ़्ते ड्राफ़्ट पढ़कर गणनाएँ और तथ्य ज़रूर जाँचें, क्योंकि AI से ग़लती हो सकती है।

---

## आसान तरीका: ईमेल से पोस्ट (शुरुआती लोगों के लिए, Google Cloud की ज़रूरत नहीं)

Blogger का "Posting using email" फ़ीचर इस्तेमाल होता है। स्क्रिप्ट पोस्ट लिखकर आपके Blogger के गुप्त ईमेल पते पर भेज देती है, और Blogger उसे पोस्ट बना देता है।

1. **Blogger का गुप्त ईमेल पता:** Blogger → Settings → Email सेक्शन में "Posting using email" के नीचे आपका पता (जैसे `नाम.गुप्तशब्द@blogger.com`) दिखेगा। गुप्त शब्द खुद बनाएँ।
   - वहीं चुनें: **Publish emails immediately** (सीधे लाइव) या **Save emails as drafts** (ड्राफ़्ट, पहले हफ़्ते के लिए यही रखें)।
   - यह पता गुप्त रखें। जिसके पास यह है, वह आपके ब्लॉग पर पोस्ट कर सकता है।
2. **Gmail App Password:** myaccount.google.com → Security → 2-Step Verification चालू करें → फिर "App passwords" में नया पासवर्ड बनाएँ (16 अक्षर)। यह आपका असली पासवर्ड नहीं है।
3. **Claude API key:** console.anthropic.com से बनाएँ।
4. **GitHub Secrets** (Private repo → Settings → Secrets and variables → Actions) में ये चार जोड़ें:

| नाम | वैल्यू |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `BLOGGER_EMAIL` | स्टेप 1 वाला Blogger का गुप्त ईमेल पता |
| `SMTP_USER` | आपकी Gmail ID (जिससे ईमेल भेजा जाएगा) |
| `SMTP_PASSWORD` | स्टेप 2 वाला 16 अक्षर का App Password |

5. फ़ाइलें GitHub पर अपलोड करें, फिर *Actions → Blogger Daily Auto Post → Run workflow* दबाकर टेस्ट करें।

इस तरीके में लेबल (Labels) अपने आप नहीं लगते। चाहिए तो नीचे वाला API तरीका इस्तेमाल करें।

---

## दूसरा तरीका: Blogger API (ज़्यादा सेटअप, पूरा कंट्रोल)

इसके लिए `daily.yml` में `PUBLISH_METHOD` को `"api"` कर दें और नीचे के स्टेप करें।

## सेटअप (एक बार, लगभग 20-30 मिनट)

### स्टेप 1: Blog ID निकालें
Blogger डैशबोर्ड खोलें। ब्राउज़र के URL में `blogID=` के बाद जो लंबा नंबर है, वही आपकी **BLOG_ID** है।

### स्टेप 2: Google Blogger API चालू करें
1. https://console.cloud.google.com पर जाएँ और नया Project बनाएँ।
2. *APIs & Services → Library* में **Blogger API v3** खोजकर **Enable** करें।
3. *OAuth consent screen* बनाएँ: User type **External**, अपना ईमेल *Test users* में जोड़ें।
4. *Credentials → Create Credentials → OAuth client ID* चुनें, Application type **Desktop app** रखें।
5. बनी हुई फ़ाइल **Download JSON** करें और उसे `client_secret.json` नाम दें।

### स्टेप 3: Refresh Token निकालें (अपने कंप्यूटर पर)
```
pip install google-auth-oauthlib
python get_refresh_token.py client_secret.json
```
ब्राउज़र खुलेगा। अपने Google अकाउंट से अनुमति दें। टर्मिनल में तीन वैल्यू छपेंगी: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`।

> टिप: Consent screen "Testing" मोड में हो तो refresh token 7 दिन में एक्सपायर हो सकता है। इसलिए consent screen को **Publish app (In production)** कर दें।

### स्टेप 4: Claude API Key
https://console.anthropic.com से API key बनाएँ। यह `ANTHROPIC_API_KEY` है।

### स्टेप 5: GitHub पर डालें
1. GitHub पर एक **Private** repository बनाएँ और इस पूरे फ़ोल्डर की फ़ाइलें (`.github` फ़ोल्डर समेत) अपलोड करें।
2. *Settings → Secrets and variables → Actions → New repository secret* में ये पाँच secrets जोड़ें:

| नाम | वैल्यू |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `BLOG_ID` | स्टेप 1 का नंबर |
| `GOOGLE_CLIENT_ID` | स्टेप 3 से |
| `GOOGLE_CLIENT_SECRET` | स्टेप 3 से |
| `GOOGLE_REFRESH_TOKEN` | स्टेप 3 से |

3. *Actions* टैब में **Blogger Daily Auto Post → Run workflow** दबाकर टेस्ट करें।

## पहले हफ़्ते में क्या करें

सिस्टम शुरू में `PUBLISH_MODE: "draft"` पर है, यानी पोस्ट Blogger में **ड्राफ़्ट** बनती है, लाइव नहीं। 3-5 ड्राफ़्ट पढ़कर गुणवत्ता जाँचें। ठीक लगे तो `.github/workflows/daily.yml` में `"draft"` को `"live"` कर दें।

## सेटिंग्स (daily.yml में)

| सेटिंग | मतलब |
|---|---|
| `BLOG_NICHE` | आपके ब्लॉग का विषय (लेखन की शैली इसी से तय होती है) |
| `NICHE_KEYWORDS` | सिर्फ़ इन शब्दों वाले ट्रेंड चुनना, जैसे `"iphone,ai,tech"`। खाली छोड़ेंगे तो सभी ट्रेंड |
| `POSTS_PER_RUN` | एक दिन में कितनी पोस्ट |
| `PUBLISH_MODE` | `draft` या `live` |

समय बदलना हो तो `cron: "30 2 * * *"` बदलें। यह UTC में है; IST = UTC + 5:30।

## ज़रूरी सावधानियाँ

- **AdSense / गुणवत्ता:** पूरी तरह AI से लिखी, बिना जाँची पोस्ट Google की स्पैम नीति में आ सकती हैं। शुरुआत में ड्राफ़्ट जाँचें और बीच-बीच में खुद भी देखते रहें।
- **संवेदनशील खबरें:** किसी की मौत, हादसे, अफ़वाह या विवादित मामलों पर ऑटो-पोस्ट जोखिम भरी है। स्क्रिप्ट ऐसे मामलों में तथ्यात्मक रहने या SKIP करने को कहती है, पर पक्का भरोसा नहीं है। `NICHE_KEYWORDS` से अपने विषय तक सीमित रहना बेहतर है।
- **Google Trends RSS:** यह अनौपचारिक फ़ीड है। कभी बंद या बदल जाए तो `fetch_trends()` को अपडेट करना पड़ेगा।
- **API key** कभी कोड में सीधे न लिखें; सिर्फ़ GitHub Secrets में रखें।

## फ़ाइलें

- `autopost.py`: मुख्य स्क्रिप्ट
- `get_refresh_token.py`: Google लॉगिन टोकन निकालने की एक-बार वाली स्क्रिप्ट
- `requirements.txt`: ज़रूरी पैकेज
- `.github/workflows/daily.yml`: रोज़ का शेड्यूल
