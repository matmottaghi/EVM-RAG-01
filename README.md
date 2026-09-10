# EVMS Intelligence

EVMS Intelligence یک برنامهٔ وب Django برای پرسش‌وپاسخ روی داده‌های مدیریت
ارزش کسب‌شده (EVMS) در Microsoft SQL Server است. مدل محلی از طریق endpoint
سازگار با OpenAI در **LM Studio** فراخوانی می‌شود. سیستم ابتدا SQL فقط‌خواندنی
می‌سازد، نتیجهٔ خام را به کاربر نشان می‌دهد و تا دریافت تأیید صریح هیچ داده‌ای
را برای تحلیل یا طراحی نمودار به مدل نمی‌فرستد.

## جریان قطعی کسب‌وکار

```text
پرسش طبیعی
  -> تولید SQL با LM Studio
  -> اعتبارسنجی قطعی SQL
  -> اجرای read-only روی SQL Server
  -> نمایش جدول داده
  -> توقف پایدار LangGraph و تأیید/رد انسان
  -> فقط در حالت تأیید: تحلیل با LM Studio
  -> chart spec ساختاریافته و اعتبارسنجی‌شده
  -> نمودار تعاملی Plotly
```

دو guard مستقل در گره‌های تحلیل و طراحی نمودار وجود دارد. بنابراین تغییر اشتباه
در routing گراف نیز نمی‌تواند دادهٔ pending یا rejected را به مدل تحلیل بفرستد.
هیچ کد Python/JavaScript تولیدشده توسط مدل اجرا نمی‌شود.

## قابلیت‌ها

- داشبورد responsive سه‌ستونه: نمودار، گفت‌وگو و جدول SQL
- Django 5 و Django REST Framework
- LangChain با `ChatOpenAI` متصل به LM Studio
- LangGraph با `interrupt()` و ادامه با `Command(resume=...)`
- checkpoint پایدار SQLite با شناسهٔ مستقل برای هر workflow run
- SQL Server از طریق SQLAlchemy، pandas و pyodbc
- validator مبتنی بر AST با sqlglot، allowlist view/schema و سقف `TOP`
- Windows Authentication و SQL Authentication
- audit مکالمه، SQL، تعداد ردیف، تصمیم کاربر، تحلیل، chart spec، زمان و خطا
- نمودارهای line، bar، scatter، area، histogram، box و heatmap
- pagination جدول و APIهای status، dataset و chart

## ساختار پروژه

```text
apps/chat/       مدل‌ها، API، سرویس اجرا، audit و migration
apps/evms/       semantic schema، glossary، validator و repository SQL Server
apps/workflow/   state، prompt، کلاینت LM Studio، graph و nodeها
config/          تنظیمات و URLهای Django
templates/       داشبورد HTML
static/          CSS و JavaScript بدون React
logs/            log چرخشی برنامه (در Git ثبت نمی‌شود)
var/             checkpoint پایدار LangGraph (در Git ثبت نمی‌شود)
```

دیتابیس `db.sqlite3` فقط metadata برنامه، مکالمه، audit و snapshotها را نگه
می‌دارد. دادهٔ EVMS از اتصال جداگانهٔ SQL Server فقط خوانده می‌شود.

## پیش‌نیازها

1. Windows 10/11 یا Windows Server
2. Python 3.12 نسخهٔ 64-bit
3. Microsoft ODBC Driver 18 for SQL Server
4. دسترسی read-only به view گزارش‌گیری EVMS
5. LM Studio و یک مدل instruction/chat بارگذاری‌شده

بررسی نصب‌ها در PowerShell:

```powershell
py -3.12 --version
Get-OdbcDriver -Name "ODBC Driver 18 for SQL Server"
```
## ۱. ساخت محیط Python

در ریشهٔ پروژه PowerShell را باز کنید:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

اگر اجرای Activate مسدود است، فقط برای همان process بنویسید:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

## ۲. راه‌اندازی LM Studio

1. LM Studio را نصب و اجرا کنید.
2. از بخش مدل‌ها یک مدل chat/instruction مناسب دانلود و Load کنید.
3. در بخش **Developer / Local Server**، سرور سازگار با OpenAI را Start کنید.
4. آدرس معمول سرور محلی `http://127.0.0.1:1234/v1` است؛ اگر port یا میزبان
   را تغییر داده‌اید همان مقدار را در `.env` بنویسید.
5. شناسهٔ دقیق مدل را از UI یا endpoint زیر بگیرید:

```powershell
Invoke-RestMethod http://127.0.0.1:1234/v1/models
```

6. قبل از اجرای Django اتصال را smoke-test کنید:

```powershell
$body = @{
  model = "MODEL_ID_FROM_PREVIOUS_COMMAND"
  messages = @(@{ role = "user"; content = "Reply with OK" })
  temperature = 0.1
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:1234/v1/chat/completions `
  -ContentType "application/json" -Body $body
```

کلید `lm-studio` یک مقدار dummy مورد انتظار کلاینت OpenAI-compatible است و
credential واقعی محسوب نمی‌شود. هیچ IP، مدل یا credential در کد hard-code نشده است.

## ۳. آماده‌سازی SQL Server

حساب ویندوزی که Django را اجرا می‌کند باید فقط مجوز `SELECT` روی view مجاز داشته
باشد. نمونهٔ حداقلی برای DBA:

```sql
CREATE USER [DOMAIN\EVMS_APP_USER] FOR LOGIN [DOMAIN\EVMS_APP_USER];
GRANT SELECT ON OBJECT::dbo.vw_EVMS_Project_Monthly TO [DOMAIN\EVMS_APP_USER];
```

نام view و ستون‌های واقعی سازمان را در `apps/evms/schema.py` ثبت کنید. هر رابطه‌ای
که در این semantic schema نباشد توسط validator رد می‌شود. starter schema شامل:

```text
dbo.vw_EVMS_Project_Monthly
ProjectCode, ProjectName, DataDate, PV, EV, AC, BAC, CPI, SPI, EAC, ETC, VAC
```

برای تست اتصال Windows Authentication می‌توانید از `sqlcmd` استفاده کنید:

```powershell
sqlcmd -S "SERVER_NAME" -d "EVMS_DB" -E -Q "SELECT TOP (1) * FROM dbo.vw_EVMS_Project_Monthly"
```
## ۴. تنظیم متغیرهای محیطی

فایل نمونه را کپی کنید؛ فایل واقعی `.env` در Git نادیده گرفته می‌شود:

```powershell
Copy-Item .env.example .env
notepad .env
```

نمونهٔ Windows Authentication با LM Studio:

```env
DJANGO_SECRET_KEY=یک-مقدار-تصادفی-طولانی
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_TIME_ZONE=Asia/Tehran

LLM_BASE_URL=http://127.0.0.1:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL=شناسه-دقیق-مدل-لودشده
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=120
LLM_MAX_DATA_ROWS=200

DB_SERVER=SERVER_NAME
DB_DATABASE=EVMS_DB
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_TRUSTED_CONNECTION=yes
DB_ENCRYPT=no
DB_TRUST_SERVER_CERTIFICATE=yes
DB_QUERY_TIMEOUT_SECONDS=30
DB_CONNECT_TIMEOUT_SECONDS=10
DB_MAX_ROWS=1000
DB_ALLOWED_SCHEMAS=dbo
```

برای SQL Authentication، `DB_TRUSTED_CONNECTION=no` و دو متغیر
`DB_USERNAME` و `DB_PASSWORD` را اضافه کنید. secretها را commit نکنید.

برای تولید `DJANGO_SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`LLM_MAX_DATA_ROWS` سقف ردیف‌هایی است که پس از تأیید برای تحلیل متنی به مدل
فرستاده می‌شود. کل دادهٔ تأییدشده برای render نمودار در Backend قابل استفاده است.
`DB_MAX_ROWS` نیز در validator به `TOP` تبدیل و حداکثر 10000 محدود می‌شود.

## ۵. migration و اجرای پروژه

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

سپس `http://127.0.0.1:8000/` را باز کنید. ترتیب استفاده:

1. سؤال را در پنل میانی ارسال کنید.
2. داده و تعداد ردیف را در پنل راست بررسی کنید.
3. **تأیید داده** یا **رد داده** را انتخاب کنید.
4. فقط پس از تأیید، تحلیل در چت و نمودار در پنل چپ ظاهر می‌شود.
5. پس از رد، دلیل را وارد و اصلاح را در پیام بعدی ارسال کنید.
## API

| Method | Path | کاربرد |
|---|---|---|
| POST | `/api/chat/query/` | ساخت run، تولید/اجرای SQL و بازگرداندن dataset |
| POST | `/api/workflow/<run_id>/approve/` | ثبت تأیید، resume گراف، تحلیل و نمودار |
| POST | `/api/workflow/<run_id>/reject/` | ثبت رد و پایان بدون تحلیل |
| GET | `/api/workflow/<run_id>/status/` | وضعیت، نتیجه یا خطای run |
| GET | `/api/workflow/<run_id>/dataset/` | داده با `page` و `page_size` |
| GET | `/api/workflow/<run_id>/chart/` | JSON نمودار تأییدشده |

نمونهٔ query:

```json
{
  "thread_id": null,
  "message": "روند CPI و SPI پروژه A در شش ماه اخیر چگونه بوده است؟"
}
```

پاسخ اولیه در حالت موفق `status=waiting_for_confirmation` و شامل `run_id`،
`thread_id` و dataset است. درخواست approve ممکن است تا پایان پاسخ مدل طول بکشد.

## امنیت SQL و داده

- فقط یک AST از نوع query دارای SELECT پذیرفته می‌شود.
- tokenها و nodeهای تغییر داده/DDL/EXEC/SELECT INTO رد می‌شوند.
- cross-database، schema ناشناخته، system table و relation خارج allowlist رد می‌شود.
- سقف ردیف در خود SQL Server با `TOP` enforce می‌شود؛ pagination جایگزین آن نیست.
- timeout اتصال و query مستقل‌اند.
- URL اتصال و password در log نوشته نمی‌شود.
- endpoint نمودار قبل از approval پاسخ conflict می‌دهد.
- snapshot تأییدنشده فقط برای نمایش و checkpoint نگهداری می‌شود و به LLM تحلیل نمی‌رود.

## تست و کنترل کیفیت

```powershell
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

تست‌ها شامل مسدودشدن DELETE/DROP و table ناشناخته، پذیرش SELECT امن، CTE،
ممنوعیت تحلیل pending/rejected، resume واقعی پس از approve، پایان بدون تحلیل پس
از reject و رد chart column نامعتبر هستند.

## فایل‌های runtime و audit

- `db.sqlite3`: مدل‌های Django شامل thread، message، run و dataset snapshot
- `var/langgraph_checkpoints.sqlite3`: state و نقطهٔ interrupt/resume LangGraph
- `logs/evms.log`: log چرخشی تا پنج فایل 5MB

هر workflow run شناسهٔ UUID مستقل دارد و همان UUID کلید checkpoint است. این طراحی
اجازه نمی‌دهد پرسش بعدی یک conversation، checkpoint run قبلی را اشتباه resume کند.
## عیب‌یابی

### LM Studio unavailable

- مدل باید Load و Local Server باید Start باشد.
- خروجی `/v1/models` را با `LLM_MODEL` تطبیق دهید.
- `LLM_BASE_URL` باید به `/v1` ختم شود.
- firewall و port 1234 را بررسی کنید.

### SQL Server unavailable یا login timeout

- نام server/instance و database را کنترل کنید.
- Driver 18 را با `Get-OdbcDriver` بررسی کنید.
- برای Windows Authentication، process Django باید با همان identity مجاز اجرا شود.
- در محیط امن production مقدارهای `DB_ENCRYPT=yes` و certificate معتبر را ترجیح دهید.

### invalid SQL

معمولاً مدل نام view/column خارج semantic schema ساخته است. schema را با view
واقعی هماهنگ و prompt را دوباره ارسال کنید؛ validator را برای عبور query ناامن
شل نکنید.

### checkpoint missing

فایل `var/langgraph_checkpoints.sqlite3` حذف یا run قبلاً تمام شده است. query را
از ابتدا اجرا کنید. در چند worker یا استقرار بزرگ، checkpointer را به PostgreSQL
مشترک ارتقا دهید.

### Plotly در مرورگر نمایش داده نمی‌شود

نسخهٔ فعلی Plotly.js از CDN بارگذاری می‌شود. در شبکهٔ air-gapped فایل Plotly.js
را داخل `static/vendor/` قرار دهید و آدرس script در template را محلی کنید.

## نکات استقرار production

MVP برای اجرای سازمانی کوچک ساختار production-oriented دارد، اما پیش از انتشار
عمومی این موارد را انجام دهید:

- `DJANGO_DEBUG=false`، secret پایدار و hostهای دقیق
- HTTPS، Secure cookie، reverse proxy و static-file hosting
- احراز هویت سازمانی و مجوز سطح پروژه/ردیف در viewهای SQL Server
- حساب SQL فقط‌خواندنی و audit/retention policy مصوب
- PostgreSQL checkpointer برای چند worker و رمزنگاری checkpoint در حالت حساس
- rate limiting، monitoring، backup و پاک‌سازی دوره‌ای snapshotها
- اجرای تست integration روی یک SQL Server staging و مدل دقیق production

SQLite checkpointer برای یک process یا استقرار سبک مناسب است؛ برای scale افقی
فایل SQLite را بین workerها share نکنید.

## توسعهٔ semantic schema

برای افزودن view جدید:

1. view گزارش‌گیری read-only را در SQL Server بسازید.
2. فقط همان view و ستون‌های مجاز را در `apps/evms/schema.py` اضافه کنید.
3. مجوز SELECT حساب برنامه را محدود کنید.
4. تست validator و تست integration بنویسید.
5. خروجی اولیه را در UI بازبینی و بعد approve کنید.

معماری مبنا در `EVMS_ARCHITECTURE.md` و مشخصات build در
`EVMS_BUILD_PROMPT.md` نگهداری شده‌اند.
