const textInput = document.getElementById("textInput");
const classifyBtn = document.getElementById("classifyBtn");
const resultBox = document.getElementById("result");

const loadBtn = document.getElementById("loadBtn");
const totalRequestsInput = document.getElementById("totalRequests");
const concurrencyInput = document.getElementById("concurrency");
const loadOutput = document.getElementById("loadOutput");
const metricsBox = document.getElementById("metrics");

async function classifyText() {
  const text = textInput.value.trim();
  if (!text) {
    resultBox.className = "result";
    resultBox.textContent = "Please enter text first.";
    return;
  }

  classifyBtn.disabled = true;
  classifyBtn.textContent = "Classifying...";

  try {
    const response = await fetch("/api/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || "Classification failed");
    }

    const data = await response.json();
    const label = data.toxic ? "TOXIC" : "NOT TOXIC";
    const confidence = Number(data.confidence || 0).toFixed(2);

    resultBox.className = `result ${data.toxic ? "toxic" : "clean"}`;
    resultBox.textContent = `Result: ${label}\nConfidence: ${confidence}\nSource: ${data.source}\nReason: ${data.reason}`;
  } catch (error) {
    resultBox.className = "result";
    resultBox.textContent = `Error: ${error.message}`;
  } finally {
    resultBox.classList.remove("hidden");
    classifyBtn.disabled = false;
    classifyBtn.textContent = "Classify";
    refreshMetrics();
  }
}

async function generateLoad() {
  const total_requests = Number(totalRequestsInput.value || 200);
  const concurrency = Number(concurrencyInput.value || 40);

  loadBtn.disabled = true;
  loadBtn.textContent = "Generating...";
  loadOutput.textContent = "Running load test...";

  try {
    const response = await fetch("/api/generate-load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ total_requests, concurrency, toxic_ratio: 0.55 }),
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || "Load generation failed");
    }

    const data = await response.json();
    loadOutput.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    loadOutput.textContent = `Error: ${error.message}`;
  } finally {
    loadBtn.disabled = false;
    loadBtn.textContent = "Generate Load and Trigger Upscaling";
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
    metricsBox.textContent = JSON.stringify(data, null, 2);
  } catch {
    // No-op if metrics call fails.
  }
}

classifyBtn.addEventListener("click", classifyText);
loadBtn.addEventListener("click", generateLoad);
setInterval(refreshMetrics, 3000);
refreshMetrics();
