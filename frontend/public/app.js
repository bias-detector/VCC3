const startBtn = document.getElementById("startBtn");
const gameContent = document.getElementById("gameContent");
const guessInput = document.getElementById("guessInput");
const guessBtn = document.getElementById("guessBtn");
const gameMessage = document.getElementById("gameMessage");
const resultBox = document.getElementById("result");

const stressStartBtn = document.getElementById("stressStartBtn");
const stressStopBtn = document.getElementById("stressStopBtn");
const stressOutput = document.getElementById("stressOutput");
const cpuPercent = document.getElementById("cpuPercent");
const scaleEnabled = document.getElementById("scaleEnabled");
const scaleStatus = document.getElementById("scaleStatus");
const scaleTimer = document.getElementById("scaleTimer");
const scaleMessage = document.getElementById("scaleMessage");

let gameActive = false;

async function startGame() {
  try {
    const response = await fetch("/api/game/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    if (!response.ok) {
      throw new Error("Failed to start game");
    }

    const data = await response.json();
    gameActive = true;
    gameContent.classList.remove("hidden");
    gameMessage.textContent = data.message;
    resultBox.classList.add("hidden");
    guessInput.value = "";
    guessInput.focus();
    startBtn.textContent = "New Game";
  } catch (error) {
    gameMessage.textContent = `Error: ${error.message}`;
  }
}

async function makeGuess() {
  const guess = guessInput.value.trim();

  if (!guess) {
    resultBox.textContent = "Please enter a number!";
    resultBox.classList.remove("hidden");
    return;
  }

  try {
    const response = await fetch("/api/game/guess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ guess: parseInt(guess) }),
    });

    if (!response.ok) {
      throw new Error("Failed to make guess");
    }

    const data = await response.json();

    if (data.error) {
      resultBox.textContent = data.error;
      resultBox.className = "result error";
    } else {
      resultBox.textContent = data.message;
      resultBox.className = `result ${data.result}`;
      
      if (data.game_over) {
        gameActive = false;
        guessBtn.disabled = true;
        guessInput.disabled = true;
      }
    }

    resultBox.classList.remove("hidden");
    guessInput.value = "";
    guessInput.focus();
  } catch (error) {
    resultBox.textContent = `Error: ${error.message}`;
    resultBox.classList.remove("hidden");
  }
}

async function startCpuStress() {
  stressStartBtn.disabled = true;
  stressOutput.textContent = "Starting CPU stress...";
  try {
    const response = await fetch("/api/stress/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || "Failed to start CPU stress");
    }

    const data = await response.json();
    stressOutput.textContent = data.message || "CPU stress started.";
    stressStopBtn.disabled = false;
  } catch (error) {
    stressOutput.textContent = `Error: ${error.message}`;
  } finally {
    stressStartBtn.disabled = false;
    refreshMetrics();
  }
}

async function stopCpuStress() {
  stressStopBtn.disabled = true;
  stressOutput.textContent = "Stopping CPU stress...";

  try {
    const response = await fetch("/api/stress/stop", {
      method: "POST",
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || "Failed to stop CPU stress");
    }

    const data = await response.json();
    stressOutput.textContent = data.message || "CPU stress stopped.";
  } catch (error) {
    stressOutput.textContent = `Error: ${error.message}`;
  } finally {
    stressStopBtn.disabled = false;
    refreshMetrics();
  }
}

async function refreshMetrics() {
  try {
    const response = await fetch("/api/metrics");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    if (cpuPercent) {
      cpuPercent.textContent = data.cpu_percent.toFixed(1) + "%";
      cpuPercent.className = data.cpu_percent > 75 ? "cpu-value high" : "cpu-value";
    }

    if (scaleEnabled) {
      scaleEnabled.textContent = data.scale_monitor_enabled ? "ON" : "OFF";
    }

    if (scaleStatus) {
      scaleStatus.textContent = data.scale_status || "idle";
    }

    if (scaleTimer) {
      const above = Number(data.scale_above_threshold_seconds || 0);
      const target = Number(data.scale_target_seconds || 0);
      scaleTimer.textContent = `${above}s / ${target}s`;
    }

    if (scaleMessage) {
      const remoteUrl = data.scale_remote_url ? `\nRemote: ${data.scale_remote_url}` : "";
      scaleMessage.textContent = (data.scale_message || "No scale events yet.") + remoteUrl;
    }

    const stressActive = Boolean(data.stress_active);
    if (stressStartBtn && stressStopBtn) {
      stressStartBtn.disabled = stressActive;
      stressStopBtn.disabled = !stressActive;
    }
  } catch {
    // No-op if metrics call fails
  }
}

startBtn.addEventListener("click", startGame);
guessBtn.addEventListener("click", makeGuess);
guessInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    makeGuess();
  }
});

if (stressStartBtn) {
  stressStartBtn.addEventListener("click", startCpuStress);
}
if (stressStopBtn) {
  stressStopBtn.addEventListener("click", stopCpuStress);
}

setInterval(refreshMetrics, 1000);
refreshMetrics();
