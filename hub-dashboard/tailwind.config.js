/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                border: "hsl(var(--border))",
                input: "hsl(var(--border))",
                ring: "hsl(var(--primary))",
                background: "hsl(var(--bg-main))",
                foreground: "hsl(var(--text-main))",
                dim: {
                    DEFAULT: "hsl(var(--text-dim))",
                    foreground: "hsl(var(--text-main))",
                },
                primary: {
                    DEFAULT: "hsl(var(--primary))",
                    foreground: "hsl(var(--text-main))",
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--text-main))",
                },
                destructive: {
                    DEFAULT: "hsl(var(--error))",
                    foreground: "hsl(0 0% 100%)",
                },
                error: "hsl(var(--error))",
                success: "hsl(var(--success))",
                muted: {
                    DEFAULT: "hsl(var(--bg-card))",
                    foreground: "hsl(var(--text-dim))",
                },
                accent: {
                    DEFAULT: "hsl(var(--bg-card))",
                    foreground: "hsl(var(--text-main))",
                },
                popover: {
                    DEFAULT: "hsl(var(--bg-card))",
                    foreground: "hsl(var(--text-main))",
                },
                card: {
                    DEFAULT: "hsl(var(--bg-card))",
                    foreground: "hsl(var(--text-main))",
                },
            },
            borderRadius: {
                lg: "var(--radius)",
                md: "calc(var(--radius) - 2px)",
                sm: "calc(var(--radius) - 4px)",
            },
            fontFamily: {
                sans: ["Inter", "sans-serif"],
                heading: ["Outfit", "sans-serif"],
            },
            width: {
                sidebar: "280px",
            },
            height: {
                "mob-nav": "70px",
            }
        },
    },
    plugins: [],
}
