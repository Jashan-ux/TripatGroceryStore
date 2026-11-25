import type { Config } from 'tailwindcss';

/**
 * Design tokens. The brand red (#B91C1C) is the primary; every colour used by
 * components resolves through a CSS variable so the palette can be re-themed
 * (and so contrast is reviewable in one place: src/styles/globals.css).
 */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: { DEFAULT: '1rem', sm: '1.25rem', lg: '2rem' },
      screens: { '2xl': '1200px' },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          50: '#FEF2F2',
          100: '#FEE2E2',
          200: '#FECACA',
          300: '#FCA5A5',
          400: '#F87171',
          500: '#EF4444',
          600: '#DC2626',
          700: '#B91C1C',
          800: '#991B1B',
          900: '#7F1D1D',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        success: {
          DEFAULT: '#15803D',
          foreground: '#FFFFFF',
          soft: '#DCFCE7',
        },
        warning: {
          DEFAULT: '#B45309',
          soft: '#FEF3C7',
        },
        info: {
          DEFAULT: '#1D4ED8',
          soft: '#DBEAFE',
        },
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Noto Sans Devanagari',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        // Light Material-style elevation.
        elev1: '0 1px 2px 0 rgb(15 23 42 / 0.06), 0 1px 3px 1px rgb(15 23 42 / 0.06)',
        elev2: '0 1px 2px 0 rgb(15 23 42 / 0.08), 0 2px 6px 2px rgb(15 23 42 / 0.08)',
        elev3: '0 4px 8px 3px rgb(15 23 42 / 0.08), 0 1px 3px 0 rgb(15 23 42 / 0.12)',
        navbar: '0 -1px 0 0 hsl(var(--border)), 0 -4px 16px -8px rgb(15 23 42 / 0.16)',
      },
      minHeight: { touch: '44px' },
      minWidth: { touch: '44px' },
      screens: {
        xs: '360px',
      },
      keyframes: {
        'slide-down': {
          from: { transform: 'translateY(-100%)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'slide-down': 'slide-down 220ms ease-out',
        shimmer: 'shimmer 1.4s infinite',
      },
    },
  },
  plugins: [],
} satisfies Config;
