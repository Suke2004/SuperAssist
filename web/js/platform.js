export function shortcutText(text) {
    if (/Mac/.test(navigator.platform)) {
        const keys = { K: 'X', Y: 'Shift+S', F1: '1', F2: '2', F3: '3',
            'PageUp/PageDown': ', / .', Arrows: 'Shift+, / . / U / D' };
        return text.replace(/Ctrl\+Shift\+Win\+([A-Za-z0-9/]+)/g, (_, key) => `Option+${keys[key] || key}`)
            .replaceAll('Ctrl+Shift+Win', 'Option');
    }
    return /Linux/.test(navigator.platform) ? text.replaceAll('Ctrl+Shift+Win', 'Ctrl+Shift+Super') : text;
}

export function updatePlatformHelp() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        if (!['SCRIPT', 'STYLE'].includes(walker.currentNode.parentElement?.tagName)) {
            walker.currentNode.nodeValue = shortcutText(walker.currentNode.nodeValue);
        }
    }
    document.querySelectorAll('[title]').forEach(element => { element.title = shortcutText(element.title); });
    const summary = document.getElementById('platform-shortcut-summary');
    if (summary) summary.textContent = /Mac/.test(navigator.platform) ? 'macOS: Option+Key (see movement and scrolling combinations below)'
        : /Linux/.test(navigator.platform) ? 'Linux: Ctrl+Shift+Super+Key; global shortcuts require X11'
        : 'Windows: Ctrl+Shift+Win+Key';
}
