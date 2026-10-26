// The tab bar: each tab shows its panel and hides the others.

export function setUpTabs() {
    for (const tab of document.querySelectorAll('[role="tab"]')) {
        tab.addEventListener("click", () => showTab(tab));
        tab.addEventListener("keydown", onTabKeydown);
    }
}

// Selects a tab: shows its panel, hides the others. Only the selected tab
// is reached with the Tab key; the arrow keys move between tabs.
function showTab(selected) {
    for (const tab of document.querySelectorAll('[role="tab"]')) {
        const isSelected = tab === selected;
        tab.setAttribute("aria-selected", String(isSelected));
        tab.tabIndex = isSelected ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !isSelected;
    }
}

// Left and right arrows select the previous or next tab, wrapping around.
function onTabKeydown(event) {
    const steps = { ArrowLeft: -1, ArrowRight: 1 };
    if (!(event.key in steps)) {
        return;
    }
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const current = tabs.indexOf(event.currentTarget);
    const next = tabs[(current + steps[event.key] + tabs.length) % tabs.length];
    showTab(next);
    next.focus();
}
