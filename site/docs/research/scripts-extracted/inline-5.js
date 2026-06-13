document.addEventListener("DOMContentLoaded", () => {
  let usecaseSwiper = new Swiper(".usecase-swiper", {
    slidesPerView: "auto",
    spaceBetween: 16,
    pagination: { 
      el: ".usecase-swiper-pagination",
      clickable: true,
    },
    navigation: { 
      prevEl: ".usecase-swiper-arrows .arrow-prev",
      nextEl: ".usecase-swiper-arrows .arrow-next" 
    },
  });
  
  // Tab functionality
  const allUsecaseTabs = document.querySelectorAll('.usecase-filter-tab');
  const allUsecaseCards = document.querySelectorAll('.usecase-card');
  
  allUsecaseTabs.forEach((tab) => {
    tab.addEventListener('click', (e) => {
      const selectedFilter = e.currentTarget.dataset.filter;
  
      allUsecaseTabs.forEach((x) => x.classList.remove('is-active'));
      e.currentTarget.classList.add('is-active');
  
      if (tab.id === 'view-all-usecase') {
        allUsecaseCards.forEach((card) => {
          card.style.display = 'block';
        });
      } else {
        allUsecaseCards.forEach((card) => {
          const tags = card.querySelectorAll('.usecase-card-tag');
  
          // Check if ANY tag matches
          const hasMatch = Array.from(tags).some(tag => {
            return tag.dataset.filter === selectedFilter;
          });
  
          card.style.display = hasMatch ? 'block' : 'none';
        });
      }

      usecaseSwiper.update();
    });
  });
});