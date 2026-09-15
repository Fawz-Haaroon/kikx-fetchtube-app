/** Renders the whole component tree once, off-browser, so a broken import or a
 *  setup() that throws is caught by `npm run test:render` instead of by a blank
 *  screen inside KIKX. It does not exercise KIKX APIs: onMounted does not run
 *  during a server render. */
import { createPinia } from "pinia";
import { createSSRApp } from "vue";
import { renderToString } from "@vue/server-renderer";

import App from "@/App.vue";

export async function render() {
  const app = createSSRApp(App);

  app.use(createPinia());

  return renderToString(app);
}
