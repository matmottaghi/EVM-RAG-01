class WorkflowError(RuntimeError):
    code = "workflow_error"
    public_message = "گردش‌کار EVMS کامل نشد."


class LLMConfigurationError(WorkflowError):
    code = "llm_configuration_error"
    public_message = "تنظیمات LM Studio در فایل .env کامل نیست."


class LLMResponseError(WorkflowError):
    code = "invalid_llm_response"
    public_message = "پاسخ مدل زبانی ساختار معتبر مورد انتظار را نداشت."


class EmptyDatasetError(WorkflowError):
    code = "empty_dataset"
    public_message = "پرس‌وجو داده‌ای برنگرداند؛ سؤال یا فیلترها را اصلاح کنید."


class UnapprovedDataError(WorkflowError):
    code = "unapproved_analysis_attempt"
    public_message = "تحلیل فقط پس از تأیید صریح داده مجاز است."


class InvalidChartSpecError(WorkflowError):
    code = "invalid_chart_specification"
    public_message = "مشخصات نمودار با ستون‌های داده تأییدشده سازگار نیست."


class CheckpointMissingError(WorkflowError):
    code = "workflow_checkpoint_missing"
    public_message = "نقطه توقف گردش‌کار پیدا نشد؛ پرس‌وجو را دوباره اجرا کنید."


class InvalidWorkflowTransition(WorkflowError):
    code = "invalid_workflow_transition"
    public_message = "این گردش‌کار دیگر در انتظار تأیید نیست."
