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

const inboxMenuButton = document.querySelector("#inbox-menu-button");
const inboxMenuPopover = document.querySelector("#inbox-menu-popover");
const enterSelectionMode = document.querySelector("#enter-selection-mode");
const bulkDeleteForm = document.querySelector("#bulk-delete-form");
const cancelSelectionMode = document.querySelector("#cancel-selection-mode");
const selectAllScreenshots = document.querySelector("#select-all-screenshots");
const deleteSelected = document.querySelector("#delete-selected");
const selectionCount = document.querySelector("#selection-count");

function selectedScreenshotBoxes() {
  return Array.from(document.querySelectorAll(".select-item"));
}

function updateBulkSelection() {
  const boxes = selectedScreenshotBoxes();
  const selectedCount = boxes.filter((box) => box.checked).length;
  if (deleteSelected) {
    deleteSelected.disabled = selectedCount === 0;
  }
  if (selectionCount) selectionCount.textContent = `${selectedCount}개 선택`;
  if (selectAllScreenshots) {
    selectAllScreenshots.checked = boxes.length > 0 && selectedCount === boxes.length;
    selectAllScreenshots.indeterminate = selectedCount > 0 && selectedCount < boxes.length;
  }
}

function closeInboxMenu() {
  if (inboxMenuPopover) inboxMenuPopover.hidden = true;
  if (inboxMenuButton) inboxMenuButton.setAttribute("aria-expanded", "false");
}

function exitSelectionMode() {
  document.body.classList.remove("selection-mode");
  if (bulkDeleteForm) bulkDeleteForm.hidden = true;
  selectedScreenshotBoxes().forEach((box) => {
    box.checked = false;
  });
  updateBulkSelection();
}

if (inboxMenuButton && inboxMenuPopover) {
  inboxMenuButton.addEventListener("click", () => {
    const willOpen = inboxMenuPopover.hidden;
    inboxMenuPopover.hidden = !willOpen;
    inboxMenuButton.setAttribute("aria-expanded", String(willOpen));
  });
}

if (enterSelectionMode && bulkDeleteForm) {
  enterSelectionMode.addEventListener("click", () => {
    closeInboxMenu();
    document.body.classList.add("selection-mode");
    bulkDeleteForm.hidden = false;
    updateBulkSelection();
  });
}

if (cancelSelectionMode) cancelSelectionMode.addEventListener("click", exitSelectionMode);

if (selectAllScreenshots) {
  selectAllScreenshots.addEventListener("change", () => {
    selectedScreenshotBoxes().forEach((box) => {
      box.checked = selectAllScreenshots.checked;
    });
    updateBulkSelection();
  });
}

document.addEventListener("change", (event) => {
  if (event.target.matches?.(".select-item")) updateBulkSelection();
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.closest(".inbox-menu")) closeInboxMenu();
  if (!document.body.classList.contains("selection-mode")) return;
  const row = target.closest(".timeline-item");
  if (!row || target.matches(".select-item") || target.closest("button, input, label")) return;
  event.preventDefault();
  const box = row.querySelector(".select-item");
  if (box) {
    box.checked = !box.checked;
    updateBulkSelection();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (document.body.classList.contains("selection-mode")) {
    exitSelectionMode();
  } else {
    closeInboxMenu();
  }
});

const toastRegion = document.querySelector("#toast-region");
const storedStatuses = window.sessionStorage.getItem("screenshotInboxStatusesV2");
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
    if (updatedTimeline) {
      timeline.replaceChildren(...updatedTimeline.childNodes);
      updateBulkSelection();
    }
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
