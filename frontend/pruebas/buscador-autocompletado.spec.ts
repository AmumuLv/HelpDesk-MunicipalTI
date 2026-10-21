import { expect, test } from '@playwright/test'

test('el buscador rechaza credenciales automáticas y conserva la búsqueda manual', async ({ page }) => {
  await page.route('**/prueba-buscador', (ruta) => ruta.fulfill({
    contentType: 'text/html',
    body: '<html><body><div id="prueba"></div><button id="perfil">Perfil</button></body></html>',
  }))
  await page.goto('/prueba-buscador')
  await page.addScriptTag({ type: 'module', content: `
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import RefreshRuntime from '/@react-refresh';
    RefreshRuntime.injectIntoGlobalHook(window);
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => (type) => type;
    window.__vite_plugin_react_preamble_installed__ = true;
    const { SearchInput } = await import('/src/componentes/base/Campo.tsx');
    function Prueba() {
      const [valor, cambiar] = React.useState('');
      return React.createElement(SearchInput, { valor, alCambiar: cambiar, etiqueta: 'Buscar personas' });
    }
    ReactDOM.createRoot(document.getElementById('prueba')).render(React.createElement(Prueba));
  ` })
  const buscador = page.getByRole('searchbox')
  await expect(buscador).toBeVisible()
  await buscador.fill('AJURIDICA')
  await expect(buscador).toHaveValue('AJURIDICA')
  await page.locator('#perfil').click()
  for (const conFoco of [false, true]) {
    for (const correo of ['jurasicpar@gmail.com', 'otra.cuenta@example.com', 'admin@example.org']) {
      for (const inputType of ['insertReplacementText', 'insertText', '']) {
        if (conFoco) await buscador.focus()
        else await page.locator('#perfil').click()
        await buscador.evaluate((campo: HTMLInputElement, datos) => {
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
          setter.call(campo, datos.correo)
          campo.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: datos.inputType }))
        }, { correo, inputType })
        await expect(buscador).toHaveValue('AJURIDICA')
      }
    }
  }
  await buscador.fill('Jorgue')
  await expect(buscador).toHaveValue('Jorgue')
  await page.getByRole('button', { name: 'Limpiar la búsqueda' }).click()
  await expect(buscador).toHaveValue('')
})
