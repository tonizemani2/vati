(function() {
      const sliderInstance = document.getElementById('gemini-image-slider-container');
      if (!sliderInstance) return;

      const slides = sliderInstance.querySelector('#gemini-slides');
      const slideElements = slides.children;
      const prevBtn = sliderInstance.querySelector('.prev-btn');
      const nextBtn = sliderInstance.querySelector('.next-btn');

      let index = 0;
      let autoPlayInterval;
      let autoplayDisabled = false;

      const AUTOPLAY_SPEED = 3000; // 3s

      function showSlide(i) {
        if (slideElements.length === 0) return;
        if (i < 0) index = slideElements.length - 1;
        else if (i >= slideElements.length) index = 0;
        else index = i;
        slides.style.transform = `translateX(${-index * 100}%)`;
      }

      function startAutoPlay() {
        if (autoplayDisabled) return;
        clearInterval(autoPlayInterval);
        autoPlayInterval = setInterval(() => {
          showSlide(index + 1);
        }, AUTOPLAY_SPEED);
      }

      function stopAutoPlayForever() {
        autoplayDisabled = true;
        clearInterval(autoPlayInterval);
      }

      // Button clicks: stop autoplay forever
      prevBtn.addEventListener('click', () => {
        stopAutoPlayForever();
        showSlide(index - 1);
      });
      nextBtn.addEventListener('click', () => {
        stopAutoPlayForever();
        showSlide(index + 1);
      });

      // Keyboard navigation (does not disable autoplay)
      sliderInstance.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') showSlide(index - 1);
        else if (e.key === 'ArrowRight') showSlide(index + 1);
      });

      // Touch/swipe (does not disable autoplay)
      let touchstartX = 0;
      let touchendX = 0;

      slides.addEventListener('touchstart', (event) => {
        touchstartX = event.changedTouches[0].screenX;
      }, { passive: true });

      slides.addEventListener('touchend', (event) => {
        touchendX = event.changedTouches[0].screenX;
        if (Math.abs(touchendX - touchstartX) < 50) return;
        if (touchendX < touchstartX) showSlide(index + 1);
        if (touchendX > touchstartX) showSlide(index - 1);
      }, { passive: true });

      // Start autoplay initially
      //startAutoPlay();
    })();