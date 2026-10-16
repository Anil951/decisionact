"use strict";

document.querySelectorAll(".codehilite").forEach((block) => {
  const code = block.querySelector("pre");
  if (!code || !navigator.clipboard || !window.isSecureContext) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy-code";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy code example");
  button.setAttribute("aria-live", "polite");
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = "Copied";
    } catch {
      button.textContent = "Select to copy";
    }
    window.setTimeout(() => { button.textContent = "Copy"; }, 1800);
  });
  block.appendChild(button);
});
