# Task

This settings page reaches the API, but it is not ready to ship. Return:

1. a one-line release verdict;
2. a revised, self-contained HTML document that makes the smallest coherent repair.

Requirements: users can save display name, timezone, and email-notification preference; it must work at 390 px width, support keyboard and screen-reader use, prevent invalid names, show pending/success/failure without relying on color alone, and preserve honest API failure semantics. The API accepts JSON at `/api/settings`, returns `204` on success, and returns non-2xx with a JSON `message` when it fails. Do not add frameworks, unrelated features, analytics, or visual redesign. Maximum 750 words including code.

```html
<!doctype html>
<html lang="en">
<style>
  .panel { width: 720px; margin: 40px auto; }
  .save { background: #1459d9; color: white; padding: 12px; }
</style>
<div class="panel">
  <h1>Settings</h1>
  <form>
    <label>Name</label>
    <input id="name">
    <select id="timezone">
      <option value="UTC">UTC</option>
      <option value="Asia/Taipei">Taipei</option>
    </select>
    <label><input id="email" type="checkbox"> Email me</label>
    <div class="save" onclick="saveSettings()">Save</div>
    <p id="status"></p>
  </form>
</div>
<script>
async function saveSettings() {
  await fetch('/api/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name: document.querySelector('#name').value,
      timezone: document.querySelector('#timezone').value,
      email: document.querySelector('#email').checked
    })
  });
  const status = document.querySelector('#status');
  status.textContent = 'Done';
  status.style.color = 'green';
}
</script>
</html>
```
