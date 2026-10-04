document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('statusButton');
  if (button) {
    button.addEventListener('click', () => {
      button.textContent = 'FloodGuard is running';
    });
  }
});
