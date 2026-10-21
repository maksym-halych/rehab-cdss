import '@fontsource/inter/cyrillic-400.css';
import '@fontsource/inter/cyrillic-500.css';
import '@fontsource/inter/cyrillic-600.css';
import '@fontsource/inter/cyrillic-700.css';
import '@fontsource/jetbrains-mono/cyrillic-400.css';
import './styles/tokens.css';
import './styles/reset.css';
import './styles/global.css';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { ClerkProvider } from '@clerk/react';
import { ukUA } from '@clerk/localizations';
import App from './App';
import { AuthGate } from './components/auth/AuthGate';

const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
if (!CLERK_PUBLISHABLE_KEY) {
  throw new Error('VITE_CLERK_PUBLISHABLE_KEY is not set. See frontend/.env.example');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} localization={ukUA} afterSignOutUrl="/">
      <AuthGate>
        <App />
      </AuthGate>
    </ClerkProvider>
  </React.StrictMode>
);
