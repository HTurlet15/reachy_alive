// Idle moves tab: play a move on demand, and set the time between idle moves.

import { wait } from "./wait.js";

// The app's routes only exist once the robot is connected and the moves are
// loaded. Until then, the server answers 404. That takes a few seconds, or
// minutes on a first start after an update: the page waits as long as it takes.
const STARTUP_POLL_MS = 2000;
// Past this, the page says the start is slow, so nobody thinks it is stuck.
const SLOW_START_MS = 15000;
const WAKING_UP = "Waking up…";
const STILL_STARTING = "Still starting… The first start after an update can take a few minutes.";
// The app serves this page: when nobody answers, the app itself has stopped.
const APP_STOPPED = "The app has stopped. Start it again from Reachy Mini Control.";

const INTERVAL_URL = "/settings/idle-move-interval";

// Returns once the moves are loaded, i.e. once the app's routes exist.
export async function loadMoves() {
    const container = document.getElementById("moves");
    container.textContent = WAKING_UP;

    const names = await fetchMoveNamesWhenReady(container);

    container.textContent = "";
    for (const name of names) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = labelFor(name);
        button.addEventListener("click", () => requestMove(name));
        container.appendChild(button);
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

// Asks until the app answers, and says meanwhile what its answers mean.
async function fetchMoveNamesWhenReady(container) {
    const slowAfter = Date.now() + SLOW_START_MS;
    for (;;) {
        try {
            const resp = await fetch("/moves");
            if (resp.ok) {
                return await resp.json();
            }
            container.textContent = Date.now() < slowAfter ? WAKING_UP : STILL_STARTING;
        } catch {
            container.textContent = APP_STOPPED;
        }
        await wait(STARTUP_POLL_MS);
    }
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
