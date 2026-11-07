/* LoginPage boundary: enterCredentials(email, password) and displayError(message).
   Demo login: the form is checked in the browser and the session is kept locally
   (see account.js) until the backend login is connected. */
(() => {
  'use strict';

  const account = window.AGroupAccount;
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
    const user = account.signIn(email);
    location.href = account.homeFor(user);
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

  // Demo account buttons fill in the form; the user still presses Log in.
  const list = document.querySelector('#demo-accounts');
  account.DEMO_ACCOUNTS.forEach(demo => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = demo.name === 'Alex Tan' ? 'Customer · Alex Tan' : demo.name;
    button.addEventListener('click', () => {
      form.email.value = demo.email;
      form.password.value = 'demo';
      displayError('');
      form.querySelector('button[type="submit"]').focus();
    });
    list.appendChild(button);
  });
})();
