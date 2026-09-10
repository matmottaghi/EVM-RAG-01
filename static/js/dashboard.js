(() => {
    "use strict";

    const state = {
        threadId: null,
        runId: null,
        workflowStatus: "idle",
        dataset: null,
        page: 1,
        chart: null,
    };
    const $ = (selector) => document.querySelector(selector);
    const els = {
        form: $("#chat-form"), input: $("#message-input"), send: $("#send-button"),
        messages: $("#messages"), status: $("#workflow-status"),
        tableWrap: $("#table-wrap"), table: $("#data-table"),
        dataPlaceholder: $("#data-placeholder"), rowCount: $("#row-count"),
        approve: $("#approve-button"), reject: $("#reject-button"),
        help: $("#confirmation-help"), pagination: $("#pagination"),
        prev: $("#prev-page"), next: $("#next-page"), pageInfo: $("#page-info"),
        chart: $("#chart-container"), toast: $("#toast"), newThread: $("#new-thread"),
    };

    const csrfToken = () => document.querySelector("[name=csrfmiddlewaretoken]").value;

    async function api(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
                ...(options.headers || {}),
            },
        });
        let payload = {};
        try { payload = await response.json(); } catch (_) { /* empty response */ }
        if (!response.ok) {
            const error = new Error(payload.error || "ارتباط با سرور ناموفق بود.");
            error.payload = payload;
            throw error;
        }
        return payload;
    }

    function setStatus(text, kind = "idle") {
        state.workflowStatus = kind;
        els.status.dataset.status = kind;
        els.status.lastElementChild.textContent = text;
    }

    function setBusy(busy) {
        const awaitingDecision = !els.approve.disabled;
        els.send.disabled = busy || awaitingDecision;
        els.input.disabled = busy || awaitingDecision;
        if (busy) setStatus("در حال پردازش", "busy");
    }

    function showError(message) {
        els.toast.textContent = message;
        els.toast.hidden = false;
        window.setTimeout(() => { els.toast.hidden = true; }, 5500);
        setStatus("خطا", "idle");
    }

    function appendMessage(role, text, label) {
        const article = document.createElement("article");
        article.className = `message ${role}-message`;
        if (role !== "system") {
            const avatar = document.createElement("span");
            avatar.className = "avatar";
            avatar.textContent = role === "user" ? "ش" : "E";
            article.appendChild(avatar);
        }
        const body = document.createElement("div");
        const strong = document.createElement("strong");
        strong.textContent = label || (role === "user" ? "شما" : "EVMS Intelligence");
        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        body.append(strong, paragraph);
        article.appendChild(body);
        els.messages.appendChild(article);
        els.messages.scrollTop = els.messages.scrollHeight;
    }
    function displayValue(value) {
        if (value === null || value === undefined) return "—";
        return typeof value === "object" ? JSON.stringify(value) : String(value);
    }

    function renderDataset(dataset) {
        state.dataset = dataset;
        state.page = dataset.page;
        const head = els.table.querySelector("thead");
        const body = els.table.querySelector("tbody");
        head.replaceChildren();
        body.replaceChildren();
        const headerRow = document.createElement("tr");
        dataset.columns.forEach((column) => {
            const th = document.createElement("th");
            th.scope = "col";
            th.textContent = column;
            headerRow.appendChild(th);
        });
        head.appendChild(headerRow);
        dataset.rows.forEach((row) => {
            const tr = document.createElement("tr");
            dataset.columns.forEach((column) => {
                const td = document.createElement("td");
                td.textContent = displayValue(row[column]);
                td.title = td.textContent;
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
        els.dataPlaceholder.hidden = true;
        els.tableWrap.hidden = false;
        els.rowCount.textContent = `${dataset.row_count.toLocaleString("fa-IR")} ردیف`;
        els.pagination.hidden = dataset.total_pages <= 1;
        els.pageInfo.textContent = `صفحه ${dataset.page.toLocaleString("fa-IR")} از ${dataset.total_pages.toLocaleString("fa-IR")}`;
        els.prev.disabled = dataset.page <= 1;
        els.next.disabled = dataset.page >= dataset.total_pages;
    }

    function setConfirmation(enabled) {
        els.approve.disabled = !enabled;
        els.reject.disabled = !enabled;
        els.input.disabled = enabled;
        els.send.disabled = enabled;
        els.help.textContent = enabled
            ? "آیا دادهٔ بازیابی‌شده برای تحلیل صحیح است؟"
            : "تصمیم این مجموعه‌داده ثبت شده است.";
    }

    async function loadDatasetPage(page) {
        if (!state.runId) return;
        try {
            const data = await api(`/api/workflow/${state.runId}/dataset/?page=${page}&page_size=100`);
            renderDataset(data);
        } catch (error) { showError(error.message); }
    }

    function renderChart(payload) {
        if (!payload || !window.Plotly) {
            showError("کتابخانه نمودار بارگذاری نشده است.");
            return;
        }
        els.chart.replaceChildren();
        window.Plotly.newPlot(
            els.chart,
            payload.data || [],
            payload.layout || {},
            {responsive: true, displaylogo: false, scrollZoom: true},
        );
        state.chart = payload;
    }

    function resetChart() {
        state.chart = null;
        els.chart.innerHTML = '<div id="chart-placeholder" class="placeholder"><span class="placeholder-icon">⌁</span><strong>نمودار پس از تأیید داده ساخته می‌شود</strong><small>بزرگ‌نمایی، جابه‌جایی و جزئیات تعاملی فعال خواهد بود.</small></div>';
    }
    els.form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = els.input.value.trim();
        if (!message) return;
        appendMessage("user", message);
        els.input.value = "";
        setConfirmation(false);
        resetChart();
        setBusy(true);
        try {
            const result = await api("/api/chat/query/", {
                method: "POST",
                body: JSON.stringify({thread_id: state.threadId, message}),
            });
            state.threadId = result.thread_id;
            state.runId = result.run_id;
            renderDataset(result.dataset);
            setConfirmation(true);
            appendMessage("system", "داده آماده است. لطفاً جدول را بررسی و سپس تأیید یا رد کنید.", "توقف برای تأیید انسانی");
            setStatus("در انتظار تأیید", "waiting");
        } catch (error) {
            if (error.payload) {
                state.threadId = error.payload.thread_id || state.threadId;
                state.runId = error.payload.run_id || state.runId;
            }
            appendMessage("system", error.message, "خطا");
            showError(error.message);
        } finally {
            setBusy(false);
            if (state.runId && !els.approve.disabled) setStatus("در انتظار تأیید", "waiting");
            els.input.focus();
        }
    });

    els.approve.addEventListener("click", async () => {
        if (!state.runId) return;
        setConfirmation(false);
        setBusy(true);
        setStatus("در حال تحلیل دادهٔ تأییدشده", "busy");
        try {
            const result = await api(`/api/workflow/${state.runId}/approve/`, {
                method: "POST", body: "{}",
            });
            appendMessage("assistant", result.analysis || "تحلیل تکمیل شد.");
            renderChart(result.chart);
            setStatus("تکمیل شد", "completed");
            els.help.textContent = "داده تأیید و تحلیل شد.";
        } catch (error) {
            appendMessage("system", error.message, "خطا");
            showError(error.message);
        } finally {
            setBusy(false);
        }
    });

    els.reject.addEventListener("click", async () => {
        if (!state.runId) return;
        const reason = window.prompt("اشکال داده یا فیلتر موردنظر را توضیح دهید (اختیاری):", "") ?? "";
        setConfirmation(false);
        try {
            await api(`/api/workflow/${state.runId}/reject/`, {
                method: "POST", body: JSON.stringify({reason}),
            });
            appendMessage("system", "داده رد شد. اصلاح موردنظر را در پیام بعدی بنویسید.", "داده تحلیل نشد");
            setStatus("رد شد", "idle");
            els.help.textContent = "این داده رد شد و به مدل تحلیل ارسال نشد.";
            els.input.focus();
        } catch (error) { showError(error.message); }
    });
    els.prev.addEventListener("click", () => loadDatasetPage(state.page - 1));
    els.next.addEventListener("click", () => loadDatasetPage(state.page + 1));
    els.input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            els.form.requestSubmit();
        }
    });
    els.newThread.addEventListener("click", () => {
        state.threadId = null;
        state.runId = null;
        state.dataset = null;
        state.chart = null;
        els.messages.querySelectorAll(".message").forEach((item, index) => {
            if (index > 0) item.remove();
        });
        els.tableWrap.hidden = true;
        els.pagination.hidden = true;
        els.dataPlaceholder.hidden = false;
        els.rowCount.textContent = "۰ ردیف";
        resetChart();
        setConfirmation(false);
        els.help.textContent = "ابتدا یک پرسش ارسال کنید.";
        setStatus("آماده", "idle");
        els.input.focus();
    });
})();
