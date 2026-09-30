// The app's routes only exist once the robot is connected and the moves are
// loaded, a few seconds after this page is shown: retry until then.
const STARTUP_POLL_MS = 2000;
const STARTUP_DEADLINE_MS = 90000;

const INTERVAL_URL = "/settings/idle-move-interval";

// "hiccup-full" -> "Hiccup full"
function labelFor(name) {
    const words = name.replaceAll("-", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}

function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// FastAPI sends a string for the app's own errors, a list for validation ones.
function errorMessage(data) {
    if (typeof data.detail === "string") {
        return data.detail;
    }
    return data.detail.map((error) => error.msg).join("; ");
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
    } catch (e) {
        status.textContent = "Backend unreachable";
    }
}

async function fetchMoveNamesUntilReady() {
    const deadline = Date.now() + STARTUP_DEADLINE_MS;
    for (;;) {
        try {
            const resp = await fetch("/moves");
            if (resp.ok) {
                return await resp.json();
            }
        } catch (e) {
            // Server not reachable yet: retry like any other failure.
        }
        if (Date.now() >= deadline) {
            return null;
        }
        await wait(STARTUP_POLL_MS);
    }
}

// Returns whether the moves loaded, i.e. whether the app's routes exist.
async function loadMoves() {
    const container = document.getElementById("moves");
    container.textContent = "Waking up…";

    const names = await fetchMoveNamesUntilReady();
    if (names === null) {
        container.textContent = "Could not load moves. Is the app running?";
        return false;
    }

    container.textContent = "";
    for (const name of names) {
        const button = document.createElement("button");
        button.textContent = labelFor(name);
        button.addEventListener("click", () => requestMove(name));
        container.appendChild(button);
    }
    return true;
}

async function loadIdleMoveInterval() {
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
    } catch (e) {
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
    } catch (e) {
        status.textContent = "Backend unreachable";
    }
}

async function start() {
    document.getElementById("interval-form").addEventListener("submit", saveIdleMoveInterval);
    if (await loadMoves()) {
        await loadIdleMoveInterval();
    }
}

start();