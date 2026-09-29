// The app's routes only exist once the robot is connected and the moves are
// loaded, a few seconds after this page is shown: retry until then.
const STARTUP_POLL_MS = 2000;
const STARTUP_DEADLINE_MS = 90000;

// "hiccup-full" -> "Hiccup full"
function labelFor(name) {
    const words = name.replaceAll("-", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}

function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
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

async function loadMoves() {
    const container = document.getElementById("moves");
    container.textContent = "Waking up…";

    const names = await fetchMoveNamesUntilReady();
    if (names === null) {
        container.textContent = "Could not load moves. Is the app running?";
        return;
    }

    container.textContent = "";
    for (const name of names) {
        const button = document.createElement("button");
        button.textContent = labelFor(name);
        button.addEventListener("click", () => requestMove(name));
        container.appendChild(button);
    }
}

loadMoves();