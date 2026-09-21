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
const knownStatuses = new Map();
let statusPollingInitialized = false;

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

async function pollAnalysisStatuses() {
  try {
    const response = await fetch("/api/screenshots/status", { cache: "no-store" });
    if (!response.ok) return;
    const items = await response.json();
    items.forEach((item) => {
      const previous = knownStatuses.get(item.id);
      const becameCompleted = previous && previous !== "completed" && item.status === "completed";
      const arrivedCompleted = statusPollingInitialized && !previous && item.status === "completed";
      if (becameCompleted || arrivedCompleted) showAnalysisToast(item);
      knownStatuses.set(item.id, item.status);
    });
    statusPollingInitialized = true;
  } catch (_error) {
    // The local server may be restarting; the next poll will recover.
  }
}

if (toastRegion) {
  pollAnalysisStatuses();
  window.setInterval(pollAnalysisStatuses, 2500);
}
