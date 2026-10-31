// Starts the app's page: waits for the app, then loads each tab.

import { loadIdleMoveInterval, loadMoves, setUpIntervalForm } from "./idle.js";
import { setUpSenseSwitches, watchSenses } from "./senses.js";
import { setUpTabs } from "./tabs.js";
import { wait } from "./wait.js";

// The page is shown before the app's routes exist: they only do once the robot
// is connected and the moves are loaded. Until then, the server answers 404.
// That takes a few seconds, or minutes on a first start after an update.
const STARTUP_POLL_MS = 2000;
// Past this, the page says the start is slow, so nobody thinks it is stuck.
const SLOW_START_MS = 15000;
const WAKING_UP = "Waking up…";
const STILL_STARTING = "Still starting… The first start after an update can take a few minutes.";
// The app serves this page: when nobody answers, the app itself has stopped.
const APP_STOPPED = "The app has stopped. Start it again from Reachy Mini Control.";

async function start() {
    setUpTabs();
    setUpIntervalForm();
    await waitForApp(); // however long it takes
    await loadMoves();
    await loadIdleMoveInterval();
    await setUpSenseSwitches();
    watchSenses(); // no await: it runs for as long as the page is open
}

// Asks until the app answers, and says meanwhile, above every tab, what its
// answers mean. The moves' route is asked: their routes are the last to exist
// on the app's side, so once they answer, every other route does too.
async function waitForApp() {
    const status = document.getElementById("app-status");
    const slowAfter = Date.now() + SLOW_START_MS;
    status.textContent = WAKING_UP;
    for (;;) {
        try {
            const resp = await fetch("/moves");
            if (resp.ok) {
                status.textContent = "";
                return;
            }
            status.textContent = Date.now() < slowAfter ? WAKING_UP : STILL_STARTING;
        } catch {
            status.textContent = APP_STOPPED;
        }
        await wait(STARTUP_POLL_MS);
    }
}

start();
