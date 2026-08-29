import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { store } from './app/store';
import { sessionExpired } from './features/auth/authSlice';
import App from './App';
import './styles.css';

// A 401 anywhere in the app drops the local session and returns to sign-in.
window.addEventListener('ne-emis:session-expired', () => {
  store.dispatch(sessionExpired());
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  </React.StrictMode>
);
