import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import ArenaOS from './ArenaOS.jsx';

// Standalone mount for the mock prototype. No Redux store, no router,
// no API client — see prototype/arenaos/README.md.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ArenaOS />
  </React.StrictMode>
);
