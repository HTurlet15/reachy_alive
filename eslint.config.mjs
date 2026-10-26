import js from "@eslint/js";
import globals from "globals";

export default [
    js.configs.recommended,
    {
        files: ["reachy_alive/static/**/*.js"],
        languageOptions: {
            globals: globals.browser,
            sourceType: "script",
        },
    },
];
