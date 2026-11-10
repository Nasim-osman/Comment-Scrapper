# OmniScrape | Multi-Platform Comment Extractor & Thesis Research Hub

> **YouTube, Reddit, Instagram, Facebook** থেকে কমেন্ট স্ক্র্যাপ করে সরাসরি **Excel (.xlsx)**, **CSV (Excel-ready UTF-8 BOM)** এবং **JSON** ফরম্যাটে এক্সপোর্ট করার একটি আধুনিক ও সম্পূর্ণ রিসার্চ প্ল্যাটফর্ম।

---

## 🌟 প্রধান সুবিধাসমূহ (Key Features)

- **৪টি প্ল্যাটফর্ম সাপোর্ট (All-in-One):**
  - 🎥 **YouTube:** আনলিমিটেড কমেন্ট ও রিপ্লাই দ্রুততম গতিতে এক্সট্রাক্ট করে (No API key required)।
  - 👽 **Reddit:** থ্রেডেড কমেন্ট, আপভোট/স্কোর ও রিপ্লাই ট্রিসহ এক্সট্রাক্ট করে (Playwright & PRAW dual-engine)।
  - 📸 **Instagram:** রিলস ও পোস্টের কমেন্ট, ইউজারনেম, লাইক ও টাইমস্ট্যাম্পসহ।
  - 📘 **Facebook:** পাবলিক পোস্ট, পেজ ও ভিডিওর কমেন্ট, রিঅ্যাকশনসহ (Auto-scroll & expand comments)।
- **থিসিস ও এনএলপি ডেটাসেট প্রি-প্রসেসিং (Thesis NLP Ready):**
  - **Bangla Text Filter (বাংলা):** চাইলে শুধুমাত্র বাংলা স্ক্রিপ্টযুক্ত কমেন্ট ফিল্টার করে ডেটাসেট তৈরি করার অপশন।
  - **Text Normalizer:** অদৃশ্য জিরো-উইডথ ক্যারেক্টার (`\u200b`, `\u200c`, `\u200d`), অপ্রয়োজনীয় ইউআরএল ও অতিরিক্ত স্পেস স্বয়ংক্রিয়ভাবে ক্লিন করে।
  - **Language Classifier:** প্রতিটি কমেন্টের ভাষা স্বয়ংক্রিয়ভাবে শনাক্ত করে: `Bangla (bn)`, `English (en)`, `Mixed/Banglish (mixed)`, বা `Other`।
- **এক্সপোর্ট সুবিধা (Academic Export Formats):**
  - **Excel (.xlsx):** ওপেনপিএক্সএল (OpenPyXL) দিয়ে তৈরি আধুনিক স্টাইলিশ হেডার ও অটো-কলাম উইডথ ফরম্যাটিং।
  - **CSV (UTF-8 BOM):** উইন্ডোজ এক্সেল (Microsoft Excel) এ সরাসরি ওপেন করলে বাংলা ফ্রন্ট ভাঙবে না।
  - **JSON:** এনএলপি মডেল ট্রেইনিং ও পাইথনে ডেটা অ্যানালাইসিসের জন্য।
- **ইন্টারেক্টিভ ড্যাশবোর্ড ও লাইভ টার্মিনাল:**
  - রিয়েল-টাইম স্ক্র্যাপিং প্রোগ্রেস ও লাইভ লগ টার্মিনাল।
  - লাইভ কমেন্ট প্রিভিউ টেবিল, সার্চ বার ও পেজিনেশন।
  - এক ক্লিকে ফেসবুক ও ইনস্টাগ্রাম সেশন কানেক্ট করার বিল্ট-ইন ব্রাউজার টুল।

---

## 🚀 কীভাবে চালু করবেন (Quick Start)

### ১. এক ক্লিকে চালু করুন (Windows):
প্রজেক্ট ফোল্ডারে থাকা [`run.bat`](file:///c:/Users/nasim/OneDrive/Desktop/all_comment_scrapper/run.bat) ফাইলে ডাবল-ক্লিক করুন।

অথবা টার্মিনাল থেকে রান করুন:
```bash
python run.py
```
> এটি স্বয়ংক্রিয়ভাবে সার্ভার চালু করে আপনার ডিফল্ট ব্রাউজারে `http://127.0.0.1:8000` ওপেন করবে!

---

## 💻 ড্যাশবোর্ড ব্যবহার নির্দেশিকা (Usage Guide)

1. **URL ইনপুট দিন:**
   - যেকোনো YouTube, Reddit, Instagram, বা Facebook পোস্টের লিংক কপি করে পেস্ট করুন।
   - সিস্টেম স্বয়ংক্রিয়ভাবে প্ল্যাটফর্ম ডিটেক্ট করবে।
   - একের অধিক লিংকের জন্য **"Batch URLs"** মোড সিলেক্ট করতে পারেন।
2. **প্যারামিটার সেট করুন:**
   - **Max Comments:** প্রতি পোস্ট থেকে কয়টি কমেন্ট চান (যেমন ২০০, ৫০০, বা ১০০০)।
   - **Clean Text for NLP:** টিক চিহ্ন দিলে অপ্রয়োজনীয় ইউআরএল ও স্পেস ক্লিন হয়ে যাবে।
   - **Bangla Comments Only:** শুধুমাত্র বাংলা কমেন্টের জন্য এটি টিক দিন।
3. **"Start Scraping" বাটনে ক্লিক করুন:**
   - লাইভ টার্মিনালে প্রোগ্রেস দেখতে পাবেন।
   - স্ক্র্যাপ হওয়া কমেন্টগুলো নিচের ডেটাসেট এক্সপ্লোরার টেবিলে তাৎক্ষণিকভাবে প্রদর্শিত হবে।
4. **ডাউনলোড করুন:**
   - **Download CSV (Excel Ready)** বা **Download Excel (.xlsx)** বাটনে ক্লিক করলেই সম্পূর্ণ ফাইল আপনার কম্পিউটারে সেভ হয়ে যাবে।
   - সমস্ত ডাউনলোড করা ফাইল প্রজেক্টের [`exports/`](file:///c:/Users/nasim/OneDrive/Desktop/all_comment_scrapper/exports) ফোল্ডারে সংরক্ষিত থাকে।

---

## 🔐 ফেসবুক ও ইনস্টাগ্রাম অথেনটিকেশন (Session Manager)

মেটা (Meta) প্ল্যাটফর্মগুলো (Facebook ও Instagram) অনেক ক্ষেত্রে লগইন ছাড়া ফুল কমেন্ট থ্রেড দেখতে দেয় না। এর সহজ সমাধান:
1. ড্যাশবোর্ডের উপরে ডানপাশে **"Session & Accounts"** বাটনে ক্লিক করুন।
2. **"Open Browser to Log In (Facebook / Instagram)"** এ ক্লিক করুন। একটি ক্রোমিয়াম ব্রাউজার ওপেন হবে।
3. ব্রাউজারে আপনার অ্যাকাউন্টে একবার লগইন করে উইন্ডোটি বন্ধ করে দিন।
4. ব্যস! আপনার সিকিউর সেশনটি [`backend/sessions/`](file:///c:/Users/nasim/OneDrive/Desktop/all_comment_scrapper/backend/sessions) ফোল্ডারে সেভ হয়ে যাবে এবং পরবর্তীতে যেকোনো পোস্টের কমেন্ট ফুল অ্যাক্সেস করতে পারবেন।

---

## 📁 প্রজেক্ট স্ট্রাকচার (Project Structure)

```
all_comment_scrapper/
├── backend/
│   ├── scrapers/
│   │   ├── base.py              # Base scraper & platform detector
│   │   ├── youtube.py           # High-speed YouTube comment downloader
│   │   ├── reddit.py            # Playwright & PRAW Reddit scrapers
│   │   ├── instagram.py         # Playwright Instagram comment scraper
│   │   └── facebook.py          # Playwright Facebook comment scraper
│   ├── services/
│   │   ├── cleaner.py           # Bengali NLP cleaning & language detector
│   │   ├── exporter.py          # CSV (UTF-8 BOM), Excel (.xlsx), JSON
│   │   └── session_store.py     # Facebook & Instagram session manager
│   ├── sessions/                # Saved browser session cookies
│   ├── models.py                # Pydantic data schemas
│   └── main.py                  # FastAPI server with WebSocket & REST API
├── frontend/
│   ├── index.html               # Modern glassmorphism UI
│   ├── styles.css               # Obsidian dark design system
│   └── app.js                   # WebSocket client, tables & interactive logic
├── exports/                     # Generated CSV, Excel, and JSON datasets
├── run.py                       # Single-click launcher script
├── run.bat                      # Windows executable shortcut
├── requirements.txt             # Python packages
└── README.md                    # Project documentation
```

---

## 🎓 থিসিস ও গবেষণার জন্য সহায়িকা (Thesis & NLP Tips)

- **বাংলা এনএলপি অ্যানালাইসিস:** এক্সপোর্ট করা ফাইলে `text` কলামে মূল কমেন্ট এবং `cleaned_text` কলামে ক্লিনিং করা টেক্সট আলাদা কলামে দেওয়া থাকে, যা Sentiment Analysis, Hate Speech Detection বা Topic Modeling এর জন্য অত্যন্ত উপযোগী।
- **Excel Encoding Issue Solution:** অনেক সময় মাইক্রোসফ্ট এক্সেলে বাংলা লিখা যুক্ত CSV ওপেন করলে প্রশ্নবোধক চিহ্ন বা অক্ষর ভেঙে যায়। এই সিস্টেমে প্রতিটি ফাইল `utf-8-sig` (Byte Order Mark) দিয়ে এনকোড করা হয়, ফলে এক্সেলে বাংলা ১০০% নিখুঁতভাবে ওপেন হয়।
- **গবেষণার নৈতিকতা:** থিসিস বা রিসার্চ পেপার প্রকাশের সময় ইউজারদের ব্যক্তিগত তথ্য (যেমন নাম/ইউজারনেম) অ্যানোনিমাইজ (Anonymize) করার পরামর্শ দেওয়া হলো।
