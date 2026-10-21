DETECTA PLAGAS — F28
Implementación: 21/10/2026.

Repositorio autorizado: https://github.com/emmanuelbarriosxcom-dev/detectaplagas-dashboards
Script: tools/seo_check.py
Tests: tools/test_seo_check.py
Workflow: .github/workflows/f28-seo-check.yml

EJECUCIÓN
python3 tools/seo_check.py --output reports/f28
python3 -m unittest discover -s tools -p 'test_seo_check.py' -v
Python 3.9 o posterior. Sin dependencias de pip, credenciales ni servicios de pago.

PROGRAMACIÓN
Día 1 de cada mes a las 06:17 UTC; próxima fecha prevista 01/11/2026.
También ejecución manual (Run workflow) y al cambiar exclusivamente los archivos del comprobador/workflow en main.
Los horarios de GitHub son orientativos: una ejecución programada puede retrasarse.
GitHub puede desactivar schedules en repositorios públicos inactivos. Revisar Actions si deja de ejecutarse.

SALIDA
report.md: resumen de incidencias URL/gravedad/problema.
report.json: todas las URLs, códigos HTTP, etiquetas observadas y hash de respuesta.
issues.csv: incidencias (solo cabecera si no existen).
urls.txt: inventario completo del sitemap.
sitemaps.json: evidencia de los mapas consultados.
GitHub conserva el artefacto 90 días y muestra el resumen en el job.
Códigos de salida: 0 sin hallazgos; 1 hallazgos a revisar; 2 ejecución incompleta/error de sitemap.

SEGURIDAD Y LÍMITES
GET públicos sin cookies. Un solo proceso, pausa mínima de un segundo y timeout de 25 s.
Máximo 250 URLs, 30 mapas y 8 MiB por respuesta. Redirects solo al host HTTPS autorizado.
No suplanta Googlebot ni SiteAuditBot, no evade bloqueos ni cambia configuración de seguridad.
Cuenta etiquetas por página, no títulos iguales entre páginas.
El canonical esperado es la propia URL del sitemap; diferencias intencionales requieren revisión humana.
Incluye noindex en meta robots/googlebot y X-Robots-Tag.
No ejecuta JavaScript ni comprueba indexación real en Google o todas las reglas de robots.txt.
Detecta incidencias cuando se ejecuta, no las previene ni garantiza detectar cambios entre dos revisiones mensuales.
Si el sitemap falla o excede límites, la ejecución no se presenta como una comprobación limpia.

EVIDENCIA INICIAL
Prueba local 14:01:37–14:04:44 UTC: 32 URLs, 0 incidencias.
Primer run GitHub 39613726423: 32 URLs, 0 incidencias, 16 tests OK; artefacto 12350544901.
Contraste en navegador integrado: Home, Cucarachas y artículo Señales de termitas; 15 comparaciones de campos coinciden.
Robots.txt consultado en navegador: User-agent: * con Disallow vacío y sitemap correcto; no bloquea estas URLs.
El primer tab XML se cerró inesperadamente; el XML se validó mediante el comprobador HTTP solicitado.
Un ensayo inicial de urllib sin cabeceras dio 406; el identificador propio y Accept explícito devolvieron 200. No se cambió WAF ni se suplantó otro crawler.

REVERSIÓN
Desactivar únicamente F28 - Monthly SEO check desde Actions para detener el schedule, o revertir sus commits/archivos.
No es necesaria reversión en WordPress: no se ha modificado.

