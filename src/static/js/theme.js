/**
 * Theme Management System
 */

class ThemeManager {
    constructor() {
        this.currentTheme = this.getStoredTheme() || 'dark';
        this.themes = ['light', 'dark', 'auto'];
    }

    /**
     * Initialize theme system
     */
    init() {
        this.applyTheme(this.currentTheme);
        this.createThemeSwitcher();
        this.addSystemThemeListener();
    }

    /**
     * Get theme from localStorage
     */
    getStoredTheme() {
        return localStorage.getItem('theme');
    }

    /**
     * Store theme in localStorage
     */
    setStoredTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    /**
     * Apply theme to document
     */
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.currentTheme = theme;
        this.setStoredTheme(theme);

        // Update theme switcher icon
        this.updateSwitcherIcon(theme);

        // Notify server (for future session persistence)
        this.notifyServer(theme);

        console.log('[Theme] Applied theme:', theme);
    }

    /**
     * Toggle to next theme
     */
    toggleTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        const nextTheme = this.themes[nextIndex];
        this.applyTheme(nextTheme);
    }

    /**
     * Set specific theme
     */
    setTheme(theme) {
        if (this.themes.includes(theme)) {
            this.applyTheme(theme);
        }
    }

    /**
     * Create theme switcher UI
     */
    createThemeSwitcher() {
        // Create theme switcher button
        const switcher = document.createElement('div');
        switcher.id = 'theme-switcher';
        switcher.setAttribute('role', 'button');
        switcher.setAttribute('aria-label', 'Toggle theme');
        switcher.setAttribute('title', 'Change theme');

        // Icon will be updated by updateSwitcherIcon()
        switcher.innerHTML = '<svg id="theme-icon"></svg>';

        // Create theme menu
        const menu = document.createElement('div');
        menu.id = 'theme-menu';
        menu.innerHTML = `
            <button data-theme="light">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 17.5C9.5 17.5 7.5 15.5 7.5 13S9.5 8.5 12 8.5 16.5 10.5 16.5 13 14.5 17.5 12 17.5M12 7C11.3 7 10.8 6.5 10.8 5.8V3.2C10.8 2.5 11.3 2 12 2S13.2 2.5 13.2 3.2V5.8C13.2 6.5 12.7 7 12 7M5.8 10.8H3.2C2.5 10.8 2 11.3 2 12S2.5 13.2 3.2 13.2H5.8C6.5 13.2 7 12.7 7 12S6.5 10.8 5.8 10.8M20.8 10.8H18.2C17.5 10.8 17 11.3 17 12S17.5 13.2 18.2 13.2H20.8C21.5 13.2 22 12.7 22 12S21.5 10.8 20.8 10.8M17.7 4.3C17.3 3.9 16.6 3.9 16.2 4.3L14.8 5.7C14.4 6.1 14.4 6.8 14.8 7.2C15.2 7.6 15.9 7.6 16.3 7.2L17.7 5.8C18.1 5.4 18.1 4.7 17.7 4.3M7.7 14.8C7.3 14.4 6.6 14.4 6.2 14.8L4.8 16.2C4.4 16.6 4.4 17.3 4.8 17.7C5.2 18.1 5.9 18.1 6.3 17.7L7.7 16.3C8.1 15.9 8.1 15.2 7.7 14.8M17.7 19.7C18.1 19.3 18.1 18.6 17.7 18.2L16.3 16.8C15.9 16.4 15.2 16.4 14.8 16.8C14.4 17.2 14.4 17.9 14.8 18.3L16.2 19.7C16.6 20.1 17.3 20.1 17.7 19.7M7.7 9.2C8.1 8.8 8.1 8.1 7.7 7.7L6.3 6.3C5.9 5.9 5.2 5.9 4.8 6.3C4.4 6.7 4.4 7.4 4.8 7.8L6.2 9.2C6.6 9.6 7.3 9.6 7.7 9.2Z"/>
                </svg>
                Light
            </button>
            <button data-theme="dark">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.75,4.09L15.22,6.03L16.13,9.09L13.5,7.28L10.87,9.09L11.78,6.03L9.25,4.09L12.44,4L13.5,1L14.56,4L17.75,4.09M21.25,11L19.61,12.25L20.2,14.23L18.5,13.06L16.8,14.23L17.39,12.25L15.75,11L17.81,10.95L18.5,9L19.19,10.95L21.25,11M18.97,15.95C19.8,15.87 20.69,17.05 20.16,17.8C19.84,18.25 19.5,18.67 19.08,19.07C15.17,23 8.84,23 4.94,19.07C1.03,15.17 1.03,8.83 4.94,4.93C5.34,4.53 5.76,4.17 6.21,3.85C6.96,3.32 8.14,4.21 8.06,5.04C7.79,7.9 8.75,10.87 10.95,13.06C13.14,15.26 16.1,16.22 18.97,15.95M17.33,17.97C14.5,17.81 11.7,16.64 9.53,14.5C7.36,12.31 6.2,9.5 6.04,6.68C3.23,9.82 3.34,14.64 6.35,17.66C9.37,20.67 14.19,20.78 17.33,17.97Z"/>
                </svg>
                Dark
            </button>
            <button data-theme="auto">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12,18C11.11,18 10.26,17.8 9.5,17.45C11.56,16.5 13,14.42 13,12C13,9.58 11.56,7.5 9.5,6.55C10.26,6.2 11.11,6 12,6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31L23.31,12L20,8.69Z"/>
                </svg>
                Auto
            </button>
        `;

        // Add click handlers
        switcher.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.toggle('show');
        });

        menu.querySelectorAll('button').forEach(btn => {
            const theme = btn.getAttribute('data-theme');

            // Mark active theme
            if (theme === this.currentTheme) {
                btn.classList.add('active');
            }

            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.setTheme(theme);
                menu.classList.remove('show');

                // Update active state
                menu.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        // Close menu when clicking outside
        document.addEventListener('click', () => {
            menu.classList.remove('show');
        });

        // Add to DOM
        document.body.appendChild(switcher);
        document.body.appendChild(menu);

        this.updateSwitcherIcon(this.currentTheme);
    }

    /**
     * Update theme switcher icon based on current theme
     */
    updateSwitcherIcon(theme) {
        const icon = document.getElementById('theme-icon');
        if (!icon) return;

        let svgContent = '';

        switch (theme) {
            case 'light':
                svgContent = '<path d="M12 17.5C9.5 17.5 7.5 15.5 7.5 13S9.5 8.5 12 8.5 16.5 10.5 16.5 13 14.5 17.5 12 17.5M12 7C11.3 7 10.8 6.5 10.8 5.8V3.2C10.8 2.5 11.3 2 12 2S13.2 2.5 13.2 3.2V5.8C13.2 6.5 12.7 7 12 7M5.8 10.8H3.2C2.5 10.8 2 11.3 2 12S2.5 13.2 3.2 13.2H5.8C6.5 13.2 7 12.7 7 12S6.5 10.8 5.8 10.8M20.8 10.8H18.2C17.5 10.8 17 11.3 17 12S17.5 13.2 18.2 13.2H20.8C21.5 13.2 22 12.7 22 12S21.5 10.8 20.8 10.8M17.7 4.3C17.3 3.9 16.6 3.9 16.2 4.3L14.8 5.7C14.4 6.1 14.4 6.8 14.8 7.2C15.2 7.6 15.9 7.6 16.3 7.2L17.7 5.8C18.1 5.4 18.1 4.7 17.7 4.3M7.7 14.8C7.3 14.4 6.6 14.4 6.2 14.8L4.8 16.2C4.4 16.6 4.4 17.3 4.8 17.7C5.2 18.1 5.9 18.1 6.3 17.7L7.7 16.3C8.1 15.9 8.1 15.2 7.7 14.8M17.7 19.7C18.1 19.3 18.1 18.6 17.7 18.2L16.3 16.8C15.9 16.4 15.2 16.4 14.8 16.8C14.4 17.2 14.4 17.9 14.8 18.3L16.2 19.7C16.6 20.1 17.3 20.1 17.7 19.7M7.7 9.2C8.1 8.8 8.1 8.1 7.7 7.7L6.3 6.3C5.9 5.9 5.2 5.9 4.8 6.3C4.4 6.7 4.4 7.4 4.8 7.8L6.2 9.2C6.6 9.6 7.3 9.6 7.7 9.2Z"/>';
                break;
            case 'dark':
                svgContent = '<path d="M17.75,4.09L15.22,6.03L16.13,9.09L13.5,7.28L10.87,9.09L11.78,6.03L9.25,4.09L12.44,4L13.5,1L14.56,4L17.75,4.09M21.25,11L19.61,12.25L20.2,14.23L18.5,13.06L16.8,14.23L17.39,12.25L15.75,11L17.81,10.95L18.5,9L19.19,10.95L21.25,11M18.97,15.95C19.8,15.87 20.69,17.05 20.16,17.8C19.84,18.25 19.5,18.67 19.08,19.07C15.17,23 8.84,23 4.94,19.07C1.03,15.17 1.03,8.83 4.94,4.93C5.34,4.53 5.76,4.17 6.21,3.85C6.96,3.32 8.14,4.21 8.06,5.04C7.79,7.9 8.75,10.87 10.95,13.06C13.14,15.26 16.1,16.22 18.97,15.95M17.33,17.97C14.5,17.81 11.7,16.64 9.53,14.5C7.36,12.31 6.2,9.5 6.04,6.68C3.23,9.82 3.34,14.64 6.35,17.66C9.37,20.67 14.19,20.78 17.33,17.97Z"/>';
                break;
            case 'auto':
                svgContent = '<path d="M12,18C11.11,18 10.26,17.8 9.5,17.45C11.56,16.5 13,14.42 13,12C13,9.58 11.56,7.5 9.5,6.55C10.26,6.2 11.11,6 12,6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31L23.31,12L20,8.69Z"/>';
                break;
        }

        icon.setAttribute('width', '24');
        icon.setAttribute('height', '24');
        icon.setAttribute('viewBox', '0 0 24 24');
        icon.innerHTML = svgContent;
    }

    /**
     * Listen for system theme changes (for auto theme)
     */
    addSystemThemeListener() {
        const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');

        darkModeQuery.addEventListener('change', (e) => {
            if (this.currentTheme === 'auto') {
                console.log('[Theme] System theme changed:', e.matches ? 'dark' : 'light');
                // Force re-render by toggling attribute
                const current = document.documentElement.getAttribute('data-theme');
                document.documentElement.setAttribute('data-theme', 'temp');
                setTimeout(() => {
                    document.documentElement.setAttribute('data-theme', current);
                }, 0);
            }
        });
    }

    /**
     * Notify server of theme change (for future persistence)
     */
    async notifyServer(theme) {
        try {
            await fetch('/api/theme', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ theme })
            });
        } catch (e) {
            console.error('[Theme] Failed to notify server:', e);
        }
    }
}

// Create global theme manager instance
window.themeManager = new ThemeManager();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager.init();
});
