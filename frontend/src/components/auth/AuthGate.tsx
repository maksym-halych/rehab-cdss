import { useCallback, useState, type ReactNode } from 'react';
import { SignIn, useAuth } from '@clerk/react';
import { configureAuth } from '../../api/client';
import { useIdleSignOut } from '../../hooks/useIdleSignOut';
import { Button } from '../ui/Button';
import styles from './AuthGate.module.css';

// Shows the Clerk sign-in form until the user signs in. Sign-up is invite-only in Clerk.
export function AuthGate({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const [forbidden, setForbidden] = useState(false);

  const handleSignOut = useCallback(() => {
    setForbidden(false);
    void signOut();
  }, [signOut]);

  // Set during render, not in an effect: child effects run first and already call the API
  configureAuth({
    getToken: () => getToken(),
    onAuthError: (status) => (status === 401 ? handleSignOut() : setForbidden(true)),
  });

  useIdleSignOut(isSignedIn === true, handleSignOut);

  if (!isLoaded) return null;

  if (!isSignedIn) {
    return (
      <div className={styles.screen}>
        <SignIn routing="hash" />
      </div>
    );
  }

  // 403: the account exists, but an admin has not given it a role yet
  if (forbidden) {
    return (
      <div className={styles.screen}>
        <div className={styles.card}>
          <h1 className={styles.title}>Немає доступу</h1>
          <p className={styles.text}>
            Ваш обліковий запис ще не має ролі. Зверніться до адміністратора.
          </p>
          <Button variant="primary" onClick={handleSignOut}>
            Вийти
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
