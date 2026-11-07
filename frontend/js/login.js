/* LoginPage boundary: enterCredentials(email, password) and displayError(message).
   Shell only: checks the form in the browser; the backend login is not connected yet. */
(() => {
  'use strict';

  const form = document.querySelector('#login-form');
  const error = document.querySelector('#login-error');
  const note = document.querySelector('#login-note');
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function displayError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  function showNote(message) {
    note.textContent = message;
    note.hidden = !message;
  }

  function enterCredentials(email, password) {
    if (!email || !password) return displayError('Enter your email and password.');
    if (!EMAIL.test(email)) return displayError('Enter a valid email address.');
    displayError('');
    showNote('Login is not connected yet. This page is a shell for the shared Log In use case.');
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(form);
    enterCredentials(String(data.get('email') || '').trim(), String(data.get('password') || ''));
  });

  form.addEventListener('input', () => displayError(''));

  document.querySelector('[data-action="register"]').addEventListener('click', () => {
    showNote('Account registration is not available yet.');
  });
})();
