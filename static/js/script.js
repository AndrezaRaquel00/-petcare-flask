// script.js
console.log("PetCare site iniciado");

window.addEventListener('DOMContentLoaded', () => {
  const slides = document.querySelectorAll('#slideshow img');
  let index = 0;

  function nextSlide() {
    slides.forEach((img) => img.classList.remove('active'));
    slides[index].classList.add('active');
    index = (index + 1) % slides.length;
  }

  setInterval(nextSlide, 2500);
});


