// Firebase configuration
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyDHnBMtE-prm2fxCWCklk2cNbLNru3KnX8",
  authDomain: "kkproject1-f5e34.firebaseapp.com",
  projectId: "kkproject1-f5e34",
  storageBucket: "kkproject1-f5e34.firebasestorage.app",
  messagingSenderId: "370630878458",
  appId: "1:370630878458:web:6a1dc0e4bbccd93c0b1543",
  measurementId: "G-5P9KN9VBP6"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

export { db };
