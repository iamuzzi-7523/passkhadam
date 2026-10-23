import { initializeApp, getApps } from 'firebase/app';
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  sendEmailVerification,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  linkWithPhoneNumber,
  PhoneAuthProvider,
  onAuthStateChanged
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyAm2y_rprQk5C51aD_1UTcw4pyfI-vsrHQ",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "passkhadam-live.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "passkhadam-live",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "passkhadam-live.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "854979434504",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:854979434504:web:f7378b2c22039d3b1159bd"
};

// Initialize Primary Firebase App Singleton
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

/**
 * Secondary Auth instance for isolated registration email dispatch.
 * Does not switch or disturb the primary auth session or trigger global onAuthStateChanged listeners.
 */
export function getSecondaryAuth() {
  const existing = getApps().find(a => a.name === 'SecondaryRegistrationApp');
  const secApp = existing || initializeApp(firebaseConfig, 'SecondaryRegistrationApp');
  return getAuth(secApp);
}

/**
 * Returns current user's Firebase ID token
 */
export async function getFirebaseToken() {
  if (!auth.currentUser) return null;
  return await auth.currentUser.getIdToken(true);
}

/**
 * Sets up invisible reCAPTCHA verifier attached to containerId
 */
export function setupRecaptcha(containerId = 'recaptcha-container') {
  if (typeof window === 'undefined') return null;
  
  let container = document.getElementById(containerId);
  if (!container) {
    console.warn(`reCAPTCHA container #${containerId} not found in DOM`);
    return null;
  }

  // 1. Destroy and clear previous verifier if present
  if (window.recaptchaVerifier) {
    try {
      window.recaptchaVerifier.clear();
    } catch (e) {
      // ignore clear errors
    }
    window.recaptchaVerifier = null;
  }
  if (typeof window !== 'undefined' && window.grecaptcha && typeof window.grecaptcha.reset === 'function') {
    try {
      window.grecaptcha.reset();
    } catch (e) {
      // ignore reset errors
    }
  }

  // 2. Completely replace the DOM node to detach Google reCAPTCHA's internal widget registry
  try {
    const parent = container.parentNode;
    if (parent) {
      const freshContainer = document.createElement('div');
      freshContainer.id = containerId;
      parent.replaceChild(freshContainer, container);
      container = freshContainer;
    } else {
      container.innerHTML = '';
    }
  } catch (domErr) {
    container.innerHTML = '';
  }

  // 3. Initialize fresh RecaptchaVerifier attached to the new DOM node
  try {
    window.recaptchaVerifier = new RecaptchaVerifier(auth, container, {
      size: 'invisible',
      callback: () => {
        // reCAPTCHA solved
      },
      'expired-callback': () => {
        try {
          if (window.recaptchaVerifier) window.recaptchaVerifier.clear();
        } catch {}
        window.recaptchaVerifier = null;
        try {
          if (container) container.innerHTML = '';
        } catch {}
      }
    });

    return window.recaptchaVerifier;
  } catch (err) {
    console.error('Failed to create RecaptchaVerifier:', err);
    try {
      if (container) container.innerHTML = '';
    } catch {}
    return null;
  }
}

export {
  app,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  sendEmailVerification,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  linkWithPhoneNumber,
  PhoneAuthProvider,
  onAuthStateChanged
};

export default app;
