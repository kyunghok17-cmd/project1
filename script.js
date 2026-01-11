// Sample blog posts data
const blogPosts = [
    {
        id: 1,
        title: "블로그 시작하기",
        excerpt: "새로운 블로그를 시작하며 첫 글을 작성합니다. 앞으로 다양한 주제로 글을 써나갈 예정입니다.",
        date: "2026-01-11",
        emoji: "🚀"
    },
    {
        id: 2,
        title: "일상 이야기",
        excerpt: "오늘 있었던 일들을 정리하며 소소한 일상의 행복을 찾아봅니다.",
        date: "2026-01-10",
        emoji: "☕"
    },
    {
        id: 3,
        title: "생각의 조각들",
        excerpt: "최근 생각해본 것들을 글로 정리해봅니다. 때로는 글쓰기가 생각을 정리하는 좋은 방법입니다.",
        date: "2026-01-09",
        emoji: "💭"
    }
];

// Navigation functionality
document.addEventListener('DOMContentLoaded', () => {
    // Mobile menu toggle
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');

    hamburger.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        hamburger.classList.toggle('active');
    });

    // Smooth scrolling and active link highlighting
    const navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href');
            const targetSection = document.querySelector(targetId);

            if (targetSection) {
                // Close mobile menu if open
                navMenu.classList.remove('active');
                hamburger.classList.remove('active');

                // Scroll to section
                const headerOffset = 80;
                const elementPosition = targetSection.offsetTop;
                const offsetPosition = elementPosition - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });

                // Update active link
                navLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            }
        });
    });

    // Highlight active section on scroll
    const sections = document.querySelectorAll('section');

    window.addEventListener('scroll', () => {
        let current = '';

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;

            if (window.pageYOffset >= sectionTop - 150) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.add('active');
            }
        });
    });

    // Render blog posts
    renderBlogPosts();

    // Contact form submission
    const contactForm = document.getElementById('contactForm');
    contactForm.addEventListener('submit', handleFormSubmit);
});

// Render blog posts dynamically
function renderBlogPosts() {
    const blogGrid = document.getElementById('blogGrid');

    if (!blogGrid) return;

    blogGrid.innerHTML = '';

    blogPosts.forEach(post => {
        const blogCard = createBlogCard(post);
        blogGrid.appendChild(blogCard);
    });
}

// Create blog card element
function createBlogCard(post) {
    const card = document.createElement('article');
    card.className = 'blog-card';
    card.setAttribute('data-id', post.id);

    card.innerHTML = `
        <div class="blog-image">
            <span>${post.emoji}</span>
        </div>
        <div class="blog-content">
            <p class="blog-date">${formatDate(post.date)}</p>
            <h3 class="blog-title">${post.title}</h3>
            <p class="blog-excerpt">${post.excerpt}</p>
            <a href="#" class="blog-read-more" onclick="readPost(${post.id}); return false;">
                자세히 보기 →
            </a>
        </div>
    `;

    return card;
}

// Format date to Korean format
function formatDate(dateString) {
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');

    return `${year}년 ${month}월 ${day}일`;
}

// Read blog post (placeholder function)
function readPost(postId) {
    const post = blogPosts.find(p => p.id === postId);

    if (post) {
        alert(`"${post.title}" 포스트를 읽습니다.\n\n실제 구현 시에는 포스트 상세 페이지로 이동하거나 모달을 띄울 수 있습니다.`);
    }
}

// Handle contact form submission
function handleFormSubmit(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const name = formData.get('name');
    const email = formData.get('email');
    const message = formData.get('message');

    // In a real application, you would send this data to a server
    console.log('Form submitted:', { name, email, message });

    // Show success message
    alert(`${name}님, 메시지가 전송되었습니다!\n\n실제 구현 시에는 서버로 데이터를 전송하고 이메일을 보낼 수 있습니다.`);

    // Reset form
    e.target.reset();
}

// Add animation on scroll (Intersection Observer)
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe blog cards for animation
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const blogCards = document.querySelectorAll('.blog-card');
        blogCards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = `opacity 0.6s ease-out ${index * 0.1}s, transform 0.6s ease-out ${index * 0.1}s`;
            observer.observe(card);
        });
    }, 100);
});

// Utility: Debounce function for performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Add scroll effect to navbar
let lastScroll = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', debounce(() => {
    const currentScroll = window.pageYOffset;

    if (currentScroll <= 0) {
        navbar.style.boxShadow = 'var(--shadow)';
        return;
    }

    if (currentScroll > lastScroll && currentScroll > 100) {
        // Scrolling down
        navbar.style.transform = 'translateY(-100%)';
    } else {
        // Scrolling up
        navbar.style.transform = 'translateY(0)';
        navbar.style.boxShadow = 'var(--shadow-lg)';
    }

    lastScroll = currentScroll;
}, 50));

// Initialize navbar transition
navbar.style.transition = 'transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out';
