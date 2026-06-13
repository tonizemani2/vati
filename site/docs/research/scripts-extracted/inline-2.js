document.addEventListener("DOMContentLoaded", () => {
  let sampleSwiper = new Swiper(".sampleqs-swiper", {
    slidesPerView: "auto",
    spaceBetween: 16,
    pagination: { 
      el: ".sampleqs-swiper-pagination",
      clickable: true,
    },
    navigation: { 
      prevEl: ".sampleqs-swiper-arrows .arrow-prev",
      nextEl: ".sampleqs-swiper-arrows .arrow-next" 
    },
  });
  
  // Tab functionality
  // function hasId(element) {
  //   return typeof element.id !== 'undefined';
  // }
  // const allVideoQATabs = document.querySelectorAll('.sampleqs-filter-tab');
  // const allVideoQACards = document.querySelectorAll('.sampleqs-card');
  // allVideoQATabs.forEach((tab) => {
  //   tab.addEventListener('click', (e) => {
  //     allVideoQATabs.forEach((x) => {
  //       if (x.classList.contains('is-active')) {
  //         x.classList.remove('is-active');
  //       }
  //     });
  //     e.currentTarget.classList.add('is-active');

  //     if (hasId(tab) && tab.id === 'view-all-tab') {
  //       allVideoQACards.forEach((card) => {
  //         card.style.display = 'block';
  //       });
  //       sampleSwiper.update();
  //     } else {
  //       allVideoQACards.forEach((card) => {
  //         card.style.display = 'none';
  //         if (e.currentTarget.dataset.filter === card.dataset.filter) {
  //           card.style.display = 'block';
  //         }
  //       });
  //       sampleSwiper.update();
  //     }
  //   });
  // });
  const allVideoQATabs = document.querySelectorAll('.sampleqs-filter-tab');
  const allVideoQACards = document.querySelectorAll('.sampleqs-card');
  
  allVideoQATabs.forEach((tab) => {
    tab.addEventListener('click', (e) => {
      const selectedFilter = e.currentTarget.dataset.filter;
  
      allVideoQATabs.forEach((x) => x.classList.remove('is-active'));
      e.currentTarget.classList.add('is-active');
  
      if (tab.id === 'view-all-tab') {
        allVideoQACards.forEach((card) => {
          card.style.display = 'block';
        });
      } else {
        allVideoQACards.forEach((card) => {
          const tags = card.querySelectorAll('.sampleqs-card-tag');
  
          // Check if ANY tag matches
          const hasMatch = Array.from(tags).some(tag => {
            return tag.dataset.filter === selectedFilter;
          });
  
          card.style.display = hasMatch ? 'block' : 'none';
        });
      }
  
      sampleSwiper.update();
    });
  });
});