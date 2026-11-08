/* LoginPage boundary: enterCredentials(email, password) and displayError(message).
   Sends the credentials to POST /api/auth/login (LoginController on the server). */
(() => {
  'use strict';

  const account = window.AGroupAccount;
  const form = document.querySelector('#login-form');
  const error = document.querySelector('#login-error');
  const note = document.querySelector('#login-note');
  const submit = form.querySelector('button[type="submit"]');
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function displayError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  function showNote(message) {
    note.textContent = message;
    note.hidden = !message;
  }

  async function enterCredentials(email, password) {
    if (!email || !password) return displayError('Enter your email and password.');
    if (!EMAIL.test(email)) return displayError('Enter a valid email address.');
    displayError('');
    submit.disabled = true;
    const result = await account.signIn(email, password);
    submit.disabled = false;
    if (result.error) return displayError(result.error);
    location.href = account.homeFor(result.user);
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(form);
    enterCredentials(String(data.get('email') || '').trim(), String(data.get('password') || ''));
  });

  form.addEventListener('input', () => displayError(''));

  // Demo account buttons fill in the form; the user still presses Log in.
  const list = document.querySelector('#demo-accounts');
  account.DEMO_ACCOUNTS.forEach(demo => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = demo.label;
    button.addEventListener('click', () => {
      form.email.value = demo.email;
      form.password.value = 'demo';
      displayError('');
      submit.focus();
    });
    list.appendChild(button);
  });
})();
