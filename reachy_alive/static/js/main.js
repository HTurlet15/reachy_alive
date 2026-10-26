// Starts the app's page. The moves load first: their routes are the last to
// exist on the app's side, so once they answer, every other route does too.

import { loadIdleMoveInterval, loadMoves, setUpIntervalForm } from "./idle.js";
import { watchSenses } from "./senses.js";
import { setUpTabs } from "./tabs.js";

async function start() {
    setUpTabs();
    setUpIntervalForm();
    if (await loadMoves()) {
        await loadIdleMoveInterval();
        watchSenses(); // no await: it runs for as long as the page is open
    }
}

start();
