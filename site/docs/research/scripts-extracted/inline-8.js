document.addEventListener("DOMContentLoaded", () => {
  const vidSlides = document.querySelectorAll('[data-video]');
  const vidModal = document.querySelector('.video-modal');
  const videoElem = vidModal.querySelector('video');
  const closeVidModal = vidModal.querySelector('.vid-modal-close');
  vidSlides.forEach((slide) => {
    slide.addEventListener('click', (e) => {
      videoElem.src = e.currentTarget.dataset.video;
      vidModal.classList.add('show');
      videoElem.play();
    });
  });
  closeVidModal.addEventListener('click', () => {
    vidModal.classList.remove('show');
    videoElem.src = '';
  });
});