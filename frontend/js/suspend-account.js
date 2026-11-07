/* Boundary logic for User Admin Story 1. Other portal actions remain previews. */
window.AGroupSuspend = {
  open() {
    const content = document.querySelector('#modal-content');
    content.innerHTML = `
      <h2>Suspend User Account</h2>
      <p>Enter an account ID from the connected account system and a suspension reason.</p>
      <form id="suspend-account-form" class="form-stack">
        <label>ACCOUNT ID
          <input name="accountId" required maxlength="100" placeholder="e.g. U001">
        </label>
        <label>SUSPENSION REASON
          <textarea name="reason" required maxlength="500" placeholder="Explain why the account is being suspended."></textarea>
        </label>
        <p class="hint">This form calls the suspension backend. The existing sample accounts are not connected yet.</p>
        <p id="suspend-error" role="alert"></p>
        <button class="button" type="submit">Confirm Suspension</button>
      </form>`;
    const modal = document.querySelector('#modal');
    if (!modal.open) modal.showModal();
  },

  async submit(form) {
    const accountId = form.elements.accountId.value.trim();
    const reason = form.elements.reason.value.trim();
    const error = document.querySelector('#suspend-error');
    const button = form.querySelector('button[type="submit"]');
    error.textContent = '';
    button.disabled = true;
    try {
      const response = await fetch(
        `/api/user-admin/accounts/${encodeURIComponent(accountId)}/suspend`,
        {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({reason})
        }
      );
      const result = await response.json();
      if (!response.ok) {
        error.textContent = result.error || 'The account could not be suspended.';
        return;
      }
      document.querySelector('#modal').close();
      AG.toast(`Account ${result.accountId} suspended successfully.`);
    } catch (_error) {
      error.textContent = 'Cannot reach the backend. Start the Flask server, not the static file server.';
    } finally {
      button.disabled = false;
    }
  }
};
