document.addEventListener("DOMContentLoaded", () => {
  const allContactOpenBtns = document.querySelectorAll('[data-contact]');
  const contactModal = document.querySelector('#contact-modal');
  const allContactCloseBtns = document.querySelectorAll('.contact-modal-close, .contact-modal-bg');

  allContactOpenBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      contactModal.classList.add('visible');
      document.body.classList.add('no-scroll');
    });
  });
  allContactCloseBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      contactModal.classList.remove('visible');
      document.body.classList.remove('no-scroll');
    });
  });
});