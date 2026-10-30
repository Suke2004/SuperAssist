export async function apiRequest(path, body) {
    const response = await fetch(path, {
        method: body === undefined ? 'GET' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-App-Token': window.__APP_TOKEN__ || '' },
        ...(body === undefined ? {} : { body: JSON.stringify(body) })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.success === false) {
        throw new Error(result.detail || result.error || result.message || `Request failed (${response.status})`);
    }
    return result;
}
