// Senses tab: what the robot perceives, read from the app every SENSES_POLL_MS.

import { wait } from "./wait.js";

const SENSES_URL = "/senses";
// Facts stay in place until the next one, so polling misses no event: it only
// shows it up to SENSES_POLL_MS late.
const SENSES_POLL_MS = 200;
// After a bump or a sudden noise, its tile stays lit this long.
const RECENT_EVENT_S = 2;

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

function showTile(id, tile) {
    const element = document.getElementById(id);
    element.querySelector(".sense-state").textContent = tile.lines.join("\n");
    element.classList.toggle("active", tile.active); // adds the class if true, removes it if false
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
