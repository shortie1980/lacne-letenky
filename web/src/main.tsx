import "@fontsource-variable/inter";
import "@fontsource/instrument-serif/400.css";
import "./styles/app.css";
import { render } from "preact";
import { App } from "./App";

render(<App />, document.getElementById("app")!);

if ("serviceWorker" in navigator && location.protocol === "https:") {
  addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => { /* bez offline režimu */ }));
}
