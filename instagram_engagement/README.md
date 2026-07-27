# أداة تحليل تفاعل حساب إنستغرام (Instagram Engagement Analyzer)

أداة بايثون تحسب معدل التفاعل (Engagement Rate) لحساب إنستغرام معيّن، بناءً على
آخر منشوراته (متوسط اللايكات + التعليقات مقارنة بعدد المتابعين).

توفر طريقتين لجلب البيانات:

## 1) Instagram Graph API الرسمي — للحسابات التي تملكها/تديرها

الطريقة الموثوقة والمدعومة رسميًا. تتطلب:

1. حساب Instagram **Business** أو **Creator** مرتبط بصفحة فيسبوك.
2. تطبيق مسجَّل على [Meta for Developers](https://developers.facebook.com/)
   مع صلاحيات `instagram_basic` و `instagram_manage_insights`.
3. رمز وصول (Access Token) صالح لحسابك.

```bash
python main.py graph-api \
  --ig-user-id 17841400000000000 \
  --access-token "EAAG..." \
  --limit 25
```

أو ضع الرمز في ملف `.env` (انظر `.env.example`):

```
IG_ACCESS_TOKEN=your_token_here
```

## 2) حساب عام (Public) — عبر بيانات إنستغرام المتاحة للعامة

مخصصة لتحليل حساب عام (غير خاص) لا تملكه، باستخدام مكتبة `instaloader`.
هذه الطريقة تعتمد على واجهات غير رسمية وقد تخضع لحدود معدل الطلبات، لذا استخدمها
بمسؤولية ووفق شروط استخدام إنستغرام، ولأغراض تحليلية/بحثية مشروعة فقط.

```bash
python main.py public --username some_public_account --limit 25
```

## 3) مراقبة التفاعل وإشعارات فورية (لايك/تعليق/متابعة جديدة)

أمر `watch` يفحص الحساب دوريًا (أو مرة واحدة عبر `--once`)، يقارن النتيجة بآخر حالة
محفوظة في ملف JSON محلي، ويرسل إشعارًا عند اكتشاف أي زيادة في: عدد المتابعين،
لايكات منشور، تعليقات منشور (مع اسم المعلّق ونص التعليق عند توفره)، أو ظهور
منشور جديد.

أول فحص لا يُصدر إشعارات تفاعل — فقط يسجّل "الحالة الأولية"، وابتداءً من الفحص
الثاني تُكتشف الفروقات (deltas) وتُرسَل كإشعارات.

```bash
# مراقبة حساب عام كل 5 دقائق، إشعار في الطرفية
python main.py watch --source public --username some_public_account --interval 300

# مراقبة حساب تملكه عبر Graph API، إشعار عبر Slack/Discord Webhook
python main.py watch --source graph-api \
  --ig-user-id 17841400000000000 --access-token "EAAG..." \
  --notify webhook --webhook-url "https://hooks.slack.com/services/..." --webhook-style slack

# فحص واحد فقط (مناسب لتشغيله عبر cron كل بضع دقائق)
python main.py watch --source public --username some_public_account --once
```

قنوات الإشعار المتاحة عبر `--notify` (يمكن الجمع بينها):
- `console`: طباعة في الطرفية (الافتراضي).
- `desktop`: إشعار سطح مكتب (عبر `notify-send` في لينكس أو `osascript` في ماك).
- `webhook`: إرسال إلى رابط Slack/Discord عبر `--webhook-url`.

## التثبيت

```bash
pip install -r requirements.txt
```

## بنية المشروع

```
instagram_engagement/
├── main.py              # واجهة سطر الأوامر
├── engagement.py         # نماذج البيانات وحساب معدل التفاعل
├── graph_api_source.py   # مصدر البيانات: Instagram Graph API الرسمي
├── public_source.py      # مصدر البيانات: instaloader (حسابات عامة)
├── watcher.py             # منطق المراقبة واكتشاف التفاعل الجديد
├── state_store.py         # حفظ/تحميل آخر حالة معروفة للحساب
├── notifier.py            # قنوات الإشعار (console / desktop / webhook)
├── requirements.txt
└── .env.example
```

## معادلة معدل التفاعل

```
Engagement Rate % = (متوسط اللايكات + متوسط التعليقات لكل منشور) / عدد المتابعين × 100
```
