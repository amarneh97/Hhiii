# سجلّ أخطاء المحادثات مع كلود

أداة سطر أوامر تسجّل **كل خطأ يقع في محادثاتك مع كلود** — في Claude Code وفي
claude.ai العادي — في ملف واحد قابل للبحث والإحصاء، بدل أن يضيع الخطأ في سجل
المحادثة.

لا تحتاج أي حزمة خارجية: مكتبة بايثون القياسية فقط.

## ما الذي يُعتبر «خطأ»؟

| النوع | ماذا يعني | من أين يُلتقَط |
|---|---|---|
| `tool_error` | فشل أداة داخل Claude Code (أمر، قراءة ملف، تعديل…) | الخطّاف + فحص الجلسات |
| `api_error` | خطأ من الـ API نفسه (529، حد طلبات، انقطاع) | فحص الجلسات + الخطّاف |
| `permission` | رفض صلاحية أو أداة محظورة | خطّاف `Notification` |
| `user_correction` | **أنت** قلت لكلود إنه أخطأ («هذا خطأ»، «غلط»، `that's wrong` …) | الخطّاف + الجلسات + تصدير claude.ai |
| `manual` | خطأ سجّلته أنت بنفسك بأمر `log` | يدوي |

`user_correction` هو الأهم عمليًا: هو الأثر الوحيد لخطأ *في محتوى* الرد (نصيحة
غلط، كود لا يعمل، معلومة خاطئة) — وهذا النوع لا يعلّمه أحد تلقائيًا، لكنه يظهر
دائمًا في ردّة فعلك عليه. في تصدير claude.ai يُحفَظ مع اقتباس ردّ كلود الذي سبقه،
أي محلّ الخطأ نفسه.

## 1) تسجيل تلقائي لأخطاء Claude Code (خطّافات)

```bash
python main.py install-hook --global     # لكل المشاريع (~/.claude/settings.json)
python main.py install-hook              # لهذا المشروع فقط (.claude/settings.json)
```

يضيف ثلاثة خطّافات: `PostToolUse` (فشل الأدوات)، `UserPromptSubmit` (تصحيحاتك)،
`Notification` (الصلاحيات). ابدأ جلسة جديدة ليسري المفعول. الخطّاف يخرج بالرمز 0
دائمًا ولا يطبع شيئًا، فلا يعطّل جلستك مهما حدث.

للإزالة: `python main.py uninstall-hook --global`

## 2) فحص جلسات Claude Code السابقة

```bash
python main.py scan                  # يقرأ ~/.claude/projects/**/*.jsonl
python main.py scan --dry-run        # عرض ما سيُسجَّل دون كتابته
python main.py scan --limit-files 20 # أحدث 20 جلسة فقط
python main.py scan --no-corrections # الأخطاء التقنية فقط
```

الفحص لا يكرّر ما سُجّل سابقًا: لكل خطأ بصمة ثابتة، فإعادة الفحص تضيف الجديد فقط.

## 3) استيراد أخطاء claude.ai

احصل على بياناتك من: claude.ai ← Settings ← Privacy ← Export data، ثم:

```bash
python main.py import --file ~/Downloads/conversations.json
python main.py import --file conversations.json --with-output-errors  # يلتقط أيضًا أي نص يحمل أثر خطأ تقني
```

## 4) العرض والإحصاء والتقارير

```bash
python main.py list --min-severity high        # الأخطاء المهمّة فقط
python main.py list --source claude_web --detail
python main.py list --search "git" --limit 10
python main.py list --since 2026-09-01
python main.py stats                           # توزيع الأخطاء على المصدر والنوع والخطورة وأكثر الجلسات
python main.py report --format markdown --output errors.md
python main.py report --format json --output errors.json
```

## 5) تسجيل خطأ يدويًا

```bash
python main.py log --message "أعطاني أمر git خاطئ حذف تغييراتي" \
                   --source claude_web --severity high \
                   --session "نقاش عن Git" --tag git --detail-file reply.txt
```

## مكان السجل

`~/.claude/error-log/errors.jsonl` افتراضيًا — سطر JSON لكل خطأ. لتغييره:

```bash
export CLAUDE_ERROR_LOG=/path/to/errors.jsonl   # أو
python main.py --log-file /path/to/errors.jsonl list
```

`--log-file` يأتي **قبل** الأمر الفرعي. لمعرفة المسار الحالي وعدد الأخطاء:
`python main.py path`

## خصوصية

كل شيء محلي: لا يُرسل أي سطر إلى أي خدمة. لكن السجل يحفظ نصوص رسائلك ومخرجات
أدواتك، فعامله كما تعامل سجلات جلساتك — ولا ترفعه إلى مستودع عام.

## الملفات

| الملف | الدور |
|---|---|
| `main.py` | واجهة سطر الأوامر |
| `hook.py` | نقطة دخول خطّافات Claude Code |
| `models.py` | نموذج الخطأ والبصمة المانعة للتكرار |
| `store.py` | تخزين JSONL + التصفية |
| `detect.py` | كشف التصحيحات وآثار الأخطاء في النصوص |
| `report.py` | العرض بصيغ نص/Markdown/JSON |
| `sources/claude_code.py` | قراءة جلسات Claude Code |
| `sources/claude_web.py` | قراءة تصدير claude.ai |

## الاختبارات

```bash
pip install -r requirements.txt
python -m pytest tests -q
```
