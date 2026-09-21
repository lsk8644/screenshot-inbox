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
const storedStatuses = window.sessionStorage.getItem("screenshotInboxStatuses");
let knownStatuses = new Map();
try {
  knownStatuses = new Map(storedStatuses ? JSON.parse(storedStatuses) : []);
} catch (_error) {
  knownStatuses = new Map();
}
let statusPollingInitialized = knownStatuses.size > 0;

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
      const becameCompleted = previous && previous !== "completed" && item.status === "completed";
      const arrivedCompleted = statusPollingInitialized && !previous && item.status === "completed";
      if (becameCompleted || arrivedCompleted) showAnalysisToast(item);
      if (statusPollingInitialized && previous !== item.status) timelineChanged = true;
      knownStatuses.set(item.id, item.status);
    });
    window.sessionStorage.setItem(
      "screenshotInboxStatuses",
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
