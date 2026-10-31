// Idle moves tab: play a move on demand, and set the time between idle moves.

const INTERVAL_URL = "/settings/idle-move-interval";

export async function loadMoves() {
    const container = document.getElementById("moves");
    try {
        const resp = await fetch("/moves");
        if (!resp.ok) {
            container.textContent = `Could not load the moves (${resp.status})`;
            return;
        }
        for (const name of await resp.json()) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = labelFor(name);
            button.addEventListener("click", () => requestMove(name));
            container.appendChild(button);
        }
    } catch {
        container.textContent = "Backend unreachable";
    }
}

// Fills the form with the app's interval, then lets it be changed. Until then,
// its fields and button stay greyed out, like the senses' boxes: nothing can
// be saved before the app has answered.
export async function loadIdleMoveInterval() {
    const status = document.getElementById("interval-status");
    try {
        const resp = await fetch(INTERVAL_URL);
        if (!resp.ok) {
            status.textContent = `Could not load the interval (${resp.status})`;
            return;
        }
        const interval = await resp.json();
        document.getElementById("interval-min").value = interval.min_s;
        document.getElementById("interval-max").value = interval.max_s;
        for (const field of document.getElementById("interval-form").elements) {
            field.disabled = false;
        }
    } catch {
        status.textContent = "Backend unreachable";
    }
}

export function setUpIntervalForm() {
    document.getElementById("interval-form").addEventListener("submit", saveIdleMoveInterval);
    document.getElementById("interval-min").addEventListener("input", checkIntervalOrder);
    document.getElementById("interval-max").addEventListener("input", checkIntervalOrder);
}

// "hiccup-full" -> "Hiccup full"
function labelFor(name) {
    const words = name.replaceAll("-", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}

async function requestMove(name) {
    const status = document.getElementById("move-status");
    try {
        const resp = await fetch(`/moves/${encodeURIComponent(name)}/play`, {
            method: "POST",
        });
        if (!resp.ok) {
            status.textContent = `Could not request ${labelFor(name)} (${resp.status})`;
            return;
        }
        status.textContent = `${labelFor(name)} requested`;
    } catch {
        status.textContent = "Backend unreachable";
    }
}

async function saveIdleMoveInterval(event) {
    event.preventDefault(); // stay on the page instead of reloading it
    const status = document.getElementById("interval-status");
    const interval = {
        min_s: Number(document.getElementById("interval-min").value),
        max_s: Number(document.getElementById("interval-max").value),
    };
    try {
        const resp = await fetch(INTERVAL_URL, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(interval),
        });
        if (!resp.ok) {
            status.textContent = `Not saved: ${errorMessage(await resp.json())}`;
            return;
        }
        status.textContent = "Saved. Applies after the next idle move.";
    } catch {
        status.textContent = "Backend unreachable";
    }
}

// The browser checks each field on its own; this adds the rule between them.
function checkIntervalOrder() {
    const minInput = document.getElementById("interval-min");
    const maxInput = document.getElementById("interval-max");
    const maxBelowMin = Number(maxInput.value) < Number(minInput.value);
    maxInput.setCustomValidity(maxBelowMin ? "Must be at least the first value." : "");
}

// FastAPI sends a string for the app's own errors, a list for validation ones.
function errorMessage(data) {
    if (typeof data.detail === "string") {
        return data.detail;
    }
    return data.detail.map((error) => error.msg).join("; ");
}
