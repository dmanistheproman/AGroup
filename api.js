/* Shared connection to the locally served application. */
(() => {
  'use strict';

  let sessionPromise;

  async function readResponse(response) {
    const type = response.headers.get('content-type') || '';
    if (!type.includes('application/json')) {
      throw new Error('Start the AGroup application server to use this workspace.');
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The request could not be completed.');
    return result;
  }

  async function get(path) {
    const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
    return readResponse(response);
  }

  function session() {
    if (!sessionPromise) {
      sessionPromise = get('/api/session').catch(error => {
        sessionPromise = null;
        throw error;
      });
    }
    return sessionPromise;
  }

  async function send(path, values, method = 'POST') {
    const settings = await session();
    const response = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': settings.csrfToken },
      body: JSON.stringify(values),
    });
    return readResponse(response);
  }

  async function trackActivity(projectId, type) {
    try {
      await send('/api/activity', { projectId, type, eventId: crypto.randomUUID() });
      return true;
    } catch (error) {
      console.warn('Activity reporting is unavailable.', error.message);
      return false;
    }
  }

  window.AGroupAPI = { get, send, session, trackActivity };
})();
