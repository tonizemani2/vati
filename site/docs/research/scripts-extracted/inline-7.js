document.addEventListener("DOMContentLoaded", () => {
  const allSampleOpenBtns = document.querySelectorAll('[data-samplemodal]');
  const sampleqsModal = document.querySelector('#sampleqs-modal');
  const sampleModalItems = sampleqsModal.querySelectorAll('.sampleqs-modal-item');

  function initSampleModal() {
    sampleModalItems.forEach(item => item.style.display = 'none');
  }
  initSampleModal();

  const allSampleCloseBtns = document.querySelectorAll('.sampleqs-modal-close, .sampleqs-modal-bg, .sampleqs-modal-footer');

  allSampleOpenBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      sampleModalItems.forEach(item => {
        if(e.currentTarget.dataset.samplemodal === item.dataset.samplemodal) {
          item.style.display = 'block';
        }
      });
      sampleqsModal.classList.add('visible');
      document.body.classList.add('no-scroll');
    });
  });
  allSampleCloseBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      sampleqsModal.classList.remove('visible');
      initSampleModal();
      document.body.classList.remove('no-scroll');
    });
  });

  // Rationale accordions
  const raccordions = document.querySelectorAll('.sampleqs-modal-accordion');

  const setMaxHeight = (acc, open) => {
    const content = acc.querySelector('.sampleqs-modal-acc-ans');
    if (!content) return;
    content.style.maxHeight = open ? `${content.scrollHeight}px` : '0px';
  };

  // Init: collapsed unless already .active
  raccordions.forEach(acc => {
    const content = acc.querySelector('.sampleqs-modal-acc-ans');
    if (content) content.style.maxHeight = '0px';
    if (acc.classList.contains('active')) setMaxHeight(acc, true);

    const tab = acc.querySelector('.sampleqs-modal-acc-que');
    if (!tab) return;

    tab.addEventListener('click', () => {
      acc.classList.toggle('active');
      setMaxHeight(acc, acc.classList.contains('active'));
    });
  });
});