// Se aplica antes de pintar y sin scripts inline, compatible con CSP estricta.
;(function () {
  try {
    var guardado = localStorage.getItem('ma.tema')
    var tema = guardado === 'claro' || guardado === 'oscuro'
      ? guardado
      : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'
    document.documentElement.dataset.tema = tema
    var meta = document.querySelector('meta[name="color-scheme"]')
    if (meta) meta.setAttribute('content', tema === 'oscuro' ? 'dark' : 'light')
  } catch (e) { /* El tema predeterminado sigue disponible sin almacenamiento. */ }
})()
