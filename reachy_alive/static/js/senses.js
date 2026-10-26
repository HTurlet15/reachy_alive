// Senses tab: what the robot perceives, read from the app every SENSES_POLL_MS,
// and a box per sense to switch it off.

import { wait } from "./wait.js";

const SENSES_URL = "/senses";
const SWITCHES_URL = "/settings/senses";
// Facts stay in place until the next one, so polling misses no event: it only
// shows it up to SENSES_POLL_MS late.
const SENSES_POLL_MS = 200;
// After a bump or a sudden noise, its tile stays lit this long.
const RECENT_EVENT_S = 2;

// Ticks each sense's box as the app has it, then lets it switch the sense.
// Until then, boxes stay ticked and greyed out: every sense runs at start.
export async function setUpSenseSwitches() {
    const status = document.getElementById("switch-status");
    try {
        const resp = await fetch(SWITCHES_URL);
        if (!resp.ok) {
            status.textContent = `Could not read which senses run (${resp.status})`;
            return;
        }
        const enabled = await resp.json();
        for (const box of document.querySelectorAll(".sense-switch")) {
            box.checked = enabled[box.dataset.sense];
            box.disabled = false;
            box.addEventListener("change", () => switchSense(box));
        }
    } catch {
        status.textContent = "Backend unreachable";
    }
}

// Never returns: reads the senses, waits, and again. Waiting after each
// answer, rather than on a fixed timer, never piles requests up.
export async function watchSenses() {
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
        } catch {
            status.textContent = "Backend unreachable";
        }
        await wait(SENSES_POLL_MS);
    }
}

// The box is ticked the moment it is clicked: the tile dims at once, and
// lights up again if the app refuses.
async function switchSense(box) {
    const status = document.getElementById("switch-status");
    const name = box.dataset.sense;
    box.disabled = true; // one request at a time
    try {
        const resp = await fetch(`${SWITCHES_URL}/${encodeURIComponent(name)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: box.checked }),
        });
        if (resp.ok) {
            status.textContent = "";
        } else {
            box.checked = !box.checked;
            status.textContent = `Could not switch ${name} (${resp.status}): nothing changed`;
        }
    } catch {
        box.checked = !box.checked;
        status.textContent = "Backend unreachable: nothing changed";
    } finally {
        box.disabled = false;
    }
}

function showTile(id, tile) {
    const element = document.getElementById(id);
    // Facts of a sense switched off may be old: past events stay recorded.
    const off = !element.querySelector(".sense-switch").checked;
    element.querySelector(".sense-state").textContent = off
        ? "Switched off"
        : tile.lines.join("\n");
    element.classList.toggle("off", off);
    element.classList.toggle("active", tile.active && !off); // adds the class if true, removes it if false
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

function touchTile(touch) {
    return {
        lines: [
            antennaLine("Right", touch.right_pushed_for_s),
            antennaLine("Left", touch.left_pushed_for_s),
        ],
        active: touch.right_pushed_for_s !== null || touch.left_pushed_for_s !== null,
    };
}

function antennaLine(side, pushedFor) {
    if (pushedFor === null) {
        return `${side}: not pushed`;
    }
    return `${side}: pushed ${duration(pushedFor)}`;
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

// 3.24 -> "3.2 s", 150 -> "3 min"
function duration(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(1)} s`;
    }
    return `${Math.round(seconds / 60)} min`;
}
