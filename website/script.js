import {
    animate,
    inView
} from "https://esm.run/framer-motion";

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    mermaid.initialize({ startOnLoad: true, theme: 'dark' });

    // Mobile menu functionality
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    mobileMenuButton.addEventListener('click', () => {
        mobileMenu.classList.toggle('hidden');
        
        // Toggle hamburger menu icon
        const icon = mobileMenuButton.querySelector('i');
        if (mobileMenu.classList.contains('hidden')) {
            icon.setAttribute('data-lucide', 'menu');
        } else {
            icon.setAttribute('data-lucide', 'x');
        }
        lucide.createIcons();
    });

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            if(targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                
                // Update URL without triggering page reload
                history.pushState(null, null, targetId);
            }
            if (!mobileMenu.classList.contains('hidden')) {
                mobileMenu.classList.add('hidden');
                const icon = mobileMenuButton.querySelector('i');
                icon.setAttribute('data-lucide', 'menu');
                lucide.createIcons();
            }
        });
    });

    // FAQ functionality
    const faqQuestions = document.querySelectorAll('.faq-question');
    faqQuestions.forEach(question => {
        question.addEventListener('click', () => {
            const faqItem = question.closest('.faq-item');
            const answer = faqItem.querySelector('.faq-answer');
            const icon = question.querySelector('i[data-lucide="chevron-down"]');
            
            // Close other FAQ items
            faqQuestions.forEach(otherQuestion => {
                if (otherQuestion !== question) {
                    const otherItem = otherQuestion.closest('.faq-item');
                    const otherAnswer = otherItem.querySelector('.faq-answer');
                    const otherIcon = otherQuestion.querySelector('i[data-lucide="chevron-down"]');
                    
                    otherAnswer.classList.remove('show');
                    otherAnswer.classList.add('hidden');
                    otherQuestion.classList.remove('active');
                    if (otherIcon) {
                        otherIcon.style.transform = 'rotate(0deg)';
                    }
                }
            });
            
            // Toggle current FAQ item
            const isOpen = answer.classList.contains('show');
            if (isOpen) {
                answer.classList.remove('show');
                answer.classList.add('hidden');
                question.classList.remove('active');
                if (icon) {
                    icon.style.transform = 'rotate(0deg)';
                }
            } else {
                answer.classList.add('show');
                answer.classList.remove('hidden');
                question.classList.add('active');
                if (icon) {
                    icon.style.transform = 'rotate(180deg)';
                }
            }
        });
    });

    // Scroll-based animations
    const sectionsToAnimate = document.querySelectorAll('.anim-on-scroll');
    sectionsToAnimate.forEach((section, index) => {
        inView(section, () => {
            animate(
                section, {
                    opacity: 1,
                    y: 0
                }, {
                    duration: 0.8,
                    delay: 0.1 * (index % 4)
                }
            );
        }, {
            amount: 0.2
        });
    });

    // Active navigation highlighting
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('nav a[href^="#"]');
    
    const updateActiveNav = () => {
        let current = '';
        const scrollY = window.scrollY;
        
        sections.forEach(section => {
            const sectionTop = section.offsetTop - 100;
            const sectionHeight = section.offsetHeight;
            
            if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
                current = section.getAttribute('id');
            }
        });
        
        navLinks.forEach(link => {
            link.classList.remove('text-cyan-400', 'font-semibold');
            link.classList.add('text-gray-300');
            
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.remove('text-gray-300');
                link.classList.add('text-cyan-400', 'font-semibold');
            }
        });
    };

    window.addEventListener('scroll', updateActiveNav);
    updateActiveNav(); // Initial call

    // Copy to clipboard functionality for code blocks
    document.querySelectorAll('pre code').forEach(codeBlock => {
        const pre = codeBlock.parentElement;
        
        // Create copy button
        const copyButton = document.createElement('button');
        copyButton.innerHTML = '<i data-lucide="copy" class="w-4 h-4"></i>';
        copyButton.className = 'absolute top-3 right-3 p-2 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors z-10 opacity-0 group-hover:opacity-100';
        copyButton.title = 'Copy to clipboard';
        
        pre.classList.add('group', 'relative');
        pre.appendChild(copyButton);
        
        copyButton.addEventListener('click', async () => {
            const text = codeBlock.textContent;
            try {
                await navigator.clipboard.writeText(text);
                copyButton.innerHTML = '<i data-lucide="check" class="w-4 h-4 text-green-400"></i>';
                setTimeout(() => {
                    copyButton.innerHTML = '<i data-lucide="copy" class="w-4 h-4"></i>';
                    lucide.createIcons();
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
            }
            lucide.createIcons();
        });
    });

    // Enhanced parallax effect for hero background with fade-out
    const hero = document.querySelector('.hero-bg');
    if (hero) {
        window.addEventListener('scroll', () => {
            const scrolled = window.scrollY;
            const windowHeight = window.innerHeight;
            
            // Parallax effect
            const parallax = scrolled * 0.5;
            hero.style.transform = `translateY(${parallax}px)`;
            
            // Fade out effect as user scrolls down
            const fadePoint = windowHeight * 0.8; // Start fading at 80% of viewport height
            const opacity = Math.max(0, 1 - (scrolled / fadePoint));
            
            // Apply opacity to the background image
            if (scrolled > 0) {
                hero.style.setProperty('--hero-opacity', opacity);
            } else {
                hero.style.setProperty('--hero-opacity', 1);
            }
        });
    }

    // Performance metrics animation
    const performanceCards = document.querySelectorAll('.requirement-card .grid > div');
    const animateNumbers = () => {
        performanceCards.forEach(card => {
            inView(card, () => {
                const numberElement = card.querySelector('.text-2xl');
                if (numberElement && !numberElement.classList.contains('animated')) {
                    numberElement.classList.add('animated');
                    
                    const finalText = numberElement.textContent;
                    const isNumber = /^\d+/.test(finalText);
                    
                    if (isNumber) {
                        const finalNumber = parseInt(finalText);
                        let currentNumber = 0;
                        const increment = finalNumber / 30;
                        
                        const timer = setInterval(() => {
                            currentNumber += increment;
                            if (currentNumber >= finalNumber) {
                                numberElement.textContent = finalText;
                                clearInterval(timer);
                            } else {
                                numberElement.textContent = Math.floor(currentNumber) + finalText.replace(/^\d+/, '');
                            }
                        }, 50);
                    }
                }
            }, { amount: 0.3 });
        });
    };
    
    animateNumbers();

    // Loading state management
    window.addEventListener('beforeunload', () => {
        document.body.classList.add('loading');
    });

    // Keyboard navigation for FAQ
    faqQuestions.forEach((question, index) => {
        question.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                question.click();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                const nextQuestion = faqQuestions[index + 1];
                if (nextQuestion) {
                    nextQuestion.focus();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                const prevQuestion = faqQuestions[index - 1];
                if (prevQuestion) {
                    prevQuestion.focus();
                }
            }
        });
        
        // Make FAQ questions focusable
        question.setAttribute('tabindex', '0');
    });

    // Intersection Observer for performance
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);

    // Observe all animatable elements
    document.querySelectorAll('.anim-on-scroll').forEach(el => {
        observer.observe(el);
    });

    // Copy code functionality
    window.copyCode = function(button) {
        const codeBlock = button.closest('.code-block-enhanced').querySelector('code');
        const text = codeBlock.textContent;
        
        navigator.clipboard.writeText(text).then(() => {
            const originalHtml = button.innerHTML;
            button.innerHTML = '<i data-lucide="check" class="w-4 h-4 text-green-400"></i>';
            lucide.createIcons();
            
            setTimeout(() => {
                button.innerHTML = originalHtml;
                lucide.createIcons();
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy text: ', err);
        });
    };

    // Initialize all icons after DOM manipulations
    setTimeout(() => {
        lucide.createIcons();
    }, 100);

});
