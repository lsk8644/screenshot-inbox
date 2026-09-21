const statusNode = document.querySelector(".processing-box");
if (statusNode) {
  window.setTimeout(() => window.location.reload(), 2500);
}

document.querySelectorAll(".code-tabs").forEach((tabs) => {
  const section = tabs.closest(".analysis-section");
  if (!section) return;
  tabs.querySelectorAll("[data-code-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const language = button.dataset.codeTab;
      tabs.querySelectorAll("[data-code-tab]").forEach((tab) => {
        tab.classList.toggle("active", tab === button);
      });
      section.querySelectorAll("[data-code-pane]").forEach((pane) => {
        pane.hidden = pane.dataset.codePane !== language;
      });
    });
  });
});

document.querySelectorAll(".chat-form").forEach((form) => {
  const question = form.querySelector("textarea[name='question']");
  if (!question) return;
  question.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    if (question.value.trim()) form.requestSubmit();
  });
});

const toastRegion = document.querySelector("#toast-region");
const notificationToggle = document.querySelector("#notification-toggle");
const storedStatuses = window.sessionStorage.getItem("screenshotInboxStatusesV2");
let knownStatuses = new Map();
try {
  knownStatuses = new Map(storedStatuses ? JSON.parse(storedStatuses) : []);
} catch (_error) {
  knownStatuses = new Map();
}
let statusPollingInitialized = knownStatuses.size > 0;

function updateNotificationToggle() {
  if (!notificationToggle || !("Notification" in window)) return;
  if (Notification.permission === "default") {
    notificationToggle.hidden = false;
    notificationToggle.disabled = false;
    notificationToggle.textContent = "알림 켜기";
  } else if (Notification.permission === "denied") {
    notificationToggle.hidden = false;
    notificationToggle.disabled = true;
    notificationToggle.textContent = "알림 차단됨";
  } else {
    notificationToggle.hidden = true;
  }
}

if (notificationToggle && "Notification" in window) {
  updateNotificationToggle();
  notificationToggle.addEventListener("click", async () => {
    await Notification.requestPermission();
    updateNotificationToggle();
  });
}

function showSystemNotification(item) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  const notification = new Notification("Screenshot Inbox · 분석 완료", {
    body: item.title || "새 스크린샷 분석이 완료됐습니다.",
    icon: new URL("/static/favicon.svg", window.location.origin).href,
    tag: `screenshot-analysis-${item.id}-${item.analyzed_at || "completed"}`,
  });
  notification.addEventListener("click", () => {
    window.focus();
    window.location.href = `/screenshots/${item.id}`;
    notification.close();
  });
}

function showAnalysisToast(item) {
  if (!toastRegion) return;
  const toast = document.createElement("a");
  toast.className = "analysis-toast";
  toast.href = `/screenshots/${item.id}`;
  const label = document.createElement("span");
  label.textContent = "분석 완료";
  const title = document.createElement("strong");
  title.textContent = item.title || "새 스크린샷";
  toast.append(label, title);
  toastRegion.append(toast);
  showSystemNotification(item);
  window.setTimeout(() => toast.classList.add("visible"), 20);
  window.setTimeout(() => {
    toast.classList.remove("visible");
    window.setTimeout(() => toast.remove(), 220);
  }, 6000);
}

async function refreshTimeline() {
  const timeline = document.querySelector(".timeline");
  if (!timeline) return;
  try {
    const response = await fetch(window.location.href, { cache: "no-store" });
    if (!response.ok) return;
    const documentText = await response.text();
    const updatedDocument = new DOMParser().parseFromString(documentText, "text/html");
    const updatedTimeline = updatedDocument.querySelector(".timeline");
    if (updatedTimeline) timeline.replaceChildren(...updatedTimeline.childNodes);
  } catch (_error) {
    // The next status poll will retry.
  }
}

async function pollAnalysisStatuses() {
  try {
    const response = await fetch("/api/screenshots/status", { cache: "no-store" });
    if (!response.ok) return;
    const items = await response.json();
    let timelineChanged = false;
    items.forEach((item) => {
      const previous = knownStatuses.get(item.id);
      const previousStatus = typeof previous === "string" ? previous : previous?.status;
      const previousAnalysis = typeof previous === "object" ? previous?.analyzed_at : null;
      const becameCompleted = previous && item.status === "completed"
        && (previousStatus !== "completed" || previousAnalysis !== item.analyzed_at);
      const arrivedCompleted = statusPollingInitialized && !previous && item.status === "completed";
      if (becameCompleted || arrivedCompleted) showAnalysisToast(item);
      if (
        statusPollingInitialized
        && (!previous || previousStatus !== item.status || previousAnalysis !== item.analyzed_at)
      ) timelineChanged = true;
      knownStatuses.set(item.id, { status: item.status, analyzed_at: item.analyzed_at });
    });
    window.sessionStorage.setItem(
      "screenshotInboxStatusesV2",
      JSON.stringify(Array.from(knownStatuses.entries()).slice(-100)),
    );
    if (timelineChanged) refreshTimeline();
    statusPollingInitialized = true;
  } catch (_error) {
    // The local server may be restarting; the next poll will recover.
  }
}

if (toastRegion) {
  pollAnalysisStatuses();
  window.setInterval(pollAnalysisStatuses, 1500);
}
