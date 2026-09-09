# EVMS Intelligence — Technical Architecture

## 1. هدف سیستم

EVMS Intelligence یک برنامه تحت وب برای تحلیل داده‌های مدیریت ارزش کسب‌شده (Earned Value Management System) است. سیستم باید به کاربر اجازه دهد سؤال خود را به زبان طبیعی وارد کند، داده مرتبط را از Microsoft SQL Server بازیابی کند، داده خام را پیش از هر تحلیل در اختیار کاربر قرار دهد، و تنها پس از تأیید کاربر تحلیل و نمودار تولید کند.

اصل کلیدی معماری:

> هیچ داده بازیابی‌شده‌ای قبل از تأیید صریح کاربر وارد مرحله تحلیل نخواهد شد.

کل برنامه با Python توسعه داده می‌شود و Django لایه اصلی وب را تشکیل می‌دهد. LangChain برای اتصال به مدل زبانی و ابزارها و LangGraph برای کنترل workflow چندمرحله‌ای و توقف جهت Human-in-the-loop استفاده می‌شود.

---

## 2. نمای کلی رابط کاربری

صفحه اصلی به سه ستون مساوی تقسیم می‌شود:

```text
+----------------------+----------------------+----------------------+
|                      |                      |                      |
|       CHART          |        CHAT          |        DATA          |
|                      |                      |                      |
|   نمودار تعاملی      |  پرسش و پاسخ کاربر  |   جدول داده SQL      |
|                      |                      |                      |
|                      |                      |                      |
+----------------------+----------------------+----------------------+
                                                [Approve] [Reject]
```

### ستون چپ — Chart Panel

وظایف:

- نمایش نمودارهای مرتبط با سؤال کاربر
- نمایش نمودار فقط بعد از تأیید dataset
- پشتیبانی از hover، zoom، pan و tooltip
- امکان تغییر اندازه نمودار متناسب با صفحه
- نمایش پیام placeholder تا قبل از تولید نمودار

پیشنهاد فنی:

- تحلیل داده و آماده‌سازی نمودار با pandas / matplotlib / seaborn
- تبدیل نتیجه به visualization تعاملی با Plotly یا mpld3

نکته:

`matplotlib` و `seaborn` به‌صورت ذاتی نمودار وب کاملاً تعاملی تولید نمی‌کنند. بنابراین پیشنهاد می‌شود مدل specification نمودار را تولید کند و Backend داده را با Plotly render کند. در صورت الزام به matplotlib/seaborn، می‌توان خروجی را با mpld3 در مرورگر نمایش داد.

### ستون وسط — Chat Panel

وظایف:

- نمایش history مکالمه
- textbox برای ورود prompt
- دکمه ارسال
- نمایش وضعیت workflow مانند:
  - Understanding question
  - Generating SQL
  - Waiting for confirmation
  - Analyzing data
  - Generating chart
- نمایش پاسخ نهایی مدل

### ستون راست — Data Panel

وظایف:

- نمایش dataset استخراج‌شده از SQL Server
- نمایش نام ستون‌ها و تعداد رکوردها
- scroll افقی و عمودی
- pagination برای داده‌های بزرگ
- دکمه‌های:
  - Approve Data
  - Reject Data

تا زمانی که کاربر داده را تأیید نکرده است، workflow در حالت pause باقی می‌ماند.

---

## 3. Technology Stack

### Backend

- Python 3.12
- Django 5.x
- Django REST Framework
- LangChain
- LangGraph
- pandas
- SQLAlchemy
- pyodbc
- pydantic
- httpx

### Database

- Microsoft SQL Server
- Windows Authentication یا SQL Authentication

### Local LLM

مدل می‌تواند از LM Studio یا هر endpoint سازگار با OpenAI API استفاده کند.

نمونه:

```text
http://<LLM_SERVER>:1234/v1
```

### Frontend

- Django Templates
- HTML5
- CSS Grid
- Vanilla JavaScript
- Fetch API

برای نسخه اول استفاده از React ضروری نیست.

### Visualization

ترکیب پیشنهادی:

- pandas برای آماده‌سازی داده
- seaborn / matplotlib برای تحلیل و styling
- Plotly برای rendering تعاملی در Browser

---

## 4. ساختار پیشنهادی پروژه

```text
evms_intelligence/
│
├── manage.py
├── requirements.txt
├── .env
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── chat/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services.py
│   │   └── serializers.py
│   │
│   ├── evms/
│   │   ├── schema.py
│   │   ├── repository.py
│   │   ├── sql_validator.py
│   │   └── services.py
│   │
│   └── workflow/
│       ├── graph.py
│       ├── state.py
│       ├── nodes/
│       │   ├── classify.py
│       │   ├── generate_sql.py
│       │   ├── execute_sql.py
│       │   ├── await_confirmation.py
│       │   ├── analyze_data.py
│       │   └── generate_chart.py
│       └── prompts/
│
├── templates/
│   └── dashboard.html
│
├── static/
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       └── dashboard.js
│
└── logs/
```

---

## 5. LangGraph State

State باید اطلاعات کامل workflow را نگه دارد.

```python
class EVMSState(TypedDict):
    thread_id: str
    user_prompt: str

    intent: str | None
    generated_sql: str | None

    columns: list[str] | None
    rows: list[dict] | None
    row_count: int | None

    confirmation_status: str | None

    analysis: str | None
    chart_spec: dict | None
    chart_payload: dict | None

    error: str | None
```

مقادیر `confirmation_status`:

```text
pending
approved
rejected
```

---

## 6. LangGraph Workflow

```text
START
  |
  v
Receive Prompt
  |
  v
Classify Intent
  |
  v
Generate SQL
  |
  v
Validate SQL
  |
  v
Execute SQL
  |
  v
Build Dataset
  |
  v
Display Dataset
  |
  v
[ INTERRUPT / WAIT FOR USER ]
  |
  +------------------+
  |                  |
Approve            Reject
  |                  |
  v                  v
Analyze Data       Return to Prompt/
  |                SQL Generation
  v
Generate Chart Spec
  |
  v
Render Interactive Chart
  |
  v
Final Answer
  |
  v
END
```

---

## 7. Node Responsibilities

### 7.1 classify_intent

هدف:

- تشخیص نوع سؤال
- مشخص کردن اینکه سؤال نیاز به query جدید دارد یا خیر
- استخراج metricهای EVMS مورد نیاز

نمونه intent:

```text
project_performance
cost_variance
schedule_variance
trend_analysis
project_comparison
forecast
general_question
```

---

### 7.2 generate_sql

مدل فقط SQL `SELECT` تولید می‌کند.

ورودی:

- سؤال کاربر
- semantic schema دیتابیس
- glossary شاخص‌های EVMS
- allowlisted tables/views

خروجی:

```json
{
  "sql": "SELECT ...",
  "reason": "..."
}
```

---

## 8. Semantic Schema

مدل نباید مستقیماً از metadata خام دیتابیس استفاده کند. یک semantic schema کنترل‌شده به مدل داده می‌شود.

نمونه:

```yaml
views:
  vw_EVMS_Project_Monthly:
    description: Monthly EVMS values for each project
    columns:
      ProjectCode: Project identifier
      DataDate: Reporting date
      PV: Planned Value
      EV: Earned Value
      AC: Actual Cost
      BAC: Budget at Completion
      CPI: Cost Performance Index
      SPI: Schedule Performance Index
```

همچنین glossary:

```text
CV = EV - AC
SV = EV - PV
CPI = EV / AC
SPI = EV / PV
EAC = Estimated Cost at Completion
VAC = BAC - EAC
```

---

## 9. SQL Security Rules

SQL generated by LLM هرگز نباید مستقیماً اجرا شود.

Validator باید موارد زیر را بررسی کند:

- فقط SELECT
- ممنوعیت INSERT
- ممنوعیت UPDATE
- ممنوعیت DELETE
- ممنوعیت DROP
- ممنوعیت ALTER
- ممنوعیت EXEC
- ممنوعیت CREATE
- ممنوعیت MERGE
- فقط tables/views مجاز
- محدودیت row count
- timeout اجرای query

پیشنهاد:

```sql
SELECT TOP (1000) ...
```

برای queryهای بدون aggregation.

---

## 10. Human-in-the-loop Confirmation

پس از اجرای SQL:

1. DataFrame ساخته می‌شود.
2. داده به مرورگر ارسال می‌شود.
3. جدول در ستون راست نمایش داده می‌شود.
4. LangGraph interrupt ایجاد می‌کند.
5. workflow متوقف می‌شود.
6. کاربر یکی از دو گزینه را انتخاب می‌کند.

### Approve

```text
confirmation_status = approved
```

Graph resume شده و dataset وارد node تحلیل می‌شود.

### Reject

```text
confirmation_status = rejected
```

در این حالت:

- داده به مدل تحلیل ارسال نمی‌شود.
- کاربر می‌تواند توضیح دهد چه چیزی اشتباه است.
- SQL مجدداً ساخته می‌شود.

---

## 11. Data Analysis Node

این node فقط dataset تأییدشده را دریافت می‌کند.

ورودی:

- original question
- confirmed dataframe
- EVMS glossary

وظایف:

- پاسخ مستقیم به سؤال
- شناسایی trend
- شناسایی anomaly
- مقایسه پروژه‌ها
- توضیح شاخص‌ها
- جلوگیری از inference بدون پشتوانه داده

مدل باید واضح اعلام کند اگر dataset برای پاسخ کافی نیست.

---

## 12. Chart Generation Node

مدل نباید Python code آزاد و بدون validation اجرا کند.

پیشنهاد اصلی:

مدل یک `chart_spec` ساختاریافته تولید کند.

نمونه:

```json
{
  "chart_type": "line",
  "x": "DataDate",
  "y": ["CPI", "SPI"],
  "group_by": "ProjectCode",
  "title": "CPI and SPI Trend",
  "x_label": "Data Date",
  "y_label": "Index",
  "reference_lines": [1.0]
}
```

Backend این specification را validate کرده و نمودار را تولید می‌کند.

انواع مجاز:

```text
line
bar
scatter
area
histogram
box
heatmap
```

---

## 13. Interactive Visualization Strategy

سه گزینه وجود دارد.

### گزینه پیشنهادی — Plotly

```text
LLM -> Chart Spec -> pandas -> Plotly -> JSON -> Browser
```

مزایا:

- zoom
- hover
- tooltip
- legend interaction
- responsive design

### گزینه دوم — mpld3

```text
seaborn/matplotlib -> mpld3 -> HTML
```

این روش استفاده مستقیم‌تر از matplotlib دارد ولی نسبت به Plotly محدودتر است.

### گزینه سوم — تصویر PNG

فقط برای fallback.

---

## 14. Django Models

### ChatThread

```text
id
created_at
updated_at
user
```

### ChatMessage

```text
id
thread
role
content
created_at
```

### WorkflowRun

```text
id
thread
status
user_prompt
generated_sql
confirmation_status
analysis
created_at
updated_at
```

### DatasetSnapshot

```text
id
workflow_run
columns_json
rows_json
row_count
approved
created_at
```

---

## 15. API Endpoints

```text
POST /api/chat/query/
POST /api/workflow/<run_id>/approve/
POST /api/workflow/<run_id>/reject/
GET  /api/workflow/<run_id>/status/
GET  /api/workflow/<run_id>/dataset/
GET  /api/workflow/<run_id>/chart/
```

### POST /api/chat/query/

ورودی:

```json
{
  "thread_id": "...",
  "message": "وضعیت CPI پروژه‌ها در سه ماه اخیر چگونه بوده؟"
}
```

خروجی اولیه:

```json
{
  "run_id": "...",
  "status": "waiting_for_confirmation",
  "dataset": {
    "columns": [],
    "rows": []
  }
}
```

---

## 16. Frontend State

Browser باید حداقل state زیر را نگه دارد:

```javascript
{
  threadId: null,
  runId: null,
  workflowStatus: null,
  dataset: null,
  analysis: null,
  chart: null
}
```

---

## 17. User Interaction Sequence

سناریو نمونه:

کاربر:

```text
کدام پروژه‌ها در سه ماه اخیر CPI کمتر از 0.9 داشته‌اند؟
```

سیستم:

1. سؤال را دریافت می‌کند.
2. SQL تولید می‌کند.
3. SQL validation انجام می‌شود.
4. query اجرا می‌شود.
5. جدول در پنل سمت راست نمایش داده می‌شود.
6. سیستم می‌پرسد:

```text
آیا داده بازیابی‌شده صحیح است؟
```

7. کاربر Approve را انتخاب می‌کند.
8. مدل تحلیل می‌کند.
9. پاسخ در پنل Chat نمایش داده می‌شود.
10. chart spec تولید می‌شود.
11. نمودار در پنل چپ نمایش داده می‌شود.

---

## 18. Error Handling

انواع خطا:

```text
LLM connection error
SQL generation error
SQL validation error
Database connection error
SQL timeout
Empty dataset
User rejected dataset
Chart generation error
```

هر خطا باید:

- log شود
- پیام قابل فهم برای کاربر داشته باشد
- باعث crash کل workflow نشود

---

## 19. Logging and Audit

برای محیط سازمانی ثبت موارد زیر ضروری است:

- user prompt
- generated SQL
- timestamp
- returned row count
- confirmation action
- analysis result
- chart specification
- execution duration
- errors

---

## 20. Recommended Development Phases

### Phase 1 — MVP

- Django UI سه ستونه
- اتصال SQL Server
- Chat endpoint
- LangChain LLM connection
- SQL generation
- DataFrame rendering
- Approve / Reject

### Phase 2 — LangGraph

- state machine
- interrupt
- resume
- workflow persistence

### Phase 3 — Analysis

- confirmed-data analysis
- EVMS glossary
- project comparison

### Phase 4 — Visualization

- chart specification
- interactive Plotly chart
- matplotlib/seaborn fallback

### Phase 5 — Enterprise Controls

- Authentication
- audit logs
- row-level access
- query allowlist
- caching
- rate limiting

---

## 21. مهم‌ترین اصل معماری

Workflow باید این ترتیب را به‌صورت اجباری enforce کند:

```text
Question
   ↓
SQL
   ↓
Dataset
   ↓
USER CONFIRMATION
   ↓
Analysis
   ↓
Visualization
```

هیچ node نباید بتواند `analysis` یا `chart generation` را با dataset تأییدنشده اجرا کند.
