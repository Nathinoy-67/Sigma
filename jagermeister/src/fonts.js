// Fonts used by the typography layer (SIL OFL, via @fontsource).
const FONTS = [
  ['Frak', 'unifrakturmaguntia-latin-400-normal.woff2', '400', 'normal'],
  ['Cinzel', 'cinzel-latin-400-normal.woff2', '400', 'normal'],
  ['Cinzel', 'cinzel-latin-600-normal.woff2', '600', 'normal'],
  ['Corm', 'cormorant-garamond-latin-300-normal.woff2', '300', 'normal'],
  ['Corm', 'cormorant-garamond-latin-300-italic.woff2', '300', 'italic'],
  ['Corm', 'cormorant-garamond-latin-400-italic.woff2', '400', 'italic'],
  ['Corm', 'cormorant-garamond-latin-500-italic.woff2', '500', 'italic'],
  ['Mont', 'montserrat-latin-300-normal.woff2', '300', 'normal'],
  ['Mont', 'montserrat-latin-400-normal.woff2', '400', 'normal'],
  ['Mont', 'montserrat-latin-500-normal.woff2', '500', 'normal'],
  ['Mont', 'montserrat-latin-600-normal.woff2', '600', 'normal'],
  ['Grenze', 'grenze-gotisch-latin-500-normal.woff2', '500', 'normal'],
  ['Grenze', 'grenze-gotisch-latin-700-normal.woff2', '700', 'normal'],
];

export async function loadFonts(base = 'assets/fonts/') {
  await Promise.all(
    FONTS.map(async ([family, file, weight, style]) => {
      const src = (window.FONT_DATA && window.FONT_DATA[file]) || `url(${base}${file})`;
      const face = new FontFace(family, src, { weight, style });
      await face.load();
      document.fonts.add(face);
    }),
  );
  await document.fonts.ready;
}
