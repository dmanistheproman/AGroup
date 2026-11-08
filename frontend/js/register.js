/* AccountForm boundary (S-13): enterDetails(name, email, password), errors shown beside each field.
   Customer self-registration through POST /api/auth/register; the new customer is logged in. */
(() => {
  'use strict';

  const account = window.AGroupAccount;
  const form = document.querySelector('#register-form');
  const formError = document.querySelector('#register-error');
  const submit = form.querySelector('button[type="submit"]');
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function displayFieldError(field, message) {
    const slot = form.querySelector(`[data-error-for="${field}"]`);
    const input = form.elements[field];
    if (slot) slot.textContent = message || '';
    if (input) input.toggleAttribute('aria-invalid', Boolean(message));
  }

  function clearErrors() {
    form.querySelectorAll('[data-error-for]').forEach(slot => displayFieldError(slot.dataset.errorFor, ''));
    formError.hidden = true;
  }

  // Same rules as AccountService on the server, so most mistakes show before sending.
  function check(values) {
    const errors = {};
    if (!values.name) errors.name = 'Enter your name.';
    if (!values.email) errors.email = 'Enter your email address.';
    else if (!EMAIL.test(values.email)) errors.email = 'Enter a valid email address, for example name@example.com.';
    if (!values.password) errors.password = 'Enter a password.';
    else if (values.password.length < 8) errors.password = 'Use at least 8 characters for the password.';
    if (values.password && values.confirm !== values.password) errors.confirm = 'The passwords do not match.';
    return errors;
  }

  async function enterDetails(values) {
    clearErrors();
    const errors = check(values);
    Object.entries(errors).forEach(([field, message]) => displayFieldError(field, message));
    if (Object.keys(errors).length) { form.elements[Object.keys(errors)[0]].focus(); return; }

    submit.disabled = true;
    const result = await account.register(values.name, values.email, values.password);
    submit.disabled = false;
    if (result.error) {
      if (result.field && form.elements[result.field]) { displayFieldError(result.field, result.error); form.elements[result.field].focus(); }
      else { formError.textContent = result.error; formError.hidden = false; }
      return;
    }
    location.href = account.homeFor(result.user);
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(form);
    enterDetails({
      name: String(data.get('name') || '').trim(),
      email: String(data.get('email') || '').trim(),
      password: String(data.get('password') || ''),
      confirm: String(data.get('confirm') || ''),
    });
  });

  form.addEventListener('input', event => displayFieldError(event.target.name, ''));
})();
