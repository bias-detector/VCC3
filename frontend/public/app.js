const stressStartBtn = document.getElementById("stressStartBtn");
const stressStopBtn = document.getElementById("stressStopBtn");
const stressOutput = document.getElementById("stressOutput");
const cpuPercent = document.getElementById("cpuPercent");
const scaleEnabled = document.getElementById("scaleEnabled");
const scaleStatus = document.getElementById("scaleStatus");
const scaleTimer = document.getElementById("scaleTimer");
const downTimer = document.getElementById("downTimer");
const vmState = document.getElementById("vmState");
const downArmed = document.getElementById("downArmed");
const remoteUrl = document.getElementById("remoteUrl");
const scaleMessage = document.getElementById("scaleMessage");
const terminalLogs = document.getElementById("terminalLogs");

function formatTs(isoString) {
  if (!isoString) {
    return "--";
  }
  const dt = new Date(isoString);
  if (Number.isNaN(dt.valueOf())) {
    return isoString;
  }
  return dt.toLocaleString();
}

async function startCpuStress() {
  stressStartBtn.disabled = true;
  stressOutput.textContent = "Starting CPU stress...";
  try {
    const response = await fetch("/api/scale/stress/start", {
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
    stressOutput.textContent = `Start failed: ${error.message}`;
  } finally {
    stressStartBtn.disabled = false;
    refreshMetrics();
  }
}

async function stopCpuStress() {
  stressStopBtn.disabled = true;
  stressOutput.textContent = "Stopping CPU stress...";

  try {
    const response = await fetch("/api/scale/stress/stop", {
      method: "POST",
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || "Failed to stop CPU stress");
    }

    const data = await response.json();
    stressOutput.textContent = data.message || "CPU stress stopped.";
  } catch (error) {
    stressOutput.textContent = `Stop failed: ${error.message}`;
  } finally {
    stressStopBtn.disabled = false;
    refreshMetrics();
  }
}

function renderLogs(events) {
  if (!terminalLogs) {
    return;
  }

  if (!Array.isArray(events) || events.length === 0) {
    terminalLogs.innerHTML = "Waiting for logs...";
    return;
  }

  const html = events.map((entry) => {
    const level = String(entry.level || "info").toLowerCase();
    const source = entry.source || "system";
    const message = entry.message || "";
    const ts = entry.timestamp ? new Date(entry.timestamp) : new Date();
    const time = ts.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const levelTag = `[${level.toUpperCase()}]`.padEnd(8);
    const line = `<span class="log-line log-${level}"><span class="log-time">${time}</span> <span class="log-level">${levelTag}</span> <span class="log-source">[${source}]</span> <span class="log-msg">${message}</span></span>`;
    return line;
  }).join("\n");

  terminalLogs.innerHTML = html;
  terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

async function refreshMetrics() {
  try {
    const response = await fetch("/api/scale/metrics");
    if (!response.ok) {
      if (stressOutput) {
        stressOutput.textContent = "Metrics fetch failed. Check backend server status.";
      }
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

    if (downTimer) {
      const below = Number(data.scale_below_threshold_seconds || 0);
      const target = Number(data.scale_down_target_seconds || 0);
      downTimer.textContent = `${below}s / ${target}s`;
    }

    if (vmState) {
      vmState.textContent = data.scale_vm_active ? "ACTIVE" : "NOT ACTIVE";
    }

    if (downArmed) {
      downArmed.textContent = data.scale_down_armed ? "YES" : "NO";
    }

    if (remoteUrl) {
      remoteUrl.textContent = data.scale_remote_url || "--";
    }

    if (scaleMessage) {
      scaleMessage.textContent = data.scale_message || "No scale events yet.";
    }

    const stressActive = Boolean(data.stress_active);
    if (stressStartBtn && stressStopBtn) {
      stressStartBtn.disabled = stressActive;
      stressStopBtn.disabled = !(stressActive || data.scale_vm_active || data.scale_down_armed);
    }

    renderLogs(data.event_log || []);
  } catch (error) {
    if (stressOutput) {
      stressOutput.textContent = `Connection issue: ${error.message}`;
    }
  }
}

if (stressStartBtn) {
  stressStartBtn.addEventListener("click", startCpuStress);
}
if (stressStopBtn) {
  stressStopBtn.addEventListener("click", stopCpuStress);
}

setInterval(refreshMetrics, 1000);
refreshMetrics();
