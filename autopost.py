#!/usr/bin/env python3
"""
Blogger Auto-Post: ट्रेंडिंग टॉपिक खोजो -> Claude से हिंदी पोस्ट लिखवाओ -> Blogger पर पब्लिश करो.

पब्लिश करने के दो तरीके (PUBLISH_METHOD):
  "email" (शुरुआती लोगों के लिए आसान): Blogger के गुप्त ईमेल पते पर Gmail से पोस्ट भेजता है।
      ज़रूरी: ANTHROPIC_API_KEY, BLOGGER_EMAIL, SMTP_USER, SMTP_PASSWORD
      (draft या live Blogger की Settings -> Email में तय होता है)
  "api": Blogger API से सीधे पब्लिश (ज़्यादा सेटअप, पर लेबल और draft/live पर पूरा कंट्रोल)।
      ज़रूरी: ANTHROPIC_API_KEY, BLOG_ID,
      GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN

वैकल्पिक:
  TOPIC_SOURCE    - "syllabus" (डिफ़ॉल्ट: topics.txt से क्रम में) या "trends" (Google Trends)
  NICHE_KEYWORDS  - सिर्फ़ trends मोड में: कॉमा से अलग शब्द, जैसे "टेक,AI" (खाली = सभी ट्रेंड)
  BLOG_NICHE      - ब्लॉग का विषय (प्रॉम्प्ट में जाता है), जैसे "टेक्नोलॉजी और मोबाइल"
  PUBLISH_MODE    - सिर्फ़ "api" तरीके में: "draft" (डिफ़ॉल्ट, सुरक्षित) या "live"
  POSTS_PER_RUN   - एक रन में कितनी पोस्ट (डिफ़ॉल्ट 1)
  CLAUDE_MODEL    - डिफ़ॉल्ट claude-sonnet-5-5
  USE_WEB_SEARCH  - "auto" (डिफ़ॉल्ट: ट्रेंड मोड या करेंट अफेयर्स टॉपिक पर सर्च), "1" हमेशा, "0" कभी नहीं
"""
import json
import os
import re
import smtplib
import ssl
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import requests

HISTORY_FILE = Path(__file__).parent / "posted.json"
TRENDS_RSS = "https://trends.google.com/trending/rss?geo=IN"
HT_NS = {"ht": "https://trends.google.com/trending/rss"}


def env(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"गड़बड़: Environment variable '{name}' सेट नहीं है।")
    return val


# ---------- इतिहास (दोहराव रोकने के लिए) ----------
def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def save_history(history):
    HISTORY_FILE.write_text(
        json.dumps(history[-500:], ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------- 1. ट्रेंडिंग टॉपिक ----------
def fetch_trends():
    """Google Trends (भारत) से आज के ट्रेंडिंग विषय. [(topic, traffic_int)]"""
    r = requests.get(TRENDS_RSS, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    trends = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        traffic_txt = item.findtext("ht:approx_traffic", default="0", namespaces=HT_NS)
        digits = re.sub(r"[^\d]", "", traffic_txt or "0")
        traffic = int(digits) if digits else 0
        if title:
            trends.append((title, traffic))
    trends.sort(key=lambda x: x[1], reverse=True)
    return trends


def is_syllabus_mode():
    return env("TOPIC_SOURCE", "syllabus").lower() == "syllabus"


def pick_syllabus_topics(count, done):
    """topics.txt की लाइनें ऊपर से नीचे क्रम में लेता है, जो लिखी जा चुकी हैं उन्हें छोड़कर."""
    path = Path(__file__).parent / "topics.txt"
    if not path.exists():
        sys.exit("गड़बड़: topics.txt फ़ाइल नहीं मिली।")
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    return [l for l in lines if l.lower() not in done][:count]


def pick_topics(count, history):
    done = {h["topic"].lower() for h in history}
    if is_syllabus_mode():
        return pick_syllabus_topics(count, done)
    keywords = [k.strip().lower() for k in env("NICHE_KEYWORDS", "").split(",") if k.strip()]
    trends = [t for t in fetch_trends() if t[0].lower() not in done]
    if keywords:
        matched = [t for t in trends if any(k in t[0].lower() for k in keywords)]
        # niche से कुछ न मिले तो भी चलता रहे: बाकी ट्रेंड्स में से लो
        trends = matched or trends
    return [t[0] for t in trends[:count]]


# ---------- 2. पोस्ट लिखना (Claude) ----------
PROMPT = """तुम एक अनुभवी हिंदी ब्लॉगर हो। ब्लॉग का विषय: {niche}

आज भारत में "{topic}" ट्रेंड कर रहा है। इस पर एक मौलिक, उपयोगी और SEO-फ्रेंडली ब्लॉग पोस्ट देवनागरी हिंदी में लिखो।

नियम:
- पहले वेब सर्च से इस टॉपिक की ताज़ा और सही जानकारी लो (अगर टूल उपलब्ध है)। सिर्फ़ वही तथ्य लिखो जिनकी पुष्टि हुई हो; अंदाज़े से तारीख़, आँकड़े या दावे मत गढ़ो।
- अगर टॉपिक किसी की निजी ज़िंदगी, त्रासदी, अफ़वाह या विवादित/संवेदनशील मामले से जुड़ा है, तो सिर्फ़ तथ्यात्मक और संतुलित लिखो। अगर पक्की जानकारी नहीं मिली तो पहली लाइन में सिर्फ़ SKIP लिखो।
- लंबाई लगभग 700-900 शब्द। सरल, बातचीत वाली भाषा।
- संरचना: आकर्षक भूमिका, 3-5 <h2> उप-शीर्षक, ज़रूरत हो तो <ul> लिस्ट, अंत में निष्कर्ष और पाठकों के लिए एक सवाल।
- कॉपी-पेस्ट मत करो; सब अपने शब्दों में।

आउटपुट का फ़ॉर्मेट (बिल्कुल यही):
TITLE: <शीर्षक, 60 अक्षर तक>
LABELS: <3-5 लेबल, कॉमा से अलग>
DESCRIPTION: <150 अक्षर तक का सर्च डिस्क्रिप्शन>
BODY:
<यहाँ से सिर्फ़ HTML बॉडी (<h1> मत लगाना, सिर्फ़ <p>, <h2>, <ul>, <li>, <strong>)>
"""


EDU_PROMPT = """तुम एक अनुभवी शिक्षक और हिंदी एजुकेशन ब्लॉगर हो। ब्लॉग का विषय: {niche}

इस विषय पर विद्यार्थियों के लिए एक सरल, सही और परीक्षा-उपयोगी ब्लॉग पोस्ट लिखो: "{topic}"

नियम:
- भाषा: सरल हिंदी (देवनागरी), और ज़रूरी शब्दों के अंग्रेज़ी रूप कोष्ठक में। शीर्षक द्विभाषी रखो: "हिंदी शीर्षक | English Title | कक्षा/विषय"।
- संरचना: संक्षिप्त परिचय; परिभाषाएँ और मुख्य बिंदु (<h2> उप-शीर्षक के साथ); हल किए हुए 2-3 उदाहरण या व्याख्या; ज़रूरत हो तो छोटी तालिका (<table>); 5 अभ्यास प्रश्न या बहुविकल्पीय प्रश्न (MCQ) और उनके उत्तर; अंत में याद रखने योग्य बातें और पाठकों के लिए एक सवाल।
- सटीकता सबसे ज़रूरी है: हर गणना, सूत्र, तारीख़ और तथ्य दो बार जाँचो। सिर्फ़ वही लिखो जिसका तुम्हें पक्का पता हो। NCERT के अध्याय नंबर, पृष्ठ संख्या या पाठ्यपुस्तक के सटीक शब्द अंदाज़े से मत लिखो।
- अगर टॉपिक में करेंट अफेयर्स या हाल की जानकारी है, तो पहले वेब सर्च से पुष्टि करो और तारीख़ के साथ लिखो। पक्की जानकारी न मिले तो पहली लाइन में सिर्फ़ SKIP लिखो।
- लंबाई लगभग 800-1000 शब्द। सब कुछ अपने शब्दों में, कॉपी-पेस्ट नहीं।

आउटपुट का फ़ॉर्मेट (बिल्कुल यही):
TITLE: <द्विभाषी शीर्षक, 70 अक्षर तक>
LABELS: <3-5 लेबल, जैसे कक्षा 8, Maths, गणित (कॉमा से अलग)>
DESCRIPTION: <150 अक्षर तक का सर्च डिस्क्रिप्शन>
BODY:
<यहाँ से सिर्फ़ HTML बॉडी (<h1> मत लगाना; सिर्फ़ <p>, <h2>, <ul>, <ol>, <li>, <strong>, <table>, <tr>, <th>, <td>)>
"""


def write_post(topic):
    model = env("CLAUDE_MODEL", "claude-sonnet-5-5")
    syllabus = is_syllabus_mode()
    default_niche = (
        "शिक्षा: NCERT/UP Board (कक्षा 8-12) और प्रतियोगी परीक्षाओं (UPSC, SSC, बैंकिंग) की तैयारी"
        if syllabus
        else "सामान्य / ट्रेंडिंग खबरें और जानकारी"
    )
    prompt = (EDU_PROMPT if syllabus else PROMPT).format(topic=topic, niche=env("BLOG_NICHE", default_niche))
    body = {
        "model": model,
        "max_tokens": 6000,
        "messages": [{"role": "user", "content": prompt}],
    }
    # वेब सर्च: "1" = हमेशा, "0" = कभी नहीं, "auto" (डिफ़ॉल्ट) = ट्रेंड मोड में या करेंट अफेयर्स वाले टॉपिक पर
    search_setting = env("USE_WEB_SEARCH", "auto").lower()
    if search_setting == "auto":
        use_search = (not syllabus) or ("करेंट" in topic) or ("current" in topic.lower())
    else:
        use_search = search_setting == "1"
    if use_search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]

    headers = {
        "x-api-key": env("ANTHROPIC_API_KEY", required=True),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=300)
    if r.status_code >= 400 and use_search:
        # वेब सर्च टूल न चले तो बिना उसके दोबारा कोशिश
        print("वेब सर्च के साथ फ़ेल, बिना सर्च के कोशिश कर रहा हूँ:", r.text[:200])
        body.pop("tools", None)
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=300)
    r.raise_for_status()
    blocks = r.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def parse_post(text):
    if text.strip().upper().startswith("SKIP"):
        return None
    m = re.search(
        r"TITLE:\s*(.+?)\s*\n\s*LABELS:\s*(.+?)\s*\n\s*DESCRIPTION:\s*(.+?)\s*\n\s*BODY:\s*(.+)",
        text,
        re.DOTALL,
    )
    if not m:
        return None
    title, labels, desc, html = m.groups()
    html = re.sub(r"^```(?:html)?|```$", "", html.strip(), flags=re.MULTILINE).strip()
    # सर्च डिस्क्रिप्शन पोस्ट की पहली लाइन के रूप में छिपा नहीं रखते; बस बॉडी में जोड़ देते हैं
    return {
        "title": title.strip(),
        "labels": [l.strip() for l in labels.split(",") if l.strip()][:5],
        "description": desc.strip(),
        "content": html,
    }


# ---------- 3. Blogger पर पब्लिश ----------
def get_access_token():
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": env("GOOGLE_CLIENT_ID", required=True),
            "client_secret": env("GOOGLE_CLIENT_SECRET", required=True),
            "refresh_token": env("GOOGLE_REFRESH_TOKEN", required=True),
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def publish(post, token):
    blog_id = env("BLOG_ID", required=True)
    is_draft = env("PUBLISH_MODE", "draft").lower() != "live"
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    payload = {
        "kind": "blogger#post",
        "title": post["title"],
        "content": post["content"],
        "labels": post["labels"],
    }
    r = requests.post(
        url,
        params={"isDraft": str(is_draft).lower()},
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json(), is_draft


def publish_email(post):
    """Blogger के गुप्त ईमेल पते पर भेजो: सब्जेक्ट = शीर्षक, बॉडी = HTML पोस्ट."""
    to_addr = env("BLOGGER_EMAIL", required=True)
    user = env("SMTP_USER", required=True)
    password = env("SMTP_PASSWORD", required=True)
    msg = MIMEText(post["content"], "html", "utf-8")
    msg["Subject"] = post["title"]
    msg["From"] = user
    msg["To"] = to_addr
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, password)
        s.sendmail(user, [to_addr], msg.as_string())
    return {"id": "emailed"}


# ---------- मुख्य ----------
def main():
    count = int(env("POSTS_PER_RUN", "1"))
    history = load_history()
    topics = pick_topics(count, history)
    if not topics:
        print("आज कोई नया टॉपिक नहीं मिला।")
        return

    method = env("PUBLISH_METHOD", "email").lower()
    token = get_access_token() if method == "api" else None
    for topic in topics:
        print(f"टॉपिक: {topic}")
        try:
            post = parse_post(write_post(topic))
        except Exception as e:  # noqa: BLE001
            print(f"  लिखने में गड़बड़: {e}")
            continue
        if not post:
            print("  छोड़ दिया (SKIP या फ़ॉर्मेट गड़बड़)।")
            history.append({"topic": topic, "status": "skipped", "at": datetime.now(timezone.utc).isoformat()})
            continue
        try:
            if method == "api":
                result, is_draft = publish(post, token)
                status = "draft" if is_draft else "live"
            else:
                result = publish_email(post)
                status = "emailed"
        except Exception as e:  # noqa: BLE001
            print(f"  पब्लिश करने में गड़बड़: {e}")
            continue
        print(f"  भेज दी ({status}): {result.get('url') or post['title']}")
        history.append(
            {
                "topic": topic,
                "title": post["title"],
                "url": result.get("url"),
                "status": status,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
    save_history(history)


if __name__ == "__main__":
    main()
