let antennasEnabled = true;

async function updateAntennasState(enabled) {
    try {
        const resp = await fetch("/antennas", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled }),
        });
        const data = await resp.json();
        antennasEnabled = data.antennas_enabled;
        updateUI();
    } catch (e) {
        document.getElementById("status").textContent = "Backend error";
    }
}

function updateUI() {
    const checkbox = document.getElementById("antenna-checkbox");
    const status = document.getElementById("status");

    checkbox.checked = antennasEnabled;

    if (antennasEnabled) {
        status.textContent = "Antennas status: running";
    } else {
        status.textContent = "Antennas status: stopped";
    }
}

// "hiccup-full" -> "Hiccup full"
function labelFor(name) {
    const words = name.replaceAll("-", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}

async function loadGestures() {
    const container = document.getElementById("gestures");
    try {
        const resp = await fetch("/gestures");
        if (!resp.ok) {
            container.textContent = `Could not load gestures (${resp.status})`;
            return;
        }
        const names = await resp.json();
        for (const name of names) {
            const button = document.createElement("button");
            button.textContent = labelFor(name);
            container.appendChild(button);
        }
    } catch (e) {
        container.textContent = "Backend unreachable";
    }
}

document.getElementById("antenna-checkbox").addEventListener("change", (e) => {
    updateAntennasState(e.target.checked);
});

updateUI();
loadGestures();