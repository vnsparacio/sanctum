import globals from 'globals';

export default [
  {
    files: ['gate/**/*.mjs', 'reliability/**/*.mjs', 'scripts/**/*.mjs'],
    languageOptions: {globals: globals.node},
    rules: {
      'no-undef': 'error',
      'no-unreachable': 'error',
      'valid-typeof': 'error',
    },
  },
];
