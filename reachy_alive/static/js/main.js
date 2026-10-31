// Starts the app's page. The moves load first: their routes are the last to
// exist on the app's side, so once they answer, every other route does too.

import { loadIdleMoveInterval, loadMoves, setUpIntervalForm } from "./idle.js";
import { setUpSenseSwitches, watchSenses } from "./senses.js";
import { setUpTabs } from "./tabs.js";

async function start() {
    setUpTabs();
    setUpIntervalForm();
    await loadMoves(); // however long the app takes to start
    await loadIdleMoveInterval();
    await setUpSenseSwitches();
    watchSenses(); // no await: it runs for as long as the page is open
}

start();
