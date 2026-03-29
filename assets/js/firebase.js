/* ──────────────────────────────────────────────────────────
   CONFIGURACIÓN FIREBASE — RENOVABOT
   Proyecto: bot-apoyo-erradicacion-vicios
────────────────────────────────────────────────────────── */
const firebaseConfig = {
  apiKey: "AIzaSyBxt6euJyj6kb2WEdrVU0w8tzJ8r_bhZa4",
  authDomain: "bot-apoyo-erradicacion-vicios.firebaseapp.com",
  databaseURL: "https://bot-apoyo-erradicacion-vicios-default-rtdb.firebaseio.com",
  projectId: "bot-apoyo-erradicacion-vicios",
  storageBucket: "bot-apoyo-erradicacion-vicios.firebasestorage.app",
  messagingSenderId: "776911051853",
  appId: "1:776911051853:web:743a364d911356bc37d004",
  measurementId: "G-E7BYE9WQ8V"
};

if (!firebase.apps || !firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}

const Database = firebase.database();
const Auth = firebase.auth();