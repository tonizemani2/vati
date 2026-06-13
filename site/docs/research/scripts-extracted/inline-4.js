document.addEventListener('DOMContentLoaded', () => {
    let solutionSwiper = new Swiper('.solutions-swiper', {
      slidesPerView: 'auto',
      spaceBetween: 20,
      pagination: {
        el: '.solutions-swiper-pagination',
        clickable: true,
      },
      navigation: {
        prevEl: '.solutions-swiper-arrows .arrow-prev',
        nextEl: '.solutions-swiper-arrows .arrow-next',
      },
      breakpoints: {
        991: {
          spaceBetween: 0,
        },
      },
    });
  });