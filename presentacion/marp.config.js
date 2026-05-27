// Marp CLI config — registra el tema custom para que `npx marp` lo encuentre
// sin necesidad de pasar --theme-set explicitamente en cada build.
//
// Uso:
//   npx marp ecobalance.md --pdf --allow-local-files --html --output build/EcoBalance.pdf
module.exports = {
  themeSet: "./theme",
  allowLocalFiles: true,
  html: true,
};
