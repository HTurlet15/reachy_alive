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
    } catch (e) {
        status.textContent = "Backend unreachable";
    }
}

async function loadMoves() {
    const container = document.getElementById("moves");
    try {
        const resp = await fetch("/moves");
        if (!resp.ok) {
            container.textContent = `Could not load moves (${resp.status})`;
            return;
        }
        const names = await resp.json();
        for (const name of names) {
            const button = document.createElement("button");
            button.textContent = labelFor(name);
            button.addEventListener("click", () => requestMove(name));
            container.appendChild(button);
        }
    } catch (e) {
        container.textContent = "Backend unreachable";
    }
}

loadMoves();