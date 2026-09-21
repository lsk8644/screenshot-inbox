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
