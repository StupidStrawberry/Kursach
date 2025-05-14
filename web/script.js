// Тема
document.getElementById('theme-toggle').addEventListener('click', () => {
    document.body.classList.toggle('dark-theme');
    localStorage.setItem('theme', document.body.classList.contains('dark-theme') ? 'dark' : 'light');
});

window.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-theme');
    }

    const username = getCookie('username');
    const userId = getCookie('user_id');
    if (!username || !userId) {
        window.location.href = 'register.html';
    } else {
        document.getElementById('username').textContent = username;
        document.getElementById('user-id').textContent = userId;
    }
});

// Куки
function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : null;
}

function deleteCookie(name) {
    document.cookie = name + '=; Max-Age=0; path=/;';
}

document.getElementById('logout-button').addEventListener('click', () => {
    deleteCookie('session');
    deleteCookie('username');
    deleteCookie('user_id');
    localStorage.clear();
    window.location.href = "index.html";
});

// Валидация
function validateForm() {
    const apiId = document.getElementById('tg_api_id').value.trim();
    const apiHash = document.getElementById('tg_api_hash').value.trim();
    const phone = document.getElementById('tg_phone').value.trim();
    const vkToken = document.getElementById('vk_token').value.trim();
    const tgUsername = document.getElementById('tg_username').value.trim();
    const vkId = document.getElementById('vk_id').value.trim();

    const errors = [];

    if (!/^\d+$/.test(apiId)) {
        errors.push("API ID должен содержать только цифры.");
    }

    if (!/^[a-zA-Z0-9]{10,}$/.test(apiHash)) {
        errors.push("API HASH должен быть не менее 10 символов и содержать только латинские буквы и цифры.");
    }

    if (!/^\+\d{11}$/.test(phone)) {
        errors.push("Телефон должен быть в формате +79991234567.");
    }

    if (!/^vk1\.[a-zA-Z0-9]{25,}$/.test(vkToken)) {
        errors.push("VK токен должен начинаться с 'vk1.' и быть длиной не менее 30 символов.");
    }

    if (!/^[a-zA-Z0-9_]{5,}$/.test(tgUsername)) {
        errors.push("Telegram username должен быть не менее 5 символов.");
    }

    if (!/^[a-zA-Z0-9_.]{5,}$/.test(vkId)) {
        errors.push("VK ID должен быть не менее 5 символов.");
    }

    if (errors.length > 0) {
        alert("Ошибки:\n" + errors.join("\n"));
        return false;
    }

    return true;
}

document.getElementById('settings-form').addEventListener('submit', function(e) {
    e.preventDefault();

    if (!validateForm()) return;

    const message = document.getElementById('success-message');
    message.style.display = 'block';

    setTimeout(() => {
        message.style.display = 'none';
    }, 2500);
});

// Модалки + карусели
const modals = document.querySelectorAll('.modal');
const overlay = document.getElementById('modal-overlay');

document.querySelectorAll('.help-button').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.modal);
        target.classList.add('show');
        overlay.style.display = 'block';
        target.dataset.slideIndex = "0";
        updateCarousel(target);
    });
});

document.querySelectorAll('.modal .close').forEach(close => {
    close.addEventListener('click', () => {
        modals.forEach(m => m.classList.remove('show'));
        overlay.style.display = 'none';
    });
});

overlay.addEventListener('click', () => {
    modals.forEach(m => m.classList.remove('show'));
    overlay.style.display = 'none';
});

function updateCarousel(modal) {
    const slides = modal.querySelectorAll('.carousel-slide');
    let index = parseInt(modal.dataset.slideIndex || "0");
    const totalSlides = slides.length;

    // Обновляем видимость слайдов
    slides.forEach((slide, i) => {
        slide.classList.toggle('active', i === index);
    });

    // Обновляем счетчик
    const counter = modal.querySelector('.slide-counter');
    if (counter) {
        counter.textContent = `${index + 1}/${totalSlides}`;
    }

    // Настройка кнопок
    const prevBtn = modal.querySelector('.prev-btn');
    const nextBtn = modal.querySelector('.next-btn');

    if (prevBtn) {
        prevBtn.disabled = index === 0;
        prevBtn.onclick = () => {
            index = Math.max(0, index - 1);
            modal.dataset.slideIndex = index;
            updateCarousel(modal);
        };
    }

    if (nextBtn) {
        nextBtn.disabled = index === totalSlides - 1;
        nextBtn.onclick = () => {
            index = Math.min(totalSlides - 1, index + 1);
            modal.dataset.slideIndex = index;
            updateCarousel(modal);
        };
    }
}
