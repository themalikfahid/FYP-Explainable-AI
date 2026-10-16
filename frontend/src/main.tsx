import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/bricolage-grotesque/500.css";
import "@fontsource/bricolage-grotesque/700.css";
import "./styles/app.css";
import App from "./App";
import { AuthProvider } from "./auth";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
