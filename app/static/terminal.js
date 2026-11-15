/* Terminal client for Fly in a Jar (design §10). */

(() => {
  const STORAGE_KEY = "fly_game_state";
  const outputEl = document.getElementById("output");
  const inputEl = document.getElementById("cli-input");
  const spinnerEl = document.getElementById("loading-spinner");
  const screenEl = document.getElementById("screen");
  const statusEl = document.getElementById("status-line");

  let gameState = null;
  let isTyping = false;
  let skipTypewriter = false;
  let printQueue = [];
  let history = [];
  let historyIdx = -1;
  let isSelectingLang = false;

  // Click anywhere to focus input
  document.addEventListener("click", () => {
    if (!inputEl.disabled) inputEl.focus();
  });

  // Skip typewriter on Space or Enter
  document.addEventListener("keydown", (e) => {
    if (isTyping && (e.key === "Enter" || e.key === " ")) {
      skipTypewriter = true;
    }
  });

  function scrollToBottom() {
    outputEl.scrollTop = outputEl.scrollHeight;
  }

  function appendLine(kind, text) {
    const div = document.createElement("div");
    div.className = `line kind-${kind}`;
    div.textContent = text;
    outputEl.appendChild(div);
    scrollToBottom();
    return div;
  }

  async function typeLine(kind, text) {
    const div = document.createElement("div");
    div.className = `line kind-${kind}`;
    outputEl.appendChild(div);

    isTyping = true;
    skipTypewriter = false;

    // Typewriter speed: ~25ms per char (40 chars/sec)
    for (let i = 0; i < text.length; i++) {
      if (skipTypewriter) {
        div.textContent = text;
        break;
      }
      div.textContent += text[i];
      scrollToBottom();
      await new Promise((r) => setTimeout(r, 22));
    }

    isTyping = false;
    skipTypewriter = false;
    scrollToBottom();
  }

  async function processQueue() {
    if (printQueue.length === 0) return;
    const item = printQueue.shift();

    // Fast-print brainlog, system, error lines; typewriter narrative lines
    const isFast = ["brainlog", "system", "error"].includes(item.kind);
    if (isFast) {
      appendLine(item.kind, item.text);
    } else {
      await typeLine(item.kind, item.text);
    }

    processQueue();
  }

  function enqueueLines(lines) {
    printQueue.push(...lines);
    if (!isTyping) {
      processQueue();
    }
  }

  function updateVisualSync(sync) {
    if (sync >= 70) {
      screenEl.classList.add("high-sync");
    } else {
      screenEl.classList.remove("high-sync");
    }
  }

  // Always-visible status bar: scene, sync, turn, inventory.
  function renderHud(hud) {
    if (!hud) return;
    const zh = (gameState && gameState.lang) === "zh";
    const items = hud.items.length ? hud.items.join(zh ? "、" : ", ") : (zh ? "空" : "empty");
    statusEl.textContent = zh
      ? `【${hud.scene}】 同化率 ${hud.sync}% · 回合 ${hud.turn} · 背包：${items}`
      : `[${hud.scene}] sync ${hud.sync}% · turn ${hud.turn} · carrying: ${items}`;
    statusEl.style.display = "";
    localStorage.setItem(STORAGE_KEY + "_hud", JSON.stringify(hud));
  }

  function saveState(state) {
    if (!state) return;
    gameState = state;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    updateVisualSync(state.sync);

    if (state.ended) {
      inputEl.disabled = true;
      inputEl.placeholder = state.lang === "zh" ? "游戏已结束。" : "Session ended.";
    }
  }

  async function apiCall(endpoint, body) {
    inputEl.disabled = true;
    spinnerEl.style.display = "inline";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || err.detail?.message || `HTTP ${res.status}`);
      }

      return await res.json();
    } finally {
      if (!gameState || !gameState.ended) {
        inputEl.disabled = false;
        inputEl.focus();
      }
      spinnerEl.style.display = "none";
    }
  }

  async function startNewGame(lang = "en") {
    appendLine("system", lang === "zh" ? "正在启动神经元仿真核心..." : "Booting neural connectome simulation...");
    try {
      const data = await apiCall("/api/new", { lang });
      saveState(data.state);
      renderHud(data.hud);
      enqueueLines(data.output);
    } catch (e) {
      appendLine("error", `Failed to initialize session: ${e.message}`);
    }
  }

  async function handleTurn(inputText) {
    const text = inputText.trim();
    if (!text) return;

    // Handle restart
    if (["restart", "重新开始", "重开"].includes(text.toLowerCase())) {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(STORAGE_KEY + "_hud");
      statusEl.style.display = "none";
      outputEl.innerHTML = "";
      askLanguage();
      return;
    }

    appendLine("user", `> ${text}`);

    if (isSelectingLang) {
      let chosen = "en";
      if (text === "2" || text.toLowerCase() === "zh" || text.includes("中")) {
        chosen = "zh";
      }
      isSelectingLang = false;
      await startNewGame(chosen);
      return;
    }

    try {
      const data = await apiCall("/api/turn", { state: gameState, input: text });
      saveState(data.state);
      renderHud(data.hud);
      enqueueLines(data.output);
    } catch (e) {
      appendLine("error", `[ERROR] ${e.message}`);
    }
  }

  function askLanguage() {
    isSelectingLang = true;
    appendLine("system", "=======================================================");
    appendLine("system", "      Fly in a Jar · 缸中之蝇 (Kiroween 2026)         ");
    appendLine("system", "=======================================================");
    appendLine("system", "Select language / 请选择语言:");
    appendLine("system", "  [1] English (default)");
    appendLine("system", "  [2] 中文");
    appendLine("system", "Type 1 or 2 and press Enter:");
  }

  // Handle Input Keydown
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) {
      const val = inputEl.value;
      inputEl.value = "";
      if (val.trim()) {
        history.push(val);
        historyIdx = history.length;
      }
      handleTurn(val);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (historyIdx > 0) {
        historyIdx--;
        inputEl.value = history[historyIdx];
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx < history.length - 1) {
        historyIdx++;
        inputEl.value = history[historyIdx];
      } else {
        historyIdx = history.length;
        inputEl.value = "";
      }
    }
  });

  // Initialization
  function init() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        gameState = parsed;
        updateVisualSync(gameState.sync);
        try { renderHud(JSON.parse(localStorage.getItem(STORAGE_KEY + "_hud"))); } catch (e) {}
        appendLine("system", gameState.lang === "zh" ? "已恢复上次会话进度。输入 'restart' 可重开。" : "Restored existing session. Type 'restart' to start over.");
        inputEl.focus();
        return;
      } catch (e) {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    askLanguage();
  }

  init();
})();
