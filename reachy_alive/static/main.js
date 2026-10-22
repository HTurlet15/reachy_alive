// The app's routes only exist once the robot is connected and the moves are
// loaded, a few seconds after this page is shown: retry until then.
const STARTUP_POLL_MS = 2000;
const STARTUP_DEADLINE_MS = 90000;

const INTERVAL_URL = "/settings/idle-move-interval";

const SENSES_URL = "/senses";
// Facts stay in place until the next one, so polling misses no event: it only
// shows it up to SENSES_POLL_MS late.
const SENSES_POLL_MS = 200;
// After a bump or a sudden noise, its tile stays lit this long.
const RECENT_EVENT_S = 2;

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

// The browser checks each field on its own; this adds the rule between them.
function checkIntervalOrder() {
    const minInput = document.getElementById("interval-min");
    const maxInput = document.getElementById("interval-max");
    const maxBelowMin = Number(maxInput.value) < Number(minInput.value);
    maxInput.setCustomValidity(maxBelowMin ? "Must be at least the first value." : "");
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

// 3.24 -> "3.2 s", 150 -> "3 min"
function duration(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(1)} s`;
    }
    return `${Math.round(seconds / 60)} min`;
}

// Each *Tile function turns one sense's facts into what its tile shows:
// its lines of text, and whether it is lit.

function inertialTile(inertial) {
    const ago = inertial.last_bump_s_ago;
    if (ago === null) {
        return { lines: ["No bump yet"], active: false };
    }
    const recent = ago < RECENT_EVENT_S;
    return { lines: [recent ? "Bump" : "Last bump", `${duration(ago)} ago`], active: recent };
}

function antennaLine(side, pushedFor) {
    if (pushedFor === null) {
        return `${side}: not pushed`;
    }
    return `${side}: pushed ${duration(pushedFor)}`;
}

function touchTile(touch) {
    return {
        lines: [
            antennaLine("Right", touch.right_pushed_for_s),
            antennaLine("Left", touch.left_pushed_for_s),
        ],
        active: touch.right_pushed_for_s !== null || touch.left_pushed_for_s !== null,
    };
}

function hearingTile(hearing) {
    const ago = hearing.last_sudden_noise_s_ago;
    if (ago === null) {
        return { lines: ["No sudden noise yet"], active: false };
    }
    const recent = ago < RECENT_EVENT_S;
    const label = recent ? "Sudden noise" : "Last noise";
    return { lines: [label, `${duration(ago)} ago`], active: recent };
}

function visionTile(vision) {
    if (vision.face_seen_for_s !== null) {
        const lines = [`Face seen · ${duration(vision.face_seen_for_s)}`];
        if (vision.face_distance_m !== null) {
            lines.push(`${vision.face_distance_m.toFixed(1)} m away`);
        }
        return { lines, active: true };
    }
    if (vision.last_face_lost_s_ago !== null) {
        return {
            lines: ["No face", `Left ${duration(vision.last_face_lost_s_ago)} ago`],
            active: false,
        };
    }
    return { lines: ["No face yet"], active: false };
}

function showTile(id, tile) {
    const element = document.getElementById(id);
    element.querySelector(".sense-state").textContent = tile.lines.join("\n");
    element.classList.toggle("active", tile.active); // adds the class if true, removes it if false
}

// Shows the panel of the clicked tab and hides the others.
function showTab(selected) {
    for (const tab of document.querySelectorAll('[role="tab"]')) {
        const isSelected = tab === selected;
        tab.setAttribute("aria-selected", isSelected);
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !isSelected;
    }
}

// Never returns: reads the senses, waits, and again. Waiting after each
// answer, rather than on a fixed timer, never piles requests up.
async function watchSenses() {
    const status = document.getElementById("senses-status");
    const panel = document.getElementById("panel-senses");
    for (;;) {
        // While the tab is hidden, nobody looks: spare the robot the requests.
        if (panel.hidden) {
            await wait(SENSES_POLL_MS);
            continue;
        }
        try {
            const resp = await fetch(SENSES_URL);
            if (resp.ok) {
                const senses = await resp.json();
                showTile("sense-inertial", inertialTile(senses.inertial));
                showTile("sense-touch", touchTile(senses.touch));
                showTile("sense-hearing", hearingTile(senses.hearing));
                showTile("sense-vision", visionTile(senses.vision));
                status.textContent = "";
            } else {
                status.textContent = `Could not read the senses (${resp.status})`;
            }
        } catch (e) {
            status.textContent = "Backend unreachable";
        }
        await wait(SENSES_POLL_MS);
    }
}

async function start() {
    for (const tab of document.querySelectorAll('[role="tab"]')) {
        tab.addEventListener("click", () => showTab(tab));
    }
    document.getElementById("interval-form").addEventListener("submit", saveIdleMoveInterval);
    document.getElementById("interval-min").addEventListener("input", checkIntervalOrder);
    document.getElementById("interval-max").addEventListener("input", checkIntervalOrder);
    if (await loadMoves()) {
        await loadIdleMoveInterval();
        watchSenses(); // no await: it runs for as long as the page is open
    }
}

start();